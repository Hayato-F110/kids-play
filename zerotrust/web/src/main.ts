// おとなのページ：パスキーで登録・ログインし、短い期限のトークンで API を読む（18日目、KIDS-62）。
// compose.zerotrust.yaml のときだけ nginx が配る。子どもの画面（frontend/）とは別にする。
// 守りの決まりは、脅威分析の T-28・T-29、対策 C-31・C-32。

type Summary = { storageEnabled: boolean; pageCount: number | null; subject: string };
type LoginResult = { token: string; expiresIn: number };

// トークンはこの変数（ページのメモリ）にだけ持つ。localStorage に置かない（XSS で読まれる場所を減らす。C-32 (5)）
let token: string | null = null;
let expiresAt = 0;

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (found === null) {
    throw new Error(`#${id} がない`);
  }
  return found as T;
}

const log = element<HTMLOListElement>("log");
const state = element<HTMLParagraphElement>("state");

function write(text: string): void {
  // 画面に出す文字は textContent で入れる（innerHTML を使わない。C-06）
  const item = document.createElement("li");
  item.textContent = `${new Date().toLocaleTimeString()} ${text}`;
  log.prepend(item);
}

function showState(): void {
  const left = Math.max(0, Math.round((expiresAt - Date.now()) / 1000));
  state.textContent =
    token !== null && left > 0 ? `ログイン中（トークンの残り ${left} 秒）` : "ログインしていない";
  if (token !== null && left === 0) {
    token = null;
  }
}

async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    // Cookie は使わない。認証はトークンだけで行う
    credentials: "omit",
  });
}

async function reason(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "code" in body) {
      return `${response.status} ${String(body.code)}`;
    }
  } catch {
    // JSON でない応答（nginx の 403 など）は、状態のコードだけを出す
  }
  return String(response.status);
}

async function register(): Promise<void> {
  const code = element<HTMLInputElement>("setup-code").value.trim();
  const optionsResponse = await postJson("/api/auth/register/options", { setupCode: code });
  if (!optionsResponse.ok) {
    write(`登録の準備を断られた：${await reason(optionsResponse)}`);
    return;
  }
  const publicKey = PublicKeyCredential.parseCreationOptionsFromJSON(await optionsResponse.json());
  // ここで Windows Hello などが本人を確かめる。生体の情報は端末の外に出ない
  const credential = await navigator.credentials.create({ publicKey });
  if (!(credential instanceof PublicKeyCredential)) {
    write("パスキーを作れなかった");
    return;
  }
  const done = await postJson("/api/auth/register/verify", credential.toJSON());
  write(done.ok ? "パスキーを登録した" : `登録を断られた：${await reason(done)}`);
}

async function login(): Promise<void> {
  const optionsResponse = await postJson("/api/auth/login/options", {});
  if (!optionsResponse.ok) {
    write(`ログインの準備を断られた：${await reason(optionsResponse)}`);
    return;
  }
  const publicKey = PublicKeyCredential.parseRequestOptionsFromJSON(await optionsResponse.json());
  const credential = await navigator.credentials.get({ publicKey });
  if (!(credential instanceof PublicKeyCredential)) {
    write("パスキーを使えなかった");
    return;
  }
  const done = await postJson("/api/auth/login/verify", credential.toJSON());
  if (!done.ok) {
    write(`ログインを断られた：${await reason(done)}`);
    return;
  }
  const result = (await done.json()) as LoginResult;
  token = result.token;
  expiresAt = Date.now() + result.expiresIn * 1000;
  write(`ログインした（トークンの期限は ${result.expiresIn} 秒）`);
  showState();
}

async function readSummary(withToken: boolean): Promise<void> {
  const headers: Record<string, string> = {};
  if (withToken && token !== null) {
    headers.authorization = `Bearer ${token}`;
  }
  const response = await fetch("/api/parent/summary", { headers, credentials: "omit" });
  if (!response.ok) {
    write(`状態の読み出しを断られた：${await reason(response)}`);
    return;
  }
  const summary = (await response.json()) as Summary;
  const pages = summary.pageCount === null ? "サーバー保存は無効" : `${summary.pageCount} ページ`;
  write(`読めた：${summary.subject}、${pages}`);
}

function run(task: () => Promise<void>): () => void {
  return () => {
    task().catch((error: unknown) => {
      // パスキーの画面を閉じた、時間切れなど
      write(`止まった：${error instanceof Error ? error.name : String(error)}`);
    });
  };
}

element<HTMLButtonElement>("register").addEventListener("click", run(register));
element<HTMLButtonElement>("login").addEventListener("click", run(login));
element<HTMLButtonElement>("summary").addEventListener(
  "click",
  run(() => readSummary(true)),
);
element<HTMLButtonElement>("summary-without-token").addEventListener(
  "click",
  run(() => readSummary(false)),
);
element<HTMLButtonElement>("logout").addEventListener("click", () => {
  token = null;
  expiresAt = 0;
  write("ログアウトした（トークンを捨てた）");
  showState();
});

window.setInterval(showState, 1000);
showState();
