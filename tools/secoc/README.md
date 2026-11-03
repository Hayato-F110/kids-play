# SecOC の模擬（学習用）

AUTOSAR SecOC の「考え方」だけを Python で真似た小さな模擬です。AUTOSAR の実装ではありません。
MAC（なりすまし・改ざんの検知）とフレッシュネス（再送の検知）が、層をたどって動くようすをログで見られます。

## 層（上から下へ）

SecOC -> CSM -> CryIf -> CryptoDriver（AES-128 CMAC）。ほかに FVM（フレッシュネス管理）があります。

- PDU の形：ペイロード、フレッシュネス（下位 8 ビット）、MAC（先頭 24 ビット）
- MAC は「Data ID、ペイロード、完全なフレッシュネス」にかけます
- 受信側は下位 8 ビットから完全な値を復元し、窓の外（古い値・再送）なら捨てます
- 検証がすべて通ったあとにだけカウンタを進めます

## 使い方（PowerShell、tools/secoc で）

```powershell
uv sync
uv run python -m secoc_sim.demo   # 正常・改ざん・再送のデモ
uv run pytest                     # テスト
uv run ruff check . ; uv run ruff format --check .
```

## 注意

- 鍵はテストとデモの中の固定値だけです。ファイルには保存しません
- 実車の SecOC とは、鍵管理・エラー処理・タイミングなどが大きく違います
