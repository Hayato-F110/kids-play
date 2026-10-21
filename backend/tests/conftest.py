"""テストの共通部品。本物の絵や声は使わず、形だけ正しい小さなデータを作る。"""

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

# 先頭のバイトだけ本物の形式に合わせた、自作の小さなデータ
PNG = b"\x89PNG\r\n\x1a\n" + b"picture"
WEBM = b"\x1a\x45\xdf\xa3" + b"voice"
OGG = b"OggS" + b"voice"
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"voice"


def page_files(
    picture: bytes | None = PNG,
    voice: bytes | None = WEBM,
    picture_type: str = "image/png",
    voice_type: str = "audio/webm",
) -> dict[str, tuple[str, bytes, str]]:
    """multipart で送るファイルの組。None の項目は送らない（絵だけ・声だけのページ）。"""
    files: dict[str, tuple[str, bytes, str]] = {}
    if picture is not None:
        files["picture"] = ("picture", picture, picture_type)
    if voice is not None:
        files["voice"] = ("voice", voice, voice_type)
    return files


@pytest.fixture
def make_client(tmp_path: Path) -> Callable[..., TestClient]:
    """設定を変えてアプリを作る。DB はテストごとの一時フォルダに置く。"""

    def _make(enabled: bool = True) -> TestClient:
        frontend = tmp_path / "frontend"
        frontend.mkdir(exist_ok=True)
        (frontend / "index.html").write_text("<!doctype html><title>test</title>", encoding="utf-8")
        settings = Settings(
            server_storage_enabled=enabled,
            db_path=tmp_path / "kids.sqlite3",
            frontend_dir=frontend,
        )
        # ブラウザが localhost で開いたときと同じ Host と Origin にする
        # （ブラウザは書き込みの要求に Origin を付ける）
        return TestClient(
            create_app(settings), base_url="http://localhost", headers={"origin": "http://localhost"}
        )

    return _make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """サーバー保存を有効にしたアプリ。"""
    return make_client(enabled=True)
