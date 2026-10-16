// 画面なしの Edge で、えほんを操作しながら画面のコマを受け取る。
// トップ → えほん → スタンプで3ページ → 偽のマイク（合成音）で録音 → 紙芝居 → トップ。
// 利用者データは毎回新しく作るので、IndexedDB は空から始まり、ほかの記録は混ざらない

import { createRequire } from "node:module";

// スタンプの置き場所（キャンバスの幅・高さに対する割合）
const LAYOUTS = [
  [
    ["sun", 0.78, 0.2],
    ["flower", 0.2, 0.72],
    ["flower", 0.42, 0.78],
    ["star", 0.3, 0.3],
  ],
  [
    ["star", 0.2, 0.25],
    ["star", 0.5, 0.18],
    ["star", 0.8, 0.28],
    ["heart", 0.5, 0.65],
  ],
  [
    ["heart", 0.25, 0.4],
    ["heart", 0.75, 0.4],
    ["sun", 0.5, 0.2],
    ["flower", 0.5, 0.75],
  ],
];
const RECORD_MS = 2800;
// スマホの縦の画面。画面の配信は CSS の画素で撮られる（deviceScaleFactor は効かない）
export const VIEW = { width: 412, height: 892 };

const loadPlaywright = () => {
  const require = createRequire(import.meta.url);
  try {
    return require(process.env.PLAYWRIGHT ?? "playwright");
  } catch {
    throw new Error(
      "Playwright が見つかりません。環境変数 PLAYWRIGHT に、playwright のフォルダを指定してください。",
    );
  }
};

/**
 * @param {{ base: string, wav: string }} options
 * @returns {Promise<{ frames: {t: number, data: string}[], events: {name: string, t: number}[],
 *   voices: {voiceMs: number, bytes: number}[], problems: string[] }>}
 */
export const record = async ({ base, wav }) => {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      // %noloop：マイクを開くたびに、合成音を頭から1回だけ流す
      `--use-file-for-fake-audio-capture=${wav}%noloop`,
      "--autoplay-policy=no-user-gesture-required",
    ],
  });
  try {
    const context = await browser.newContext({
      viewport: VIEW,
      isMobile: true,
      hasTouch: true,
      permissions: ["microphone"],
    });
    const page = await context.newPage();

    // 外への通信やエラーがあれば、録画を使わない（呼ぶ側で止める）
    const problems = [];
    page.on("pageerror", (error) => problems.push(`error ${error.message}`));
    page.on("requestfailed", (request) => problems.push(`failed ${request.url()}`));
    page.on("request", (request) => {
      if (!request.url().startsWith(base)) problems.push(`external ${request.url()}`);
    });

    // 録画：ブラウザの画面の配信（CDP の screencast）からコマを受け取る。
    // Playwright の録画機能は、位置合わせ（シーク）のできない webm になったため使わない
    const frames = [];
    const cdp = await context.newCDPSession(page);
    cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
      frames.push({ t: metadata.timestamp, data });
      cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
    });
    await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92 });

    const events = [];
    const mark = (name) => events.push({ name, t: Date.now() / 1000 });
    const wait = (ms) => page.waitForTimeout(ms);
    const tap = (selector) => page.locator(selector).first().tap();
    const speaking = (on) =>
      page.waitForFunction(
        (want) => document.querySelector("[data-screen]").classList.contains("is-speaking") === want,
        on,
      );

    await page.goto(`${base}/index.html`);
    mark("top");
    await wait(2500);
    await tap(".menu__item--storybook");
    await page.waitForURL(/storybook/);
    mark("shelf");
    await wait(1200);

    for (const [index, layout] of LAYOUTS.entries()) {
      const n = index + 1;
      await tap(".page-new");
      mark(`edit${n}`);
      await wait(800);
      if ((await page.locator("[data-tools]").getAttribute("data-tool")) !== "stamp") {
        await tap("[data-switch]");
        await wait(300);
      }
      const box = await page.locator("[data-canvas]").boundingBox();
      let current = null;
      for (const [stamp, x, y] of layout) {
        if (stamp !== current) {
          await tap(`[data-tools] [data-stamp="${stamp}"]`);
          current = stamp;
          await wait(300);
        }
        await page.touchscreen.tap(box.x + box.width * x, box.y + box.height * y);
        await wait(450);
      }
      await wait(400);
      await tap("[data-record]");
      await page.waitForSelector('[data-recorder][data-state="recording"]');
      mark(`rec${n}-start`);
      await wait(RECORD_MS);
      await tap("[data-stop]");
      await page.waitForSelector('[data-recorder][data-state="recorded"]');
      mark(`rec${n}-stop`);
      await wait(900);
      await tap("[data-back]");
      await wait(1000);
    }

    mark("read");
    await tap("[data-read]");
    for (let i = 0; i < LAYOUTS.length; i += 1) {
      await page.waitForFunction(
        (n) => document.querySelectorAll(".read__dot")[n]?.classList.contains("is-current"),
        i,
      );
      await speaking(true);
      mark(`play${i + 1}-start`);
      await speaking(false);
      mark(`play${i + 1}-end`);
    }
    await wait(1500);
    await tap('a[aria-label="おうちに もどる"]');
    await page.waitForURL(/index\.html$/);
    mark("top-again");
    await wait(2000);

    // 声が保存されたか（長さと大きさだけを見る。中身は読まない）
    const voices = await page.evaluate(
      () =>
        new Promise((resolve, reject) => {
          const request = indexedDB.open("kids-play-storybook");
          request.onsuccess = () => {
            const all = request.result.transaction("pages").objectStore("pages").getAll();
            all.onsuccess = () =>
              resolve(all.result.map((p) => ({ voiceMs: p.voiceMs, bytes: p.voice?.size ?? 0 })));
            all.onerror = () => reject(all.error);
          };
          request.onerror = () => reject(request.error);
        }),
    );
    mark("end");
    await cdp.send("Page.stopScreencast");
    return { frames, events, voices, problems };
  } finally {
    await browser.close();
  }
};
