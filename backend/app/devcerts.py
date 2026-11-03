"""nginx と api の間の mTLS に使う、その場かぎりの CA と証明書を作る。脅威分析 T-30、対策 C-33。

compose.zerotrust.yaml の certs コンテナが、起動のたびに1回だけ動かす：

    python -m app.devcerts /certs

置き場所（/certs）は、メモリ上の共有の置き場所（tmpfs）にする。PC のディスク、Git、イメージには出ない。
CA の秘密鍵は書き出さず、関数を抜けると消える。作り終えたあとは、だれも新しい証明書を作れない。
"""

import datetime
import os
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

# 書き出すファイル。CA は証明書だけ（秘密鍵は書き出さない）
FILES = {
    "ca_cert": "ca.crt",
    "api_cert": "api.crt",
    "api_private": "api.key",
    "nginx_cert": "nginx.crt",
    "nginx_private": "nginx.key",
}
# 期限は1日。起動のたびに作り直すので、長く使える証明書を残さない
LIFETIME = datetime.timedelta(days=1)
# 持ち主（api）と同じグループ（nginx）だけが読める。ほかのユーザーは読めない
FILE_MODE = 0o640


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _private_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _issue(
    ca_key: ec.EllipticCurvePrivateKey,
    ca_name: x509.Name,
    common_name: str,
    usage: x509.ObjectIdentifier,
    dns_names: list[str],
    now: datetime.datetime,
) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + LIFETIME)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        # サーバー用とクライアント用を分ける。nginx の証明書で api になりすませないようにする
        .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
        # どの CA の鍵で署名したかの印。Python 3.13 以降の既定の検査（VERIFY_X509_STRICT）が求める
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
    )
    if dns_names:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in dns_names]), critical=False
        )
    return builder.sign(ca_key, hashes.SHA256()), key


def _write(path: Path, data: bytes) -> None:
    # 作るときから読める人を絞る（あとで chmod すると、その間に読まれうる）
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def make_dev_certs(folder: Path, server_names: list[str] | None = None) -> None:
    """CA を作り、api（サーバー）と nginx（クライアント）の証明書を出して、folder に書く。"""
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = _name("kids-play-zerotrust-ca")
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + LIFETIME)
        # この CA は、末端の証明書しか出せない（下に別の CA を作れない）
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    api_cert, api_key = _issue(
        ca_key, ca_name, "api", ExtendedKeyUsageOID.SERVER_AUTH, server_names or ["api"], now
    )
    nginx_cert, nginx_key = _issue(ca_key, ca_name, "nginx", ExtendedKeyUsageOID.CLIENT_AUTH, [], now)

    pem = serialization.Encoding.PEM
    _write(folder / FILES["ca_cert"], ca_cert.public_bytes(pem))
    _write(folder / FILES["api_cert"], api_cert.public_bytes(pem))
    _write(folder / FILES["api_private"], _private_pem(api_key))
    _write(folder / FILES["nginx_cert"], nginx_cert.public_bytes(pem))
    _write(folder / FILES["nginx_private"], _private_pem(nginx_key))
    # ca_key はここで参照がなくなる。ファイルにもログにも出していない


if __name__ == "__main__":
    make_dev_certs(Path(sys.argv[1]))
