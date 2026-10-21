// 保存先を選ぶ入口。画面はここで受け取った保存先だけを使う（docs/storage-interface.md）。
// サーバー保存は、次の両方がそろったときだけ選ぶ。1つでも欠けたら端末の中（IndexedDB）に保存する（T-08、C-12）
//   1. PC 内の開発用サーバーで開いている（Android アプリの中ではない）
//   2. サーバーが「有効」と答えた（サーバーの既定は無効）
// さらに CSP（connect-src 'self'）が、通信先を自分のオリジンに限っている

import { createIndexedDBStorage } from "./indexeddb.js";
import { createMemoryStorage } from "./memory.js";
import { createServerStorage } from "./server.js";

// PC で FastAPI を動かすときのポート（docs/storage-interface.md）
const DEV_PORT = "8000";
const DEV_HOSTS = new Set(["localhost", "127.0.0.1"]);
// サーバーの答えを待つ時間。答えがなければ端末の中に保存する（子どもを待たせない）
const STATUS_TIMEOUT_MS = 1500;

/**
 * PC 内の開発用サーバーで開いているか。
 * Android アプリ（Capacitor）もホスト名が localhost なので、ホスト名だけでは見分けられない。
 * そのため、アプリの中であること（window.Capacitor がある）も見る
 * @param {URL | Location} location
 * @param {unknown} [capacitor]
 */
export const isLocalDevServer = (location, capacitor = globalThis.Capacitor) =>
  capacitor === undefined &&
  location.protocol === "http:" &&
  DEV_HOSTS.has(location.hostname) &&
  location.port === DEV_PORT;

// サーバーが「有効」と、はっきり答えたときだけ true。つながらない・遅い・形が違うは、すべて false
const serverStorageEnabled = async (fetch, base, timeoutMs) => {
  try {
    const response = await fetch(`${base}/api/storage/status`, {
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!response.ok) {
      return false;
    }
    const body = await response.json();
    return body.enabled === true;
  } catch {
    return false;
  }
};

const openOnDevice = async (indexedDB) => {
  try {
    return await createIndexedDBStorage({ indexedDB });
  } catch {
    // IndexedDB が使えない環境（ブラウザの設定で止めている、など）でも遊べるようにする。
    // そのときは再読み込みで消えるが、子どもの画面にはエラーを出さない。
    // 切り替え先は必ずメモリ版にする。サーバー保存にすると、失敗したときに絵と声が端末の外へ出る側に倒れるため（T-08）
    return createMemoryStorage();
  }
};

/**
 * @param {{location?: URL | Location, fetch?: typeof globalThis.fetch, capacitor?: unknown,
 *   indexedDB?: IDBFactory, statusTimeoutMs?: number}} [options] テストでは偽の値を渡す
 */
export const openStorage = async ({
  location = globalThis.location,
  fetch = globalThis.fetch,
  capacitor = globalThis.Capacitor,
  indexedDB = globalThis.indexedDB,
  statusTimeoutMs = STATUS_TIMEOUT_MS,
} = {}) => {
  // 公開サイトとアプリでは、サーバーに問い合わせもしない
  if (location && isLocalDevServer(location, capacitor)) {
    const base = location.origin;
    if (await serverStorageEnabled(fetch, base, statusTimeoutMs)) {
      return createServerStorage({ base, fetch });
    }
  }
  return openOnDevice(indexedDB);
};
