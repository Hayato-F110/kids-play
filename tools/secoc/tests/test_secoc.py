"""SecOC 模擬のテスト（先に書いた）。鍵はテスト専用の固定値で、ファイルには書かない。"""

import logging

import pytest

from secoc_sim.secoc import Result, build_secoc

TEST_KEY = bytes(range(16))  # テスト専用。本物の鍵ではない
OTHER_KEY = bytes(range(16, 32))  # テスト専用
DATA_ID = 0x0123


def make_pair(rx_key: bytes = TEST_KEY):
    return build_secoc(TEST_KEY, DATA_ID), build_secoc(rx_key, DATA_ID)


def test_valid_pdu_is_accepted():
    tx, rx = make_pair()
    result, payload = rx.receive(tx.send(b"\x01\x02"))
    assert result is Result.OK
    assert payload == b"\x01\x02"


def test_tampered_payload_is_rejected_and_fvm_not_advanced():
    tx, rx = make_pair()
    pdu = bytearray(tx.send(b"\x01\x02"))
    pdu[0] ^= 0xFF
    result, payload = rx.receive(bytes(pdu))
    assert result is Result.MAC_FAILED
    assert payload is None
    assert rx.fvm.last(DATA_ID) == 0
    # 改ざんで FVM が進んでいなければ、次の正しい PDU は受け付けられる
    assert rx.receive(tx.send(b"\x03"))[0] is Result.OK


def test_tampered_mac_is_rejected():
    tx, rx = make_pair()
    pdu = bytearray(tx.send(b"\x01"))
    pdu[-1] ^= 0x01
    assert rx.receive(bytes(pdu))[0] is Result.MAC_FAILED


def test_replay_is_rejected():
    tx, rx = make_pair()
    pdu = tx.send(b"\x01")
    assert rx.receive(pdu)[0] is Result.OK
    assert rx.receive(pdu)[0] is Result.FRESHNESS_FAILED


def test_older_counter_is_rejected():
    tx, rx = make_pair()
    first = tx.send(b"\x01")
    second = tx.send(b"\x02")
    assert rx.receive(second)[0] is Result.OK
    assert rx.receive(first)[0] is Result.FRESHNESS_FAILED


def test_truncated_freshness_wraparound_is_accepted():
    tx, rx = make_pair()
    tx.fvm.set_last(DATA_ID, 0x0FE)
    rx.fvm.set_last(DATA_ID, 0x0FE)
    assert rx.receive(tx.send(b"\x01"))[0] is Result.OK  # 0x0FF
    assert rx.receive(tx.send(b"\x02"))[0] is Result.OK  # 0x100（下位8ビットは 0x00 に戻る）
    assert rx.fvm.last(DATA_ID) == 0x100


def test_wrong_key_on_receiver_is_rejected():
    tx, rx = make_pair(rx_key=OTHER_KEY)
    assert rx.receive(tx.send(b"\x01"))[0] is Result.MAC_FAILED


@pytest.mark.parametrize("pdu", [b"", b"\x01\x02\x03", b"\x01" * 4])
def test_too_short_pdu_is_malformed(pdu: bytes):
    _, rx = make_pair()
    assert rx.receive(pdu)[0] is Result.MALFORMED


def test_log_shows_layer_call_chain_in_order(caplog: pytest.LogCaptureFixture):
    tx, rx = make_pair()
    pdu = tx.send(b"\x01")
    with caplog.at_level(logging.INFO, logger="secoc_sim"):
        rx.receive(pdu)
    text = "\n".join(r.getMessage() for r in caplog.records)
    marks = ["[SecOC] -> CSM.mac_verify", "[CSM] -> CryIf.", "[CryIf] -> CryptoDriver.mac_verify"]
    positions = [text.index(m) for m in marks]
    assert positions == sorted(positions)
