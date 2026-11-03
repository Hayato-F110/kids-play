"""デモ：正常、改ざん、リプレイ。層の呼び出しがログで辿れる。

実行：uv run python -m secoc_sim.demo
"""

import logging

from secoc_sim.secoc import build_secoc

DEMO_KEY = bytes(range(16))  # デモ専用。本物の鍵ではない


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tx = build_secoc(DEMO_KEY, data_id=0x0123)
    rx = build_secoc(DEMO_KEY, data_id=0x0123)

    print("\n=== 1. 正常に送って受ける ===")
    pdu = tx.send(b"\x10\x20")
    print("PDU:", pdu.hex(), "->", rx.receive(pdu)[0])

    print("\n=== 2. ペイロードを改ざん ===")
    bad = bytearray(tx.send(b"\x10\x21"))
    bad[0] ^= 0xFF
    print("結果:", rx.receive(bytes(bad))[0])

    print("\n=== 3. 受け付け済みの PDU を再送（リプレイ）===")
    print("結果:", rx.receive(pdu)[0])


if __name__ == "__main__":
    main()
