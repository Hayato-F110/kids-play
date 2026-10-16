// 受け取ったコマを 30fps に並べ直し、連番の JPEG・webm・音の WAV・時刻の一覧を作る

import { appendFileSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { PHRASE_SECONDS, phraseNotes, render, writeWav } from "./synth.mjs";

const FPS = 30;

// Playwright が配っている ffmpeg（npx playwright install ffmpeg で入る）を探す
export const findFfmpeg = () => {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const root = join(process.env.LOCALAPPDATA ?? "", "ms-playwright");
  const folder = readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith("ffmpeg-"))
    .map((entry) => entry.name)
    .sort()
    .at(-1);
  if (!folder) {
    throw new Error("ffmpeg が見つかりません。npx playwright install ffmpeg を実行してください。");
  }
  return join(root, folder, "ffmpeg-win64.exe");
};

/**
 * @param {{ frames: {t: number, data: string}[], events: {name: string, t: number}[],
 *   dest: string, work: string, ffmpeg: string }} options
 */
export const build = ({ frames, events, dest, work, ffmpeg }) => {
  const start = frames[0].t;
  const at = (name) => events.find((event) => event.name === name).t - start;
  const total = Math.floor(at("end") * FPS);

  // 画面が変わったときだけコマが届くので、各時刻に「その時点で最新のコマ」を置く
  const sequence = join(dest, "03_storybook_frames");
  rmSync(sequence, { recursive: true, force: true });
  mkdirSync(sequence, { recursive: true });
  // この ffmpeg はパイプを読めないので、JPEG をつなげた1つのファイル（MJPEG）にして渡す
  const stream = join(work, "frames.mjpeg");
  rmSync(stream, { force: true });
  let k = 0;
  for (let i = 0; i < total; i += 1) {
    const t = start + i / FPS;
    while (k + 1 < frames.length && frames[k + 1].t <= t) k += 1;
    const jpeg = Buffer.from(frames[k].data, "base64");
    writeFileSync(join(sequence, `frame_${String(i + 1).padStart(5, "0")}.jpg`), jpeg);
    appendFileSync(stream, jpeg);
  }
  // -g：1秒ごとにキーフレームを入れ、編集ソフトで好きな位置に飛べるようにする
  execFileSync(
    ffmpeg,
    [
      ...["-hide_banner", "-loglevel", "error", "-y"],
      ...["-f", "image2pipe", "-c:v", "mjpeg", "-framerate", String(FPS), "-i", stream],
      ...["-c:v", "libvpx", "-b:v", "8M", "-crf", "6", "-g", String(FPS), "-auto-alt-ref", "0"],
      join(dest, "03_storybook.webm"),
    ],
    { stdio: "inherit" },
  );
  rmSync(stream);

  // 音：録音の場面（PCのピアノをマイクに聞かせる）と、紙芝居の再生の場面に、同じ合成音を置く。
  // 画面なしのブラウザは音を出さないので、14日目に編集ソフトで映像に重ねる
  const pages = events.filter((event) => /^rec\d+-start$/.test(event.name)).length;
  const notes = [];
  for (let n = 1; n <= pages; n += 1) {
    notes.push(...phraseNotes(at(`rec${n}-start`)), ...phraseNotes(at(`play${n}-start`)));
  }
  writeWav(join(dest, "03_storybook_audio.wav"), render(notes, total / FPS + PHRASE_SECONDS));

  const seconds = (total / FPS).toFixed(1);
  const lines = events.map((event) => `${at(event.name).toFixed(2).padStart(6)}s  ${event.name}`);
  writeFileSync(
    join(dest, "03_storybook_timeline.txt"),
    `${FPS}fps、${total}コマ、${seconds}秒\n${lines.join("\n")}\n`,
  );
  return { total, seconds };
};
