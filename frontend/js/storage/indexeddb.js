// 端末の中（IndexedDB）に置く保存先。再読み込みしても、アプリを閉じても残る。
// すべての公開環境の既定。絵と声は端末の外に出さない（脅威分析の T-08）。約束は docs/storage-interface.md

import { MAX_PAGES, StorageError, toStoredPage, validatePage } from "./validate.js";

const DB_NAME = "kids-play-storybook";
// 保存の形を変えたら上げる（onupgradeneeded で作り直す処理を足す）
const DB_VERSION = 1;
const STORE = "pages";

// IndexedDB の「要求」を Promise にする。IndexedDB はイベントで結果を返すため
const done = (request) =>
  new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

// 書き込みは、取引（transaction）が最後までそろって終わったときに確定する
const committed = (transaction) =>
  new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });

const open = (indexedDB) =>
  new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE, { keyPath: "id" });
    };
    request.onsuccess = () => {
      const db = request.result;
      // 新しい版の画面が開いたら、こちらは閉じて道をあける（そうしないと新しい版が開けない）
      db.onversionchange = () => db.close();
      resolve(db);
    };
    request.onerror = () => reject(request.error);
    // 古い版の画面が別のタブで開いたままだと、開く要求が終わらない。待ち続けず失敗として扱い、
    // 呼ぶ側（index.js）がメモリ版に切り替えられるようにする
    request.onblocked = () => reject(new Error("blocked"));
  });

// 保存した記録 { id, order, picture, voice, voiceMs } から、約束どおりの形だけを返す。
// order（並び順の番号）は保存先の中の都合なので、画面には見せない
const toPage = (record) => toStoredPage(record, record.id);

const byOrder = (records) => records.sort((a, b) => a.order - b.order);

/**
 * @param {{indexedDB?: IDBFactory}} [options] テストでは fake-indexeddb を渡す
 */
export const createIndexedDBStorage = async ({ indexedDB = globalThis.indexedDB } = {}) => {
  const db = await open(indexedDB);

  const store = (mode) => {
    const transaction = db.transaction(STORE, mode);
    return { transaction, pages: transaction.objectStore(STORE) };
  };

  return {
    listPages: async () => {
      const { pages } = store("readonly");
      return byOrder(await done(pages.getAll())).map(toPage);
    },

    getPage: async (id) => {
      const { pages } = store("readonly");
      const record = await done(pages.get(id));
      return record ? toPage(record) : null;
    },

    savePage: async (page) => {
      validatePage(page);
      // 数を数える・番号を決める・書くを1つの取引にまとめ、
      // 同時に2回保存されても上限（8ページ）を超えないようにする
      const { transaction, pages } = store("readwrite");
      const records = await done(pages.getAll());
      const existing = records.find((record) => record.id === page.id);
      let record;
      if (existing) {
        record = { ...toStoredPage(page, page.id), order: existing.order };
      } else {
        if (records.length >= MAX_PAGES) {
          transaction.abort();
          throw new StorageError("page-limit", "ページがいっぱい");
        }
        const order = Math.max(0, ...records.map((item) => item.order)) + 1;
        record = { ...toStoredPage(page, crypto.randomUUID()), order };
      }
      pages.put(record);
      await committed(transaction);
      return toPage(record);
    },

    deletePage: async (id) => {
      const { transaction, pages } = store("readwrite");
      pages.delete(id);
      await committed(transaction);
    },

    deleteAll: async () => {
      const { transaction, pages } = store("readwrite");
      pages.clear();
      await committed(transaction);
    },

    // 開き直すテストのために閉じられるようにする
    close: () => db.close(),
  };
};
