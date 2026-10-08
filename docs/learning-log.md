# 学習ログ

毎日 `/end-day` で追記する。子どもの実名・写真・絵・録音、秘密情報、個人を特定できる情報は書かない。

## テンプレート

```markdown
## N日目（YYYY-MM-DD）

- 進捗：計画どおり ／ 遅れ（何が、どれくらい）
- 作業時間：約 h

### やったこと

-

### 学んだこと3行

1.
2.
3.

### つまずいたこと（原因と解決）

-

### Claude Code活用メモ（QCD）

- Q：
- C：
- D：

### 次にやること

-
```

---

## 1日目（2026-10-08）

- 進捗：計画どおり
- 作業時間：約3時間

### やったこと

- 環境確認（git、python、node、java、adb、code、claude はあり。uv をインストール。wsl は11日目に導入）
- Gitの設定（user.name、noreplyメール、core.autocrlf=false、init.defaultBranch=main）
- Claude Codeのプロジェクト設定（CLAUDE.md、CLAUDE.local.md、.claude/settings.json、カスタムコマンド9個）
- 土台ファイル（docs一式、README、.gitignore、.gitattributes、フォルダ構成）と最初のコミット
- SSH鍵（ed25519、パスフレーズあり）の作成、GitHubへの登録、リポジトリ kids-play への push、ssh-agent の設定
- GitHubの Secret Protection と Push protection が有効であることを確認。コミットのメールを非公開にする設定（Emails）を有効化
- /memory と /permissions で、CLAUDE.md と権限設定が読み込まれていることを確認
- Jira：スペース KIDS（スクラム、企業管理対象）の作成、作業項目の手動作成、CSVで49件をインポート、スプリント1を開始
- GitHub for Atlassian で Jira と kids-play を連携（対象は kids-play のみ）
- /release-notes をターミナル版で実行、/end-day を初めて使用

### 学んだこと3行

1. Gitは「commit（PC内に記録）」と「push（GitHubに送る）」が別。SVNのコミットは、この2つを合わせたものに当たる
2. Git（道具）、コミット（記録）、GitHub（置き場所）、SSH（通り道）は別々の役割。公開鍵だけを渡し、秘密鍵はパスフレーズで守る
3. 秘密情報は .gitignore、Claude Codeのdeny、Push protection の3段で守る。外部連携は必要なリポジトリだけに絞る（最小権限）

### つまずいたこと（原因と解決）

- スクリーンショットを撮ると、クリップボードの公開鍵が画像に置き換わる → コピーし直してから貼り付けた
- GitHubには「アカウントのSettings」と「リポジトリのSettings」がある → URLで見分ける
- Jiraのサイトが長期間未使用で無効化されていた → 請求の管理画面から再開し、数分で復旧した
- Jiraの用語が「プロジェクト」から「スペース」に変わっていた。古い記憶での案内は外れることがあるので、公式情報を確認してから進める
- CSVインポートでは、スプリントを名前で指定できない（数字のIDが必要）→ 取り込み後にバックログからまとめて移動した
- /release-notes は VS Code拡張のパネルでは使えない → ターミナルで claude を起動して実行した

### Claude Code活用メモ（QCD）

- Q：実装（ファイル作成）の前に、権限設定の案と進め方を確認してから進めた。画面が変わりやすい外部サービスは、公式情報を調べてから案内してもらう
- C：1つの会話が長くなった。明日は新しいセッションで /start-day から始める（前提は CLAUDE.md にある）
- D：定型の指示をカスタムコマンドにした。画面で迷ったらスクリーンショットを貼ると、説明より早い

### 次にやること

- 2日目：/start-day → 企画とバックログ整理 → Claude Designでデザインシステムとプロトタイプ → 脅威分析の初版 → トップ画面とどうぶつタッチ → 最初のPR
- 新しい会話で、カスタムコマンドが入力候補に出るかを確認する
