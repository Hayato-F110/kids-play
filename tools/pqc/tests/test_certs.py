"""テスト6：試験用の証明書を作り、Git の外に置く。"""

from pathlib import Path

from cryptography import x509

from pqc_bench.certs import DEFAULT_CERT_DIR, write_self_signed

PQC_DIR = Path(__file__).resolve().parents[1]


def test_鍵と証明書ができる(tmp_path: Path):
    cert_path, key_path = write_self_signed(tmp_path)
    assert cert_path.exists() and key_path.exists()
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "localhost" in names.get_values_for_type(x509.DNSName)
    # 試験用なので期限は短く（1日）
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days <= 1


def test_既定の置き場所はgitignoreに入っている():
    assert DEFAULT_CERT_DIR == PQC_DIR / ".certs"
    ignored = (PQC_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".certs/" in ignored
