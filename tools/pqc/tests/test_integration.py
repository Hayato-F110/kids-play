"""テスト8〜10：試験用の nginx（compose.yaml）につなぐ。Docker が要るので手元だけで動かす。

動かし方：`docker compose up -d` のあと、`$env:PQC_INTEGRATION = "1"; uv run pytest`
"""

import os
import ssl

import pytest

from pqc_bench.certs import DEFAULT_CERT_DIR
from pqc_bench.measure import PORT_CLASSIC, PORT_HYBRID, handshake_once, make_client_context
from pqc_bench.serverhello import GROUP_X25519, GROUP_X25519MLKEM768

pytestmark = pytest.mark.skipif(
    os.environ.get("PQC_INTEGRATION") != "1", reason="Docker の nginx が要る（PQC_INTEGRATION=1 で動かす）"
)

CERT = DEFAULT_CERT_DIR / "cert.pem"


def test_ハイブリッドのクライアントとハイブリッドだけの入口は_ML_KEMで決まる():
    record = handshake_once("127.0.0.1", PORT_HYBRID, make_client_context("hybrid", CERT))
    assert record.group == GROUP_X25519MLKEM768


def test_従来の方式だけのクライアントはハイブリッドだけの入口につながらない():
    # 気づかずに従来の方式へ戻らないこと（T-31）
    with pytest.raises(ssl.SSLError):
        handshake_once("127.0.0.1", PORT_HYBRID, make_client_context("classic", CERT))


def test_ハイブリッドのクライアントと従来の方式だけの入口は_X25519で決まる():
    record = handshake_once("127.0.0.1", PORT_CLASSIC, make_client_context("hybrid", CERT))
    assert record.group == GROUP_X25519
