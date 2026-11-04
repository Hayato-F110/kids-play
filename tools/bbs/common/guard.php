<?php
// 両方の版に共通の閉じ込め（C-35 (3)）。Host が localhost か 127.0.0.1 でない要求は断る。
// ブラウザで開いた別のサイトが、DNS リバインディングで自分の名前を 127.0.0.1 に向けても、
// Host にはそのサイトの名前が入るので、ここで止まる。
declare(strict_types=1);

function bbs_guard_host(): void
{
    $host = strtolower((string) ($_SERVER['HTTP_HOST'] ?? ''));
    // ポートを外して名前だけにする（IPv6 の書き方は使わないので、最後の「:」より前）
    $name = preg_replace('/:\d+$/', '', $host);
    if ($name !== 'localhost' && $name !== '127.0.0.1') {
        http_response_code(403);
        header('Content-Type: text/plain; charset=utf-8');
        echo "forbidden host\n";
        exit;
    }
}
