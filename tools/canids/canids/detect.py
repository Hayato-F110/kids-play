"""CAN のログを DuckDB に読み込み、SQL の規則で異常を検知し、答え（ラベル）と比べる。

学習の区間（最初の train_s 秒）で「ふだん」を学ぶ：ID ごとの周期（間隔の中央値）と、いつもの長さ（DLC）。
そのあとの区間に、4つの規則を上から順に当てる。

使い方：uv run python -m canids.detect
"""

import argparse
from pathlib import Path

import duckdb

from canids.generate import DEFAULT_OUT

SPEED_ID = 0x100

DETECT_SQL = """
WITH f AS (
    SELECT *,
        ts - lag(ts) OVER (PARTITION BY can_id ORDER BY ts) AS gap,
        CASE WHEN can_id = $speed_id AND dlc >= 2
             THEN ('0x' || substr(data, 1, 4))::INTEGER / 100.0 END AS speed
    FROM frames
),
f2 AS (
    SELECT *, abs(speed - lag(speed) OVER (PARTITION BY can_id ORDER BY ts)) AS speed_delta
    FROM f
),
base AS (
    -- 学習の区間で、ID ごとの「ふだん」を決める
    SELECT can_id, median(gap) AS period, mode(dlc) AS usual_dlc
    FROM f
    WHERE ts < $train
    GROUP BY can_id
)
SELECT f2.ts, f2.can_id, f2.label,
    CASE
        WHEN base.can_id IS NULL                 THEN 'unknown_id'  -- 学習の区間に出てこない ID
        WHEN f2.dlc <> base.usual_dlc            THEN 'dlc'         -- いつもと違う長さ
        WHEN f2.gap < base.period * $ratio       THEN 'timing'      -- 周期より短すぎる間隔
        WHEN f2.speed_delta > $jump              THEN 'jump'        -- ありえない車速の変わり方
    END AS alert
FROM f2 LEFT JOIN base USING (can_id)
WHERE f2.ts >= $train
ORDER BY f2.ts, f2.can_id
"""

EVAL_BY_LABEL_SQL = """
SELECT label,
    count(*) FILTER (WHERE alert IS NOT NULL) AS detected,
    count(*) FILTER (WHERE alert IS NULL)     AS missed
FROM detections
WHERE label <> 'normal'
GROUP BY label
ORDER BY label
"""

EVAL_FALSE_POSITIVE_SQL = """
SELECT alert, count(*) AS n
FROM detections
WHERE label = 'normal' AND alert IS NOT NULL
GROUP BY alert
ORDER BY alert
"""


def _connect(csv_path: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()  # メモリの中だけ
    con.execute(
        "CREATE TABLE frames AS SELECT * FROM read_csv(?, header = true, columns = "
        "{'ts': 'DOUBLE', 'can_id': 'INTEGER', 'dlc': 'INTEGER', 'data': 'VARCHAR', 'label': 'VARCHAR'})",
        [str(csv_path)],
    )
    return con


def _params(train_s: float, timing_ratio: float, jump_kmh: float) -> dict[str, object]:
    if train_s <= 0:
        raise ValueError("学習の区間の長さは正の値にする")
    return {"train": train_s, "ratio": timing_ratio, "jump": jump_kmh, "speed_id": SPEED_ID}


def detect(
    csv_path: Path, train_s: float, timing_ratio: float = 0.5, jump_kmh: float = 20.0
) -> list[dict[str, object]]:
    params = _params(train_s, timing_ratio, jump_kmh)
    con = _connect(csv_path)
    try:
        cursor = con.execute(DETECT_SQL, params)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()


def evaluate(
    csv_path: Path, train_s: float, timing_ratio: float = 0.5, jump_kmh: float = 20.0
) -> dict[str, object]:
    """異常の種類ごとの「検知・見逃し」と、正常なフレームの誤検知の数を返す。"""
    params = _params(train_s, timing_ratio, jump_kmh)
    con = _connect(csv_path)
    try:
        con.execute("CREATE TABLE detections AS " + DETECT_SQL, params)
        by_label = {
            label: {"detected": detected, "missed": missed}
            for label, detected, missed in con.execute(EVAL_BY_LABEL_SQL).fetchall()
        }
        fp_by_rule = dict(con.execute(EVAL_FALSE_POSITIVE_SQL).fetchall())
        normal_frames = con.execute("SELECT count(*) FROM detections WHERE label = 'normal'").fetchone()[0]
        return {
            "by_label": by_label,
            "false_positive": sum(fp_by_rule.values()),
            "false_positive_by_rule": fp_by_rule,
            "normal_frames": normal_frames,
        }
    finally:
        con.close()


def to_markdown(result: dict[str, object]) -> str:
    lines = ["| 異常の種類 | 入れた数 | 検知 | 見逃し |", "|---|---|---|---|"]
    for label, c in result["by_label"].items():  # type: ignore[union-attr]
        lines.append(f"| {label} | {c['detected'] + c['missed']} | {c['detected']} | {c['missed']} |")
    lines.append("")
    lines.append(f"誤検知：正常なフレーム {result['normal_frames']} 件のうち {result['false_positive']} 件")
    for rule, n in result["false_positive_by_rule"].items():  # type: ignore[union-attr]
        lines.append(f"- 規則 {rule}：{n} 件")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--train", type=float, default=20.0)
    parser.add_argument("--ratio", type=float, default=0.5, help="周期の何倍より短い間隔を異常とするか")
    parser.add_argument(
        "--jump", type=float, default=20.0, help="1フレームで何 km/h を超えて変わったら異常か"
    )
    args = parser.parse_args()
    print(to_markdown(evaluate(args.csv, args.train, args.ratio, args.jump)))


if __name__ == "__main__":
    main()
