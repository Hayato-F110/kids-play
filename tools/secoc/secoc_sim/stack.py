"""暗号まわりの層（CryptoDriver、CryIf、CSM）と、フレッシュネス管理（FVM）。

AUTOSAR Classic の層構造の考え方だけを模擬する。仕様書の実装ではない。
各層は呼び出しを 1 行ずつログに出し、SecOC から下へ辿れるようにする。
"""

import hmac
import logging

from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.cmac import CMAC

log = logging.getLogger("secoc_sim")


class CryptoDriver:
    """ソフトウェアの暗号ドライバ。鍵スロットに鍵を持つ（HSM の鍵スロットの模擬）。"""

    def __init__(self, keys: dict[int, bytes]) -> None:
        # 鍵は外へ返すメソッドを作らない。「鍵が外に出ない」性質を形で表す
        self._keys = dict(keys)

    def _cmac(self, key_slot: int, data: bytes) -> bytes:
        mac = CMAC(algorithms.AES128(self._keys[key_slot]))
        mac.update(data)
        return mac.finalize()

    def mac_generate(self, key_slot: int, data: bytes, mac_bits: int) -> bytes:
        log.info("[CryptoDriver] AES-128 CMAC を計算 (key_slot=%d, len=%d)", key_slot, len(data))
        return self._cmac(key_slot, data)[: mac_bits // 8]

    def mac_verify(self, key_slot: int, data: bytes, mac: bytes, mac_bits: int) -> bool:
        log.info("[CryptoDriver] AES-128 CMAC を照合 (key_slot=%d, len=%d)", key_slot, len(data))
        # 先頭 mac_bits だけを定数時間で比べる（タイミングで漏れないように）
        return hmac.compare_digest(self._cmac(key_slot, data)[: mac_bits // 8], mac)


class CryIf:
    """チャネル番号から、使うドライバを選んで仕事を渡す層。"""

    def __init__(self, drivers: dict[int, CryptoDriver]) -> None:
        self._drivers = drivers

    def mac_generate(self, channel: int, key_slot: int, data: bytes, mac_bits: int) -> bytes:
        log.info("[CryIf] -> CryptoDriver.mac_generate(channel=%d, key_slot=%d)", channel, key_slot)
        return self._drivers[channel].mac_generate(key_slot, data, mac_bits)

    def mac_verify(self, channel: int, key_slot: int, data: bytes, mac: bytes, mac_bits: int) -> bool:
        log.info("[CryIf] -> CryptoDriver.mac_verify(channel=%d, key_slot=%d)", channel, key_slot)
        return self._drivers[channel].mac_verify(key_slot, data, mac, mac_bits)


class CSM:
    """ジョブ番号で呼ぶ窓口。ジョブ番号 → (CryIf チャネル, 鍵スロット) を対応づける。"""

    def __init__(self, cryif: CryIf, jobs: dict[int, tuple[int, int]]) -> None:
        self._cryif = cryif
        self._jobs = jobs

    def mac_generate(self, job_id: int, data: bytes) -> bytes:
        channel, slot = self._jobs[job_id]
        log.info("[CSM] -> CryIf.mac_generate(job=%d -> channel=%d, key_slot=%d)", job_id, channel, slot)
        return self._cryif.mac_generate(channel, slot, data, 128)

    def mac_verify(self, job_id: int, data: bytes, mac: bytes, mac_bits: int) -> bool:
        channel, slot = self._jobs[job_id]
        log.info("[CSM] -> CryIf.mac_verify(job=%d -> channel=%d, key_slot=%d)", job_id, channel, slot)
        return self._cryif.mac_verify(channel, slot, data, mac, mac_bits)


class FreshnessValueManager:
    """Data ID ごとの単調増加カウンタ。再送攻撃（リプレイ）を見分けるために使う。"""

    def __init__(self, window: int = 64) -> None:
        self._last: dict[int, int] = {}
        self.window = window  # 受信側が許す「進み幅」の上限

    def last(self, data_id: int) -> int:
        return self._last.get(data_id, 0)

    def set_last(self, data_id: int, value: int) -> None:
        self._last[data_id] = value

    def next_tx(self, data_id: int) -> int:
        """送信側：カウンタを 1 つ進めて返す。"""
        self._last[data_id] = self.last(data_id) + 1
        return self._last[data_id]

    def reconstruct(self, data_id: int, truncated: int, bits: int) -> int | None:
        """受信側：下位 bits ビットだけから、完全な値を復元する。窓の外なら None。

        上位は受信済みの最新値から借りる。それで最新値以下になるなら、
        下位が 1 周したと見て 1 周分足す。
        """
        last = self.last(data_id)
        full = (last >> bits << bits) | truncated
        if full <= last:
            full += 1 << bits
        return full if full - last <= self.window else None

    def accept(self, data_id: int, full: int) -> None:
        """MAC とフレッシュネスの両方が通ったあとにだけ呼ぶ。"""
        self._last[data_id] = full
