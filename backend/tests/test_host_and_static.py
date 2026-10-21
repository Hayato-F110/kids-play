"""localhost 以外からの要求を断ることと、フロントを同じオリジンで配ること。"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("host", ["evil.example", "192.168.1.10", "localhost.evil.example"])
def test_よその_Host_ヘッダーは拒否する(make_client: Callable[..., TestClient], host: str) -> None:
    # DNS リバインディング（よそのサイトの名前を 127.0.0.1 に向ける攻撃）で、
    # ブラウザ経由で読まれないようにする
    response = make_client(enabled=True).get("/api/pages", headers={"host": host})
    assert response.status_code == 400


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000"])
def test_localhost_と_127_0_0_1_は受け付ける(make_client: Callable[..., TestClient], host: str) -> None:
    response = make_client(enabled=True).get("/api/pages", headers={"host": host})
    assert response.status_code == 200


def test_フロントを同じオリジンで配る(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>test</title>" in response.text


def test_無効でもフロントは配る(make_client: Callable[..., TestClient]) -> None:
    # 保存は IndexedDB に切り替わるだけで、遊ぶことはできる
    assert make_client(enabled=False).get("/").status_code == 200


def test_フロントの外のファイルは配らない(client: TestClient) -> None:
    assert client.get("/../pyproject.toml").status_code == 404
