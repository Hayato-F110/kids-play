// PreToolUse の Hook：秘密情報と個人データへのアクセスを、ツールの実行前に止める。
// 権限設定の deny は Read だけが対象なので、書き込みとコマンド経由の読み取りをここで補う。
// コマンドの文字列での判定は完全ではない（変数で組み立てたパスは見抜けない）。deny 設定と併用する。
// 元は キッズあそびランドの .claude/hooks/protect-secrets.mjs。守るフォルダは PROTECTED_DIRS で変える
import { homedir } from "node:os";
import path from "node:path";

// 終了コード2で終わると、Claude Code はツールの実行を止め、標準エラーの文を Claude に渡す
const BLOCK = 2;

// プロジェクトの直下で、Claude に触らせないフォルダ（秘密情報と個人データの置き場所）
const PROTECTED_DIRS = /^(secrets|data|backend\/data)(\/|$)/;

const toSlash = (text) => text.replace(/\\/g, "/");

const readStdin = async () => {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
};

// 守る対象なら理由を返し、そうでなければ null を返す
const findReason = (pathLike, cwd, root) => {
  const expanded = toSlash(pathLike).replace(/^~(?=\/|$)/, toSlash(homedir()));
  // Windows はファイル名の大文字と小文字を区別しないので、小文字にそろえて比べる
  const absolute = toSlash(path.resolve(cwd, expanded)).toLowerCase();
  const segments = absolute.split("/");
  const base = segments.at(-1);

  // env.example（先頭ドットなし）は設定の見本なので通す
  if (base === ".env" || base.startsWith(".env.")) return "環境変数のファイル（.env）";
  if (/\.(pem|key|jks|keystore)$/.test(base)) return "鍵のファイル";
  if (segments.includes(".ssh") || segments.includes(".aws")) return "SSH・AWSの認証情報";

  const relative = toSlash(path.relative(root, path.resolve(cwd, expanded))).toLowerCase();
  if (PROTECTED_DIRS.test(relative)) return "秘密情報・個人データのフォルダ";
  return null;
};

// ツールごとに、パスとして調べる文字列を取り出す
const collectCandidates = (toolName, toolInput) => {
  if (toolName === "Bash" || toolName === "PowerShell") {
    // 引用符や区切り記号で分け、1語ずつパスとして調べる
    return String(toolInput.command ?? "").split(/[\s"'`;|&()<>=,]+/);
  }
  // Grep の pattern は探す文字列なので調べない（「.env」という語を文書から探すのは問題ない）
  const keys = toolName === "Grep" ? ["path", "glob"] : ["file_path", "path", "pattern"];
  return keys.map((key) => toolInput[key]).filter((value) => typeof value === "string");
};

const main = async () => {
  const input = JSON.parse(await readStdin());
  const cwd = input.cwd ?? process.cwd();
  const root = process.env.CLAUDE_PROJECT_DIR ?? cwd;

  for (const candidate of collectCandidates(input.tool_name, input.tool_input ?? {})) {
    if (candidate === "") continue;
    const reason = findReason(candidate, cwd, root);
    if (reason !== null) {
      console.error(
        `ブロックしました：${reason}には、Claudeからアクセスしない決まりです（対象：${candidate}）`,
      );
      process.exit(BLOCK);
    }
  }
};

main().catch((error) => {
  // 入力を読めないときは、安全側に倒して止める（fail-safe）
  console.error(`protect-secrets の実行に失敗したため、止めました：${error.message}`);
  process.exit(BLOCK);
});
