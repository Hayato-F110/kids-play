"""テスト4・5：DuckDB の SQL で集計する。期待と違う方式の記録があれば止める。"""

import csv
from pathlib import Path

import pytest

from pqc_bench.analyze import UnexpectedGroupError, summarize, summarize_by_run
from pqc_bench.measure import CSV_FIELDS

GROUP_HYBRID = 0x11EC
GROUP_CLASSIC = 0x001D


def _write(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(scenario: str, expected: int, group: int, ms: float, out: int, inn: int) -> dict[str, object]:
    return {
        "run_id": "r1",
        "scenario": scenario,
        "expected_group": expected,
        "group": group,
        "hrr": False,
        "elapsed_ms": ms,
        "bytes_out": out,
        "bytes_in": inn,
    }


def test_方式ごとに件数と中央値と平均が出る(tmp_path: Path):
    rows = [_row("hybrid", GROUP_HYBRID, GROUP_HYBRID, ms, 1500, 2000) for ms in (1.0, 2.0, 3.0, 10.0)] + [
        _row("classic", GROUP_CLASSIC, GROUP_CLASSIC, ms, 300, 900) for ms in (1.0, 1.0, 2.0)
    ]
    result = {r["scenario"]: r for r in summarize(_write(tmp_path / "m.csv", rows))}

    assert result["hybrid"]["n"] == 4
    assert result["hybrid"]["median_ms"] == pytest.approx(2.5)
    assert result["hybrid"]["avg_ms"] == pytest.approx(4.0)
    assert result["hybrid"]["avg_bytes_out"] == pytest.approx(1500)
    assert result["classic"]["n"] == 3
    assert result["classic"]["median_ms"] == pytest.approx(1.0)
    assert result["classic"]["avg_bytes_in"] == pytest.approx(900)


def test_回ごとに中央値が出る(tmp_path: Path):
    rows = [_row("hybrid", GROUP_HYBRID, GROUP_HYBRID, ms, 1500, 2000) for ms in (1.0, 3.0)]
    rows += [
        {**_row("hybrid", GROUP_HYBRID, GROUP_HYBRID, ms, 1500, 2000), "run_id": "r2"} for ms in (5.0, 7.0)
    ]
    result = summarize_by_run(_write(tmp_path / "m.csv", rows))
    assert [(r["run_id"], r["scenario"], r["median_ms"]) for r in result] == [
        ("r1", "hybrid", pytest.approx(2.0)),
        ("r2", "hybrid", pytest.approx(6.0)),
    ]


def test_期待と違う方式で決まった記録があれば止める(tmp_path: Path):
    rows = [
        _row("hybrid", GROUP_HYBRID, GROUP_HYBRID, 1.0, 1500, 2000),
        # ハイブリッドのはずが、従来の方式で決まった（気づかずに戻った）
        _row("hybrid", GROUP_HYBRID, GROUP_CLASSIC, 1.0, 300, 900),
    ]
    with pytest.raises(UnexpectedGroupError):
        summarize(_write(tmp_path / "m.csv", rows))
