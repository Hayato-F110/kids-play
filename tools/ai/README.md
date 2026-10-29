# tools/ai：大人の開発者が PC で使う AI の道具

15日目（KIDS-60）に作った学習用の道具。**子ども向けの画面（`frontend/`）には組み込まない。** 理由は2つ。

- 子どもの絵・声・入力を、外部の AI に送らない（CLAUDE.md の決まり、脅威 T-24）
- Gemini API の利用規約が、18歳未満が使う、または使いそうなアプリへの組み込みを禁じている（2026-10-29 に確認）

公開物にも Docker のイメージにも入らない（`.dockerignore` は許可リスト）。脅威と対策は [docs/security/threat-model.md](../../docs/security/threat-model.md) の T-24〜T-26、試験の結果は [docs/security/ai-injection.md](../../docs/security/ai-injection.md)。

| ファイル | 中身 | 外への通信 |
|---|---|---|
| `docs_mcp.py` | `docs/` の `.md` を読むだけの MCP サーバー（`.mcp.json` の `kids-docs`） | なし |
| `rag.py` | 公開文書に答える RAG | Gemini API |
| `evals.py` | RAG の自動採点（インジェクションの試験つき） | Gemini API |

## 準備

1. Google AI Studio で API キーを作り、「Restrict to Gemini API only」で制限する。請求先は設定しない（無料枠。上限を超えると 429 のエラーになり、料金は発生しない）
2. このフォルダーに `.env`（Git の外）を作り、`GEMINI_API_KEY=...` の1行を書く。キーは会話・画面・コミットに出さない
3. `uv sync`

無料枠では、送った内容が Google のサービスの改善に使われ、人が読むこともある。送るのは、Git で管理された公開済みの文書（`docs/` の `.md` と `README.md`）だけにしている。質問の欄にも、個人の情報や会社の情報を書かない。

## 使い方（PowerShell。このフォルダーで実行）

```powershell
uv run python rag.py "えほんの絵と録音はどこに保存されますか？"   # 質問する（初回は埋め込みに数分）
uv run python rag.py "質問" --no-defense                          # 対策なしの形と比べる
uv run python evals.py                                            # 採点する（数分。詳細は .cache/）
uv run pytest ; uv run ruff check .                               # 通信しない試験と静的解析
```
