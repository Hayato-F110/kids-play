"""既定（無効）のときに、保存の API がすべて拒否することを確かめる（脅威分析 T-08、対策 C-12）。

公開環境で設定を忘れても、子どもの絵と声を受け取らないことを、ここで機械的に保証する。
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from tests.conftest import page_files

PAGE_ID = "00000000-0000-4000-8000-000000000000"


def test_環境変数がなければ無効(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIDS_SERVER_STORAGE", raising=False)
    assert Settings.from_env().server_storage_enabled is False


@pytest.mark.parametrize("value", ["", "1", "true", "yes", "Enabled", " enabled", "on"])
def test_決めた値以外は無効(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    # 「それらしい値」で有効にならないようにする。有効にするには enabled と正確に書く
    monkeypatch.setenv("KIDS_SERVER_STORAGE", value)
    assert Settings.from_env().server_storage_enabled is False


def test_enabled_と書いたときだけ有効(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIDS_SERVER_STORAGE", "enabled")
    assert Settings.from_env().server_storage_enabled is True


def test_DB_の置き場所は環境変数で変えられる(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # フロントの約束のテスト（npm run test:server）で、一時フォルダの DB を使うため
    monkeypatch.setenv("KIDS_DB_PATH", str(tmp_path / "test.sqlite3"))
    assert Settings.from_env().db_path == tmp_path / "test.sqlite3"


def test_DB_の置き場所の既定は_backend_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIDS_DB_PATH", raising=False)
    assert Settings.from_env().db_path == Settings().db_path


def test_無効なら状態は_false_と答える(make_client: Callable[..., TestClient]) -> None:
    response = make_client(enabled=False).get("/api/storage/status")
    assert response.status_code == 200
    assert response.json() == {"enabled": False}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/pages"),
        ("POST", "/api/pages"),
        ("DELETE", "/api/pages"),
        ("GET", f"/api/pages/{PAGE_ID}/picture"),
        ("GET", f"/api/pages/{PAGE_ID}/voice"),
        ("PUT", f"/api/pages/{PAGE_ID}"),
        ("DELETE", f"/api/pages/{PAGE_ID}"),
    ],
)
def test_無効なら保存のAPIはすべて拒否する(
    make_client: Callable[..., TestClient], method: str, path: str
) -> None:
    client = make_client(enabled=False)
    kwargs = {"files": page_files(), "data": {"voiceMs": "1000"}} if method in ("POST", "PUT") else {}
    response = client.request(method, path, **kwargs)
    assert response.status_code == 403
    assert response.json() == {"code": "server-storage-disabled"}


def test_無効なら送られたページを保存しない(make_client: Callable[..., TestClient]) -> None:
    # 無効のときに送られたものが、あとで有効にしても出てこない（どこにも書いていない）こと
    make_client(enabled=False).post("/api/pages", files=page_files(), data={"voiceMs": "1000"})
    assert make_client(enabled=True).get("/api/pages").json() == []
