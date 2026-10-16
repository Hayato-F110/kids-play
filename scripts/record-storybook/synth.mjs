// ピアノと同じ作り（三角波、立ち上がり → 減衰）の合成音を、WAV（16bit、48kHz、モノラル）にする。
// 素材③の偽のマイクに流す音と、動画に重ねる音の両方に使う。人の声は使わない

import { writeFileSync } from "node:fs";

const RATE = 48000;
// frontend/apps/piano/piano.js の NOTES と同じ高さ
const NOTES = { c4: 261.63, d4: 293.66, e4: 329.63, g4: 392.0 };
// 1回の「ピアノを弾く」：ド・レ・ミ・ソ
const PHRASE = [
  { note: "c4", at: 0.2 },
  { note: "d4", at: 0.7 },
  { note: "e4", at: 1.2 },
  { note: "g4", at: 1.7 },
];
export const PHRASE_SECONDS = 3.0;
const NOTE_SECONDS = 0.6;
const ATTACK_SECONDS = 0.02;

const triangle = (phase) => 1 - 4 * Math.abs(Math.round(phase - 0.25) - (phase - 0.25));

// offset 秒から始まる、1回分の音の並び
export const phraseNotes = (offset = 0) =>
  PHRASE.map(({ note, at }) => ({ freq: NOTES[note], at: offset + at }));

// 音の並び [{ freq, at }] を、長さ seconds の波形にする
export const render = (notes, seconds, gain = 0.35) => {
  const samples = new Float32Array(Math.ceil(seconds * RATE));
  const length = Math.floor(NOTE_SECONDS * RATE);
  for (const { freq, at } of notes) {
    const start = Math.floor(at * RATE);
    for (let i = 0; i < length && start + i < samples.length; i += 1) {
      const t = i / RATE;
      const attack = Math.min(t / ATTACK_SECONDS, 1);
      const decay = Math.exp((-5 * t) / NOTE_SECONDS);
      samples[start + i] += gain * attack * decay * triangle(freq * t);
    }
  }
  return samples;
};

export const writeWav = (path, samples) => {
  const data = Buffer.alloc(samples.length * 2);
  samples.forEach((value, i) => {
    data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, value)) * 32767), i * 2);
  });
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16); // fmt の大きさ
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(1, 22); // モノラル
  header.writeUInt32LE(RATE, 24);
  header.writeUInt32LE(RATE * 2, 28); // 1秒あたりのバイト数
  header.writeUInt16LE(2, 32); // 1サンプルのバイト数
  header.writeUInt16LE(16, 34); // ビット数
  header.write("data", 36);
  header.writeUInt32LE(data.length, 40);
  writeFileSync(path, Buffer.concat([header, data]));
};
