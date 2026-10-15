// えほんのページを保存する前の確認。どの保存先（メモリ、IndexedDB、FastAPI）も、ここを通してから保存する。
// 規則を1か所に集め、保存先によって受け入れるデータが変わらないようにする（docs/storage-interface.md）

// 1冊のページ数と、1ページの録音の長さの上限（docs/design.md の仕様）
export const MAX_PAGES = 8;
export const MAX_VOICE_MS = 30_000;

// 理由の名前（code）を付けて拒否する。画面は code を見て、失敗の表現を出さずに静かに扱う
export class StorageError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "StorageError";
    this.code = code;
  }
}

const isBlobOf = (value, kind) => value instanceof Blob && value.type.startsWith(`${kind}/`);

/**
 * 保存してよいページかを確かめる。だめなときは StorageError を投げる。
 * @param {{id?: string, picture: Blob | null, voice: Blob | null, voiceMs: number}} page
 */
export const validatePage = (page) => {
  const { id, picture, voice, voiceMs } = page ?? {};
  if (id !== undefined && typeof id !== "string") {
    throw new StorageError("invalid-page", "id は文字列");
  }
  if (picture !== null && !isBlobOf(picture, "image")) {
    throw new StorageError("invalid-page", "絵は画像の Blob か null");
  }
  if (voice !== null && !isBlobOf(voice, "audio")) {
    throw new StorageError("invalid-page", "声は音の Blob か null");
  }
  if (!Number.isFinite(voiceMs) || voiceMs < 0) {
    throw new StorageError("invalid-page", "voiceMs は 0 以上の数");
  }
  if (voiceMs > MAX_VOICE_MS) {
    throw new StorageError("voice-too-long", "録音が長すぎる");
  }
};

// 保存する形にそろえる。知らない項目は捨てる（画面の作りかけの値などを保存先に入れない）
export const toStoredPage = ({ picture, voice, voiceMs }, id) => ({ id, picture, voice, voiceMs });
