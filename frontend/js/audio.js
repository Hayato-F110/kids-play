// 音を出すモジュール。全ミニアプリが、ここだけを通して音を鳴らす。
// 音量の上限、同時に鳴る数、消音の確認を1か所に集め、どの画面でも急な大音量が出ないようにする。

import { isMuted } from "./mute.js";

// 子ども向けなので控えめにする（docs/design.md の音量の方針）
const MASTER_VOLUME = 0.25;
// 連打や複数の指で音が重なり、合計の音量が大きくなるのを防ぐ
const MAX_VOICES = 8;
// 音の立ち上がりと終わりをなめらかにし、プチッという雑音を出さない
const ATTACK_SECONDS = 0.02;
const RELEASE_SECONDS = 0.1;
const SILENCE = 0.0001;

let context = null;
let master = null;
let activeVoices = 0;

// 最初に音を鳴らすときまで作らない。ブラウザは、操作の前に音を出すことを許さないため
const ensureContext = () => {
  if (context) {
    return context;
  }
  if (!window.AudioContext) {
    return null;
  }
  context = new AudioContext();
  master = context.createGain();
  master.gain.value = MASTER_VOLUME;
  master.connect(context.destination);
  return context;
};

// タッチでは、指を離したときに初めて音が許可される。
// 押した瞬間に頼んだ再開（resume）は保留になるので、離したときにもう一度頼んで通す
document.addEventListener("pointerup", () => {
  if (context && context.state === "suspended") {
    context.resume();
  }
});

const scheduleNote = (note, startAt) => {
  const { type = "sine", freq, at = 0, dur, gain = 1, vibrato } = note;
  const begin = startAt + at;
  const end = begin + dur;

  const oscillator = context.createOscillator();
  oscillator.type = type;

  // freq は通過する高さの並び。等間隔でなめらかにつなぐ（例：[650, 950, 600] は上がって下がる）
  const points = Array.isArray(freq) ? freq : [freq];
  oscillator.frequency.setValueAtTime(points[0], begin);
  for (let i = 1; i < points.length; i += 1) {
    oscillator.frequency.linearRampToValueAtTime(points[i], begin + (dur * i) / (points.length - 1));
  }

  const envelope = context.createGain();
  envelope.gain.setValueAtTime(SILENCE, begin);
  envelope.gain.linearRampToValueAtTime(gain, begin + ATTACK_SECONDS);
  envelope.gain.exponentialRampToValueAtTime(SILENCE, end);

  oscillator.connect(envelope);
  envelope.connect(master);

  // ビブラート：ゆっくりした別の波で、高さを細かく揺らす
  if (vibrato) {
    const lfo = context.createOscillator();
    lfo.frequency.value = vibrato.rate;
    const depth = context.createGain();
    depth.gain.value = vibrato.depth;
    lfo.connect(depth);
    depth.connect(oscillator.frequency);
    lfo.start(begin);
    lfo.stop(end);
  }

  activeVoices += 1;
  oscillator.addEventListener("ended", () => {
    activeVoices -= 1;
    envelope.disconnect();
  });
  oscillator.start(begin);
  oscillator.stop(end);
};

/**
 * 音の並びを鳴らす。
 * @param {Array<{type?: OscillatorType, freq: number | number[], at?: number, dur: number, gain?: number,
 *   vibrato?: {rate: number, depth: number}}>} notes at と dur は秒、freq は Hz、gain は 0〜1
 */
export const playNotes = (notes) => {
  if (isMuted()) {
    return;
  }
  if (!ensureContext()) {
    return;
  }
  if (activeVoices + notes.length > MAX_VOICES) {
    return;
  }

  const start = () => {
    // 再開を待つ間に消音された場合に備えて、もう一度確かめる
    if (isMuted()) {
      return;
    }
    for (const note of notes) {
      scheduleNote(note, context.currentTime);
    }
  };

  if (context.state === "running") {
    start();
  } else {
    context.resume().then(start, () => {});
  }
};

/**
 * 止めるまで鳴り続ける音を始める（ピアノの鍵盤など、押している間だけ鳴らすとき）。
 * @param {{type?: OscillatorType, freq: number, gain?: number}} tone freq は Hz、gain は 0〜1
 * @returns {(() => void) | null} 音を止める関数。鳴らせなかったとき（消音中、音の数が上限）は null
 */
export const startTone = ({ type = "sine", freq, gain = 1 }) => {
  if (isMuted()) {
    return null;
  }
  if (!ensureContext()) {
    return null;
  }
  if (activeVoices >= MAX_VOICES) {
    return null;
  }

  // 止まっている間は時計（currentTime）も進まないので、先に予約しておけば、再開したところから鳴り始める
  if (context.state !== "running") {
    context.resume().catch(() => {});
  }

  const startedAt = context.currentTime;

  const oscillator = context.createOscillator();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(freq, startedAt);

  const envelope = context.createGain();
  envelope.gain.setValueAtTime(SILENCE, startedAt);
  envelope.gain.linearRampToValueAtTime(gain, startedAt + ATTACK_SECONDS);

  oscillator.connect(envelope);
  envelope.connect(master);

  activeVoices += 1;
  oscillator.addEventListener("ended", () => {
    activeVoices -= 1;
    envelope.disconnect();
  });
  oscillator.start(startedAt);

  let stopped = false;
  return () => {
    // 2回呼ばれても、止める予約を重ねない
    if (stopped) {
      return;
    }
    stopped = true;

    // 立ち上がりの途中で切るとプチッと鳴るので、立ち上がりが終わってから下げ始める
    const releaseAt = Math.max(context.currentTime, startedAt + ATTACK_SECONDS);
    envelope.gain.setValueAtTime(gain, releaseAt);
    envelope.gain.exponentialRampToValueAtTime(SILENCE, releaseAt + RELEASE_SECONDS);
    oscillator.stop(releaseAt + RELEASE_SECONDS);
  };
};
