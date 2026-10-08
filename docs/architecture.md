# 構成

雛形。各日の作業で実態に合わせて更新する（⬜＝未構築）。

## 動かす場所の全体像

```mermaid
flowchart LR
    subgraph PC["Windows PC（開発・ローカル）"]
        dev["VS Code + Claude Code"]
        localfe["フロントエンド<br>localhost"]
        localapi["FastAPI + SQLite<br>localhost のみ保存可"]
        localfe -. "サーバー保存<br>（PC内のみ）" .-> localapi
    end

    subgraph GH["GitHub"]
        repo["リポジトリ kids-play"]
        actions["GitHub Actions"]
        pages["GitHub Pages<br>フロントのみ"]
        ghcr["GHCR<br>Dockerイメージ"]
    end

    subgraph AWS["AWS"]
        ec2["EC2（Ubuntu）+ Elastic IP"]
        nginx["nginx<br>HTTPS・リバースプロキシ"]
        fe["フロントエンド（コンテナ）"]
        api["FastAPIデモ（コンテナ）<br>アップロードAPIは無効"]
        nginx --> fe
        nginx --> api
    end

    subgraph Device["家族のAndroid端末"]
        browser["ブラウザ / PWA"]
        app["Androidアプリ（Capacitor）"]
        idb[("IndexedDB<br>絵と録音は端末内のみ")]
        browser --> idb
        app --> idb
    end

    dev -- "git push" --> repo
    repo --> actions
    actions --> pages
    actions --> ghcr
    actions -- "OIDC + SSM" --> ec2
    ghcr -- "docker compose pull" --> ec2
    pages -- "HTTPS" --> browser
    nginx -- "HTTPS（DuckDNS + Let's Encrypt）" --> browser
    dev -- "USB（adb）" --> app
```

## データの置き場所（プライバシーの要点）

| 環境 | 絵と録音の保存先 | サーバーへの送信 |
|---|---|---|
| PC（localhost） | IndexedDB、または設定でFastAPI + SQLite | PC内のみ |
| GitHub Pages | IndexedDB（端末内） | なし |
| Androidアプリ / PWA | IndexedDB（端末内） | なし |
| AWS版 | IndexedDB（端末内） | なし（アップロードAPIは無効） |

保存先の切り替えは環境変数で行い、既定は「サーバー保存なし」とする（設定を忘れても安全側に倒れる）。

## CI/CDの流れ

```mermaid
flowchart TD
    A["ブランチで作業<br>feature/KIDS-xx-..."] --> B["プルリクエスト"]
    B --> C["CI：整形・静的解析・pytest"]
    C --> D{"成功？"}
    D -- "いいえ" --> A
    D -- "はい" --> E["レビュー → mainへマージ"]
    E --> F["Dockerイメージをビルド"]
    F --> G["Trivyでスキャン・SBOM生成"]
    G --> H["GHCRへpush"]
    H --> I["OIDCでAWSのIAMロールを引き受ける<br>（アクセスキーなし）"]
    I --> J["SSM Run Command"]
    J --> K["EC2：docker compose pull && up -d"]
    E --> P["GitHub Pagesへ公開"]
```

## 構築の状況

| 要素 | 状態 | 構築日 | メモ |
|---|---|---|---|
| ローカルのフロントエンド | ⬜ | 2日目 | |
| GitHub Pages | ⬜ | 5日目 | |
| PWA | ⬜ | 5日目 | |
| Androidアプリ | ⬜ | 6日目 | |
| FastAPI（localhost） | ⬜ | 10日目 | |
| Docker / compose | ⬜ | 11日目 | |
| CI（GitHub Actions、GHCR） | ⬜ | 11日目 | |
| EC2 + nginx（HTTP） | ⬜ | 12日目 | |
| HTTPS（DuckDNS + Let's Encrypt） | ⬜ | 13日目 | |
| CD（OIDC + SSM） | ⬜ | 13日目 | |

## AWSのリソース一覧（12日目から記入。14日目の後片付けの確認に使う）

IDやIPアドレスなど、公開したくない値は書かない（種類と個数だけ書く）。

| リソース | 個数 | 料金が発生する条件 | 削除済み |
|---|---|---|---|
| | | | |
