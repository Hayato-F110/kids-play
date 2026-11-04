"""TLS のハンドシェイクを繰り返し、1回ごとの時間・送受信の量・決まった方式を CSV に足す。

ハンドシェイクは Python の中で MemoryBIO を通して行う。送ったバイトと受け取ったバイトを数え、
受け取ったバイトから ServerHello を読む。TCP の接続の時間は含めない（鍵交換の差だけを見るため）。

使い方：uv run python -m pqc_bench.measure --count 200
"""

import argparse
import csv
import datetime
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from pqc_bench.certs import DEFAULT_CERT_DIR
from pqc_bench.serverhello import GROUP_X25519, GROUP_X25519MLKEM768, read_negotiated_group

PORT_HYBRID = 8443  # ハイブリッドだけ（X25519MLKEM768）を受け付ける入口
PORT_CLASSIC = 8444  # 従来の方式だけ（X25519）を受け付ける入口

# （名前, クライアントの種類, 入口, 期待する方式）
SCENARIOS: list[tuple[str, str, int, int]] = [
    ("hybrid", "hybrid", PORT_HYBRID, GROUP_X25519MLKEM768),
    ("classic", "classic", PORT_CLASSIC, GROUP_X25519),
    # PQC に対応したブラウザが、まだ対応していないサーバーにつなぐ場合
    ("hybrid-client-classic-server", "hybrid", PORT_CLASSIC, GROUP_X25519),
]

CSV_FIELDS = ["run_id", "scenario", "expected_group", "group", "hrr", "elapsed_ms", "bytes_out", "bytes_in"]
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "results" / "measurements.csv"


@dataclass(frozen=True)
class Record:
    group: int
    hrr: bool
    elapsed_ms: float
    bytes_out: int
    bytes_in: int


def make_client_context(kind: str, cafile: Path) -> ssl.SSLContext:
    """kind が "hybrid" なら OpenSSL 3.5 の既定（ML-KEM のハイブリッドと従来の方式の両方を提案）、
    "classic" なら X25519 だけを提案する。"""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(cafile)
    if kind == "classic":
        ctx.set_ecdh_curve("X25519")
    elif kind != "hybrid":
        raise ValueError(f"クライアントの種類が分からない：{kind}")
    return ctx


def handshake_once(
    host: str, port: int, ctx: ssl.SSLContext, server_hostname: str = "localhost", timeout: float = 5.0
) -> Record:
    incoming = ssl.MemoryBIO()
    outgoing = ssl.MemoryBIO()
    received = bytearray()
    bytes_out = 0
    with socket.create_connection((host, port), timeout=timeout) as sock:
        tls = ctx.wrap_bio(incoming, outgoing, server_hostname=server_hostname)
        start = time.perf_counter()
        while True:
            try:
                tls.do_handshake()
                break
            except ssl.SSLWantReadError:
                pending = outgoing.read()
                if pending:
                    sock.sendall(pending)
                    bytes_out += len(pending)
                chunk = sock.recv(65536)
                if not chunk:
                    raise ConnectionError("ハンドシェイクの途中で切られた") from None
                received += chunk
                incoming.write(chunk)
        # 最後の Finished を送り終えるまでをハンドシェイクとする
        pending = outgoing.read()
        if pending:
            sock.sendall(pending)
            bytes_out += len(pending)
        elapsed_ms = (time.perf_counter() - start) * 1000
    group, hrr = read_negotiated_group(bytes(received))
    return Record(group=group, hrr=hrr, elapsed_ms=elapsed_ms, bytes_out=bytes_out, bytes_in=len(received))


def run(count: int, out: Path, cafile: Path, host: str = "127.0.0.1") -> int:
    run_id = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    written = 0
    with out.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        for _ in range(count):
            # 方式を交互に並べ、時間による揺れ（PC の負荷）が片方だけに偏らないようにする
            for name, kind, port, expected in SCENARIOS:
                record = handshake_once(host, port, make_client_context(kind, cafile))
                writer.writerow(
                    {"run_id": run_id, "scenario": name, "expected_group": expected, **asdict(record)}
                )
                written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200, help="1つの方式あたりの回数")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cafile", type=Path, default=DEFAULT_CERT_DIR / "cert.pem")
    args = parser.parse_args()
    written = run(args.count, args.out, args.cafile)
    print(f"{written} 件を {args.out} に足しました")


if __name__ == "__main__":
    main()
