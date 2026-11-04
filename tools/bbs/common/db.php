<?php
// データベース（SQLite）を開き、初めてなら表を作る。両方の版で同じ。
// 中身は自作の架空の値だけ（C-35 (4)）。admin の secret は、SQL インジェクションで読まれる「守りたい値」の役。
declare(strict_types=1);

function bbs_db(): PDO
{
    $path = getenv('BBS_DB') ?: '/data/bbs.sqlite';
    $pdo = new PDO('sqlite:' . $path, null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $pdo->exec('CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        body TEXT NOT NULL
    )');
    $pdo->exec('CREATE TABLE IF NOT EXISTS admin (name TEXT NOT NULL, secret TEXT NOT NULL)');
    if ((int) $pdo->query('SELECT count(*) FROM admin')->fetchColumn() === 0) {
        $pdo->exec("INSERT INTO admin (name, secret) VALUES ('admin', 'FAKE-SECRET-0001')");
        $pdo->exec("INSERT INTO posts (name, body) VALUES ('くま', 'こんにちは')");
    }
    return $pdo;
}
