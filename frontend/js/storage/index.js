// 保存先を選ぶ入口。画面はここで受け取った保存先だけを使う（docs/storage-interface.md）。
// 10日目に、PC の localhost で設定したときだけサーバー保存を選ぶ分岐を足す（KIDS-34）

import { createIndexedDBStorage } from "./indexeddb.js";
import { createMemoryStorage } from "./memory.js";

export const openStorage = async () => {
  try {
    return await createIndexedDBStorage();
  } catch {
    // IndexedDB が使えない環境（ブラウザの設定で止めている、など）でも遊べるようにする。
    // そのときは再読み込みで消えるが、子どもの画面にはエラーを出さない。
    // 切り替え先は必ずメモリ版にする。サーバー保存にすると、失敗したときに絵と声が端末の外へ出る側に倒れるため（T-08）
    return createMemoryStorage();
  }
};
