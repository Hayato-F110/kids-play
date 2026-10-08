# キッズあそびランド（kids-play）

4〜8歳の子ども向けミニアプリ集。Web、PWA、Androidアプリ、HTTPS化したAWS版で遊べる。
14日間の個人学習プロジェクトとして、Web開発からCI/CD、クラウド、セキュリティまでを一通り体験する。

> 状態：開発中（1日目／14日）

## ミニアプリ

| | なまえ | 内容 |
|---|---|---|
| 1 | どうぶつタッチ | 動物をタップすると鳴き声とアニメーション |
| 2 | おとあそびピアノ | 色の鍵盤をタップすると音が鳴る |
| 3 | おえかきスタンプ | 指でお絵かき、スタンプ、画像として保存 |
| 4 | わたしのえほん | 描いた絵に声を録音し、紙芝居のように再生 |

## スクリーンショット

（5日目以降に追加。サンプルデータのみを使う）

## 紹介動画

（14日目に追加）

## 遊び方

| 環境 | 方法 |
|---|---|
| Web（GitHub Pages） | （5日目にURLを追加） |
| PWA | 上のURLをAndroidのChromeで開き、「ホーム画面に追加」 |
| Androidアプリ | Android Studioでビルドし、USBデバッグで実機にインストール（Google Playでは配布しない） |
| AWS版（HTTPS） | （13日目に追加。学習後に停止する場合がある） |
| ローカル | （2日目に手順を追加） |

## 使用技術

| 分野 | 技術 |
|---|---|
| フロントエンド | HTML / CSS / JavaScript（フレームワークなし、ES Modules）、Web Audio API、Canvas、Pointer Events、IndexedDB、MediaRecorder |
| PWA / Android | Web App Manifest、Service Worker、Capacitor |
| バックエンド | Python、FastAPI、SQLite、uv、pytest、ruff |
| コンテナ | Docker、docker compose |
| CI/CD | GitHub Actions、GitHub Container Registry、GitHub Pages |
| クラウド・サーバー | AWS（EC2、IAM、OIDC、Systems Manager）、Ubuntu、nginx、DuckDNS、Let's Encrypt |
| セキュリティ | 脅威分析（STRIDE）、Secret scanning、Dependabot、CodeQL、Trivy、SBOM（CycloneDX）、pip-audit、OWASP ZAP |
| 進め方 | Jira（スクラム）、Claude Code、Claude Design |

## 構成図

詳細は [docs/architecture.md](docs/architecture.md)。（各日の作業に合わせて更新）

## CI/CDの流れ

プルリクエストでテスト → mainへのマージでDockerイメージをビルドしてGHCRへpush → OIDCとSSMでEC2へデプロイ。
詳細は [docs/architecture.md](docs/architecture.md)。（11〜13日目に構築）

## プライバシー方針

- 子どもが描いた絵と録音した声は、**端末の中（IndexedDB）にだけ**保存する。公開サーバーには送信しない
- 広告、解析、外部への通信はない
- このリポジトリと公開サイトに含まれる絵と音は、すべてサンプル（自作SVGと合成音）である
- サーバーへの保存機能は、開発者のPC内（localhost）で動かす場合にのみ有効になる

## セキュリティ

- 脅威分析：[docs/security/threat-model.md](docs/security/threat-model.md)
- 報告書：[docs/security/security-report.md](docs/security/security-report.md)
- 秘密情報はリポジトリに含めない。GitHub ActionsからAWSへはOIDCで接続し、アクセスキーを発行しない

## Claude Codeの活用方法

このプロジェクトは Claude Code と一緒に進めている。

- 設定の説明：[docs/claude-code-guide.md](docs/claude-code-guide.md)
- 活用ガイド（QCD別）：[docs/claude-code-playbook.md](docs/claude-code-playbook.md)
- 学習ログ：[docs/learning-log.md](docs/learning-log.md)

## ドキュメント

| ファイル | 内容 |
|---|---|
| [docs/plan.md](docs/plan.md) | 14日間の計画 |
| [docs/design.md](docs/design.md) | デザインのルールと方針 |
| [docs/architecture.md](docs/architecture.md) | 構成図とCI/CDの流れ |
| [docs/video-storyboard.md](docs/video-storyboard.md) | 紹介動画の絵コンテ |

## 素材の出典

| 素材 | 作者・出典 | ライセンス |
|---|---|---|
| 画像（SVG） | 自作 | – |
| 音 | Web Audio APIで生成 | – |

外部の素材を使う場合は、ライセンスと再配布可否を確認してここに記載する。

## 今後の予定

- Terraformによるインフラのコード化
- CloudWatchによる監視とアラート
- 独自ドメインと Route 53
- TypeScriptへの移行、Kotlinでのネイティブ機能
