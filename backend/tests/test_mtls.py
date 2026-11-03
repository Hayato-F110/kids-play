"""nginx → api の mTLS の試験。脅威分析 T-30、対策 C-33。

本物の uvicorn を TLS で動かし、証明書のない接続や、別の CA の証明書の接続が断られることを確かめる。
証明書と秘密鍵は、テストの一時フォルダにだけ作る（PC のほかの場所、Git には出さない）。
"""

import datetime
import socket
import ssl
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from app.config import Settings
from app.devcerts import FILES, make_dev_certs
from app.main import create_app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def certs(tmp_path: Path) -> Path:
    folder = tmp_path / "certs"
    # 試験では、PC の中の名前（localhost）で api につなぐ
    make_dev_certs(folder, server_names=["api", "localhost"])
    return folder


@pytest.fixture
def server(tmp_path: Path, certs: Path) -> Iterator[int]:
    settings = Settings(
        db_path=tmp_path / "kids.sqlite3",
        frontend_dir=tmp_path / "none",
        zero_trust_enabled=True,
    )
    port = free_port()
    config = uvicorn.Config(
        create_app(settings),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        ssl_certfile=str(certs / FILES["api_cert"]),
        ssl_keyfile=str(certs / FILES["api_private"]),
        ssl_ca_certs=str(certs / FILES["ca_cert"]),
        # クライアントの証明書を必須にする（compose の api と同じ設定）
        ssl_cert_reqs=ssl.CERT_REQUIRED,
    )
    runner = uvicorn.Server(config)
    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not runner.started:
        if time.time() > deadline:
            raise RuntimeError("uvicorn が起動しない")
        time.sleep(0.05)
    yield port
    runner.should_exit = True
    thread.join(timeout=5)


def client_context(certs: Path, with_client_cert: bool = True) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(certs / FILES["ca_cert"]))
    if with_client_cert:
        context.load_cert_chain(str(certs / FILES["nginx_cert"]), str(certs / FILES["nginx_private"]))
    return context


def get(port: int, context: ssl.SSLContext) -> httpx.Response:
    with httpx.Client(verify=context, timeout=5) as client:
        return client.get(f"https://localhost:{port}/api/parent/summary")


def test_with_nginx_cert_reaches_api(server: int, certs: Path) -> None:
    # TLS の段階は通り、そのあとアプリがトークンを確かめる（401）。2つの層が別々に効く
    response = get(server, client_context(certs))
    assert response.status_code == 401
    assert response.json() == {"code": "token-required"}


def test_without_client_cert_is_rejected(server: int, certs: Path) -> None:
    # nginx を通らない要求（証明書を持たない相手）は、HTTP の中身に届く前に断られる
    with pytest.raises(httpx.TransportError):
        get(server, client_context(certs, with_client_cert=False))


def test_cert_from_other_ca_is_rejected(server: int, certs: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    make_dev_certs(other, server_names=["api", "localhost"])
    # 別の CA が出した nginx の証明書。形は正しいが、api の CA の署名がない
    context = ssl.create_default_context(cafile=str(certs / FILES["ca_cert"]))
    context.load_cert_chain(str(other / FILES["nginx_cert"]), str(other / FILES["nginx_private"]))
    with pytest.raises(httpx.TransportError):
        get(server, context)


def test_plain_http_is_rejected(server: int) -> None:
    # 暗号化しない接続は受け付けない
    with pytest.raises(httpx.TransportError), httpx.Client(timeout=5) as client:
        client.get(f"http://localhost:{server}/api/parent/summary")


def test_dev_certs_shape(certs: Path) -> None:
    # CA の秘密鍵は書き出さない。証明書を作り終えたら、新しい証明書を作れないようにする
    assert sorted(p.name for p in certs.iterdir()) == sorted(FILES.values())
    api = x509.load_pem_x509_certificate((certs / FILES["api_cert"]).read_bytes())
    nginx = x509.load_pem_x509_certificate((certs / FILES["nginx_cert"]).read_bytes())
    # 期限は1日
    assert api.not_valid_after_utc - api.not_valid_before_utc <= datetime.timedelta(days=1, minutes=5)
    # api はサーバー用、nginx はクライアント用だけに使える
    api_usage = api.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    nginx_usage = nginx.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(api_usage) == [ExtendedKeyUsageOID.SERVER_AUTH]
    assert list(nginx_usage) == [ExtendedKeyUsageOID.CLIENT_AUTH]
    names = api.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert names.get_values_for_type(x509.DNSName) == ["api", "localhost"]
