# 13日目：TLS の評価とセキュリティヘッダー、ZAP のベースライン（KIDS-44）

- 日付：2026-10-24
- 対象：`https://kidsplay-110.duckdns.org/`（自分の EC2。ほかのサーバーは診断しない）
- 設定：`server/nginx/kids-play.conf`（EC2 の nginx。HTTPS の入口）
- 脅威分析との対応：T-05（配信の途中での書き換え、なりすまし）、C-14（HTTPS とセキュリティヘッダー）、C-08（CSP）

## 1. SSL Labs（Qualys SSL Server Test）

結果を公開の一覧に載せない設定（Do not show the results on the boards）で診断した。

| 項目 | 結果 | 判断 |
|---|---|---|
| 総合の評価 | **A+** | 目標（A 以上）を満たした |
| TLS の版 | 1.3 と 1.2 だけ。1.1、1.0、SSL 3、SSL 2 は無効 | よい（certbot の `options-ssl-nginx.conf`） |
| 暗号の組 | すべて前方秘匿性（FS）あり、AES-GCM と ChaCha20-Poly1305 だけ | よい |
| 証明書 | Let's Encrypt、EC 256 bit、信頼済み、チェーンの問題なし、CT あり、失効なし。期限は 2027-01-22（90日） | よい。自動更新は certbot のタイマー（`certbot renew --dry-run` で確認） |
| HSTS | `max-age=31536000`（1年）、preload なし | 計画どおり（下の 2 を参照） |
| 既知の脆弱性（Heartbleed、POODLE、ROBOT、BEAST など） | すべて該当なし | よい |
| OCSP stapling | なし | 対応は要らない。Let's Encrypt は失効の確認を CRL に切り替えている（結果にも CRL と出ている） |

### 受け入れたリスク

| 項目 | 結果 | 理由 |
|---|---|---|
| DNS CAA（黄色） | なし | CAA は「この名前の証明書を出してよい認証局」を DNS で宣言するもの。DuckDNS では自分で書けない。独自ドメイン（plan.md の「発展」）にすれば書ける。評価は減点されていない |
| 古い端末で接続できない（赤） | Safari 6〜8（iOS 6〜8、OS X 10.9〜10.10）、XP の Chrome 49 で handshake_failure | つなげるには、古くて弱い暗号を許す必要があり、新しい端末の守りまで下がる。どの OS も更新が止まっている。家族の端末（Android、Windows 11 の Chrome・Edge）は対象 |
| 耐量子暗号（PQC）の鍵交換 | なし | Ubuntu 24.04 の nginx と OpenSSL の版の都合。OS を上げるときに見直す |

## 2. セキュリティヘッダー

EC2 の nginx の 443 の `server` に、`always`（エラーの応答にも付ける）で付けた。PC から `curl` で、200、404、書き込みを断ったときの 403 のどれにも付くことを確かめた。

| ヘッダー | 値 | 何を防ぐか |
|---|---|---|
| Strict-Transport-Security | `max-age=31536000` | 2回目から、ブラウザが HTTP を使わない（T-05）。preload はしない（DuckDNS のサブドメインで、外したくなったときに戻せなくなるため） |
| Content-Security-Policy | meta と同じ内容 ＋ `connect-src 'self'`、`frame-ancestors 'none'` | 読み込み元を自分のサイトに限る（C-08）。`frame-ancestors` は meta では効かないので、ヘッダーで足した。ヘッダーと meta の CSP は両方が効くので、えほん以外のページは meta の側で通信を禁止したまま。Service Worker（sw.js）には meta が効かず、ヘッダーだけが効く。`connect-src 'self'` は sw.js の取得にも要るので、消すと PWA が壊れる（privacy-reviewer の指摘） |
| X-Frame-Options | `DENY` | 他のサイトの枠に入れさせない（古いブラウザ向け） |
| X-Content-Type-Options | `nosniff` | ファイルの種類をブラウザに推測させない |
| Referrer-Policy | `no-referrer` | どのページから来たかを相手に送らない |
| Permissions-Policy | `microphone=(self), camera=(), geolocation=(), payment=(), usb=()` | マイクは自分のページだけ。ほかの機能は使わせない（T-06） |
| Cross-Origin-Opener-Policy、Cross-Origin-Resource-Policy | `same-origin` | 別のサイトの窓や読み込みから手を出させない |
| Cache-Control（HTML だけ） | `no-cache` | 使う前に毎回サーバーに確かめさせる。デプロイのあとに古い画面を出さない（下の 3） |

## 3. ZAP のベースライン（受け身の診断）

- 道具：公式の `ghcr.io/zaproxy/zaproxy:stable` の `zap-baseline.py`（PC の Docker で実行）。1分ほどページを巡回し、応答を調べるだけで、攻撃の通信は送らない
- 結果：**FAIL 0、WARN 1、PASS 60**（37 の URL）

| 規則 | 結果 | 対応 |
|---|---|---|
| Re-examine Cache-control Directives（10015）、5件（トップ、どうぶつ、ぴあの、えほんの HTML と、manifest.webmanifest。おえかきと準備中の画面は、この規則の対象に出なかった） | WARN（危険度は Informational） | HTML に `Cache-Control: no-cache` を足した。ZAP は、秘密の中身には `no-store` を勧め、それ以外は「中身を見直す」ことを求めている。HTML は公開してよい静的なページだけで、子どもの絵と声は端末の IndexedDB にあり、HTTP の応答に入らない。`no-store` にしても守れるものが増えないので、見直したうえで受け入れた（WARN は残る） |
| CSP、HSTS、クリックジャッキング、nosniff、サーバーの版の表示、混在コンテンツ など | PASS | 2 のヘッダーが効いている |

## 4. 次に見直すとき

- OS（Ubuntu）を上げるとき：PQC の鍵交換、nginx の版
- 独自ドメインにするとき：CAA を書く、HSTS の preload を考える
- ページに秘密の中身が入るとき（いまは予定なし）：Cache-Control を `no-store` にする
