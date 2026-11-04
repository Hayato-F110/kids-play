"""架空の CAN のログを作り、答え（ラベル）付きで異常を入れる。

実車や会社のログは使わない。ID、周期、値の意味は、学習のために自分で決めたもの。
乱数の種を固定するので、同じ引数なら毎回同じログになる（試験の再現性）。

使い方：uv run python -m canids.generate
"""

import argparse
import csv
import random
from pathlib import Path

# ID → 周期（秒）。CAN の ID は小さいほど優先度が高い
PERIODS: dict[int, float] = {
    0x100: 0.010,  # 車速
    0x200: 0.020,  # エンジンの回転数
    0x300: 0.100,  # ドア
    0x400: 1.000,  # 水温
}
DLC: dict[int, int] = {0x100: 8, 0x200: 8, 0x300: 2, 0x400: 4}

# 入れる異常の種類と数（フレームの数）
ATTACK_COUNTS: dict[str, int] = {
    "dos": 200,  # 最も優先度の高い ID 0x000 を 1ms ごとに流し、バスを占める
    "spoof": 50,  # 0x100 のなりすましを、本物の間に差し込む（値はもっともらしい）
    "unknown_id": 10,  # 設計にない ID 0x7FF
    "dlc": 10,  # 0x200 の長さを 8 から 4 に変える
    "jump": 5,  # 車速を1フレームだけ 250 km/h にする
}

FIELDS = ["ts", "can_id", "dlc", "data", "label"]
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "results" / "can_log.csv"

Row = dict[str, object]


def _speed_bytes(speed_kmh: float) -> bytes:
    # 0.01 km/h 単位の 16ビット（ビッグエンディアン）。残りは 0
    return int(round(speed_kmh * 100)).to_bytes(2, "big")


def _frame(ts: float, can_id: int, payload: bytes, dlc: int, label: str = "normal") -> Row:
    data = payload[:dlc].ljust(dlc, b"\x00")
    return {"ts": round(ts, 6), "can_id": can_id, "dlc": dlc, "data": data.hex().upper(), "label": label}


def _normal_traffic(rng: random.Random, duration_s: float) -> list[Row]:
    rows: list[Row] = []
    speed = 40.0
    for can_id, period in PERIODS.items():
        t = rng.uniform(0, period)  # ECU ごとに送り始めの時刻がずれる
        while t < duration_s:
            if can_id == 0x100:
                # なめらかに変わる車速（1フレームで 1 km/h まで）
                speed = min(120.0, max(0.0, speed + rng.uniform(-1.0, 1.0)))
                payload = _speed_bytes(speed)
            elif can_id == 0x200:
                payload = (800 + rng.randrange(0, 50)).to_bytes(2, "big")
            elif can_id == 0x300:
                payload = b"\x00\x00"
            else:
                payload = bytes([90 + rng.randrange(0, 3)])
            rows.append(_frame(t, can_id, payload, DLC[can_id]))
            # 時刻の揺れ（ジッター）は周期の ±3% まで
            t += period * (1 + max(-0.03, min(0.03, rng.gauss(0, 0.01))))
    return rows


def _speed_of(row: Row) -> float:
    return int(str(row["data"])[:4], 16) / 100


def _inject(rng: random.Random, rows: list[Row], train_s: float, duration_s: float) -> list[Row]:
    span = duration_s - train_s
    starts = [train_s + span * k / 6 for k in range(1, 6)]  # 異常ごとに別の時間帯に入れる
    t_dos, t_spoof, t_unknown, t_dlc, t_jump = starts
    added: list[Row] = []

    added += [_frame(t_dos + i * 0.001, 0x000, b"", 8, "dos") for i in range(ATTACK_COUNTS["dos"])]

    speed_frames = [r for r in rows if r["can_id"] == 0x100]
    after = [r for r in speed_frames if float(r["ts"]) >= t_spoof][: ATTACK_COUNTS["spoof"]]
    for genuine in after:
        # 本物の 2〜8ms 後に差し込む。周期（10ms）の半分より遅いものは、間隔では見分けにくい
        delay = rng.uniform(0.002, 0.008)
        added.append(
            _frame(float(genuine["ts"]) + delay, 0x100, _speed_bytes(_speed_of(genuine)), 8, "spoof")
        )

    added += [
        _frame(t_unknown + i * 0.050, 0x7FF, b"\x01", 8, "unknown_id")
        for i in range(ATTACK_COUNTS["unknown_id"])
    ]

    rpm = [r for r in rows if r["can_id"] == 0x200 and float(r["ts"]) >= t_dlc][: ATTACK_COUNTS["dlc"]]
    for r in rpm:
        r["dlc"] = 4
        r["data"] = str(r["data"])[:8]
        r["label"] = "dlc"

    # 跳びは、割り当てた時間帯（span / 6）の中に等間隔で入れる。短いログでも終わりを越えない
    step = span / 6 / (ATTACK_COUNTS["jump"] + 1)
    jump_times = [t_jump + (i + 1) * step for i in range(ATTACK_COUNTS["jump"])]
    for t in jump_times:
        target = next(r for r in speed_frames if float(r["ts"]) >= t)
        target["data"] = (_speed_bytes(250.0) + b"\x00" * 6).hex().upper()
        target["label"] = "jump"

    return rows + added


def generate(seed: int, duration_s: float, train_s: float, attacks: bool = True) -> list[Row]:
    """duration_s 秒のログを作る。train_s 秒までは異常を入れない（検知の側が「ふだん」を学ぶ区間）。"""
    rng = random.Random(seed)  # noqa: S311 試験のデータを作るだけで、暗号には使わない
    rows = _normal_traffic(rng, duration_s)
    if attacks:
        rows = _inject(rng, rows, train_s, duration_s)
    return sorted(rows, key=lambda r: (float(r["ts"]), int(r["can_id"])))


def write_csv(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--train", type=float, default=20.0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    rows = generate(args.seed, args.duration, args.train)
    write_csv(rows, args.out)
    print(f"{len(rows)} フレームを {args.out} に書きました")


if __name__ == "__main__":
    main()
