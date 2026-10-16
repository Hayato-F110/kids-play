// 紹介動画の素材③（えほん）を、画面なしの Edge で録る。録り方と理由は docs/video-storyboard.md
//
// 使い方（リポジトリの直下で、PowerShell）：
//   python -m http.server 8000 --directory frontend   # 別のターミナルで動かしておく
//   npm run record:storybook
//
// 必要なもの：Edge、Playwright（環境変数 PLAYWRIGHT でフォルダを指定できる）、
// Playwright の ffmpeg（npx playwright install ffmpeg）。
// 出力は video/raw/（gitignore 済み）。子どもの絵や声は使わず、自作のスタンプと合成音だけで録る

import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { build, findFfmpeg } from "./build.mjs";
import { record } from "./record.mjs";
import { PHRASE_SECONDS, phraseNotes, render, writeWav } from "./synth.mjs";

const BASE = "http://localhost:8000";
const dest = resolve("video/raw");

const response = await fetch(`${BASE}/index.html`).catch(() => null);
if (!response?.ok) {
  throw new Error(
    `${BASE} に つながりません。先に python -m http.server 8000 --directory frontend を動かしてください。`,
  );
}
const ffmpeg = findFfmpeg();

const work = mkdtempSync(join(tmpdir(), "record-storybook-"));
try {
  const wav = join(work, "phrase.wav");
  writeWav(wav, render(phraseNotes(), PHRASE_SECONDS));

  const { frames, events, voices, problems } = await record({ base: BASE, wav });
  if (problems.length > 0) {
    throw new Error(`録画中に問題がありました。素材は作りません：\n${problems.join("\n")}`);
  }
  if (voices.length !== 3 || voices.some((voice) => voice.bytes === 0)) {
    throw new Error(`声が保存されていません：${JSON.stringify(voices)}`);
  }

  mkdirSync(dest, { recursive: true });
  const { total, seconds } = build({ frames, events, dest, work, ffmpeg });
  console.log(`できた：${dest}（${total}コマ、${seconds}秒）`);
  console.log(`声：${voices.map((voice) => `${voice.voiceMs}ms`).join("、")}`);
} finally {
  rmSync(work, { recursive: true, force: true });
}
