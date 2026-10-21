// PostToolUse の Hook：Claude がファイルを編集した直後に、整形（Prettier）と静的解析（ESLint）をかける。
// 人や AI の注意に頼らず、毎回かならず実行するための仕組み。
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

// 終了コード2で終わると、標準エラーの文が Claude に渡る（編集はもう済んでいるので、取り消しはできない）
const FEEDBACK = 2;

const toSlash = (text) => text.replace(/\\/g, "/");

const readStdin = async () => {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
};

// 指摘がなければ null、あれば出力の文を返す
const runCommand = (command, args, cwd) => {
  try {
    execFileSync(command, args, { cwd, encoding: "utf8", stdio: "pipe" });
    return null;
  } catch (error) {
    return `${error.stdout ?? ""}${error.stderr ?? ""}`.trim() || error.message;
  }
};

// npx は Windows では .cmd で、シェルなしでは起動できない。node で本体のスクリプトを直接呼ぶ
const runTool = (root, script, args) =>
  runCommand(process.execPath, [path.join(root, "node_modules", script), ...args], root);

const main = async () => {
  const input = JSON.parse(await readStdin());
  const root = process.env.CLAUDE_PROJECT_DIR ?? input.cwd ?? process.cwd();
  const filePath = input.tool_input?.file_path;
  if (typeof filePath !== "string" || !existsSync(filePath)) return;

  const relative = toSlash(path.relative(root, filePath));
  // プロジェクトの外のファイルと、依存パッケージには手を出さない
  if (relative.startsWith("..") || path.isAbsolute(relative) || relative.startsWith("node_modules/")) return;

  const problems = [];

  // 対応していない種類のファイルと .prettierignore にあるものは、Prettier が自分で読み飛ばす
  const formatError = runTool(root, "prettier/bin/prettier.cjs", ["--write", "--ignore-unknown", filePath]);
  if (formatError !== null) problems.push(`Prettier:\n${formatError}`);

  if (/^frontend\/.*\.m?js$/.test(relative)) {
    const lintError = runTool(root, "eslint/bin/eslint.js", [filePath]);
    if (lintError !== null) problems.push(`ESLint:\n${lintError}`);
  }

  // Python は ruff で整形と静的解析をする。設定（セキュリティの S ルールを含む）は backend/pyproject.toml
  if (/^backend\/.*\.py$/.test(relative)) {
    const backend = path.join(root, "backend");
    // backend/ からの相対パスで渡す。絶対パスだと、ドライブ名の大文字・小文字の違い（c: と C:）で、
    // pyproject.toml のファイルごとの設定（テストでは assert を許す、など）が当てはまらないことがあるため
    const target = toSlash(path.relative("backend", relative));
    const formatPy = runCommand("uv", ["run", "ruff", "format", target], backend);
    if (formatPy !== null) problems.push(`ruff format:\n${formatPy}`);
    const lintPy = runCommand("uv", ["run", "ruff", "check", target], backend);
    if (lintPy !== null) problems.push(`ruff check:\n${lintPy}`);
  }

  if (problems.length > 0) {
    console.error(`${relative} に指摘があります。直してください。\n${problems.join("\n")}`);
    process.exit(FEEDBACK);
  }
};

main().catch((error) => {
  // 整形の失敗で作業を止めない。知らせるだけにする
  console.error(`format-and-lint の実行に失敗しました：${error.message}`);
  process.exit(1);
});
