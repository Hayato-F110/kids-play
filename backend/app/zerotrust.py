"""ゼロトラストの構成：パスキーでのログイン、短い期限のトークン、要求ごとの認可。

compose.zerotrust.yaml で KIDS_ZERO_TRUST=enabled のときだけ使う（既定は無効）。
「内側から来たから信じる」をやめ、/api/ への要求ごとに、誰か（トークン）と何をしてよいか（scope）を確かめる
（NIST SP 800-207 の原則3・6）。送り元の確かめ（mTLS）は uvicorn の TLS の設定で行う（devcerts.py）。

守りの決まりは、脅威分析の T-28・T-29 と、対策 C-31・C-32。
"""

import base64
import hmac
import json
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.responses import JSONResponse
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json_dict
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.errors import ApiError

# パスキーを結びつけるサイトの名前（RP ID）。ブラウザは localhost で開く
RP_ID = "localhost"
RP_NAME = "kids-play"
# 登録の名前は仮の名前だけ。実名を使わない（C-31 (5)）
USER_NAME = "tester"

# チャレンジの期限（秒）。期限のない使い捨ての値は、盗んだ応答をあとで使える
CHALLENGE_TTL = 120
# 同時に待つログインのチャレンジの上限。要求を繰り返されてもメモリが増え続けないようにする
MAX_PENDING_LOGINS = 16
# トークンの期限（秒）。盗まれても短い時間しか使えない（C-32 (1)）
TOKEN_TTL = 300
ISSUER = "kids-play-zt"
AUDIENCE = "kids-play-api"
# 署名の方式は1つに固定する。トークンの中の alg を信じない（alg: none や方式の取り違えを防ぐ）
ALGORITHM = "EdDSA"
SCOPE_PARENT_READ = "parent:read"
# ログインで渡す権限。おとなのページが読むものだけ
GRANTED_SCOPES = (SCOPE_PARENT_READ,)

AUTH_PREFIX = "/api/auth/"

logger = logging.getLogger("uvicorn.error")


def required_scope(method: str, path: str) -> str | None:
    """要求に要る権限。決めていない要求は None（だれにも許さない。既定は拒否）。"""
    reading = method in ("GET", "HEAD")
    if path.startswith("/api/parent/"):
        return SCOPE_PARENT_READ if reading else None
    if path.startswith("/api/pages") or path.startswith("/api/storage"):
        # えほんのページは子どものデータ（A1）。この構成のトークンには、この権限を渡さない
        return "pages:read" if reading else "pages:write"
    return None


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass
class Passkey:
    credential_id: bytes
    public_key: bytes
    sign_count: int


class ZeroTrust:
    """1回の起動の間だけの状態。鍵もパスキーもメモリにだけ置き、再起動で消える（C-31 (4)、C-32 (2)）。"""

    def __init__(self, origin: str, clock: Callable[[], float]) -> None:
        self.origin = origin
        self._clock = clock
        # 登録の合言葉。コンテナのログにだけ出す。知っている人（PC の持ち主）だけが登録できる（C-31 (1)）
        self.setup_code = secrets.token_urlsafe(12)
        self._setup_open = True
        # トークンの署名の鍵。起動のたびに作り、ファイルに書かない
        self._signing_key = ed25519.Ed25519PrivateKey.generate()
        self._verify_key = self._signing_key.public_key()
        self._passkey: Passkey | None = None
        self._register_challenge: tuple[bytes, float] | None = None
        self._login_challenges: dict[bytes, float] = {}

    def announce(self) -> None:
        logger.warning("おとなのページの登録の合言葉（この起動の間だけ、1回だけ使える）: %s", self.setup_code)

    # ---- 登録 ----

    def registration_options(self, setup_code: str | None) -> dict[str, Any]:
        if self._passkey is not None or not self._setup_open:
            raise ApiError(409, "already-registered")
        # 長さの違いで比べる時間が変わらないよう、決まった時間で比べる
        if not setup_code or not hmac.compare_digest(setup_code.encode(), self.setup_code.encode()):
            raise ApiError(403, "setup-code")
        challenge = secrets.token_bytes(32)
        self._register_challenge = (challenge, self._clock() + CHALLENGE_TTL)
        options = generate_registration_options(
            rp_id=RP_ID,
            rp_name=RP_NAME,
            user_name=USER_NAME,
            user_id=secrets.token_bytes(16),
            challenge=challenge,
            timeout=CHALLENGE_TTL * 1000,
            # 生体認証や PIN で本人を確かめる。端末に置くパスキー（resident key）にする
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        return options_to_json_dict(options)

    def register(self, credential: dict[str, Any]) -> None:
        # チャレンジは成功しても失敗しても使い捨てにする
        pending, self._register_challenge = self._register_challenge, None
        if pending is None or self._clock() > pending[1] or self._passkey is not None:
            raise ApiError(400, "passkey-rejected")
        try:
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=pending[0],
                expected_rp_id=RP_ID,
                expected_origin=self.origin,
                require_user_verification=True,
            )
        except WebAuthnException, ValueError, KeyError, TypeError:
            raise ApiError(400, "passkey-rejected") from None
        self._passkey = Passkey(verified.credential_id, verified.credential_public_key, verified.sign_count)
        # 登録したら合言葉は使えなくなる。2つめは登録できない
        self._setup_open = False

    # ---- ログイン ----

    def login_options(self) -> dict[str, Any]:
        now = self._clock()
        self._login_challenges = {c: exp for c, exp in self._login_challenges.items() if exp >= now}
        if len(self._login_challenges) >= MAX_PENDING_LOGINS:
            oldest = min(self._login_challenges, key=self._login_challenges.__getitem__)
            del self._login_challenges[oldest]
        # 暗号用の乱数で作る。予測できる値は、応答を先に作られる（C-31 (2)）
        challenge = secrets.token_bytes(32)
        self._login_challenges[challenge] = now + CHALLENGE_TTL
        allow = [PublicKeyCredentialDescriptor(id=self._passkey.credential_id)] if self._passkey else []
        options = generate_authentication_options(
            rp_id=RP_ID,
            challenge=challenge,
            timeout=CHALLENGE_TTL * 1000,
            allow_credentials=allow,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return options_to_json_dict(options)

    def login(self, credential: dict[str, Any]) -> dict[str, Any]:
        failed = ApiError(401, "login-failed")
        try:
            client_data = json.loads(_b64url_decode(credential["response"]["clientDataJSON"]))
            challenge = _b64url_decode(client_data["challenge"])
        except ValueError, KeyError, TypeError:
            raise failed from None
        # サーバーが出したチャレンジだけを、1回だけ受け付ける（再送を断る）
        expires = self._login_challenges.pop(challenge, None)
        if expires is None or self._clock() > expires or self._passkey is None:
            raise failed
        passkey = self._passkey
        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=RP_ID,
                expected_origin=self.origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
                require_user_verification=True,
            )
        except WebAuthnException, ValueError, KeyError, TypeError:
            raise failed from None
        if verified.credential_id != passkey.credential_id:
            raise failed
        passkey.sign_count = verified.new_sign_count
        return {"token": self._issue_token(), "expiresIn": TOKEN_TTL}

    # ---- トークン ----

    def _issue_token(self) -> str:
        now = int(self._clock())
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": USER_NAME,
            "scope": " ".join(GRANTED_SCOPES),
            "iat": now,
            "exp": now + TOKEN_TTL,
            "jti": uuid4().hex,
        }
        return jwt.encode(claims, self._signing_key, algorithm=ALGORITHM)

    def _verify_token(self, token: str) -> dict[str, Any] | None:
        try:
            claims = jwt.decode(
                token,
                self._verify_key,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                # 期限はこのクラスの時計で確かめる（試験で時計を進めるため）。項目がないトークンは断る
                options={
                    "require": ["iss", "aud", "sub", "scope", "iat", "exp"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
        except jwt.InvalidTokenError:
            return None
        now = self._clock()
        if not isinstance(claims["exp"], int) or now >= claims["exp"] or claims["iat"] > now + 5:
            return None
        return claims

    def authorize(
        self, method: str, path: str, authorization: str | None
    ) -> tuple[JSONResponse | None, str | None]:
        """要求ごとの認可。断るなら (応答, None)、通すなら (None, 利用者の名前)。"""
        if not authorization or not authorization.startswith("Bearer "):
            response = JSONResponse({"code": "token-required"}, status_code=401)
            response.headers["WWW-Authenticate"] = "Bearer"
            return response, None
        claims = self._verify_token(authorization.removeprefix("Bearer ").strip())
        if claims is None:
            response = JSONResponse({"code": "token-invalid"}, status_code=401)
            response.headers["WWW-Authenticate"] = "Bearer"
            return response, None
        needed = required_scope(method, path)
        if needed is None or needed not in str(claims["scope"]).split():
            return JSONResponse({"code": "insufficient-scope"}, status_code=403), None
        return None, str(claims["sub"])
