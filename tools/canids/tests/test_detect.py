"""テスト3〜8：DuckDB の SQL で検知し、見逃しと誤検知を数える。"""

from pathlib import Path

import pytest

from canids.detect import detect, evaluate
from canids.generate import ATTACK_COUNTS, generate, write_csv

TRAIN_S = 1.0


def _normal(ts: float, can_id: int, speed: float = 50.0, dlc: int = 8) -> dict[str, object]:
    data = int(round(speed * 100)).to_bytes(2, "big").hex().upper() + "00" * (dlc - 2)
    return {"ts": round(ts, 6), "can_id": can_id, "dlc": dlc, "data": data, "label": "normal"}


def _base(until: float = 2.0) -> list[dict[str, object]]:
    """0x100 を 10ms ごとに流す、異常のないログ。"""
    return [_normal(i * 0.010, 0x100) for i in range(int(until / 0.010))]


def _write(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "log.csv"
    write_csv(sorted(rows, key=lambda r: r["ts"]), path)
    return path


def _alerts(tmp_path: Path, rows: list[dict[str, object]]) -> dict[float, str]:
    return {r["ts"]: r["alert"] for r in detect(_write(tmp_path, rows), TRAIN_S) if r["alert"]}


def test_3_学習の区間にないIDを見つける(tmp_path: Path):
    rows = _base() + [{**_normal(1.5005, 0x7FF), "label": "unknown_id"}]
    assert _alerts(tmp_path, rows)[1.5005] == "unknown_id"


def test_4_周期の半分より短い間隔を見つける(tmp_path: Path):
    # 1.500 と 1.510 の本物の間に、1.502 になりすましを差し込む
    rows = _base() + [{**_normal(1.502, 0x100), "label": "spoof"}]
    assert _alerts(tmp_path, rows)[1.502] == "timing"


def test_5_DLCが違うフレームを見つける(tmp_path: Path):
    rows = [r for r in _base() if r["ts"] != 1.5]
    rows.append({**_normal(1.5, 0x100, dlc=4), "label": "dlc"})
    assert _alerts(tmp_path, rows)[1.5] == "dlc"


def test_6_車速の跳びを見つける(tmp_path: Path):
    rows = [r for r in _base() if r["ts"] != 1.5]
    rows.append({**_normal(1.5, 0x100, speed=250.0), "label": "jump"})
    assert _alerts(tmp_path, rows)[1.5] == "jump"


def test_7_異常のないログでは誤検知が0件(tmp_path: Path):
    rows = generate(seed=3, duration_s=30, train_s=10, attacks=False)
    result = evaluate(_write(tmp_path, rows), train_s=10)
    assert result["false_positive"] == 0


def test_8_検知と見逃しと誤検知を正しく数える(tmp_path: Path):
    rows = [r for r in _base() if r["ts"] != 1.5]
    rows += [
        {**_normal(1.5005, 0x7FF), "label": "unknown_id"},  # 検知できる
        {**_normal(1.5, 0x100, speed=50.5), "label": "spoof"},  # 値も間隔もふつうなので見逃す
        {**_normal(1.7, 0x100, speed=250.0), "label": "jump"},  # 検知できる
    ]
    rows = [r for r in rows if not (r["ts"] == 1.7 and r["label"] == "normal")]
    result = evaluate(_write(tmp_path, rows), TRAIN_S)
    assert result["by_label"]["unknown_id"] == {"detected": 1, "missed": 0}
    assert result["by_label"]["spoof"] == {"detected": 0, "missed": 1}
    assert result["by_label"]["jump"] == {"detected": 1, "missed": 0}
    # 跳びのあと、次の本物のフレーム（1.71）も「前との差」が大きいので、誤検知になる
    assert result["false_positive"] == 1


def test_全体のログで全種類の異常が数えられる(tmp_path: Path):
    rows = generate(seed=1, duration_s=30, train_s=10)
    result = evaluate(_write(tmp_path, rows), train_s=10)
    assert set(result["by_label"]) == set(ATTACK_COUNTS)
    for label, counts in result["by_label"].items():
        assert counts["detected"] + counts["missed"] == ATTACK_COUNTS[label], label


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_学習の区間の長さは正の値(tmp_path: Path, bad: float):
    with pytest.raises(ValueError):
        detect(_write(tmp_path, _base()), bad)
