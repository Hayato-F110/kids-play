// おえかきスタンプ：指やマウスで線を描き、スタンプを押し、PNGとして端末に保存する。
// 描いた絵は、この画面のキャンバスの中にだけある。どこにも送信しない（保存はダウンロードだけ）。

import { playNotes } from "../../js/audio.js";
import { createPaint, SIZE_STEPS } from "../../js/paint.js";

// ぜんぶけすの1回目のあと、何もしなければ元に戻すまでの時間。ほぞんの吹き出しを出しておく時間
const CLEAR_CONFIRM_MS = 4000;
const SAVED_NOTICE_MS = 2000;

const SOUNDS = {
  stamp: [{ type: "sine", freq: [520, 780], dur: 0.12, gain: 0.4 }],
  clear: [{ type: "triangle", freq: [620, 300], dur: 0.25, gain: 0.3 }],
  save: [
    { type: "triangle", freq: 523.25, dur: 0.15, gain: 0.3 },
    { type: "triangle", freq: 783.99, at: 0.12, dur: 0.25, gain: 0.3 },
  ],
};

const paper = document.querySelector("[data-paper]");
const canvas = document.querySelector("[data-canvas]");
const tools = document.querySelector("[data-tools]");
const clearButton = document.querySelector("[data-clear]");
const clearBubble = document.querySelector("[data-clear-bubble]");
const saveButton = document.querySelector("[data-save]");
const saveBubble = document.querySelector("[data-save-bubble]");
const sizeCycleButton = document.querySelector("[data-size-cycle]");
const switchButton = document.querySelector("[data-switch]");

// いま持っている道具。画面の表示は、すべてここから作る（render）
const state = {
  tool: tools.dataset.tool,
  color: tools.dataset.color,
  size: Number(tools.dataset.size),
  stamp: "star",
};

// 「けす？」を取り消したタップ。同じタップで線を描かないように覚えておく
let dismissedPointerId = null;

// ---- 道具の表示 ----

const render = () => {
  tools.dataset.tool = state.tool;
  tools.dataset.color = state.color;
  tools.dataset.size = String(state.size);

  for (const button of tools.querySelectorAll(".tools__group--colors [data-color]")) {
    const selected = state.tool === "pen" && button.dataset.color === state.color;
    button.setAttribute("aria-pressed", String(selected));
  }
  for (const button of tools.querySelectorAll(".tools__group--sizes [data-size]")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.size) === state.size));
  }
  for (const button of tools.querySelectorAll("[data-stamp]")) {
    const selected = state.tool === "stamp" && button.dataset.stamp === state.stamp;
    button.setAttribute("aria-pressed", String(selected));
  }
  switchButton.setAttribute("aria-label", state.tool === "pen" ? "すたんぷに かえる" : "ぺんに かえる");
};

// 色は tokens.css だけで決める。ここに色の値を書かず、ボタンの面の色を読んで使う
const inkColor = () => {
  const button = tools.querySelector(`.tools__group--colors [data-color="${state.color}"]`);
  return getComputedStyle(button).backgroundColor;
};

const stampImage = () => tools.querySelector(`[data-stamp="${state.stamp}"] img`);

const paint = createPaint({
  paper,
  canvas,
  getTool: () => ({ tool: state.tool, color: inkColor(), size: state.size, stampImage: stampImage() }),
  onStamp: () => playNotes(SOUNDS.stamp),
  // 「けす？」を出している間のタップは、取り消しの合図として使い、描かない
  shouldIgnore: (event) => dismissedPointerId === event.pointerId,
});

// ボタンの「押した」は click で受ける（キーボードでも動くため）
tools.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) {
    return;
  }
  if (button === switchButton) {
    state.tool = state.tool === "pen" ? "stamp" : "pen";
  } else if (button === sizeCycleButton) {
    state.size = (state.size % SIZE_STEPS) + 1;
  } else if (button.dataset.stamp) {
    state.tool = "stamp";
    state.stamp = button.dataset.stamp;
  } else if (button.dataset.color) {
    state.tool = "pen";
    state.color = button.dataset.color;
  } else if (button.dataset.size) {
    state.size = Number(button.dataset.size);
  }
  render();
});

// ---- ぜんぶけす（1回目で確かめ、2回目で消す）----

let clearTimer = 0;

const isClearArmed = () => clearButton.classList.contains("is-armed");

const setClearArmed = (armed) => {
  clearTimeout(clearTimer);
  clearButton.classList.toggle("is-armed", armed);
  clearButton.setAttribute("aria-label", armed ? "もういちど おすと ぜんぶ きえる" : "ぜんぶ けす");
  clearBubble.hidden = !armed;
  paper.classList.toggle("is-fading", armed);
  if (armed) {
    clearTimer = setTimeout(() => {
      setClearArmed(false);
    }, CLEAR_CONFIRM_MS);
  }
};

clearButton.addEventListener("click", () => {
  if (!isClearArmed()) {
    setClearArmed(true);
    return;
  }
  setClearArmed(false);
  paint.clear();
  playNotes(SOUNDS.clear);
});

// ほかの場所を押したら、消さずに元に戻す。capture にして、紙や道具の処理より先に受ける
document.addEventListener(
  "pointerdown",
  (event) => {
    dismissedPointerId = null;
    if (isClearArmed() && !clearButton.contains(event.target)) {
      setClearArmed(false);
      dismissedPointerId = event.pointerId;
    }
  },
  { capture: true },
);

// ---- ほぞん（PNGを端末に保存するだけ。通信はしない）----
// ブラウザとPWAは、ダウンロードとして保存する。
// Androidアプリ版は、ダウンロードを受け取れないので、アプリ側の入口（PictureSaver）から「ピクチャ」に保存する

// Androidアプリ版（Capacitor）のときだけ入る。ブラウザとPWAでは undefined
const nativeApp = window.Capacitor?.isNativePlatform?.() ? window.Capacitor : undefined;
const pictureSaver = nativeApp?.Plugins?.PictureSaver;

let savedTimer = 0;

// ファイル名には日時だけを入れる（名前など、個人が分かるものを入れない）
const fileName = () => {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  return `oekaki-${date}-${time}.png`;
};

const showSaved = () => {
  clearTimeout(savedTimer);
  saveButton.classList.add("is-done");
  saveBubble.hidden = false;
  savedTimer = setTimeout(() => {
    saveButton.classList.remove("is-done");
    saveBubble.hidden = true;
  }, SAVED_NOTICE_MS);
};

const notifySaved = () => {
  showSaved();
  playNotes(SOUNDS.save);
};

// アプリ版で保存できない端末（古いAndroid）では、押しても残らないボタンを出さない
if (nativeApp) {
  const hideSave = () => {
    saveButton.closest(".action").hidden = true;
  };
  if (pictureSaver) {
    pictureSaver.canSave().then(({ value }) => !value && hideSave(), hideSave);
  } else {
    hideSave();
  }
}

saveButton.addEventListener("click", () => {
  if (pictureSaver) {
    // 保存できたときだけ「できた」を出す。できなかったときは、何も起こさない（失敗の表示は出さない）
    const data = canvas.toDataURL("image/png").split(",")[1];
    pictureSaver.savePng({ fileName: fileName(), data }).then(notifySaved, () => {});
    return;
  }
  canvas.toBlob((blob) => {
    // 画像にできなかったとき（メモリ不足など）は、何も起こさない。失敗の表示は出さない
    if (!blob) {
      return;
    }
    // 画像のデータを、この端末の中だけで通じる一時的なURLにして、ダウンロードのリンクを押したことにする
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName();
    link.click();
    // 使い終わったURLを捨てて、画像の分のメモリを返す。すぐ捨てるとダウンロードが始まらないことがあるので、少し待つ
    setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 1000);
    notifySaved();
  }, "image/png");
});

render();
