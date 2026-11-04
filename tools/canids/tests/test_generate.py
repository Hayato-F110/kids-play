"""テスト1・2：模擬ログを作る。"""

import statistics
from collections import Counter

from canids.generate import ATTACK_COUNTS, PERIODS, generate


def test_1_同じ種なら同じログ():
    assert generate(seed=1, duration_s=5, train_s=2) == generate(seed=1, duration_s=5, train_s=2)
    assert generate(seed=1, duration_s=5, train_s=2) != generate(seed=2, duration_s=5, train_s=2)


def test_1_IDごとの周期の中央値が設定どおり():
    rows = generate(seed=1, duration_s=20, train_s=20, attacks=False)
    for can_id, period in PERIODS.items():
        ts = [r["ts"] for r in rows if r["can_id"] == can_id]
        gaps = [b - a for a, b in zip(ts, ts[1:], strict=False)]
        assert abs(statistics.median(gaps) - period) < period * 0.05, hex(can_id)


def test_1_時刻の順に並んでいる():
    rows = generate(seed=1, duration_s=10, train_s=2)
    assert [r["ts"] for r in rows] == sorted(r["ts"] for r in rows)


def test_2_入れた異常の数と種類がラベルと一致する():
    rows = generate(seed=1, duration_s=30, train_s=10)
    labels = Counter(r["label"] for r in rows if r["label"] != "normal")
    assert dict(labels) == ATTACK_COUNTS


def test_2_学習の区間には異常を入れない():
    rows = generate(seed=1, duration_s=30, train_s=10)
    assert all(r["label"] == "normal" for r in rows if r["ts"] < 10)
