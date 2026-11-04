# PHP の掲示板で、3つの攻撃を試す（19日目）

- 日付：2026-11-04（KIDS-63）。脅威分析の T-32、対策 C-35
- 道具：[tools/bbs/](../../tools/bbs/)。危険な版 `127.0.0.1:8081`、安全な版 `127.0.0.1:8082`（`php:8.5.12-apache-trixie`）
- 目的：PHP のコードを読んで、危険な箇所に気づけるようになる。社内のコードは使わない。投稿は自作の文だけ

## 結果

テストは [tests/test_attacks.py](../../tools/bbs/tests/test_attacks.py)（16件、手元の Docker で実行。すべて通った）。学習者がブラウザでも、SQL インジェクションと XSS を両方の版で試した。

| 攻撃 | 試したこと | 危険な版 | 安全な版 | 安全な版の守り |
|---|---|---|---|---|
| SQL インジェクション | 検索の欄に `zzz' UNION SELECT name, secret FROM admin --` | 管理者の値（架空の `FAKE-SECRET-0001`）が画面に出た | 出なかった（ただの検索の言葉として扱われた） | プリペアドステートメント |
| XSS | 投稿に `<script>…</script>` | そのまま HTML に出た | `&lt;script&gt;` に変わった。CSP の `default-src 'none'` も付く | `htmlspecialchars`、CSP |
| CSRF | よそのオリジン（`http://evil.example`）から、トークンなしで投稿 | 投稿された（303） | 403 で断られた。トークンを盗めた場合も、よその Origin なら 403 | CSRF トークン、`SameSite=Strict`、Origin の確認 |
| 正しい使い方 | 自分の画面から、トークンつきで投稿 | – | 投稿できた | 守りが正しい使い方を邪魔しない |
| よその Host | `Host: evil.example` | 403 | 403 | 両方の版に共通の閉じ込め（C-35 (3)） |

**テストが守りを見分けられることの確認**：実装をテストより先に書いてしまったので、安全な版の守りを3つ一時的に外して（エスケープ、プリペアドステートメント、トークンの確認）、テストを動かした。安全な版のテストが3件失敗し、元に戻すと14件すべて通った。

**ブラウザで見つけた誤り**：学習者がブラウザで安全な版に投稿すると、「forbidden origin」で断られた。安全な版は `Referrer-Policy: no-referrer` を付けていて、ブラウザはその設定のページからのフォームの送信で `Origin` を `null` にする（Fetch の仕様）。テストは `Origin` を自分で付けて送っていたので、この食い違いに気づけなかった。`same-origin` に直し、「設定が same-origin であること」と「Origin が null の投稿は断ること」のテストを足した（16件）。テストが何を模擬しているか（ここではブラウザの代わり）を確かめ、本物の環境でも試す必要がある。

**気づいたこと**：XSS の試験の文字列に `'` を入れると、危険な版の投稿そのものが失敗した。SQL を文字列でつないでいるので、`'` で SQL が壊れる。XSS を試すつもりが、SQL インジェクションの弱さにも当たった。

## 危険な書き方と安全な書き方

**SQL インジェクション**

```php
// 危険：入力が SQL の文の一部になる。' で文字列を閉じて、別の SQL を続けられる
$rows = $pdo->query("SELECT name, body FROM posts WHERE body LIKE '%$q%'");

// 安全：SQL と値を別々に渡す。値は、どんな文字でも「値」としてしか扱われない
$stmt = $pdo->prepare('SELECT name, body FROM posts WHERE body LIKE :q');
$stmt->execute([':q' => '%' . $q . '%']);
```

**XSS**

```php
// 危険：投稿がそのまま HTML になる。<script> が動く
<li><?= $row['body'] ?></li>

// 安全：表示の直前に、HTML で意味のある文字（< > & " '）を変換する
<li><?= htmlspecialchars($row['body'], ENT_QUOTES | ENT_SUBSTITUTE | ENT_HTML5, 'UTF-8') ?></li>
```

**CSRF**

```php
// 安全：セッションに結びついた乱数のトークンを、フォームに隠して入れる。送られてきた値と比べる
$_SESSION['csrf'] ??= bin2hex(random_bytes(32));
if (!hash_equals($token, (string) ($_POST['csrf'] ?? ''))) { deny(403, 'bad token'); }
```

PHP のコードを読むときの目印：

- `query(` や `exec(` の中に `$` の変数がある → SQL インジェクションを疑う
- `<?=` や `echo` のあとに、`htmlspecialchars` を通さない変数がある → XSS を疑う
- `$_POST` を受ける処理に、トークンの確認（`hash_equals`）がない → CSRF を疑う

## FastAPI（kids-play のバックエンド）との比べ

| 観点 | PHP（今日の掲示板） | FastAPI（`backend/`） |
|---|---|---|
| 入力の検証 | 自分で書く（`trim`、`mb_strlen`）。書き忘れても動く | Pydantic のモデルで、型と長さを宣言する。合わない入力は、関数に届く前に 422 |
| SQL | PDO。文字列でつなぐ書き方もできてしまう | 標準の `sqlite3` の `?` のプレースホルダー。文字列でつなぐと ruff の `S608` が知らせる |
| 表示 | PHP のファイルが HTML を作る。エスケープは書く人の責任 | JSON を返すだけ。画面（JS）は `textContent` で表示し、`innerHTML` を使わない（CLAUDE.md の規約） |
| CSRF | トークンを自分で作る | Cookie を使わず、書き込みは Origin の確認（C-22）とトークン（18日目） |

PHP は、「危険な書き方も、同じくらい簡単に書ける」のが弱点。FastAPI は、型の宣言と道具（ruff）が、危険な書き方を早く知らせる。どちらでも、最後に守るのは、レビューで上の目印を見ること。

## Composer の部品の検査

- 掲示板は部品を使わない（`composer.json` がない）ので、検査する部品は0件
- 見本（わざと古い Twig 3.11.0）：**Composer 2.11.1 は、部品を選ぶ段階で拒否した**。17件の勧告がある版は選ばない（`policy.advisories.block`。Composer 2.9 以降は既定で有効）
- 選ぶ段階の拒否だけを外した見本：`composer audit` が twig/twig の勧告を見つけ、終了コードが 0 以外になった
- どちらも `--no-install --no-scripts --no-plugins` で、部品の一覧（lock）だけを作った。部品のコードは PC にも、コンテナにも入れていない
- 見本の `composer.json` は、テストのたびに一時フォルダーに作る。最初はリポジトリ（`tools/bbs/audit-demo/`）に置いたが、GitHub の Dependabot がそれを読み、使っていない Twig の通知を32件（勧告16件 × 見本2つ）出した。本物の通知が埋もれる（アラート疲れ）ので、リポジトリから外した（PR #111）。21434 の脆弱性の監視（第8章）でも、関係のない部品の情報が多いと、対応が要るものを見落とす。監視の対象（どの一覧を読ませるか）も設計の一部

npm の `npm audit`、Python の `pip-audit`（10日目）と同じ役目。Composer は「入れる前に止める」ところまで既定で行う点が進んでいる。

## CISA KEV（WordPress の TOCTOU）の点検

2026-11-03 に、WordPress Core（PHP）の TOCTOU が KEV に入った。TOCTOU は「確かめてから使うまでの間に、状態を変えられる」弱さ（例：ファイルの種類を確かめたあと、使う前に差し替えられる）。

- 掲示板には、ファイルの読み書き、アップロード、「確かめてから別の処理で使う」流れがない。データベースへの書き込みは1回の SQL で終わる
- CSRF のトークンの確認と書き込みは同じ要求の中で続けて行い、間に外から状態を変えられる処理はない

## 守りについての注意

- CodeQL は PHP に対応していないので、この掲示板の危険な版は、GitHub のコードスキャンでは指摘されない。C-35 (6) の「指摘を理由つきで閉じる」は、今は該当しない。PHP の静的解析をするなら、Psalm や PHPStan などを別に使う
- 危険な版は、先頭のコメントで「試験用。使わない・写さない」と書いた（C-35 (2)）

## 再現の手順（tools/bbs で）

```powershell
docker compose up -d
$env:BBS_INTEGRATION = "1"; uv run pytest
docker compose down
```
