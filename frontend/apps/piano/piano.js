// おとあそびピアノ：鍵盤を押している間だけ、光って音が鳴る。手本も採点もない。

import { playNotes, startTone } from "../../js/audio.js";

// 鍵盤の data-note と、音の高さ（Hz）の対応。ド〜高いド
const NOTES = {
  c4: 261.63,
  d4: 293.66,
  e4: 329.63,
  f4: 349.23,
  g4: 392.0,
  a4: 440.0,
  b4: 493.88,
  c5: 523.25,
};

// やわらかい音にする。8音が重なっても大きくなりすぎない音量（0.3 × 8 × 全体の音量 0.25 = 0.6）
const TONE_TYPE = "triangle";
const TONE_GAIN = 0.3;
// キーボードで押したときは「押している間」が分からないので、決まった長さで鳴らす
const KEYBOARD_NOTE_SECONDS = 0.4;

const keys = document.querySelector(".keys");

// どの指（またはマウス）が、いまどの鍵盤を押しているか。指ごとに分けて持つので、同時押しができる。
// key は、鍵盤のすき間の上にいる間は null。stop は、消音中などで鳴らせなかったときは null
const pointers = new Map();

// 画面のその場所にある鍵盤を返す。押した要素ではなく場所で調べるのは、
// タッチでは、指をすべらせても「最初に押した鍵盤」にイベントが届き続けるため
const keyAt = (x, y) => {
  const element = document.elementFromPoint(x, y);
  const key = element ? element.closest("[data-note]") : null;
  return key && keys.contains(key) ? key : null;
};

// 2本の指が同じ鍵盤にいるとき、片方を離しても光ったままにする
const updateLight = (key) => {
  const isDown = [...pointers.values()].some((held) => held.key === key);
  key.classList.toggle("is-down", isDown);
};

const press = (pointerId, key) => {
  const stop = key
    ? startTone({ type: TONE_TYPE, freq: NOTES[key.dataset.note], gain: TONE_GAIN })
    : null;
  pointers.set(pointerId, { key, stop });
  if (key) {
    updateLight(key);
  }
};

const release = (pointerId) => {
  const held = pointers.get(pointerId);
  if (!held) {
    return;
  }
  pointers.delete(pointerId);
  if (held.stop) {
    held.stop();
  }
  if (held.key) {
    updateLight(held.key);
  }
};

// 音が鳴りっぱなしにならないよう、まとめて止める
const releaseAll = () => {
  for (const pointerId of [...pointers.keys()]) {
    release(pointerId);
  }
};

keys.addEventListener("pointerdown", (event) => {
  // マウスは左ボタンだけ
  if (event.pointerType === "mouse" && event.button !== 0) {
    return;
  }
  // すき間を押したときも覚えておく。そのまますべらせて鍵盤に入れば鳴るようにするため
  press(event.pointerId, keyAt(event.clientX, event.clientY));
});

// 動きと離す操作は document で受ける。鍵盤の外へ出たあとも追いかけて、確実に止めるため
document.addEventListener("pointermove", (event) => {
  const held = pointers.get(event.pointerId);
  if (!held) {
    return;
  }
  // 画面の外でマウスのボタンを離すと pointerup が届かないことがあるので、ここでも確かめる
  if (event.pointerType === "mouse" && (event.buttons & 1) === 0) {
    release(event.pointerId);
    return;
  }
  const key = keyAt(event.clientX, event.clientY);
  if (key === held.key) {
    return;
  }
  // 指をすべらせて別の鍵盤に入った：前の音を止めて、次の音を鳴らす
  release(event.pointerId);
  press(event.pointerId, key);
});

document.addEventListener("pointerup", (event) => {
  release(event.pointerId);
});

// 着信や通知などで、ブラウザが操作を取り上げたとき
document.addEventListener("pointercancel", (event) => {
  release(event.pointerId);
});

// 画面が隠れたとき（別のタブ、ホーム画面、別のページ）は、離す操作が届かないことがある
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    releaseAll();
  }
});
window.addEventListener("pagehide", releaseAll);
window.addEventListener("blur", releaseAll);

// 押している最中に消音されたら、すぐに止める
const muteButton = document.querySelector("[data-mute-button]");
if (muteButton) {
  muteButton.addEventListener("click", releaseAll);
}

// 長押しでメニューが出ると、子どもが遊びに戻れなくなるため
keys.addEventListener("contextmenu", (event) => {
  event.preventDefault();
});

// キーボード（Enter、スペース）で押したときは pointerdown が来ない。
// そのときの click は detail が 0 になるので、それだけを拾う（二重に鳴らさないため）
keys.addEventListener("click", (event) => {
  if (event.detail !== 0) {
    return;
  }
  const key = event.target.closest("[data-note]");
  if (!key) {
    return;
  }
  playNotes([
    { type: TONE_TYPE, freq: NOTES[key.dataset.note], dur: KEYBOARD_NOTE_SECONDS, gain: TONE_GAIN },
  ]);
  key.classList.add("is-down");
  setTimeout(() => {
    updateLight(key);
  }, KEYBOARD_NOTE_SECONDS * 1000);
});
