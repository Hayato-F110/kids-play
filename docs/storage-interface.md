# えほんの保存のインターフェース

わたしのえほんの絵と録音を保存する入口。画面（`frontend/apps/storybook/`）はこのインターフェースだけを呼び、保存先の中身を知らない。
保存先を差し替えても画面を直さなくてよいようにするため（C言語で、関数ポインタの構造体を通してドライバを差し替えるのと同じ考え方）。

## 保存先

| 保存先 | ファイル | 使う場面 | 状態 |
|---|---|---|---|
| メモリ | `frontend/js/storage/memory.js` | テスト。IndexedDB が使えないブラウザでの代わり（再読み込みで消える） | 8日目 |
| IndexedDB | `frontend/js/storage/indexeddb.js` | すべての公開環境（GitHub Pages、PWA、Androidアプリ、AWS版）の既定 | 9日目（KIDS-31）。再読み込みしても残る |
| FastAPI + SQLite | `frontend/js/storage/server.js`、`backend/` | PC の localhost で、設定で有効にしたときだけ | 10日目（KIDS-34） |

### 保存先の選び方（安全側に倒す）

サーバー保存は、次の **4つ** がすべてそろったときだけ使う。1つでも欠けたら IndexedDB を使う。

1. フロント：PC 内の開発用サーバーで開いている。`http:` で、ホスト名が `localhost` または `127.0.0.1`、ポートが開発用（`8000`）、かつ Android アプリ（Capacitor）の中ではない（`window.Capacitor` がない）。Android アプリもホスト名は `localhost` なので、ホスト名だけでは見分けられない。公開サイトとアプリでは、サーバーに問い合わせもしない
2. サーバー：環境変数 `KIDS_SERVER_STORAGE` に `enabled` と正確に書いたときだけ有効（`true` や `1` では有効にならない）。既定は無効で、無効のときは保存の API をすべて 403 で拒否し、DB も作らない。フロントは `/api/storage/status` が `{"enabled": true}` と答えたときだけサーバーを使い、つながらない・1.5秒で答えない・形が違うときは IndexedDB にする
3. CSP：えほんの画面だけ `connect-src 'self'` を足し、通信先を自分のオリジンに限る。ほかの画面には足さない（`npm run check:pwa` で確かめる。C-08）。FastAPI がフロントも配るので、通信先は同じオリジンになる
4. サーバーの待ち受け：`127.0.0.1` だけで待ち受け（ほかの機器から届かない）、`Host` ヘッダーが `localhost` / `127.0.0.1` 以外の要求を拒否する（DNS リバインディング対策）

設定を忘れたり誤ったりしても、子どもの絵と声が公開サーバーに送られないようにするため（脅威分析の T-08。ISO/SAE 21434 でいう、独立した複数の対策を重ねる考え方）。
選ぶ処理は `frontend/js/storage/index.js` に置く。IndexedDB が開けなければメモリ版にする（サーバーには倒さない）。

### サーバー保存の起動（PC の中だけ）

```powershell
# backend/ で実行する。DB は backend/data/（gitignore 済み）に作られる
$env:KIDS_SERVER_STORAGE = "enabled"
uv run uvicorn app.main:create_app_from_env --factory --host 127.0.0.1 --port 8000
# ブラウザで http://localhost:8000/apps/storybook/ を開く
```

- `--factory`：`create_app_from_env` を呼んでアプリを作る。import しただけでは DB を作らないため
- `--host 127.0.0.1`：PC の中からだけ届くようにする（`0.0.0.0` にしない）
- 無効に戻すには、PowerShell を閉じるか `Remove-Item Env:KIDS_SERVER_STORAGE`（環境変数はその PowerShell の中だけで有効）

### サーバーの API

| メソッドとパス | 動き |
|---|---|
| `GET /api/storage/status` | `{"enabled": true/false}`。無効でも答える |
| `GET /api/pages` | 一覧（`id`、`pictureType`、`voiceType`、`voiceMs`）。絵と声の中身は含めない |
| `GET /api/pages/{id}/picture`、`/voice` | 絵・声の中身。なければ 404 |
| `POST /api/pages` | 新しいページ（multipart：`picture`、`voice`、`voiceMs`）。201 |
| `PUT /api/pages/{id}` | 上書き（順番は変えない）。ない id なら新しいページとして最後に足す（201） |
| `DELETE /api/pages/{id}`、`DELETE /api/pages` | 1ページ／全部を消す。204 |

受け付けるのは、絵は `image/png`、声は `audio/webm`・`audio/ogg`・`audio/mp4` だけ。申告の種類と先頭のバイトの両方で確かめる。大きさは絵 2MB、声 1MB まで（超えたら 413、`too-large`）。
API の応答には `Cache-Control: no-store` を付け、ブラウザに写しを残さない。

書き込みの要求（POST・PUT・DELETE）は、`Origin` が自分自身（`http://` ＋ Host）のときだけ受け付ける（CSRF 対策。脅威分析の T-18、C-22）。ほかのサイトからの要求は 403（`cross-origin`）。

サーバーが返す理由の名前：上の3つに加えて、`too-large`（413）、`length-required`（411）、`cross-origin`（403）、`server-storage-disabled`（403）。`server.js` は、そのまま `StorageError` の `code` にして渡す。

#### サーバー保存だけの違い（PC の中の確認用なので、そのままにしている）

- 画面が隠れたときの保存は、届かないことがある（ブラウザが通信を途中で止めるため）
- 大きさと種類の上限は、サーバーだけにある（絵は PNG で 2MB まで、声は webm・ogg・mp4 で 1MB まで）。フロントの `validate.js` に足すと、公開版（IndexedDB）で大きな絵が保存できなくなるので、足さない（10日目の /code-review の指摘）
- 2つのタブで同時に開き、一方で消している途中にもう一方が一覧を読むと、一覧の読み込みが失敗することがある

#### 11日目への申し送り（nginx の後ろに置くとき）

- CSRF の確認は、`Origin` と `Host` が一致することを見る。nginx で `proxy_set_header Host $host;` にするとポートが落ちて一致しなくなるので、`$http_host` で Host をそのまま渡す
- nginx の後ろでは、Host の許可リスト（localhost / 127.0.0.1）が本物のホスト名を断る。そのとき `allowed_hosts=["*"]` にしない。AWS ではサーバー保存を有効にしない（10日目の /security-review の注意）

## データの形（ページ）

| 項目 | 型 | 意味 |
|---|---|---|
| `id` | 文字列 | 保存先が付ける。新しいページを保存するときは付けない |
| `picture` | `Blob`（`image/*`）または `null` | 絵。描いていなければ `null` |
| `voice` | `Blob`（`audio/*`）または `null` | 録音。録っていなければ `null`。形式は端末が録れるもの（Chrome は `audio/webm`） |
| `voiceMs` | 数（0〜30000） | 録音の長さ（ミリ秒）。録音していなければ 0 |

ページの順番は、`listPages()` が返す並びそのもの。ページ番号（1〜8）は画面が並びから付ける。
名前、日時、端末の情報など、上にない項目は保存しない（知らない項目は捨てる）。

## 関数

すべて `Promise` を返す（IndexedDB とサーバーは、待ってから結果が返るため）。

| 関数 | 動き |
|---|---|
| `listPages()` | すべてのページを順番どおりに返す。はじめは空の配列 |
| `getPage(id)` | 1ページを返す。なければ `null` |
| `savePage(page)` | `id` なしなら最後に足して `id` を付ける。`id` ありなら、その位置のまま上書きする。保存したページを返す |
| `deletePage(id)` | 1ページを消す。残りのページは順番を保って詰まる |
| `deleteAll()` | すべて消す（保護者向けの全削除） |

返すページは写し。受け取った側が書き換えても、保存した中身は変わらない。

## 拒否するとき

保存の前に、すべての保存先が `frontend/js/storage/validate.js` で同じ確認をする。だめなときは `StorageError` を投げ、`code` で理由を区別する。

| `code` | 理由 |
|---|---|
| `page-limit` | 9ページ目を足そうとした（上限 `MAX_PAGES` = 8） |
| `voice-too-long` | 録音が30秒（`MAX_VOICE_MS`）を超えている |
| `invalid-page` | 形が違う（絵が画像でない、声が音でない、長さが負など） |

画面は、拒否されても失敗の表現を出さない（子ども向けデザインのルール）。たとえば、8ページあるときは「ページを足す」ボタンを出さない。

## テスト

約束は `tests/storage-contract.mjs` に書いてある。新しい保存先を作ったら、そのテストに保存先を作る関数を渡して呼ぶ（`tests/storage-memory.test.mjs` が例）。

```powershell
npm test             # Node 標準のテスト（node:test）。IndexedDB 版は fake-indexeddb（開発用）で動かす
npm run test:server  # サーバー版。本物の FastAPI を空の一時DB（OS の一時フォルダ）で起動して、同じ約束を試す。uv が必要
cd backend; uv run pytest   # API そのもの（無効なら拒否、入力の検証など）
```

約束のテストの見本データは、先頭のバイトだけ本物の形式（PNG、WebM）に合わせてある。サーバー版が、種類と中身が合っているかを確かめるため。
