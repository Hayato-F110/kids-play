// IndexedDB 版の保存先を、保存のインターフェースの約束で確かめる。
// Node には IndexedDB がないので、fake-indexeddb（開発用。公開物には入らない）を代わりに使う
import assert from "node:assert/strict";
import { test } from "node:test";

import { IDBFactory } from "fake-indexeddb";

import { runStorageContract } from "./storage-contract.mjs";
import { createIndexedDBStorage } from "../frontend/js/storage/indexeddb.js";

// テストごとに空の IndexedDB を用意し、前のテストの中身が混ざらないようにする
runStorageContract("IndexedDB", () => createIndexedDBStorage({ indexedDB: new IDBFactory() }));

const newPage = (voiceMs) => ({
  picture: new Blob(["picture"], { type: "image/png" }),
  voice: new Blob(["voice"], { type: "audio/webm" }),
  voiceMs,
});

// 再読み込みは「同じ IndexedDB を開き直す」ことに当たる
test("IndexedDB：開き直しても、ページが順番どおりに残る", async () => {
  const indexedDB = new IDBFactory();
  const before = await createIndexedDBStorage({ indexedDB });
  const first = await before.savePage(newPage(1));
  const second = await before.savePage(newPage(2));
  before.close();

  const after = await createIndexedDBStorage({ indexedDB });
  const pages = await after.listPages();
  assert.deepEqual(
    pages.map((page) => page.id),
    [first.id, second.id],
  );
  assert.equal(await pages[1].voice.text(), "voice");
});

test("IndexedDB：上書きしても、開き直したときの順番は変わらない", async () => {
  const indexedDB = new IDBFactory();
  const before = await createIndexedDBStorage({ indexedDB });
  const first = await before.savePage(newPage(1));
  const second = await before.savePage(newPage(2));
  await before.savePage({ ...newPage(3), id: first.id });
  before.close();

  const after = await createIndexedDBStorage({ indexedDB });
  const pages = await after.listPages();
  assert.deepEqual(
    pages.map((page) => [page.id, page.voiceMs]),
    [
      [first.id, 3],
      [second.id, 2],
    ],
  );
});

test("IndexedDB：返すページには、約束にない項目（並び順の番号など）を含めない", async () => {
  const storage = await createIndexedDBStorage({ indexedDB: new IDBFactory() });
  await storage.savePage({ ...newPage(1), name: "なまえ" });
  const [page] = await storage.listPages();
  assert.deepEqual(Object.keys(page).sort(), ["id", "picture", "voice", "voiceMs"]);
});

// 返す形だけでなく、端末に書かれた中身そのものに、名前や日時が入っていないことを確かめる
test("IndexedDB：端末に書く記録は、約束の4項目と並び順の番号だけ", async () => {
  const indexedDB = new IDBFactory();
  const storage = await createIndexedDBStorage({ indexedDB });
  await storage.savePage({ ...newPage(1), name: "なまえ", createdAt: Date.now() });
  storage.close();

  const records = await new Promise((resolve, reject) => {
    const request = indexedDB.open("kids-play-storybook");
    request.onsuccess = () => {
      const all = request.result.transaction("pages").objectStore("pages").getAll();
      all.onsuccess = () => resolve(all.result);
      all.onerror = () => reject(all.error);
    };
    request.onerror = () => reject(request.error);
  });
  assert.equal(records.length, 1);
  assert.deepEqual(Object.keys(records[0]).sort(), ["id", "order", "picture", "voice", "voiceMs"]);
});
