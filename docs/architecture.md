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

    subgraph AWS["AWS（東京リージョン）"]
        ec2["EC2（Ubuntu 24.04、t3.micro）+ Elastic IP<br>SG：SSH は自分のIPだけ、HTTP 80<br>ufw、SSH は kidsops の鍵だけ"]
        nginx["web コンテナ（nginx）<br>80 → 8080。フロントエンドを配信<br>HTTPS は ⬜13日目"]
        api["api コンテナ（FastAPI）<br>外に出さない。アップロードAPIは無効"]
        ec2 --> nginx
        nginx -- "/api/ は読む要求だけ" --> api
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
    ghcr -- "docker compose pull（公開イメージ）" --> ec2
    dev -- "SSH（12日目の構築）" --> ec2
    pages -- "HTTPS" --> browser
    nginx -- "12日目は HTTP。⬜13日目に HTTPS（DuckDNS + Let's Encrypt）" --> browser
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
| ローカルのフロントエンド | ✅ | 2日目 | トップ画面とどうぶつタッチ。`python -m http.server` で確認 |
| GitHub Pages | ✅ | 5日目 | |
| PWA | ✅ | 5日目 | |
| Androidアプリ | ✅ | 6日目 | |
| FastAPI（localhost） | ✅ | 10日目 | 127.0.0.1:8000。サーバー保存は既定で無効 |
| Docker / compose | ✅ | 11日目 | WSL2（Ubuntu 24.04）＋ Docker Desktop。`docker compose up -d --build` で 127.0.0.1:8080。web（nginx）と api（FastAPI）、どちらも root 以外。サーバー保存は無効 |
| CI（GitHub Actions、GHCR） | ✅ | 11日目 | `.github/workflows/ci.yml`。PR でテストとイメージの検査（Trivy で CRITICAL なら失敗、SBOM を成果物に）。main で GHCR へ push（公開。`ghcr.io/hayato-f110/kids-play-api`・`kids-play-web`、タグは `main` と `sha-<コミット>`） |
| EC2 + nginx（HTTP） | ✅ | 12日目 | Ubuntu 24.04、t3.micro（クレジット仕様は標準）。`server/compose.yaml` で GHCR のイメージを起動（web だけ 80 で外に出す）。ログは journald（14日・200MB、ファイルは1日ごとに切り替え。`server/journald/`）。`/opt/kids-play` には `compose.yaml` だけを置く。ハードニングは docs/security/threat-model.md の C-15 |
| HTTPS（DuckDNS + Let's Encrypt） | ✅ → 終了 | 13日目 | 14日目に DuckDNS のドメインを削除 |
| CD（OIDC + SSM） | ✅ → 終了 | 13日目 | 14日目に CI から deploy を外し（#76）、ロールと OIDC プロバイダーを削除 |
| AWS 版の全体 | 終了 | 14日目 | 2026-10-28 に片付けた。公開の入口は GitHub Pages だけ。手順は threat-model.md の C-26 |

## AWSのリソース一覧（12日目から記入。14日目の後片付けの確認に使う）

IDやIPアドレスなど、公開したくない値は書かない（種類と個数だけ書く）。

アカウントは無料プラン（2026-10-23 作成。$100 のクレジット、6か月で自動で閉じる。請求は起こらない）。料金はクレジットから引かれる。

| リソース | 個数 | 料金が発生する条件 | 削除済み |
|---|---|---|---|
| EC2 インスタンス（t3.micro、東京） | 1 | 動いている間（$0.0136／時間）。止めれば止まる | ✅ 10/28 終了 |
| EBS ボリューム（gp3 10GiB、暗号化） | 1 | あるだけでかかる（インスタンスを止めてもかかる）。インスタンスを終了すると一緒に消える設定 | ✅ 10/28（終了とともに消えたことをボリュームの一覧で確認） |
| Elastic IP | 1 | あるだけでかかる（$0.005／時間。つないでいなくても同じ）。インスタンスを消しても残るので、別に解放する | ✅ 10/28 解放（DuckDNS の名前を先に消してから） |
| セキュリティグループ（kids-play-sg） | 1 | かからない | ✅ 10/28 |
| キーペア（kids-play-ec2、ED25519） | 1 | かからない。秘密鍵は PC の `~/.ssh` にだけある | ✅ 10/28（AWS 側だけ。PC の秘密鍵は学習者が判断） |
| SSM の命令書（KidsPlayDeploy） | 1 | かからない | ✅ 10/28 |
| IAM ロール（kids-play-ec2-ssm、kids-play-github-deploy） | 2 | かからない | ✅ 10/28（自分で作ったポリシーはなし。インラインはロールとともに削除） |
| IAM の ID プロバイダー（token.actions.githubusercontent.com） | 1 | かからない | ✅ 10/28 |
| DuckDNS のドメイン、リポジトリの秘密の設定値（2つ） | 1・2 | かからない | ✅ 10/28 |
| AWS Budgets（ゼロ支出、月 $15） | 2 | かからない（通知だけの予算） | 残す |
| IAM ユーザー（kids-admin、MFA あり、アクセスキーなし）とグループ（admins） | 1・1 | かからない | 残す（発展で使う） |

14日目の確認：10月の請求は USD 0.00（無料プランのクレジットから約 $2.20）。クレジットの残りは $137.81、期限は 2027-04-23。EC2 のグローバルビューで、全リージョンのボリューム・Elastic IP・S3 バケットが0。
