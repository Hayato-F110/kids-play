---
name: kids-svg
description: キッズあそびランドの作風（太い線、丸い形、デザイントークンの色）で、子ども向けのSVG素材を作る。スタンプ、アイコン、動物などの絵を追加するときに使う
argument-hint: [作りたいもの（例：はな おひさま）]
---

「$ARGUMENTS」のSVG素材を、このプロジェクトの作風で作ってください。複数あるときは、1つずつ作ります。
何を作るかが書かれていない場合は、作りたいものを質問してください。

## 作風の決まり（docs/design.md の「アイコンとイラストの作風」）

- viewBox は `0 0 200 200`。絵は中央に置き、端から 16 以上あける（線が切れないようにするため）
- 線は `#23324a`（--color-text）の太さ 6。細い線は 5。`stroke-linecap="round"` と `stroke-linejoin="round"` で、先と角を丸くする
- 形は、円・だ円・角丸の四角・なめらかな曲線の組み合わせ。細かい模様、グラデーション、ぼかし、影は使わない
- 塗りは、frontend/css/tokens.css にある色だけを使う。作る前に tokens.css を読み、値を確かめる
  - 白い面は --color-surface、黒い部分（目など）は --color-text
  - ほっぺ、耳の内側は --color-accent-2
  - 鍵盤の色（--color-key-1〜8）は、鍵盤の面以外に使わない
- 顔を描くときは、やさしい表情にする。目は黒い丸（半径 7 前後）、口は上向きの曲線
- 1つの絵は、図形 12 個以内を目安にする（小さく表示しても形が分かるようにするため）
- 文字は入れない。写真、外部の画像、外部のフォントは使わない
- こわい表現、失敗や禁止を表す絵（×印、赤い警告）は描かない

## 出力の形（使う場所で選ぶ）

どちらにするか分からないときは質問する。

### A. 単独のファイル（キャンバスに描くスタンプ、PWAのアイコンなど）

- 置き場所：`frontend/assets/<種類>/<名前>.svg`（例：`frontend/assets/stamps/star.svg`）。名前は英語の小文字とハイフン
- 単独のファイルでは CSS の変数が使えないので、色は tokens.css の値（16進数）を直接書く
- ルートの `<svg>` に、線の指定をまとめて書く

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" fill="none" stroke="#23324a" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
  <path fill="#ffb23e" d="…" />
</svg>
```

### B. HTMLの中の `<symbol>`（画面に並べる絵。どうぶつタッチの動物など）

- 見本：`frontend/apps/animals/index.html` の `<symbol id="animal-dog">`
- 色は直接書かず、class で塗り分ける（`art-white`、`art-ink`、`art-yellow`、`art-pink`、`art-green`、`art-cheek`、`art-thin`）。定義は `frontend/apps/animals/animals.css`
- 足りない色の class が必要なときは、勝手に足さず、先に相談する

## 守ること（セキュリティとプライバシー）

- SVGの中に `<script>`、`on…` で始まる属性、`<foreignObject>`、外部を指す `href` や `xlink:href` を入れない
- 子どもの名前、顔、描いた絵を元にしない。素材はすべて自作する
- 既存のキャラクターやロゴに似せない（再配布できる素材だけを入れる）

## 作ったあとの確認

1. ファイルを読み直し、上の決まりに合っているかを確かめる（viewBox、線の太さ、色が tokens.css にあるか、禁止の要素がないか）
2. 何を作り、どの色を使ったかを、1素材につき1〜2行で報告する
3. 見た目を確かめる。Edge を画面なしで動かし、作った素材を1枚の画像にまとめて書き出し、読み込んで形と色を見る（画像は小さくし、リポジトリの外の一時フォルダに置く）。崩れていれば直す
4. 確かめられなかったときは、その旨を伝え、「ブラウザでファイルを開いて確認してください」と頼む。確認用のURLは `http://localhost:8000/assets/<種類>/<名前>.svg`
