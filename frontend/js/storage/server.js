// PC の中のサーバー（FastAPI + SQLite）に置く保存先。約束は docs/storage-interface.md。
// index.js が、PC 内の開発用サーバーで、サーバーが「有効」と答えたときだけ選ぶ。公開環境では使わない（T-08）。
// 送り先は自分のオリジン（同じサーバー）だけ。CSP も connect-src 'self' までしか許していない

import { StorageError, validatePage } from "./validate.js";

// サーバーが返す理由の名前のうち、画面が区別するもの。それ以外は形の違いとして扱う
const KNOWN_CODES = new Set(["page-limit", "voice-too-long", "invalid-page"]);

/**
 * @param {{base?: string, fetch?: typeof globalThis.fetch}} [options]
 *   base は API のあるオリジン（既定は今のページと同じ）。テストでは別のポートを渡す
 */
export const createServerStorage = ({ base = "", fetch = globalThis.fetch } = {}) => {
  // 子どもの絵と声を、ブラウザのキャッシュに写しとして残さない
  const request = (path, options = {}) =>
    fetch(`${base}${path}`, { cache: "no-store", credentials: "same-origin", ...options });

  const failed = async (response) => {
    let code = "invalid-page";
    try {
      const body = await response.json();
      code = KNOWN_CODES.has(body.code) ? body.code : code;
    } catch {
      // 理由が読めないときも、形の違いとして扱う
    }
    return new StorageError(code, `サーバーが拒否した（${response.status}）`);
  };

  const media = async (id, kind, type) => {
    if (!type) {
      return null;
    }
    const response = await request(`/api/pages/${encodeURIComponent(id)}/${kind}`);
    if (!response.ok) {
      throw await failed(response);
    }
    // 種類はサーバーが確かめて保存した名前を使う
    return new Blob([await response.arrayBuffer()], { type });
  };

  // 一覧の1行（中身なし）から、約束の形のページを作る。絵と声は別の URL から読む
  const toPage = async ({ id, pictureType, voiceType, voiceMs }) => ({
    id,
    picture: await media(id, "picture", pictureType),
    voice: await media(id, "voice", voiceType),
    voiceMs,
  });

  const listMeta = async () => {
    const response = await request("/api/pages");
    if (!response.ok) {
      throw await failed(response);
    }
    return response.json();
  };

  return {
    listPages: async () => Promise.all((await listMeta()).map(toPage)),

    getPage: async (id) => {
      // 1冊は8ページまでなので、一覧から探せば足りる（1ページだけの情報を返す API を増やさない）
      const meta = (await listMeta()).find((item) => item.id === id);
      return meta ? toPage(meta) : null;
    },

    savePage: async (page) => {
      // サーバーも同じ確認をするが、送る前にも確かめ、だめなものは端末の外に出さない
      validatePage(page);
      // 送るのは約束の項目だけ。画面の作りかけの値などを足さない
      const form = new FormData();
      form.append("voiceMs", String(Math.round(page.voiceMs)));
      if (page.picture) {
        form.append("picture", page.picture, "picture");
      }
      if (page.voice) {
        form.append("voice", page.voice, "voice");
      }
      const path = page.id === undefined ? "/api/pages" : `/api/pages/${encodeURIComponent(page.id)}`;
      const response = await request(path, { method: page.id === undefined ? "POST" : "PUT", body: form });
      if (!response.ok) {
        throw await failed(response);
      }
      const { id } = await response.json();
      return { id, picture: page.picture, voice: page.voice, voiceMs: page.voiceMs };
    },

    deletePage: async (id) => {
      const response = await request(`/api/pages/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!response.ok) {
        throw await failed(response);
      }
    },

    deleteAll: async () => {
      const response = await request("/api/pages", { method: "DELETE" });
      if (!response.ok) {
        throw await failed(response);
      }
    },
  };
};
