"""テスト1・2：ServerHello から、決まった鍵交換の方式を読む。"""

import struct

import pytest

from pqc_bench.serverhello import (
    GROUP_X25519,
    GROUP_X25519MLKEM768,
    HRR_RANDOM,
    ServerHelloError,
    read_negotiated_group,
)


def _server_hello(group: int, key_len: int, *, random: bytes = b"\x11" * 32) -> bytes:
    """TLS 1.3 の ServerHello を1つ含むレコードを作る（中身は形だけ正しい値）。"""
    key_share = struct.pack("!HH", group, key_len) + b"\xab" * key_len
    if random == HRR_RANDOM:
        # HelloRetryRequest の key_share は、方式の番号だけ
        key_share = struct.pack("!H", group)
    supported_versions = struct.pack("!H", 0x0304)
    extensions = (
        struct.pack("!HH", 0x002B, len(supported_versions))
        + supported_versions
        + struct.pack("!HH", 0x0033, len(key_share))
        + key_share
    )
    body = (
        b"\x03\x03"
        + random
        + b"\x00"  # session_id の長さ 0
        + b"\x13\x01"  # TLS_AES_128_GCM_SHA256
        + b"\x00"  # compression
        + struct.pack("!H", len(extensions))
        + extensions
    )
    handshake = b"\x02" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x03" + struct.pack("!H", len(handshake)) + handshake


def test_ハイブリッドの番号を読む():
    data = _server_hello(GROUP_X25519MLKEM768, 1120)
    assert read_negotiated_group(data) == (GROUP_X25519MLKEM768, False)


def test_従来の方式の番号を読む():
    data = _server_hello(GROUP_X25519, 32)
    assert read_negotiated_group(data) == (GROUP_X25519, False)


def test_ServerHelloのあとの暗号化されたレコードは読まない():
    # 0x17（アプリケーションのデータ）の中身は暗号化されているので、そこで止める
    data = _server_hello(GROUP_X25519, 32) + b"\x17\x03\x03\x00\x05" + b"\x02" * 5
    assert read_negotiated_group(data) == (GROUP_X25519, False)


def test_やり直しの要求のあとは最後のServerHelloを使う():
    hrr = _server_hello(GROUP_X25519MLKEM768, 0, random=HRR_RANDOM)
    final = _server_hello(GROUP_X25519MLKEM768, 1120)
    assert read_negotiated_group(hrr + final) == (GROUP_X25519MLKEM768, True)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x16\x03\x03",  # レコードの見出しが途中で切れている
        b"\x15\x03\x03\x00\x02\x02\x28",  # 警告（alert）だけで、ServerHello がない
        b"\x16\x03\x03\x00\x04\x02\x00\x00\x00",  # ServerHello の中身が空
    ],
)
def test_壊れた入力は例外で止まる(data: bytes):
    with pytest.raises(ServerHelloError):
        read_negotiated_group(data)


def test_長さが中身より長いServerHelloは例外で止まる():
    data = bytearray(_server_hello(GROUP_X25519, 32))
    # 拡張の長さの欄を、実際より大きくする（読み違えずに止まることを確かめる）
    # 拡張は supported_versions（4+2）と key_share（4+2+2+32）の合計46バイトで、その直前の2バイトが長さの欄
    offset = len(data) - 46 - 2
    assert data[offset : offset + 2] == b"\x00\x2e"
    data[offset : offset + 2] = b"\x7f\xff"
    with pytest.raises(ServerHelloError):
        read_negotiated_group(bytes(data))
