"""入力の検証（KIDS-35）。拒否の理由の名前は、フロントの StorageError の code と同じにする。"""

import pytest
from fastapi.testclient import TestClient

from app.config import MAX_PICTURE_BYTES, MAX_VOICE_BYTES
from tests.conftest import PNG, WEBM, page_files


def post(client: TestClient, voice_ms: str = "1000", **files: object) -> object:
    return client.post("/api/pages", files=page_files(**files), data={"voiceMs": voice_ms})


def assert_rejected(response, code: str, status: int = 422) -> None:
    assert response.status_code == status, response.text
    assert response.json() == {"code": code}


def test_30秒ちょうどの声は受け付ける(client: TestClient) -> None:
    assert post(client, voice_ms="30000").status_code == 201


def test_30秒を超える声は拒否する(client: TestClient) -> None:
    assert_rejected(post(client, voice_ms="30001"), "voice-too-long")


@pytest.mark.parametrize("voice_ms", ["-1", "abc", "", "1.5", "1e3", "NaN"])
def test_長さが0以上の整数でなければ拒否する(client: TestClient, voice_ms: str) -> None:
    assert_rejected(post(client, voice_ms=voice_ms), "invalid-page")


def test_長さがなければ拒否する(client: TestClient) -> None:
    assert_rejected(client.post("/api/pages", files=page_files()), "invalid-page")


@pytest.mark.parametrize(
    "picture_type", ["image/svg+xml", "text/html", "image/jpeg", "application/octet-stream"]
)
def test_絵の種類が許可リストになければ拒否する(client: TestClient, picture_type: str) -> None:
    # SVG と HTML は中にスクリプトを書けるので、特に受け付けない
    assert_rejected(post(client, picture_type=picture_type), "invalid-page")


@pytest.mark.parametrize("voice_type", ["text/html", "audio/x-wav", "video/webm"])
def test_声の種類が許可リストになければ拒否する(client: TestClient, voice_type: str) -> None:
    assert_rejected(post(client, voice_type=voice_type), "invalid-page")


def test_絵の中身が申告と違えば拒否する(client: TestClient) -> None:
    # 種類は送る側が自由に書けるので、先頭のバイトでも確かめる
    assert_rejected(post(client, picture=b"<svg onload=alert(1)>"), "invalid-page")


def test_声の中身が申告と違えば拒否する(client: TestClient) -> None:
    assert_rejected(post(client, voice=PNG), "invalid-page")


def test_ogg_と申告して_webm_の中身なら拒否する(client: TestClient) -> None:
    assert_rejected(post(client, voice=WEBM, voice_type="audio/ogg"), "invalid-page")


def test_空のファイルは拒否する(client: TestClient) -> None:
    assert_rejected(post(client, picture=b""), "invalid-page")


def test_大きすぎる絵は拒否する(client: TestClient) -> None:
    picture = PNG + b"\0" * (MAX_PICTURE_BYTES - len(PNG) + 1)
    assert_rejected(post(client, picture=picture), "too-large", status=413)


def test_上限ちょうどの絵は受け付ける(client: TestClient) -> None:
    picture = PNG + b"\0" * (MAX_PICTURE_BYTES - len(PNG))
    assert post(client, picture=picture).status_code == 201


def test_大きすぎる声は拒否する(client: TestClient) -> None:
    voice = WEBM + b"\0" * (MAX_VOICE_BYTES - len(WEBM) + 1)
    assert_rejected(post(client, voice=voice), "too-large", status=413)


def test_送られた全体が大きすぎれば中身を読む前に拒否する(client: TestClient) -> None:
    # Content-Length だけで判断し、大きなデータを受け取りきる前に断る
    response = client.post(
        "/api/pages",
        content=b"x",
        headers={"content-type": "multipart/form-data; boundary=x", "content-length": str(10 * 1024 * 1024)},
    )
    assert_rejected(response, "too-large", status=413)


def test_知らない項目は保存しない(client: TestClient) -> None:
    # 名前・日時・端末の情報などを送られても、保存する項目は約束の4つだけ
    response = client.post(
        "/api/pages",
        files=page_files(),
        data={"voiceMs": "1000", "name": "たろう", "createdAt": "2026-10-21"},
    )
    assert response.status_code == 201
    assert set(client.get("/api/pages").json()[0]) == {"id", "pictureType", "voiceType", "voiceMs"}


@pytest.mark.parametrize("page_id", ["abc", "1", "../etc/passwd", "00000000-0000-4000-8000-00000000000g"])
def test_id_が_UUID_の形でなければ拒否する(client: TestClient, page_id: str) -> None:
    # "../" を含むパスは送る前に正規化され、API ではなくフロントの配信に届く（405）。
    # どこに届いても、拒否されて何も保存されなければよい
    assert 400 <= client.get(f"/api/pages/{page_id}/picture").status_code < 500
    response = client.put(f"/api/pages/{page_id}", files=page_files(), data={"voiceMs": "1"})
    assert 400 <= response.status_code < 500
    assert client.get("/api/pages").json() == []


def test_SQL_の文字を含む値でも表は壊れない(client: TestClient) -> None:
    # 値はすべてプレースホルダで渡すので、SQL として解釈されない
    response = client.delete("/api/pages/' OR 1=1; DROP TABLE pages; --")
    assert response.status_code in (404, 422)
    assert client.get("/api/pages").status_code == 200
