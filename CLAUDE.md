# キッズあそびランド（kids-play）

4〜8歳の子ども向けミニアプリ集を、14日間で「Web → PWA → Android → Docker → AWS（HTTPS + 自動デプロイ）」まで作る個人学習プロジェクト。
詳細は別ファイルを参照する：

- 14日間の計画：@docs/plan.md
- デザインのルール：@docs/design.md
- 構成図：docs/architecture.md ／ 脅威分析：docs/security/threat-model.md
- 学習ログ：docs/learning-log.md ／ Claude Code活用ガイド：docs/claude-code-playbook.md

## 学習者について

- 車載ソフトウェア開発のエンジニア。C言語（車載ECU）、Python、過去にJava（Android）とMATLABの経験あり
- 自動車サイバーセキュリティ（ISO/SAE 21434、TARA）に詳しい
- **初心者**：Web開発、Docker、CI/CD、クラウド、サーバー構築、Jira、動画編集
- 1日4〜6時間、14日間で完了させる。業務でもClaude Codeを使うので、使い方を仕事に持ち帰りたい
- 個人を特定できる情報（氏名、勤務先、住所）はこのファイルに書かない。必要なら CLAUDE.local.md にのみ書く

## 学習の目的（どれも削らない）

Webアプリ開発（HTML/CSS/JS、FastAPI、PWA、Capacitor + Android）／Git・GitHub／CI/CD（GitHub Actions、GHCR、AWS自動デプロイ）／Jira（スクラム）／Docker／サーバー構築（Ubuntu、nginx、HTTPS）／AWS（IAM、EC2、OIDC、SSM）／DaVinci Resolve／Claude Design（デザイン→実装）／DevSecOps／Claude Codeの習熟

## 作るもの

1. どうぶつタッチ：動物をタップすると鳴き声とアニメーション
2. おとあそびピアノ：色の鍵盤をタップすると音が鳴る（Web Audio API）
3. おえかきスタンプ：指でお絵かき、スタンプ、画像として保存
4. わたしのえほん：描いた絵に声を録音し、紙芝居のように再生

トップ画面は大きなアイコンのメニュー。遊ぶ環境はWindows PC（Chrome/Edge）、Android（ブラウザ・PWA・アプリ）、AWS版（HTTPS）。

## プライバシーとセキュリティのルール（最重要・例外なし）

- 子どもの実名、顔写真、子どもが描いた絵、録音した声を、コード・README・コミット・Jira・公開サイト・AWS・動画・Claude Designに**絶対に含めない**
- えほんの絵と録音は端末内（IndexedDB）にのみ保存する。公開サーバー（GitHub Pages、AWS）には送信しない
  - サーバー保存（FastAPI）は localhost で動かす場合のみ有効。切り替えは環境変数で行い、公開環境では既定で無効（fail-safe）
- 公開版のサンプルは自作SVGと合成音のみ
- 秘密情報（AWS認証情報、SSH秘密鍵、DuckDNSトークン、.env、署名鍵）をリポジトリに入れない。設定の見本は `env.example`（先頭ドットなし）
- GitHub Actions は GitHub Secrets と OIDC を使う。AWSのアクセスキーは発行しない
- AWS：rootを日常使用しない、MFA必須、予算アラートを最初に設定、SSHは自分のIPのみ、自動デプロイはSSM
- 診断・スキャンは自分が管理するリポジトリ・サーバー・アプリにのみ行う

## 子ども向けデザインのルール（要点。詳細は docs/design.md）

- 文字に頼らない（絵・アイコン・音。文字はひらがなで最小限）
- ボタンは最小 64px 四方。縦横どちらの向きでも使える
- Pointer Events でタッチとマウスの両方に対応
- 点数・制限時間・失敗の表現なし
- 音量は控えめが既定。全画面に消音ボタン。急な大音量・激しい点滅なし
- 広告・外部リンク・外部通信なし
- どの画面からも1タップでトップに戻れる

## 素材のルール

- 画像は自作SVG、音は Web Audio API で生成
- 外部素材はライセンスと再配布可否を確認し、出典をREADMEに記載。再配布不可のものは入れない

## 技術構成

- フロント：HTML/CSS/JavaScript（フレームワークなし、ES Modules）。整形 Prettier、静的解析 ESLint
- 保存：IndexedDB。保存処理は1モジュールに集約し、インターフェースを先に決めてFastAPI版に差し替え可能にする
- バックエンド：Python + FastAPI + SQLite（uv、pytest、ruff）
- コンテナ：Docker（WSL2 + Docker Desktop）、docker compose
- CI/CD：GitHub Actions（PRでテスト → mainでイメージをビルドしGHCRへpush → OIDC + SSM Run Command でEC2にデプロイ）
- サーバー：AWS EC2（Ubuntu）+ Elastic IP + nginx、DuckDNS + Let's Encrypt
- 公開：GitHub Pages（フロント）、AWS EC2（HTTPSのフロント + FastAPIデモ）
- PWA（manifest、Service Worker）／Android：Capacitor → Android Studio → USB実機（エミュレータ不使用、Play公開なし）
- タスク管理：Jira Cloud Free（スクラム、キー KIDS）
- **設計上の注意**：パスはすべて相対パス。ミニアプリはサーバーなしで動く

## フォルダ構成

```
frontend/            フロントエンド（index.html、css/、js/、apps/<ミニアプリ>/、assets/）
backend/             FastAPI（app/、tests/）
docker/              Dockerfile、compose
server/nginx/        nginxの設定
.github/workflows/   GitHub Actions
scripts/             補助スクリプト
docs/                ドキュメント（security/ を含む）
android/             Capacitorが6日目に生成する（先に作らない）
data/ secrets/       子どものデータ／秘密情報（gitignore済み。Claudeは読めない）
```

## コーディング規約

- JavaScript：ES Modules、`const` 優先、セミコロンあり、2スペース。`innerHTML` を使わず `textContent` と `createElement` を使う。イベントは Pointer Events
- CSS：色・余白・大きさは CSS カスタムプロパティ（デザイントークン）で定義。単位は `rem` と `clamp()` を基本にする
- Python：型ヒント必須、入力は Pydantic で検証、ruff に従う
- コメントは「なぜ」を書く。画面に出す文字はひらがな
- 外部CDN・外部フォント・解析タグを読み込まない
- テスト：バックエンドは pytest。テストを先に書く（8日目以降）

## Git / Jira のルール

- ブランチ：`<種別>/KIDS-<番号>-<短い説明>` 例：`feature/KIDS-12-animal-touch`（種別：feature / fix / docs / chore / ci）
- コミット：`KIDS-<番号> <種別>: <要約>` 例：`KIDS-12 feat: どうぶつタッチの鳴き声を追加`
- mainに直接コミットしない（1日目の初回コミットを除く）。ブランチ → PR → レビュー → マージ
- 変更は小さく。1つのPRは1つの課題

## よく使うコマンド（Windows PowerShell）

```powershell
python -m http.server 8000 --directory frontend   # フロントをローカルで確認（3日目〜）
npx prettier --check . ; npx eslint frontend       # 整形と静的解析（導入後）
uv run pytest ; uv run ruff check .                # バックエンドのテストと静的解析（10日目〜）
docker compose up -d ; docker compose logs -f      # コンテナ起動とログ（11日目〜）
```

カスタムコマンド：`/start-day` `/end-day` `/review` `/explain` `/commit` `/qcd` `/design-prompt` `/sec-check` `/whats-new`（説明は docs/claude-code-guide.md）

## 環境と制約

- Windows 11、メモリ16GB。10日目まではWindows（PowerShell）で開発。コマンドはPowerShell用で示す
- WSL・サーバー上のコマンドはbash用で示し、**どこで実行するか**を必ず明記する
- WSL2は `.wslconfig` でメモリ上限を設定。Docker Desktopは使うときだけ起動
- 無料のツール・サービスのみ。有料になりうる操作（AWSなど）は事前に料金条件を説明して確認を取る
- インストールや大きなダウンロードは、容量の目安を伝えて確認を取る
- JDK：システムはJDK 26。Androidのビルドは Android Studio 同梱のJBRを使う

## 学習の進め方（Claudeへのお願い）

- 回答は日本語で簡潔に
- 毎日の最初に「今日のゴール、完了条件、今日のClaude Code機能、今日のセキュリティ作業」、最後に「進捗（計画どおり／遅れ）と翌日の予定」を示す
- 実装の前に「何を・なぜ・どの順で」を示し、確認を取ってから進める
- 新しい概念は、C言語・MATLAB・Java（Android）・車載ソフト開発に例えて短く説明する。セキュリティはISO/SAE 21434、UN-R155、TARAと対比する
- 学習効果が高い部分はヒントを出して学習者に書かせ、書いたコードは理由つきでレビューする。定型部分（設定ファイル、見た目、SVG素材）はClaudeが書いてよい
- サーバー・AWS・CI/CDのコマンドと設定は、各行の意味を1行で説明する
- 作業は小さく区切り、区切りごとに「完了したこと／次にやること」を3行でまとめる
- パッケージのインストール、git push、AWS・Jira・DuckDNSなど外部サービスの操作は、実行前に必ず確認を取る
- エラーは、原因の仮説と確認方法を示してから修正する
- 遅れが出たら、docs/plan.md の「発展」や各日の仕上げから削る案を出して確認を取る。学習の目的は削らない
- 手順や画面操作を案内する前に、その技術・サービスの最新仕様を公式情報で確認する（記憶だけで案内しない）。確認できなかった場合は、その旨を先に伝える
- Claude Codeの機能説明は公式ドキュメント（https://code.claude.com/docs）に基づく。費用が発生しうる機能は事前に確認を取る

## QCDの観点（使い方に改善点があればその場で短く指摘する）

- **Q**：Planモードで計画 → 実装、テストを先に書く、Hooksで整形と静的解析、レビュー用サブエージェント、変更は小さく
- **C**：切れ目で `/clear`、長い作業は `/compact`、`/context` と `/usage` で確認、調査はサブエージェントへ、繰り返す指示はスキルやコマンドにする
- **D**：git worktree と複数セッション、バックグラウンド実行、`claude -p`、カスタムコマンドとスキル
