"""ゼロトラストの構成（KIDS_ZERO_TRUST=enabled）の試験。脅威分析 T-28、T-29、対策 C-31、C-32。

ブラウザの代わりに、テスト用のソフトの認証器（softauthn.py）でパスキーの応答を作る。
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.zerotrust import ZeroTrust
from tests.softauthn import SoftAuthenticator, b64url

ORIGIN = "http://localhost:8080"


class Clock:
    """時刻を進められる時計。トークンとチャレンジの期限切れを、待たずに試す。"""

    def __init__(self) -> None:
        self.now = time.time()

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make_zt(tmp_path: Path, clock: Clock) -> Callable[..., tuple[TestClient, ZeroTrust]]:
    def _make(storage: bool = False) -> tuple[TestClient, ZeroTrust]:
        settings = Settings(
            server_storage_enabled=storage,
            db_path=tmp_path / "kids.sqlite3",
            frontend_dir=tmp_path / "none",
            zero_trust_enabled=True,
            zero_trust_origin=ORIGIN,
        )
        app = create_app(settings, clock=clock)
        # nginx の後ろと同じ Host と Origin（ブラウザは localhost:8080 で開く）
        client = TestClient(app, base_url="http://localhost:8080", headers={"origin": ORIGIN})
        return client, app.state.zero_trust

    return _make


@pytest.fixture
def zt(make_zt: Callable[..., tuple[TestClient, ZeroTrust]]) -> tuple[TestClient, ZeroTrust]:
    return make_zt()


def register(client: TestClient, zt: ZeroTrust, authn: SoftAuthenticator) -> None:
    options = client.post("/api/auth/register/options", json={"setupCode": zt.setup_code})
    assert options.status_code == 200
    done = client.post("/api/auth/register/verify", json=authn.create(options.json()))
    assert done.status_code == 201, done.text


def login(client: TestClient, authn: SoftAuthenticator) -> str:
    options = client.post("/api/auth/login/options")
    assert options.status_code == 200
    done = client.post("/api/auth/login/verify", json=authn.get(options.json()))
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["expiresIn"] == 300
    return body["token"]


def bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


# ---- 既定は無効（fail-safe）----


def test_disabled_by_default(tmp_path: Path) -> None:
    app = create_app(Settings(db_path=tmp_path / "kids.sqlite3", frontend_dir=tmp_path / "none"))
    client = TestClient(app, base_url="http://localhost", headers={"origin": "http://localhost"})
    # ログインの窓口も、おとなの API も存在しない。これまでの API は、これまでどおりトークンなしで動く
    assert client.post("/api/auth/login/options").status_code == 404
    assert client.get("/api/parent/summary").status_code == 404
    assert client.get("/api/storage/status").json() == {"enabled": False}


def test_env_value_must_be_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("1", "true", "Enabled", ""):
        monkeypatch.setenv("KIDS_ZERO_TRUST", value)
        assert Settings.from_env().zero_trust_enabled is False
    monkeypatch.setenv("KIDS_ZERO_TRUST", "enabled")
    assert Settings.from_env().zero_trust_enabled is True


# ---- 登録とログイン（C-31）----


def test_register_login_and_read_summary(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    authn = SoftAuthenticator()
    register(client, state, authn)
    token = login(client, authn)
    summary = client.get("/api/parent/summary", headers=bearer(token))
    assert summary.status_code == 200
    # 子どもの絵と声は返さない。確かめるための値だけ
    assert summary.json() == {"storageEnabled": False, "pageCount": None, "subject": "tester"}


@pytest.mark.parametrize("code", [None, "", "wrong-code"])
def test_register_needs_setup_code(zt: tuple[TestClient, ZeroTrust], code: str | None) -> None:
    client, _ = zt
    body: dict[str, Any] = {} if code is None else {"setupCode": code}
    response = client.post("/api/auth/register/options", json=body)
    assert response.status_code == 403
    assert response.json() == {"code": "setup-code"}


def test_only_one_passkey(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    register(client, state, SoftAuthenticator())
    # 登録したら合言葉は使えなくなる。正しい合言葉でも、2つめは登録できない
    response = client.post("/api/auth/register/options", json={"setupCode": state.setup_code})
    assert response.status_code == 409
    assert response.json() == {"code": "already-registered"}


def test_register_rejects_other_origin(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    options = client.post("/api/auth/register/options", json={"setupCode": state.setup_code}).json()
    # 偽のページ（別のオリジン）を通した応答は、署名が正しくても断る
    response = client.post(
        "/api/auth/register/verify", json=SoftAuthenticator().create(options, origin="http://evil.example")
    )
    assert response.status_code == 400
    assert response.json() == {"code": "passkey-rejected"}


def test_register_requires_user_verification(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    options = client.post("/api/auth/register/options", json={"setupCode": state.setup_code}).json()
    # 生体認証や PIN で本人を確かめていない応答は断る
    response = client.post(
        "/api/auth/register/verify", json=SoftAuthenticator(user_verified=False).create(options)
    )
    assert response.status_code == 400


def test_login_without_passkey_is_rejected(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    register(client, state, SoftAuthenticator())
    options = client.post("/api/auth/login/options").json()
    # 登録していない別の鍵でのログイン
    response = client.post("/api/auth/login/verify", json=SoftAuthenticator().get(options))
    assert response.status_code == 401
    assert response.json() == {"code": "login-failed"}


def test_challenge_is_single_use(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    authn = SoftAuthenticator()
    register(client, state, authn)
    options = client.post("/api/auth/login/options").json()
    first = authn.get(options)
    assert client.post("/api/auth/login/verify", json=first).status_code == 200
    # 同じ応答の再送（リプレイ）は、チャレンジが使い済みなので断る
    assert client.post("/api/auth/login/verify", json=first).status_code == 401


def test_challenge_expires(zt: tuple[TestClient, ZeroTrust], clock: Clock) -> None:
    client, state = zt
    authn = SoftAuthenticator()
    register(client, state, authn)
    options = client.post("/api/auth/login/options").json()
    clock.now += 121
    assert client.post("/api/auth/login/verify", json=authn.get(options)).status_code == 401


def test_challenge_is_random(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, _ = zt
    challenges = {client.post("/api/auth/login/options").json()["challenge"] for _ in range(20)}
    # 毎回違い、32バイト（base64url で43文字）ある
    assert len(challenges) == 20
    assert all(len(c) == 43 for c in challenges)


def test_unknown_challenge_is_rejected(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, state = zt
    authn = SoftAuthenticator()
    register(client, state, authn)
    # サーバーが出していないチャレンジ（攻撃者が決めた値）
    response = client.post("/api/auth/login/verify", json=authn.get({"challenge": b64url(b"x" * 32)}))
    assert response.status_code == 401


def test_auth_requires_same_origin(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, _ = zt
    # ログインの窓口も書き込みの要求なので、ほかのサイトからは断る（T-18 と同じ守り）
    response = client.post("/api/auth/login/options", headers={"origin": "http://evil.example"})
    assert response.status_code == 403


# ---- トークンと要求ごとの認可（C-32）----


def logged_in(zt: tuple[TestClient, ZeroTrust]) -> tuple[TestClient, ZeroTrust, str]:
    client, state = zt
    authn = SoftAuthenticator()
    register(client, state, authn)
    return client, state, login(client, authn)


def test_no_token_is_rejected(zt: tuple[TestClient, ZeroTrust]) -> None:
    client, _ = zt
    for path in ("/api/parent/summary", "/api/storage/status", "/api/pages"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json() == {"code": "token-required"}
        assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_rejected(zt: tuple[TestClient, ZeroTrust], clock: Clock) -> None:
    client, _, token = logged_in(zt)
    clock.now += 301
    response = client.get("/api/parent/summary", headers=bearer(token))
    assert response.status_code == 401
    assert response.json() == {"code": "token-invalid"}


def test_forged_tokens_are_rejected(zt: tuple[TestClient, ZeroTrust], clock: Clock) -> None:
    client, _, token = logged_in(zt)
    claims = jwt.decode(token, options={"verify_signature": False})
    other_key = ed25519.Ed25519PrivateKey.generate()
    forged = [
        # 別の鍵で署名したトークン
        jwt.encode(claims, other_key, algorithm="EdDSA"),
        # 署名なし（alg: none）。方式を相手に選ばせない
        jwt.encode(claims, None, algorithm="none"),
        # 共通鍵の方式に変えたトークン
        jwt.encode(claims, "secret-for-test-only-0123456789abcdef", algorithm="HS256"),
        # 1文字だけ書き換えた署名
        token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1],
        "not-a-token",
    ]
    for value in forged:
        response = client.get("/api/parent/summary", headers=bearer(value))
        assert response.status_code == 401, value


def test_token_from_previous_start_is_rejected(
    make_zt: Callable[..., tuple[TestClient, ZeroTrust]],
) -> None:
    client, state = make_zt()
    authn = SoftAuthenticator()
    register(client, state, authn)
    token = login(client, authn)
    # 起動し直すと署名の鍵が変わるので、前のトークンは使えない
    restarted, _ = make_zt()
    assert restarted.get("/api/parent/summary", headers=bearer(token)).status_code == 401


def test_scope_is_checked_per_request(make_zt: Callable[..., tuple[TestClient, ZeroTrust]]) -> None:
    client, state = make_zt(storage=True)
    authn = SoftAuthenticator()
    register(client, state, authn)
    token = login(client, authn)
    assert client.get("/api/parent/summary", headers=bearer(token)).json()["pageCount"] == 0
    # 正しいトークンでも、権限（parent:read）にない操作は断る
    for method, path in (("GET", "/api/pages"), ("DELETE", "/api/pages"), ("GET", "/api/storage/status")):
        response = client.request(method, path, headers=bearer(token))
        assert response.status_code == 403, path
        assert response.json() == {"code": "insufficient-scope"}


def test_token_claims(zt: tuple[TestClient, ZeroTrust], clock: Clock) -> None:
    _, _, token = logged_in(zt)
    header = jwt.get_unverified_header(token)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert header["alg"] == "EdDSA"
    assert claims["exp"] - claims["iat"] == 300
    assert claims["scope"] == "parent:read"
    assert claims["aud"] == "kids-play-api"
    assert claims["sub"] == "tester"
