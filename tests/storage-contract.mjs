// 保存のインターフェースの「約束」を確かめるテスト。
// 保存先（メモリ、IndexedDB、FastAPI）が変わっても、画面から見た動きは同じでなければならない。
// どの保存先も、このテストを通す。新しい保存先を作ったら、createStorage を渡して呼ぶだけでよい

import assert from "node:assert/strict";
import { test } from "node:test";

import { MAX_PAGES, MAX_VOICE_MS } from "../frontend/js/storage/validate.js";

// 中身は自作の小さなデータ（本物の絵や声は使わない）。
// 先頭のバイトだけは本物の形式（PNG、WebM）に合わせる。サーバー版は種類と中身が合っているかを確かめるため
const PNG_HEADER = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const WEBM_HEADER = new Uint8Array([0x1a, 0x45, 0xdf, 0xa3]);
const picture = () => new Blob([PNG_HEADER, "picture"], { type: "image/png" });
const voice = () => new Blob([WEBM_HEADER, "voice"], { type: "audio/webm" });
// 見本データの、先頭の印より後ろ（中身が同じかを比べる）
const body = async (blob, header) => (await blob.text()).slice(new TextDecoder().decode(header).length);
const newPage = (overrides = {}) => ({ picture: picture(), voice: voice(), voiceMs: 1000, ...overrides });

// 拒否されたときに、理由の名前（code）で区別できること
const rejectsWith = (promise, code) => assert.rejects(promise, (error) => error.code === code);

export const runStorageContract = (name, createStorage) => {
  test(`${name}：はじめは空`, async () => {
    const storage = await createStorage();
    assert.deepEqual(await storage.listPages(), []);
  });

  test(`${name}：新しいページは最後に足され、id が付く`, async () => {
    const storage = await createStorage();
    const first = await storage.savePage(newPage({ voiceMs: 1 }));
    const second = await storage.savePage(newPage({ voiceMs: 2 }));
    assert.equal(typeof first.id, "string");
    assert.notEqual(first.id, second.id);
    const pages = await storage.listPages();
    assert.deepEqual(
      pages.map((page) => page.id),
      [first.id, second.id],
    );
  });

  test(`${name}：保存したページを id で読める。絵と声は同じ中身`, async () => {
    const storage = await createStorage();
    const saved = await storage.savePage(newPage());
    const page = await storage.getPage(saved.id);
    assert.equal(await body(page.picture, PNG_HEADER), "picture");
    assert.equal(await body(page.voice, WEBM_HEADER), "voice");
    assert.equal(page.voice.type, "audio/webm");
    assert.equal(page.voiceMs, 1000);
  });

  test(`${name}：ないページを読むと null`, async () => {
    const storage = await createStorage();
    assert.equal(await storage.getPage("nothing"), null);
  });

  test(`${name}：id を付けて保存すると上書きになり、順番と数は変わらない`, async () => {
    const storage = await createStorage();
    const first = await storage.savePage(newPage());
    await storage.savePage(newPage());
    await storage.savePage({ ...newPage({ voice: null, voiceMs: 0 }), id: first.id });
    const pages = await storage.listPages();
    assert.equal(pages.length, 2);
    assert.equal(pages[0].id, first.id);
    assert.equal(pages[0].voice, null);
  });

  test(`${name}：絵だけ、声だけのページも保存できる（描きかけ・録りかけ）`, async () => {
    const storage = await createStorage();
    await storage.savePage(newPage({ picture: null }));
    await storage.savePage(newPage({ voice: null, voiceMs: 0 }));
    assert.equal((await storage.listPages()).length, 2);
  });

  test(`${name}：${MAX_PAGES + 1}ページ目は拒否する`, async () => {
    const storage = await createStorage();
    for (let i = 0; i < MAX_PAGES; i += 1) {
      await storage.savePage(newPage());
    }
    await rejectsWith(storage.savePage(newPage()), "page-limit");
    assert.equal((await storage.listPages()).length, MAX_PAGES);
  });

  test(`${name}：${MAX_VOICE_MS / 1000}秒を超える声は拒否する`, async () => {
    const storage = await createStorage();
    await storage.savePage(newPage({ voiceMs: MAX_VOICE_MS }));
    await rejectsWith(storage.savePage(newPage({ voiceMs: MAX_VOICE_MS + 1 })), "voice-too-long");
  });

  test(`${name}：形の違うデータは拒否する（絵が画像でない、声が音でない）`, async () => {
    const storage = await createStorage();
    await rejectsWith(storage.savePage(newPage({ picture: "<svg>" })), "invalid-page");
    await rejectsWith(
      storage.savePage(newPage({ voice: new Blob(["x"], { type: "text/html" }) })),
      "invalid-page",
    );
    await rejectsWith(storage.savePage(newPage({ voiceMs: -1 })), "invalid-page");
    assert.deepEqual(await storage.listPages(), []);
  });

  test(`${name}：ページを消すと、残りのページは順番を保って詰まる`, async () => {
    const storage = await createStorage();
    const [a, b, c] = [
      await storage.savePage(newPage()),
      await storage.savePage(newPage()),
      await storage.savePage(newPage()),
    ];
    await storage.deletePage(b.id);
    assert.deepEqual(
      (await storage.listPages()).map((page) => page.id),
      [a.id, c.id],
    );
    assert.equal(await storage.getPage(b.id), null);
  });

  test(`${name}：ぜんぶ消すと空になる`, async () => {
    const storage = await createStorage();
    await storage.savePage(newPage());
    await storage.savePage(newPage());
    await storage.deleteAll();
    assert.deepEqual(await storage.listPages(), []);
  });

  test(`${name}：読んだページを書き換えても、保存した中身は変わらない`, async () => {
    const storage = await createStorage();
    const saved = await storage.savePage(newPage());
    const page = await storage.getPage(saved.id);
    page.voiceMs = 9999;
    assert.equal((await storage.getPage(saved.id)).voiceMs, 1000);
  });
};
