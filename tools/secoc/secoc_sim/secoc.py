"""SecOC 層：PDU に MAC とフレッシュネスを付ける／検証する（考え方の模擬）。

PDU の形：ペイロード | フレッシュネス（下位だけ） | MAC（先頭だけ）
MAC の入力：Data ID | ペイロード | フレッシュネス（完全な値）
完全な値を MAC に入れるので、下位だけ送っても、受信側が復元を間違えれば MAC が合わない。
"""

import logging
from enum import Enum

from secoc_sim.stack import CSM, CryIf, CryptoDriver, FreshnessValueManager

log = logging.getLogger("secoc_sim")

FRESH_BITS = 8
MAC_BITS = 24
FULL_FRESH_BYTES = 8


class Result(Enum):
    OK = "ok"
    MAC_FAILED = "mac_failed"
    FRESHNESS_FAILED = "freshness_failed"
    MALFORMED = "malformed"


class SecOC:
    def __init__(self, csm: CSM, fvm: FreshnessValueManager, job_id: int, data_id: int) -> None:
        self.csm = csm
        self.fvm = fvm
        self.job_id = job_id
        self.data_id = data_id

    def _mac_input(self, payload: bytes, fresh: int) -> bytes:
        return self.data_id.to_bytes(2, "big") + payload + fresh.to_bytes(FULL_FRESH_BYTES, "big")

    def send(self, payload: bytes) -> bytes:
        fresh = self.fvm.next_tx(self.data_id)
        data = self._mac_input(payload, fresh)
        log.info("[SecOC] -> CSM.mac_generate(job=%d, len=%d, freshness=0x%X)", self.job_id, len(data), fresh)
        mac = self.csm.mac_generate(self.job_id, data)[: MAC_BITS // 8]
        trunc = (fresh & ((1 << FRESH_BITS) - 1)).to_bytes(FRESH_BITS // 8, "big")
        return payload + trunc + mac

    def receive(self, pdu: bytes) -> tuple[Result, bytes | None]:
        fbytes, mbytes = FRESH_BITS // 8, MAC_BITS // 8
        if len(pdu) <= fbytes + mbytes:  # ペイロードが 1 バイトもない
            log.info("[SecOC] 短すぎる PDU (len=%d) -> malformed", len(pdu))
            return Result.MALFORMED, None
        payload, trunc, mac = pdu[: -(fbytes + mbytes)], pdu[-(fbytes + mbytes) : -mbytes], pdu[-mbytes:]
        # 先に窓を確かめる。古い値や再送は、復元した値が窓の外になる
        fresh = self.fvm.reconstruct(self.data_id, int.from_bytes(trunc, "big"), FRESH_BITS)
        if fresh is None:
            log.info("[SecOC] フレッシュネスが窓の外 -> freshness_failed")
            return Result.FRESHNESS_FAILED, None
        data = self._mac_input(payload, fresh)
        log.info("[SecOC] -> CSM.mac_verify(job=%d, len=%d, freshness=0x%X)", self.job_id, len(data), fresh)
        if not self.csm.mac_verify(self.job_id, data, mac, MAC_BITS):
            log.info("[SecOC] MAC が合わない -> mac_failed")
            return Result.MAC_FAILED, None
        # 検証が全部通ったあとにだけカウンタを進める（偽の PDU でカウンタを壊されないように）
        self.fvm.accept(self.data_id, fresh)
        log.info("[SecOC] 検証OK -> アプリへ渡す")
        return Result.OK, payload


def build_secoc(key: bytes, data_id: int, job_id: int = 1, key_slot: int = 1) -> SecOC:
    """1 つの ECU 分の層を組み立てる。鍵はドライバの鍵スロットにだけ入る。"""
    driver = CryptoDriver({key_slot: key})
    csm = CSM(CryIf({0: driver}), {job_id: (0, key_slot)})
    return SecOC(csm, FreshnessValueManager(), job_id, data_id)
