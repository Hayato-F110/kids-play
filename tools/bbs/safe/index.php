<?php
// 安全な版。危険な版（../unsafe/index.php）と同じ画面で、3つの攻撃を防ぐ。
// (1) SQL インジェクション → プリペアドステートメント（SQL と値を分けて渡す）
// (2) XSS                  → 表示のときに htmlspecialchars。CSP で、スクリプトを読み込ませない
// (3) CSRF                 → セッションに結びついたトークン、SameSite=Strict の Cookie、Origin の確認
declare(strict_types=1);

require __DIR__ . '/../common/guard.php';
require __DIR__ . '/../common/db.php';

const NAME_MAX = 20;
const BODY_MAX = 200;

function h(string $s): string
{
    return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE | ENT_HTML5, 'UTF-8');
}

function deny(int $code, string $reason): never
{
    http_response_code($code);
    header('Content-Type: text/plain; charset=utf-8');
    echo $reason . "\n";
    exit;
}

bbs_guard_host();

// スクリプト、外部の読み込み、よそへのフォームの送信、枠への埋め込みを、すべて止める
header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

session_set_cookie_params(['path' => '/', 'httponly' => true, 'samesite' => 'Strict']);
session_start();
$_SESSION['csrf'] ??= bin2hex(random_bytes(32));
$token = $_SESSION['csrf'];

$pdo = bbs_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Origin があれば、自分自身でなければ断る（ブラウザは POST に Origin を付ける）
    $origin = $_SERVER['HTTP_ORIGIN'] ?? null;
    if ($origin !== null && $origin !== 'http://' . $_SERVER['HTTP_HOST']) {
        deny(403, 'forbidden origin');
    }
    // トークンは、時間で差が出ない比べ方で確かめる
    if (!hash_equals($token, (string) ($_POST['csrf'] ?? ''))) {
        deny(403, 'bad token');
    }
    $name = trim((string) ($_POST['name'] ?? ''));
    $body = trim((string) ($_POST['body'] ?? ''));
    if ($name === '' || $body === '' || mb_strlen($name) > NAME_MAX || mb_strlen($body) > BODY_MAX) {
        deny(400, 'bad input');
    }
    $stmt = $pdo->prepare('INSERT INTO posts (name, body) VALUES (:name, :body)');
    $stmt->execute([':name' => $name, ':body' => $body]);
    header('Location: /', true, 303);
    exit;
}

$q = (string) ($_GET['q'] ?? '');
$stmt = $pdo->prepare('SELECT name, body FROM posts WHERE body LIKE :q ORDER BY rowid DESC');
$stmt->execute([':q' => '%' . $q . '%']);
$rows = $stmt->fetchAll();
?>
<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>けいじばん（あんぜんな版）</title></head>
<body>
<h1>けいじばん（あんぜんな版）</h1>
<form method="get"><input name="q" value="<?= h($q) ?>"><button>さがす</button></form>
<form method="post">
  <input type="hidden" name="csrf" value="<?= h($token) ?>">
  <input name="name" placeholder="なまえ" maxlength="<?= NAME_MAX ?>">
  <input name="body" placeholder="ほんぶん" maxlength="<?= BODY_MAX ?>">
  <button>かく</button>
</form>
<ul>
<?php foreach ($rows as $row): ?>
  <li><b><?= h($row['name']) ?></b> <?= h($row['body']) ?></li>
<?php endforeach; ?>
</ul>
</body>
</html>
