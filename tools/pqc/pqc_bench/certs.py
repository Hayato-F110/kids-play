"""試験用の自己署名の証明書を作る（C-34 (4)）。

証明書と秘密鍵は Git の外（tools/pqc/.certs/、.gitignore 済み）に置き、イメージにも入れない。
"""

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DEFAULT_CERT_DIR = Path(__file__).resolve().parents[1] / ".certs"


def write_self_signed(directory: Path = DEFAULT_CERT_DIR) -> tuple[Path, Path]:
    """localhost 用の証明書（ECDSA P-256、期限1日）を作り、(証明書, 秘密鍵) のパスを返す。

    署名は従来の ECDSA のまま。今日比べるのは鍵交換で、署名の PQC（ML-DSA）は nginx とブラウザの対応が
    まだそろっていないため（CBOM に「移行が残る」として記録する）。
    """
    directory.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=23))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "cert.pem"
    key_path = directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


if __name__ == "__main__":
    cert_path, _ = write_self_signed()
    print(f"作成しました：{cert_path.parent}")
