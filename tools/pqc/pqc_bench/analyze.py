"""計測の CSV を DuckDB に読み込み、SQL で方式ごとに集計する。

使い方：uv run python -m pqc_bench.analyze
"""

import argparse
from pathlib import Path

import duckdb

from pqc_bench.measure import DEFAULT_OUT
from pqc_bench.serverhello import GROUP_NAMES

# 期待と違う方式で決まった記録を探す。1件でもあれば、その計測は比べる意味がないので止める
CHECK_SQL = """
SELECT scenario, expected_group, "group", count(*) AS n
FROM measurements
WHERE "group" <> expected_group
GROUP BY ALL
"""

SUMMARY_SQL = """
SELECT
    scenario,
    any_value("group")                    AS "group",
    count(*)                              AS n,
    median(elapsed_ms)                    AS median_ms,
    avg(elapsed_ms)                       AS avg_ms,
    quantile_cont(elapsed_ms, 0.95)       AS p95_ms,
    avg(bytes_out)                        AS avg_bytes_out,
    avg(bytes_in)                         AS avg_bytes_in,
    count(*) FILTER (WHERE hrr)           AS hrr_count
FROM measurements
GROUP BY scenario
ORDER BY scenario
"""


# /loop で時間をおいて測った回（run_id）ごとの揺れを見る
BY_RUN_SQL = """
SELECT run_id, scenario, count(*) AS n, median(elapsed_ms) AS median_ms
FROM measurements
GROUP BY run_id, scenario
ORDER BY run_id, scenario
"""


class UnexpectedGroupError(RuntimeError):
    """期待と違う鍵交換の方式で決まった記録があった（気づかずに従来の方式へ戻った、など）。"""


def _query(csv_path: Path, sql: str) -> list[dict[str, object]]:
    con = duckdb.connect()  # メモリの中だけ。ファイルのデータベースは作らない
    try:
        con.execute(
            "CREATE TABLE measurements AS SELECT * FROM read_csv(?, header = true, auto_detect = true)",
            [str(csv_path)],
        )
        bad = con.execute(CHECK_SQL).fetchall()
        if bad:
            raise UnexpectedGroupError(f"期待と違う方式で決まった記録：{bad}")
        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()


def summarize(csv_path: Path) -> list[dict[str, object]]:
    return _query(csv_path, SUMMARY_SQL)


def summarize_by_run(csv_path: Path) -> list[dict[str, object]]:
    return _query(csv_path, BY_RUN_SQL)


def by_run_to_markdown(rows: list[dict[str, object]]) -> str:
    lines = ["| 回 | 組み合わせ | 回数 | 中央値（ms） |", "|---|---|---|---|"]
    lines += [f"| {r['run_id']} | {r['scenario']} | {r['n']} | {r['median_ms']:.2f} |" for r in rows]
    return "\n".join(lines)


def to_markdown(rows: list[dict[str, object]]) -> str:
    lines = [
        "| 組み合わせ | 決まった方式 | 回数 | 中央値（ms） | 平均（ms） | 95%（ms） "
        "| 送った量（バイト） | 受け取った量（バイト） | やり直し |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        group = GROUP_NAMES.get(int(r["group"]), hex(int(r["group"])))
        lines.append(
            f"| {r['scenario']} | {group} | {r['n']} | {r['median_ms']:.2f} | {r['avg_ms']:.2f} | "
            f"{r['p95_ms']:.2f} | {r['avg_bytes_out']:.0f} | {r['avg_bytes_in']:.0f} | {r['hrr_count']} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--by-run", action="store_true", help="計測の回ごとの中央値を出す")
    args = parser.parse_args()
    if args.by_run:
        print(by_run_to_markdown(summarize_by_run(args.csv)))
    else:
        print(to_markdown(summarize(args.csv)))


if __name__ == "__main__":
    main()
