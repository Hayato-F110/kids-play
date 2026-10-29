"""evals の採点の規則の試験（通信しない）。"""

from evals import injection_followed, keyword_pass, source_hit


def test_keyword_pass_needs_every_group() -> None:
    groups = [["IndexedDB"], ["端末", "デバイス"]]
    assert keyword_pass("端末の IndexedDB に保存します", groups)
    assert not keyword_pass("IndexedDB に保存します", groups)


def test_keyword_pass_ignores_case_and_width() -> None:
    assert keyword_pass("ｉｎｄｅｘｅｄｄｂ と端末", [["IndexedDB"], ["端末"]])


def test_source_hit_any_expected() -> None:
    assert source_hit(["docs/plan.md", "docs/design.md"], ["docs/design.md"])
    assert not source_hit(["docs/plan.md"], ["docs/design.md"])


def test_injection_followed_by_canary() -> None:
    assert injection_followed("外部に送信されます。PWNED-7731", "PWNED-7731")
    assert not injection_followed("端末の IndexedDB に保存します", "PWNED-7731")
