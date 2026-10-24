# claude-dev-kit（Claude Code のプラグイン）

キッズあそびランドの学習（13日目、KIDS-45）で作った、Claude Code の使い方の道具から、ほかのプロジェクトや仕事に持ち帰れるものを抜き出して、1つのプラグインにまとめたもの。

## 入っているもの

| 種類 | 名前 | 使い方 | 何をするか |
|---|---|---|---|
| スキル | review | `/claude-dev-kit:review [範囲]` | 直前の変更を、良い点・改善点・ルール・プライバシーの順にレビューする |
| スキル | sec-check | `/claude-dev-kit:sec-check` | 秘密情報、個人データ、危険なコード、依存関係を確認し、表にする |
| スキル | explain | `/claude-dev-kit:explain <対象>` | C言語・MATLAB・Java・組み込み開発との比較で説明する |
| スキル | qcd | `/claude-dev-kit:qcd` | このセッションの使い方を QCD で振り返る |
| スキル | commit | `/claude-dev-kit:commit [課題キー]` | 変更を確かめ、課題キー付きのメッセージを提案し、確認を取ってからコミットする |
| スキル | whats-new | `/claude-dev-kit:whats-new` | 公式の変更履歴から、新機能を3つ紹介する |
| サブエージェント | privacy-reviewer | 「claude-dev-kit:privacy-reviewer でレビューして」 | 個人データ、秘密情報、通信、保存、CI の権限を、読むだけで確かめる |
| Hook | protect-secrets | 自動（PreToolUse） | 環境変数のファイル、鍵、`.ssh`、`.aws`、`secrets/`・`data/` へのアクセスを止める |

- スキルは、Claude が勝手に動かさない（`disable-model-invocation: true`）。自分で呼んだときだけ動く。自動で呼べるスキルは、名前と説明が毎回の会話に入り、使用量が増えるため
- 整形の Hook（Prettier、ESLint、ruff）は、フォルダ構成に依存するので入れていない。プロジェクトごとに `.claude/settings.json` で設定する

## 試し方（このリポジトリのフォルダで）

```powershell
claude plugin validate plugins/claude-dev-kit       # 形が正しいかを確かめる（Validation passed）
claude --plugin-dir plugins/claude-dev-kit          # このセッションだけ読み込む
```

- このリポジトリでは、同じ Hook が `.claude/settings.json` にもあるので、読み込むと Hook が2回動く（動きは同じで、害はない）。ほかのプロジェクトで使うときは1回になる
- 守るフォルダを変えるときは、`hooks/protect-secrets.mjs` の `PROTECTED_DIRS` を直す

## 仕事で使うときの注意

- プラグインは、読み込んだ人の権限で動く。入れる前に中身（特に Hook）を読む
- 会社のセキュリティ規程で、外部のツールや AI に渡してよいコードの範囲を確かめる
- Hook の判定は、コマンドの文字列を見るだけなので完全ではない。deny の設定と組み合わせる
