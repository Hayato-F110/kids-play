// main との差分を Claude Code のヘッドレス実行（claude -p）に渡し、プライバシーと秘密情報のルールに反していないかを確かめる。
// 使い方：npm run check:ai-privacy（指摘があれば終了コード1）
//
// 決まった頼みごとを、会話を開かずに1コマンドで回すための例（10日目、KIDS-35）。
// - 差分は標準入力で渡す。Claude に git や Bash の権限を渡さずに済む
// - --permission-mode dontAsk：許可が必要な操作はすべて断る（読むだけの確認にする）
// - --json-schema：結果を決めた形で受け取り、スクリプトで判定できるようにする
// 使用量はサブスクリプションの枠から引かれる。CI では動かさず、PR の前に手で回す
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const base = process.argv[2] ?? "origin/main";

const SCHEMA = {
  type: "object",
  properties: {
    findings: {
      type: "array",
      items: {
        type: "object",
        properties: {
          file: { type: "string" },
          line: { type: "integer" },
          rule: { type: "string" },
          detail: { type: "string" },
        },
        required: ["file", "rule", "detail"],
      },
    },
  },
  required: ["findings"],
};

const PROMPT = `あなたはプライバシーの確認担当です。標準入力は git の差分です。次のルールに反する追加だけを、findings に挙げてください。
ルールに反していなければ、findings は空の配列にします。推測や一般的な助言は挙げません。
1. 子どもの実名、顔写真、子どもが描いた絵、録音した声が、コード・文書・テストデータに含まれている
2. 秘密情報（AWS の認証情報、SSH 秘密鍵、トークン、パスワード、.env の中身、署名鍵）が含まれている
3. 子どもの絵や声を、公開サーバー（GitHub Pages、AWS）や外部の宛先に送る処理が、既定で有効になっている
4. 外部の CDN、外部フォント、解析タグ、広告を読み込んでいる
rule にはルールの番号、detail には日本語で1文の理由を書きます。`;

// --stdin のときは、標準入力の差分を見る（例：git diff --cached | node scripts/ai-privacy-check.mjs --stdin）
const diff =
  base === "--stdin"
    ? readFileSync(0, "utf8")
    : execFileSync("git", ["diff", `${base}...HEAD`], { encoding: "utf8", maxBuffer: 20 * 1024 * 1024 });
if (diff.trim() === "") {
  console.log(`${base} との差分がない`);
  process.exit(0);
}

// シェルを通さずに呼ぶ（claude は claude.exe）。プロンプトの改行や引用符が、シェルに解釈されて壊れないようにするため
const run = spawnSync(
  "claude",
  [
    "-p",
    PROMPT,
    "--output-format",
    "json",
    "--json-schema",
    JSON.stringify(SCHEMA),
    "--permission-mode",
    "dontAsk",
  ],
  { input: diff, encoding: "utf8", maxBuffer: 20 * 1024 * 1024 },
);
if (run.status !== 0) {
  console.error(`claude -p が失敗した（終了コード ${run.status}）\n${run.stderr || run.stdout}`);
  process.exit(2);
}

const output = JSON.parse(run.stdout);
if (!output.structured_output) {
  console.error(`決めた形の結果が返らなかった：\n${output.result}`);
  process.exit(2);
}
const { findings } = output.structured_output;
for (const item of findings) {
  console.log(`${item.file}${item.line ? `:${item.line}` : ""}  ルール${item.rule}  ${item.detail}`);
}
console.log(findings.length === 0 ? "OK  指摘なし" : `指摘 ${findings.length} 件`);
process.exit(findings.length === 0 ? 0 : 1);
