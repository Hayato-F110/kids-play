<?php
// ==========================================================================
// 試験用。わざと危険に書いている。使わない・写さない（T-32、C-35 (2)）
// 3つの弱点：(1) SQL を文字列でつなぐ → SQL インジェクション
//            (2) 表示でエスケープしない → XSS
//            (3) CSRF トークンがない   → CSRF
// 安全な書き方は ../safe/index.php
// ==========================================================================
declare(strict_types=1);

require __DIR__ . '/../common/guard.php';
require __DIR__ . '/../common/db.php';

bbs_guard_host();
$pdo = bbs_db();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name = (string) ($_POST['name'] ?? '');
    $body = (string) ($_POST['body'] ?? '');
    // 危険 (1)(3)：入力をそのまま SQL に入れ、どこから来た要求かも確かめない
    $pdo->exec("INSERT INTO posts (name, body) VALUES ('$name', '$body')");
    header('Location: /', true, 303);
    exit;
}

$q = (string) ($_GET['q'] ?? '');
// 危険 (1)：検索の言葉をそのまま SQL に入れる
$rows = $pdo->query("SELECT name, body FROM posts WHERE body LIKE '%$q%' ORDER BY rowid DESC")->fetchAll();
?>
<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>けいじばん（きけんな版）</title></head>
<body>
<h1>けいじばん（きけんな版）</h1>
<form method="get"><input name="q" value="<?= $q ?>"><button>さがす</button></form>
<form method="post">
  <input name="name" placeholder="なまえ">
  <input name="body" placeholder="ほんぶん">
  <button>かく</button>
</form>
<ul>
<?php foreach ($rows as $row): ?>
  <?php /* 危険 (2)：投稿をそのまま HTML に出す */ ?>
  <li><b><?= $row['name'] ?></b> <?= $row['body'] ?></li>
<?php endforeach; ?>
</ul>
</body>
</html>
