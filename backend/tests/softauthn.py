"""テスト用のソフトの認証器。ブラウザと Windows Hello の代わりに、パスキーの応答を作る。

本物の認証器と同じ形（WebAuthn の attestationObject と assertion）を作るが、鍵はテストのたびに
メモリで作る ECDSA P-256 で、どこにも保存しない。生体の情報は使わない。
"""

import base64
import hashlib
import json
import os
import struct
from dataclasses import dataclass, field
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

# 認証器のデータのフラグ。UP：人が触れた、UV：本人を確かめた（生体や PIN）、AT：鍵の情報つき
FLAG_UP = 0x01
FLAG_UV = 0x04
FLAG_AT = 0x40


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass
class SoftAuthenticator:
    rp_id: str = "localhost"
    origin: str = "http://localhost:8080"
    user_verified: bool = True
    private_key: ec.EllipticCurvePrivateKey = field(
        default_factory=lambda: ec.generate_private_key(ec.SECP256R1())
    )
    credential_id: bytes = field(default_factory=lambda: os.urandom(16))
    sign_count: int = 0

    def _flags(self, attested: bool) -> int:
        flags = FLAG_UP | (FLAG_UV if self.user_verified else 0)
        return flags | (FLAG_AT if attested else 0)

    def _cose_public_key(self) -> bytes:
        numbers = self.private_key.public_key().public_numbers()
        # COSE の EC2 鍵：kty=2（EC2）、alg=-7（ES256）、crv=1（P-256）、x、y
        return cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")}
        )

    def _client_data(self, kind: str, challenge: str, origin: str | None) -> bytes:
        data = {"type": kind, "challenge": challenge, "origin": origin or self.origin, "crossOrigin": False}
        return json.dumps(data, separators=(",", ":")).encode("utf-8")

    def create(self, options: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        """navigator.credentials.create() の応答（登録）を、toJSON() の形で返す。"""
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        rp_hash = hashlib.sha256(self.rp_id.encode("utf-8")).digest()
        attested = bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id
        auth_data = (
            rp_hash + bytes([self._flags(True)]) + struct.pack(">I", 0) + attested + self._cose_public_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "response": {"clientDataJSON": b64url(client_data), "attestationObject": b64url(attestation)},
            "clientExtensionResults": {},
        }

    def get(self, options: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        """navigator.credentials.get() の応答（ログイン）を、toJSON() の形で返す。"""
        self.sign_count += 1
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        rp_hash = hashlib.sha256(self.rp_id.encode("utf-8")).digest()
        auth_data = rp_hash + bytes([self._flags(False)]) + struct.pack(">I", self.sign_count)
        signed = auth_data + hashlib.sha256(client_data).digest()
        signature = self.private_key.sign(signed, ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(signature),
                "userHandle": None,
            },
            "clientExtensionResults": {},
        }
