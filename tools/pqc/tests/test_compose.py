"""テスト7：試験用の nginx は 127.0.0.1 だけで待つ（C-34 (4)）。"""

import re
from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[1] / "compose.yaml"


def test_ポートは127_0_0_1だけで開く():
    text = COMPOSE.read_text(encoding="utf-8")
    ports = re.findall(r'"([^"]*:\d+:\d+)"', text)
    assert ports, "ポートの指定が見つからない"
    for port in ports:
        assert port.startswith("127.0.0.1:"), port
