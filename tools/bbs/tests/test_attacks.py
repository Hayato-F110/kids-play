"""テスト1〜6：PHP の掲示板に3つの攻撃を試す。危険な版では成功し、安全な版では防げること。

Docker が要るので手元だけで動かす：
  docker compose up -d ; $env:BBS_INTEGRATION = "1" ; uv run pytest
"""

import http.client
import json
import os
import re
import secrets
import subprocess
import urllib.parse
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BBS_INTEGRATION") != "1", reason="Docker の掲示板が要る（BBS_INTEGRATION=1 で動かす）"
)

UNSAFE = 8081
SAFE = 8082
ADMIN_MARKER = "FAKE-SECRET-0001"  # common/db.php の架空の値
BBS_DIR = Path(__file__).resolve().parents[1]


def request(
    port: int,
    method: str = "GET",
    path: str = "/",
    form: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    body = urllib.parse.urlencode(form) if form is not None else None
    sent = {"Host": f"localhost:{port}", **(headers or {})}
    if body is not None:
        sent["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(method, path, body=body, headers=sent)
    resp = conn.getresponse()
    result = resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read().decode("utf-8")
    conn.close()
    return result


def safe_session() -> tuple[str, str]:
    """安全な版の画面を開き、（Cookie, CSRF トークン）を受け取る。"""
    _, headers, html = request(SAFE)
    cookie = headers["set-cookie"].split(";", 1)[0]
    token = re.search(r'name="csrf" value="([0-9a-f]{64})"', html)
    assert token, "トークンが画面にない"
    return cookie, token.group(1)


def search(port: int, q: str) -> str:
    return request(port, path="/?q=" + urllib.parse.quote(q))[2]


# --- テスト1：SQL インジェクション ---------------------------------------------

INJECTION = "zzz' UNION SELECT name, secret FROM admin --"


def test_1_SQLインジェクションで危険な版は秘密の値を読まれる():
    assert ADMIN_MARKER in search(UNSAFE, INJECTION)


def test_1_SQLインジェクションを安全な版は防ぐ():
    assert ADMIN_MARKER not in search(SAFE, INJECTION)


# --- テスト2：XSS ----------------------------------------------------------------


# 「'」を入れない。危険な版は SQL を文字列でつなぐので、「'」があると SQL が壊れて投稿そのものが失敗する
def _xss_payload(marker: str) -> str:
    return f"<script>document.title=/{marker}/</script>"


def test_2_XSSで危険な版はスクリプトをそのまま返す():
    marker = secrets.token_hex(4)
    payload = _xss_payload(marker)
    request(UNSAFE, "POST", form={"name": "x", "body": payload})
    assert payload in request(UNSAFE)[2]


def test_2_XSSを安全な版はエスケープとCSPで防ぐ():
    marker = secrets.token_hex(4)
    payload = _xss_payload(marker)
    cookie, token = safe_session()
    status, _, _ = request(
        SAFE,
        "POST",
        form={"csrf": token, "name": "x", "body": payload},
        headers={"Cookie": cookie, "Origin": f"http://localhost:{SAFE}"},
    )
    assert status == 303
    _, headers, html = request(SAFE, headers={"Cookie": cookie})
    assert payload not in html
    assert f"&lt;script&gt;document.title=/{marker}/&lt;/script&gt;" in html
    assert "default-src 'none'" in headers["content-security-policy"]


# --- テスト3・4：CSRF -----------------------------------------------------------


def test_3_CSRFで危険な版はよそからの投稿を受け付ける():
    marker = "csrf-" + secrets.token_hex(4)
    status, _, _ = request(
        UNSAFE, "POST", form={"name": "x", "body": marker}, headers={"Origin": "http://evil.example"}
    )
    assert status == 303
    assert marker in request(UNSAFE)[2]


def test_3_CSRFを安全な版は断る_トークンなし():
    marker = "csrf-" + secrets.token_hex(4)
    cookie, _ = safe_session()
    status, _, _ = request(SAFE, "POST", form={"name": "x", "body": marker}, headers={"Cookie": cookie})
    assert status == 403
    assert marker not in request(SAFE)[2]


def test_3_CSRFを安全な版は断る_よそのOrigin():
    # トークンを盗めたとしても、よそのページからの送信は Origin で止まる
    marker = "csrf-" + secrets.token_hex(4)
    cookie, token = safe_session()
    status, _, _ = request(
        SAFE,
        "POST",
        form={"csrf": token, "name": "x", "body": marker},
        headers={"Cookie": cookie, "Origin": "http://evil.example"},
    )
    assert status == 403


def test_4_安全な版は正しい投稿を受け付ける():
    marker = "ok-" + secrets.token_hex(4)
    cookie, token = safe_session()
    status, _, _ = request(
        SAFE,
        "POST",
        form={"csrf": token, "name": "くま", "body": marker},
        headers={"Cookie": cookie, "Origin": f"http://localhost:{SAFE}"},
    )
    assert status == 303
    assert marker in request(SAFE)[2]


def test_4_安全なCookieの属性():
    _, headers, _ = request(SAFE)
    cookie = headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


# --- テスト5：Host の確認（両方の版） ---------------------------------------------


@pytest.mark.parametrize("port", [UNSAFE, SAFE])
def test_5_よそのHostは両方の版で断る(port: int):
    status, _, _ = request(port, headers={"Host": "evil.example"})
    assert status == 403


# --- テスト6：composer audit -------------------------------------------------------


# わざと古い Twig を書いた見本。リポジトリには置かず、テストのたびに一時フォルダーに作る。
# 置くと、GitHub の Dependabot がこれを読んで、使っていない部品の通知を大量に出す（19日目に32件出た）
def _demo_manifest(directory: Path, *, block: bool) -> Path:
    config: dict[str, object] = {"allow-plugins": False}
    if not block:
        # composer audit が見つけることを確かめるためだけに、選ぶ段階の拒否を外す。本物の開発では外さない
        config["policy"] = {"advisories": {"block": False}}
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"require": {"twig/twig": "3.11.0"}, "config": config}
    (directory / "composer.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def _composer(demo: Path, args: str) -> subprocess.CompletedProcess[str]:
    # 部品の中のスクリプトとプラグインを動かさない（部品のコードを PC で実行しない）
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{demo}:/app",
            "-e",
            "COMPOSER_HOME=/tmp/composer",
            "composer:2.11.1",
            "sh",
            "-c",
            args,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


UPDATE = "composer update --no-install --no-scripts --no-plugins --no-interaction"


def test_6_Composerは既定で脆弱な版を選ばない(tmp_path: Path):
    # Composer 2.9 以降の policy.advisories.block（既定で有効）
    lock = _composer(_demo_manifest(tmp_path, block=True), UPDATE)
    assert lock.returncode != 0
    assert "affected by security advisories" in lock.stderr


def test_6_composer_auditは古いTwigの脆弱性を見つける(tmp_path: Path):
    demo = _demo_manifest(tmp_path, block=False)
    lock = _composer(demo, UPDATE + " -q")
    assert lock.returncode == 0, lock.stderr
    audit = _composer(demo, "composer audit --locked --format=json --no-plugins")
    # 脆弱性があると、終了コードが 0 以外になる
    assert audit.returncode != 0
    advisories = json.loads(audit.stdout)["advisories"]
    assert advisories.get("twig/twig"), audit.stdout


def test_6_リポジトリに部品の一覧のファイルを置かない():
    # 掲示板は部品を使わない。見本も置かない（Dependabot の誤った通知を出さない）
    assert list(BBS_DIR.rglob("composer.json")) == []
