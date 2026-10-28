# キッズあそびランド（kids-play）

4〜8歳の子ども向けミニアプリ集。Web、PWA、Androidアプリで遊べる。
14日間の個人学習プロジェクトとして、Web開発からCI/CD、クラウド、セキュリティまでを一通り体験した。

> 状態：14日間の学習を 2026-10-28 に完了。2026-10-29〜11-04 は発展の学習（スプリント3）を続けている

## ミニアプリ

| | なまえ | 内容 |
|---|---|---|
| 1 | どうぶつタッチ | 動物をタップすると鳴き声とアニメーション |
| 2 | おとあそびピアノ | 色の鍵盤をタップすると音が鳴る |
| 3 | おえかきスタンプ | 指でお絵かき、スタンプ、画像として保存 |
| 4 | わたしのえほん | 描いた絵に声を録音し、紙芝居のように再生 |

## スクリーンショット

| トップ | どうぶつタッチ | おとあそびピアノ | わたしのえほん |
|---|---|---|---|
| ![トップ画面](docs/images/top.png) | ![どうぶつタッチ](docs/images/animals.png) | ![おとあそびピアノ](docs/images/piano.png) | ![わたしのえほん](docs/images/storybook.png) |

文字に頼らず、大きな絵とアイコンで遊べるようにした。映っている絵はすべてサンプル（自作SVG）。

## 紹介動画

1分で、ミニアプリ、Androidアプリ、えほん（サンプルデータ）、マージから AWS への自動デプロイまでを紹介する。

https://github.com/user-attachments/assets/e48b3895-02bf-483d-bb89-e8952b75ec23

- 映っている絵と音は、すべてサンプル（自作SVGと合成音）。人の声は入っていない
- 編集：DaVinci Resolve（無料版）。タイトルと最後の場面は Remotion でコードから作成（[video/title/](video/title/)）。作り方は [docs/video-storyboard.md](docs/video-storyboard.md)

## 発表資料

| 資料 | 内容 |
|---|---|
| [成果発表（PDF、17ページ）](docs/slides/kids-play-presentation.pdf) | 目的と結果、作ったもの、構成図、進め方、プライバシーとセキュリティ、AI との分担、学んだこと、失敗から学んだこと |
| [1枚資料（PDF）](docs/slides/kids-play-one-pager.pdf) | 全体を1枚にまとめたもの |

どちらも Claude Design（Claude Code の会話の中）で、アプリのデザインシステムを読み込んで作った。

## 遊び方

| 環境 | 方法 |
|---|---|
| Web（GitHub Pages） | https://hayato-f110.github.io/kids-play/ |
| PWA | 上のURLをAndroidのChromeで開き、「ホーム画面に追加」 |
| Androidアプリ | Android Studioでビルドし、USBデバッグで実機にインストール（Google Playでは配布しない） |
| AWS版（HTTPS） | 2026-10-24〜10-28 に公開し、学習の区切りで終了した（AWS のリソースは削除済み）。作り方は [docs/architecture.md](docs/architecture.md) と `server/` に残している |
| ローカル（PC） | 下の「PC で動かす」 |

### PC で動かす

```powershell
# フロントエンドだけ（サーバーなしで動く）。http://localhost:8000 を開く
python -m http.server 8000 --directory frontend

# nginx + FastAPI のコンテナ（Docker Desktop が必要）。http://127.0.0.1:8080 を開く
docker compose up -d --build
```

サーバーへの保存は、既定で無効。PC の中（localhost）で動かす場合だけ、環境変数で有効にできる（[docs/storage-interface.md](docs/storage-interface.md)）。

## 使用技術

| 分野 | 技術 |
|---|---|
| フロントエンド | HTML / CSS / JavaScript（フレームワークなし、ES Modules）、Web Audio API、Canvas、Pointer Events、IndexedDB、MediaRecorder |
| PWA / Android | Web App Manifest、Service Worker、Capacitor |
| バックエンド | Python、FastAPI、SQLite、uv、pytest、ruff |
| コンテナ | Docker、docker compose |
| CI/CD | GitHub Actions、GitHub Container Registry、GitHub Pages |
| クラウド・サーバー（12〜14日目） | AWS（EC2、IAM、OIDC、Systems Manager）、Ubuntu、nginx、DuckDNS、Let's Encrypt |
| セキュリティ | 脅威分析（STRIDE）、Secret scanning、Dependabot、CodeQL、Trivy、SBOM（CycloneDX）、pip-audit、OWASP ZAP、SSL Labs |
| 動画 | DaVinci Resolve、Remotion |
| 進め方 | Jira（スクラム）、Claude Code、Claude Design |

## 構成図

```mermaid
flowchart LR
    subgraph device["家族の端末（Android / PC）"]
        app["ブラウザ / PWA / Androidアプリ"]
        idb[("IndexedDB<br>絵と声は端末の中だけ")]
        app --> idb
    end
    subgraph github["GitHub"]
        repo[("リポジトリ")]
        ci["GitHub Actions<br>テスト・Trivy・SBOM"]
        pages["GitHub Pages"]
        ghcr[("GHCR<br>コンテナイメージ")]
        repo --> ci
        ci --> pages
        ci --> ghcr
    end
    subgraph pc["開発用PC"]
        dev["VS Code + Claude Code"]
        local["FastAPI + SQLite<br>localhost だけ。保存は既定で無効"]
    end
    dev -- "git push" --> repo
    pages -- "HTTPS" --> app
    app -. "localhost のときだけ" .-> local
```

AWS 版（EC2、nginx、HTTPS、OIDC と SSM による自動デプロイ）は 2026-10-24〜10-28 に動かし、14日目に片付けた。そのときの構成と片付けの記録は [docs/architecture.md](docs/architecture.md)。

## CI/CDの流れ

1. プルリクエスト：フロントとバックエンドのテスト、コンテナイメージの検査（Trivy。直し方のある CRITICAL があれば失敗）、SBOM の作成、CodeQL
2. main へのマージ：検査を通ったイメージを GHCR へ push。`frontend/` は GitHub Pages へ公開
3. （13〜14日目）OIDC で AWS のロールを引き受け、SSM Run Command で EC2 へデプロイしていた。AWS の片付けに合わせて外した

詳細は [docs/architecture.md](docs/architecture.md)。

## プライバシー方針

- 子どもが描いた絵と録音した声は、**端末の中にだけ**保存する。公開サーバーには送信しない
  - おえかきスタンプの「ほぞん」：絵をPNGにして、端末のダウンロードフォルダに保存する
  - わたしのえほん：絵と声を、ブラウザの中の保存場所（IndexedDB）に保存する
- 保護者の方へ：「ほぞん」した絵は、ふつうの画像ファイルとして端末に残る。写真アプリのクラウド同期や端末のバックアップが有効だと、端末の外にも保存される。必要に応じて、同期の設定を確認し、要らない絵は削除する
- 広告、解析、外部への通信はない
- このリポジトリと公開サイトに含まれる絵と音は、すべてサンプル（自作SVGと合成音）である
- サーバーへの保存機能は、開発者のPC内（localhost）で動かす場合にのみ有効になる

## セキュリティ

- 脆弱性の報告：[SECURITY.md](SECURITY.md)（GitHub の非公開の報告の仕組みを使う）
- 報告書：[docs/security/security-report.md](docs/security/security-report.md)。脅威 23件、対策 26件。今の CodeQL・Dependabot・Secret scanning の警告は 0件
- 脅威分析：[docs/security/threat-model.md](docs/security/threat-model.md)（データフロー図、STRIDE、ISO/SAE 21434 との対応）
- 秘密情報はリポジトリに含めない。GitHub Actions から AWS へは OIDC で接続し、アクセスキーを発行しなかった

## Claude Codeの活用方法

このプロジェクトは Claude Code と一緒に進めた。コードは Claude が書き、学習者は依頼・動作確認・判断を担当した。

- 設定の説明：[docs/claude-code-guide.md](docs/claude-code-guide.md)
- 活用ガイド（QCD別）：[docs/claude-code-playbook.md](docs/claude-code-playbook.md)
- 仕事に持ち帰るスキル・エージェント・Hook をまとめたプラグイン：[plugins/claude-dev-kit/](plugins/claude-dev-kit/)
- 紹介動画のタイトルと最後の場面は、Claude Code に Remotion のコードを書かせて作った：[video/title/](video/title/)
- 学習ログ：[docs/learning-log.md](docs/learning-log.md)

## ドキュメント

| ファイル | 内容 |
|---|---|
| [docs/plan.md](docs/plan.md) | 計画（14日間とスプリント3） |
| [docs/design.md](docs/design.md) | デザインのルールと方針 |
| [docs/architecture.md](docs/architecture.md) | 構成図、CI/CDの流れ、AWS のリソースと片付けの記録 |
| [docs/storage-interface.md](docs/storage-interface.md) | えほんの保存のインターフェース |
| [docs/security/security-report.md](docs/security/security-report.md) | セキュリティ報告書 |
| [docs/security/threat-model.md](docs/security/threat-model.md) | 脅威分析 |
| [docs/video-storyboard.md](docs/video-storyboard.md) | 紹介動画の絵コンテと編集の記録 |
| [docs/learning-log.md](docs/learning-log.md) | 毎日の学習ログ |
| [docs/glossary.md](docs/glossary.md) | 用語集 |

## 素材の出典

| 素材 | 作者・出典 | ライセンス |
|---|---|---|
| 画像（SVG） | 自作 | – |
| 音 | Web Audio APIで生成 | – |
| 紹介動画 | 自作（画面の録画、Remotion で作ったタイトル） | – |

外部の素材を使う場合は、ライセンスと再配布可否を確認してここに記載する。

## 今後の予定

スプリント3（2026-10-29〜11-04）。詳細は [docs/plan.md](docs/plan.md)。

| 日 | テーマ |
|---|---|
| 15日目 | MCP サーバーの自作と、AI エージェントのセキュリティ |
| 16日目 | コンテナイメージの署名と来歴（サプライチェーン） |
| 17日目 | C のファジングと静的解析、Rust での書き直し |
| 18日目 | ゼロトラスト（パスキーと mTLS） |
| 19日目 | 耐量子暗号（ML-KEM の TLS）と暗号の一覧 |
| 20日目 | Kubernetes（kind）で動かして守る |
| 21日目 | 最新動向の整理と振り返り |

その先の発展：OpenTofu によるインフラのコード化、CloudWatch による監視、TypeScript への移行、Kotlin でのネイティブ機能。
