"""サーバー保存を有効にしたときの動き。約束は docs/storage-interface.md（IndexedDB 版と同じ動き）。"""

from fastapi.testclient import TestClient

from tests.conftest import MP4, OGG, PNG, WEBM, page_files

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


def save(client: TestClient, voice_ms: int = 1000, **files: bytes | None) -> dict:
    response = client.post("/api/pages", files=page_files(**files), data={"voiceMs": str(voice_ms)})
    assert response.status_code == 201, response.text
    return response.json()


def ids(client: TestClient) -> list[str]:
    return [page["id"] for page in client.get("/api/pages").json()]


def test_有効なら状態は_true_と答える(client: TestClient) -> None:
    assert client.get("/api/storage/status").json() == {"enabled": True}


def test_はじめは空(client: TestClient) -> None:
    assert client.get("/api/pages").json() == []


def test_新しいページは最後に足され_id_が付く(client: TestClient) -> None:
    first = save(client, voice_ms=1)
    second = save(client, voice_ms=2)
    assert first["id"] != second["id"]
    assert ids(client) == [first["id"], second["id"]]


def test_一覧は約束の項目だけを返し_中身は含めない(client: TestClient) -> None:
    saved = save(client)
    assert client.get("/api/pages").json() == [
        {
            "id": saved["id"],
            "pictureType": "image/png",
            "voiceType": "audio/webm",
            "voiceMs": 1000,
        }
    ]


def test_絵と声を同じ中身で読める(client: TestClient) -> None:
    saved = save(client)
    picture = client.get(f"/api/pages/{saved['id']}/picture")
    voice = client.get(f"/api/pages/{saved['id']}/voice")
    assert picture.content == PNG
    assert picture.headers["content-type"] == "image/png"
    assert voice.content == WEBM
    assert voice.headers["content-type"] == "audio/webm"


def test_返す絵と声は保存されない指定と種類の決め打ちが付く(client: TestClient) -> None:
    # ブラウザや途中の仕組みに写しを残させない。申告と違う種類として解釈させない
    saved = save(client)
    response = client.get(f"/api/pages/{saved['id']}/picture")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_ないページの絵を読むと404(client: TestClient) -> None:
    assert client.get(f"/api/pages/{UNKNOWN_ID}/picture").status_code == 404


def test_絵のないページの絵を読むと404(client: TestClient) -> None:
    saved = save(client, picture=None)
    assert client.get(f"/api/pages/{saved['id']}/picture").status_code == 404


def test_絵だけ_声だけのページも保存できる(client: TestClient) -> None:
    only_voice = save(client, picture=None)
    only_picture = save(client, voice=None, voice_ms=0)
    pages = client.get("/api/pages").json()
    assert pages[0] == {
        "id": only_voice["id"],
        "pictureType": None,
        "voiceType": "audio/webm",
        "voiceMs": 1000,
    }
    assert pages[1] == {"id": only_picture["id"], "pictureType": "image/png", "voiceType": None, "voiceMs": 0}


def test_声の種類は_ogg_と_mp4_も受け付ける(client: TestClient) -> None:
    save(client, voice=OGG, voice_type="audio/ogg")
    save(client, voice=MP4, voice_type="audio/mp4")
    assert len(ids(client)) == 2


def test_種類の後ろの指定は捨てて保存する(client: TestClient) -> None:
    # MediaRecorder は "audio/webm;codecs=opus" のように付ける。保存するのは種類の名前だけにする
    saved = save(client, voice_type="audio/webm;codecs=opus")
    assert client.get("/api/pages").json()[0]["voiceType"] == "audio/webm"
    assert client.get(f"/api/pages/{saved['id']}/voice").headers["content-type"] == "audio/webm"


def test_上書きすると順番と数は変わらない(client: TestClient) -> None:
    first = save(client)
    second = save(client)
    response = client.put(f"/api/pages/{first['id']}", files=page_files(voice=None), data={"voiceMs": "0"})
    assert response.status_code == 200
    assert response.json()["id"] == first["id"]
    assert ids(client) == [first["id"], second["id"]]
    assert client.get("/api/pages").json()[0]["voiceType"] is None


def test_ない_id_で上書きすると新しいページとして最後に足す(client: TestClient) -> None:
    # メモリ版・IndexedDB 版と同じ動き。送られた id は使わず、サーバーが付け直す
    first = save(client)
    response = client.put(f"/api/pages/{UNKNOWN_ID}", files=page_files(), data={"voiceMs": "1000"})
    assert response.status_code == 201
    new_id = response.json()["id"]
    assert new_id != UNKNOWN_ID
    assert ids(client) == [first["id"], new_id]


def test_9ページ目は拒否する(client: TestClient) -> None:
    for _ in range(8):
        save(client)
    response = client.post("/api/pages", files=page_files(), data={"voiceMs": "1000"})
    assert response.status_code == 409
    assert response.json() == {"code": "page-limit"}
    assert len(ids(client)) == 8


def test_8ページあっても上書きはできる(client: TestClient) -> None:
    first = save(client)
    for _ in range(7):
        save(client)
    response = client.put(f"/api/pages/{first['id']}", files=page_files(), data={"voiceMs": "5"})
    assert response.status_code == 200


def test_ページを消すと残りは順番を保って詰まる(client: TestClient) -> None:
    a, b, c = save(client), save(client), save(client)
    assert client.delete(f"/api/pages/{b['id']}").status_code == 204
    assert ids(client) == [a["id"], c["id"]]
    assert client.get(f"/api/pages/{b['id']}/picture").status_code == 404


def test_消したあとに足したページは最後に来る(client: TestClient) -> None:
    a, b = save(client), save(client)
    client.delete(f"/api/pages/{a['id']}")
    c = save(client)
    assert ids(client) == [b["id"], c["id"]]


def test_ないページを消してもエラーにしない(client: TestClient) -> None:
    assert client.delete(f"/api/pages/{UNKNOWN_ID}").status_code == 204


def test_ぜんぶ消すと空になる(client: TestClient) -> None:
    save(client)
    save(client)
    assert client.delete("/api/pages").status_code == 204
    assert client.get("/api/pages").json() == []


def test_再起動しても残る(make_client) -> None:
    saved = save(make_client(enabled=True))
    assert ids(make_client(enabled=True)) == [saved["id"]]
