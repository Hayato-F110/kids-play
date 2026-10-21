// 保存先の選び方（frontend/js/storage/index.js）を確かめる。
// サーバー保存は、PC 内の開発用サーバーで開き、サーバーが「有効」と答えたときだけ選ぶ。
// それ以外は、サーバーに問い合わせもしない（docs/storage-interface.md、脅威分析 T-08）
import assert from "node:assert/strict";
import { test } from "node:test";

import { indexedDB } from "fake-indexeddb";

import { isLocalDevServer, openStorage } from "../frontend/js/storage/index.js";

const at = (url) => new URL(url);

// 呼ばれた URL を記録する、偽の fetch
const fakeFetch = (respond) => {
  const calls = [];
  const fetch = async (url, options) => {
    calls.push(String(url));
    return respond(String(url), options);
  };
  return { fetch, calls };
};

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const open = (url, fetch, extra = {}) => openStorage({ location: at(url), fetch, indexedDB, ...extra });

test("PC の開発用サーバー（localhost / 127.0.0.1 の 8000 番）だけを見分ける", () => {
  assert.equal(isLocalDevServer(at("http://localhost:8000/apps/storybook/")), true);
  assert.equal(isLocalDevServer(at("http://127.0.0.1:8000/")), true);
  assert.equal(isLocalDevServer(at("https://hayato-f110.github.io/kids-play/")), false);
  assert.equal(isLocalDevServer(at("http://localhost:5500/")), false);
  assert.equal(isLocalDevServer(at("http://localhost/")), false);
  assert.equal(isLocalDevServer(at("https://localhost:8000/")), false);
  assert.equal(isLocalDevServer(at("http://192.168.1.10:8000/")), false);
});

test("Android アプリの中は、ホスト名が localhost でも開発用サーバーとみなさない", () => {
  assert.equal(isLocalDevServer(at("http://localhost:8000/"), {}), false);
  assert.equal(isLocalDevServer(at("https://localhost/"), {}), false);
});

test("公開サイトでは、サーバーに問い合わせない", async () => {
  const { fetch, calls } = fakeFetch(() => json({ enabled: true }));
  const storage = await open("https://hayato-f110.github.io/kids-play/apps/storybook/", fetch);
  await storage.listPages();
  assert.deepEqual(calls, []);
});

test("Android アプリの中では、サーバーに問い合わせない", async () => {
  const { fetch, calls } = fakeFetch(() => json({ enabled: true }));
  const storage = await open("http://localhost:8000/apps/storybook/", fetch, { capacitor: {} });
  await storage.listPages();
  assert.deepEqual(calls, []);
});

test("サーバーが有効と答えたら、サーバー保存を使う", async () => {
  const { fetch, calls } = fakeFetch((url) => json(url.endsWith("/status") ? { enabled: true } : []));
  const storage = await open("http://localhost:8000/apps/storybook/", fetch);
  assert.deepEqual(await storage.listPages(), []);
  assert.deepEqual(calls, ["http://localhost:8000/api/storage/status", "http://localhost:8000/api/pages"]);
});

for (const [name, respond] of [
  ["無効と答えた", () => json({ enabled: false })],
  ['enabled が true でない（文字の "true"）', () => json({ enabled: "true" })],
  ["API がない（python -m http.server で開いた）", () => new Response("not found", { status: 404 })],
  ["JSON でない", () => new Response("<html>", { status: 200 })],
  [
    "つながらない",
    () => {
      throw new TypeError("fetch failed");
    },
  ],
]) {
  test(`サーバーが${name}ときは、端末の中（IndexedDB）に保存する`, async () => {
    const { fetch, calls } = fakeFetch(respond);
    const storage = await open("http://localhost:8000/apps/storybook/", fetch);
    await storage.savePage({ picture: null, voice: null, voiceMs: 0 });
    // 問い合わせの1回だけで、保存はサーバーに送っていない
    assert.deepEqual(calls, ["http://localhost:8000/api/storage/status"]);
    assert.equal((await storage.listPages()).length, 1);
    await storage.deleteAll();
  });
}

test("サーバーが答えないときは、待ち続けずに端末の中に保存する", async () => {
  // 答えが返らない fetch。中断の合図（signal）が来たら失敗する
  const fetch = (_url, { signal }) =>
    new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(signal.reason)));
  // Node の AbortSignal.timeout の時計は、それだけではテストの実行を待たせない。待つ間だけ時計を置く
  const keepAlive = setTimeout(() => {}, 5000);
  try {
    const storage = await open("http://localhost:8000/apps/storybook/", fetch, { statusTimeoutMs: 50 });
    assert.deepEqual(await storage.listPages(), []);
    await storage.deleteAll();
  } finally {
    clearTimeout(keepAlive);
  }
});
