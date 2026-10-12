// Service Worker。ページとネットワークの間に立ち、端末に保存したファイルを返す。電波がなくても遊べるようにするため。
//
// 保存するのは、下の FILES に書いた公開物だけ（許可リスト）。
// 一覧にない要求には手を出さず、そのままネットワークへ通す。子どもの絵や声は、通信に乗らないので、ここには入らない。
// 10日目以降にAPIを足しても、一覧に書かない限り、その応答が端末に残ることはない。
//
// 一覧は、frontend/ の中身と一致させる。ずれは `npm run check:pwa` で見つける。

// 保存場所の名前。一覧からファイルを消したときは、番号を上げて古い保存場所を捨てる
const CACHE_PREFIX = "kids-play-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;

const FILES = [
  "index.html",
  "manifest.webmanifest",
  "css/tokens.css",
  "css/base.css",
  "css/menu.css",
  "js/main.js",
  "js/mute.js",
  "js/audio.js",
  "apps/animals/index.html",
  "apps/animals/animals.css",
  "apps/animals/animals.js",
  "apps/piano/index.html",
  "apps/piano/piano.css",
  "apps/piano/piano.js",
  "apps/draw/index.html",
  "apps/draw/draw.css",
  "apps/draw/draw.js",
  "apps/soon/index.html",
  "assets/stamps/star.svg",
  "assets/stamps/flower.svg",
  "assets/stamps/heart.svg",
  "assets/stamps/sun.svg",
  "assets/icons/icon.svg",
  "assets/icons/icon-maskable.svg",
  "assets/icons/icon-192.png",
  "assets/icons/icon-512.png",
  "assets/icons/icon-maskable-512.png",
];

// 置き場所（/kids-play/ など）を決め打ちにせず、このファイルのある場所から絶対URLを作る
const SCOPE = self.registration.scope;
const ALLOWED = new Set(FILES.map((file) => new URL(file, SCOPE).href));

// 入れたとき：一覧のファイルをまとめて保存する。1つでも取れなければ、入れること自体をやめる（半端な状態を作らない）
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      // cache: "reload" は、ブラウザの通常のキャッシュを使わず、サーバーから取り直す指定
      .then((cache) => cache.addAll([...ALLOWED].map((url) => new Request(url, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

// 動き始めたとき：名前の違う古い保存場所を消し、開いているページをすぐに受け持つ。
// 消すのは、このアプリの保存場所（kids-play- で始まる名前）だけにする。
// 保存場所はオリジン（github.io ならアカウント全体）で共有するので、同じオリジンの別のサイトの分を消さないため
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
            .map((name) => caches.delete(name)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// ページからの要求を、一覧のURLに直す。一覧になければ null
const toAllowedUrl = (request) => {
  if (request.method !== "GET") {
    return null;
  }
  const url = new URL(request.url);
  url.search = "";
  url.hash = "";
  // フォルダで終わるURL（…/kids-play/）は、その中の index.html として扱う
  if (url.pathname.endsWith("/")) {
    url.pathname += "index.html";
  }
  return ALLOWED.has(url.href) ? url.href : null;
};

// 保存してあるものをすぐ返し、裏で新しいものを取って保存し直す。
// すぐ表示でき、電波がなくても動き、次に開いたときには新しくなる。
// 更新の直後に1回だけ、新旧のファイルが混ざることがある（次に開けばそろう）
const respond = async (url, event) => {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(url);
  const refresh = fetch(url, { cache: "no-cache" }).then(async (response) => {
    // 正常な、自分のサイトからの応答だけを保存する（エラーページを保存しない）
    if (response.ok && response.type === "basic") {
      await cache.put(url, response.clone());
    }
    return response;
  });
  if (cached) {
    // 電波がないときの失敗は、黙って捨てる（保存してある分で遊べている）
    event.waitUntil(refresh.catch(() => {}));
    return cached;
  }
  return refresh;
};

self.addEventListener("fetch", (event) => {
  const url = toAllowedUrl(event.request);
  if (url) {
    event.respondWith(respond(url, event));
  }
});
