"""ほかのサイトから書き込ませる攻撃（CSRF）を断ることを確かめる（脅威分析 T-18、対策 C-22）。

multipart の POST は、ブラウザが事前の問い合わせ（プリフライト）なしで送る「単純な要求」になる。
CORS は応答を読ませないだけで、書き込みは止めない。
そこで、書き込みの要求は Origin が自分自身のときだけ受け付ける。
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import page_files

PAGE_ID = "00000000-0000-4000-8000-000000000000"


def post(client: TestClient, headers: dict[str, str]):
    return client.post("/api/pages", files=page_files(), data={"voiceMs": "1000"}, headers=headers)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://evil.example:8000",
        "null",
        "https://localhost",
        "http://localhost:8001",
    ],
)
def test_よそのサイトからの保存は拒否する(client: TestClient, origin: str) -> None:
    response = post(client, {"origin": origin})
    assert response.status_code == 403
    assert response.json() == {"code": "cross-origin"}
    assert client.get("/api/pages").json() == []


def test_Origin_のない書き込みは拒否する(make_client: Callable[..., TestClient]) -> None:
    # ブラウザは、同じサイトからでも POST・PUT・DELETE に Origin を付ける。付いていない要求は信じない
    client = make_client(enabled=True)
    client.headers.pop("origin")
    response = post(client, {})
    assert response.status_code == 403
    assert response.json() == {"code": "cross-origin"}


@pytest.mark.parametrize(
    ("method", "path"),
    [("PUT", f"/api/pages/{PAGE_ID}"), ("DELETE", f"/api/pages/{PAGE_ID}"), ("DELETE", "/api/pages")],
)
def test_よそのサイトからの上書きと削除も拒否する(client: TestClient, method: str, path: str) -> None:
    kwargs = {"files": page_files(), "data": {"voiceMs": "1"}} if method == "PUT" else {}
    response = client.request(method, path, headers={"origin": "https://evil.example"}, **kwargs)
    assert response.status_code == 403


def test_Host_と違う_Origin_は拒否する(client: TestClient) -> None:
    # localhost と 127.0.0.1 は、ブラウザから見ると別のサイト
    response = post(client, {"host": "localhost:8000", "origin": "http://127.0.0.1:8000"})
    assert response.status_code == 403


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000"])
def test_自分自身の_Origin_なら保存できる(client: TestClient, host: str) -> None:
    response = post(client, {"host": host, "origin": f"http://{host}"})
    assert response.status_code == 201


def test_読むだけの要求は_Origin_がなくてもよい(make_client: Callable[..., TestClient]) -> None:
    # 読む要求は、ほかのサイトからは応答を読めない（CORS の許可を出していない）ので、Origin を求めない
    client = make_client(enabled=True)
    client.headers.pop("origin")
    assert client.get("/api/pages").status_code == 200
    assert client.get("/api/storage/status").status_code == 200
