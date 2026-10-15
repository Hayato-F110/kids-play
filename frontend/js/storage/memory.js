// メモリに置く保存先。再読み込みで消える。
// テストと、IndexedDB 版（9日目）ができるまでの画面の確認に使う。約束は docs/storage-interface.md

import { MAX_PAGES, StorageError, toStoredPage, validatePage } from "./validate.js";

export const createMemoryStorage = () => {
  // 並び順がそのままページの順番
  let pages = [];

  // 外へ渡すときは写しにする。受け取った側が書き換えても、保存した中身が変わらないように
  // （Blob は中身を書き換えられないので、そのまま渡してよい）
  const copy = (page) => ({ ...page });

  return {
    listPages: async () => pages.map(copy),

    getPage: async (id) => {
      const page = pages.find((item) => item.id === id);
      return page ? copy(page) : null;
    },

    savePage: async (page) => {
      validatePage(page);
      const index = pages.findIndex((item) => item.id === page.id);
      if (index >= 0) {
        pages[index] = toStoredPage(page, page.id);
        return copy(pages[index]);
      }
      if (pages.length >= MAX_PAGES) {
        throw new StorageError("page-limit", "ページがいっぱい");
      }
      const stored = toStoredPage(page, crypto.randomUUID());
      pages.push(stored);
      return copy(stored);
    },

    deletePage: async (id) => {
      pages = pages.filter((item) => item.id !== id);
    },

    deleteAll: async () => {
      pages = [];
    },
  };
};
