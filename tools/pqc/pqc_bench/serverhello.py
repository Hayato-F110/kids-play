"""サーバーの最初の返事（ServerHello）から、実際に決まった鍵交換の方式を読む。

Python 3.14 の ssl には、決まった方式を返す関数がない。TLS 1.3 の ServerHello は暗号化されずに届くので、
受け取ったバイト列をそのまま読む。設定に名前を書いただけで安心せず、実際の結果を確かめるため（C-34 (3)）。
"""

import struct

# 方式の番号（IANA の TLS Supported Groups）
GROUP_X25519 = 0x001D
GROUP_SECP256R1 = 0x0017
GROUP_X25519MLKEM768 = 0x11EC

GROUP_NAMES = {
    GROUP_X25519: "X25519",
    GROUP_SECP256R1: "secp256r1",
    GROUP_X25519MLKEM768: "X25519MLKEM768",
}

# HelloRetryRequest（やり直しの要求）は、random がこの決まった値の ServerHello（RFC 8446 4.1.3）
HRR_RANDOM = bytes.fromhex("CF21AD74E59A6111BE1D8C021E65B891C2A211167ABB8C5E079E09E2C8A8339C")

_RECORD_HANDSHAKE = 0x16
_RECORD_CHANGE_CIPHER_SPEC = 0x14
_HANDSHAKE_SERVER_HELLO = 0x02
_EXT_KEY_SHARE = 0x0033


class ServerHelloError(ValueError):
    """ServerHello を読めなかった。推測で埋めずに止める。"""


class _Reader:
    """長さを確かめながら読む。足りなければ例外にする（C の境界の確認と同じ）。"""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self._pos + n > len(self._data):
            raise ServerHelloError(f"長さが足りない（位置 {self._pos} から {n} バイト）")
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("!H", self.take(2))[0]

    def u24(self) -> int:
        return int.from_bytes(self.take(3), "big")

    def done(self) -> bool:
        return self._pos == len(self._data)


def _handshake_bytes(data: bytes) -> bytes:
    """暗号化されていない handshake のレコードの中身をつなげる。暗号化されたレコードの手前で止める。"""
    reader = _Reader(data)
    out = bytearray()
    while not reader.done():
        record_type = reader.u8()
        reader.take(2)  # legacy_record_version
        length = reader.u16()
        payload = reader.take(length)
        if record_type == _RECORD_HANDSHAKE:
            out += payload
        elif record_type == _RECORD_CHANGE_CIPHER_SPEC:
            continue  # 互換のためのダミー。中身はない
        else:
            break  # 0x17 から先は暗号化されている。0x15（警告）でも止める
    return bytes(out)


def _parse_server_hello(body: bytes) -> tuple[int, bool]:
    reader = _Reader(body)
    reader.take(2)  # legacy_version
    is_hrr = reader.take(32) == HRR_RANDOM
    reader.take(reader.u8())  # legacy_session_id_echo
    reader.take(2)  # cipher_suite
    reader.take(1)  # legacy_compression_method
    extensions = _Reader(reader.take(reader.u16()))
    while not extensions.done():
        ext_type = extensions.u16()
        ext_data = extensions.take(extensions.u16())
        if ext_type == _EXT_KEY_SHARE:
            # ServerHello では「方式の番号、鍵の長さ、鍵」。HelloRetryRequest では方式の番号だけ
            return _Reader(ext_data).u16(), is_hrr
    raise ServerHelloError("key_share の拡張がない（TLS 1.3 ではない可能性）")


def read_negotiated_group(data: bytes) -> tuple[int, bool]:
    """受け取ったバイト列から（決まった方式の番号, やり直しの要求があったか）を返す。

    やり直しの要求（HelloRetryRequest）のあとに ServerHello がもう1つ来るので、最後のものを使う。
    """
    reader = _Reader(_handshake_bytes(data))
    group: int | None = None
    hrr_seen = False
    while not reader.done():
        try:
            msg_type = reader.u8()
            body = reader.take(reader.u24())
        except ServerHelloError:
            break  # 次のレコードに続くメッセージ（証明書など）は、ここでは読まない
        if msg_type != _HANDSHAKE_SERVER_HELLO:
            continue
        found, is_hrr = _parse_server_hello(body)
        hrr_seen = hrr_seen or is_hrr
        if not is_hrr:
            group = found
    if group is None:
        raise ServerHelloError("ServerHello が見つからない")
    return group, hrr_seen
