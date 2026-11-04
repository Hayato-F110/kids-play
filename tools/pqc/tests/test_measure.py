"""テスト3：PC の中の Python の TLS サーバーにつなぎ、1回分の記録がそろう。"""

import socket
import ssl
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from pqc_bench.certs import write_self_signed
from pqc_bench.measure import Record, handshake_once, make_client_context
from pqc_bench.serverhello import GROUP_X25519


@pytest.fixture
def tls_server(tmp_path: Path) -> Iterator[tuple[int, Path]]:
    cert_path, key_path = write_self_signed(tmp_path)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    server_ctx.load_cert_chain(cert_path, key_path)
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    stop = threading.Event()

    def serve() -> None:
        listener.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                continue
            with conn:
                try:
                    with server_ctx.wrap_socket(conn, server_side=True):
                        pass
                except ssl.SSLError, OSError:
                    pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port, cert_path
    stop.set()
    thread.join()
    listener.close()


def test_1回分の記録がそろう(tls_server: tuple[int, Path]):
    port, cert_path = tls_server
    ctx = make_client_context("classic", cert_path)
    record = handshake_once("127.0.0.1", port, ctx, server_hostname="localhost")
    assert isinstance(record, Record)
    assert record.group == GROUP_X25519
    assert record.hrr is False
    assert record.elapsed_ms > 0
    assert record.bytes_out > 0 and record.bytes_in > 0


def test_未知のクライアントの種類は断る(tmp_path: Path):
    cert_path, _ = write_self_signed(tmp_path)
    with pytest.raises(ValueError):
        make_client_context("unknown", cert_path)
