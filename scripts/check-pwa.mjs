// PWAまわりの、手で合わせている値のずれを見つける。使い方：npm run check:pwa
//
// 1. sw.js の一覧（FILES）と、frontend/ の実際のファイルが一致しているか
//    （足し忘れると、そのファイルだけ電波なしで開けない。消し忘れると、Service Worker を入れられなくなる）
// 2. すべてのHTMLで、CSP が同じ内容か。manifest とアイコンを指定しているか
// 3. manifest と theme-color の色が、tokens.css の --color-bg と同じか
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "frontend");
const problems = [];

const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)],
  );
const actual = walk(root)
  .map((file) => relative(root, file).replaceAll("\\", "/"))
  // sw.js 自身は、ブラウザが別に管理する。先頭がドットのファイルは公開されない
  .filter((file) => file !== "sw.js" && !file.split("/").some((part) => part.startsWith(".")));

const sw = readFileSync(join(root, "sw.js"), "utf8");
const block = sw.match(/const FILES = \[([\s\S]*?)\];/);
const listed = block ? [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
if (!block) {
  problems.push("sw.js に FILES の一覧が見つからない");
}
for (const file of actual.filter((f) => !listed.includes(f))) {
  problems.push(`sw.js の一覧にない：${file}`);
}
for (const file of listed.filter((f) => !actual.includes(f))) {
  problems.push(`sw.js の一覧にあるが、ファイルがない：${file}`);
}

// えほんの画面だけは、PC 内のサーバー保存のために、自分のオリジンへの通信を許す（C-08、C-12）。
// ほかの画面には通信の許可を広げない。違いはこの1つだけであることを確かめる
const CONNECT_SELF = "; connect-src 'self'";
const CONNECT_ALLOWED = new Set(["apps/storybook/index.html"]);

const htmlFiles = actual.filter((file) => file.endsWith(".html"));
const policies = new Map();
for (const file of htmlFiles) {
  const html = readFileSync(join(root, file), "utf8");
  let csp = html.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/)?.[1];
  if (!csp) {
    problems.push(`CSP がない：${file}`);
  } else if (CONNECT_ALLOWED.has(file)) {
    if (!csp.endsWith(CONNECT_SELF)) {
      problems.push(`CSP の最後に connect-src 'self' がない：${file}`);
    }
    csp = csp.replace(CONNECT_SELF, "");
  }
  if (csp?.includes("connect-src")) {
    problems.push(`CSP に connect-src を足してよいのは、えほんの画面だけ：${file}`);
  }
  policies.set(file, csp);
  if (!/<link rel="manifest" /.test(html)) {
    problems.push(`manifest の指定がない：${file}`);
  }
  if (!/<link rel="icon" /.test(html)) {
    problems.push(`アイコンの指定がない：${file}`);
  }
}
if (new Set(policies.values()).size > 1) {
  problems.push("CSP の内容が、HTMLによって違う");
}

const bg = readFileSync(join(root, "css/tokens.css"), "utf8").match(/--color-bg:\s*(#[0-9a-f]{6})/i)?.[1];
const manifest = JSON.parse(readFileSync(join(root, "manifest.webmanifest"), "utf8"));
for (const key of ["background_color", "theme_color"]) {
  if (manifest[key] !== bg) {
    problems.push(`manifest の ${key}（${manifest[key]}）が、--color-bg（${bg}）と違う`);
  }
}
for (const file of htmlFiles) {
  const theme = readFileSync(join(root, file), "utf8").match(/name="theme-color" content="([^"]+)"/)?.[1];
  if (theme !== bg) {
    problems.push(`theme-color（${theme}）が、--color-bg（${bg}）と違う：${file}`);
  }
}
for (const icon of manifest.icons) {
  if (!actual.includes(icon.src)) {
    problems.push(`manifest のアイコンがない：${icon.src}`);
  }
}

if (problems.length > 0) {
  console.error(problems.map((p) => `NG  ${p}`).join("\n"));
  process.exit(1);
}
console.log(`OK  一覧 ${listed.length} 件、HTML ${htmlFiles.length} 件、色 ${bg}`);
