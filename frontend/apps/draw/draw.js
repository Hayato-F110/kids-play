// おえかきスタンプ：指やマウスで線を描き、スタンプを押し、PNGとして端末に保存する。
// 描いた絵は、この画面のキャンバスの中にだけある。どこにも送信しない（保存はダウンロードだけ）。

import { playNotes } from "../../js/audio.js";

// 線の太さとスタンプの大きさ（CSSのpx）。data-size の 1〜3 に対応する
const LINE_WIDTHS = [4, 10, 22];
const STAMP_SIZES = [48, 80, 120];
// 画素の細かい端末でも、キャンバスが大きくなりすぎてメモリを使いすぎないようにする
const MAX_PIXEL_RATIO = 3;
const PAPER_COLOR = "#ffffff";
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
const context = canvas.getContext("2d");

// いま持っている道具。画面の表示は、すべてここから作る（render）
const state = {
  tool: tools.dataset.tool,
  color: tools.dataset.color,
  size: Number(tools.dataset.size),
  stamp: "star",
};

// キャンバスの画素と、CSSのpxの比。紙を作り直したときに決まる
let pixelRatio = 1;
// まだ何も描いていない紙かどうか。白紙の間だけ、画面の大きさに合わせて紙を作り直す
let isBlank = true;
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

// ボタンの「押した」は click で受ける（キーボードでも動くため）
tools.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) {
    return;
  }
  if (button === switchButton) {
    state.tool = state.tool === "pen" ? "stamp" : "pen";
  } else if (button === sizeCycleButton) {
    state.size = (state.size % LINE_WIDTHS.length) + 1;
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

// ---- 紙 ----

// 紙を、いまの画面の大きさで作り直す（中身は白紙になる）
const resetPaper = () => {
  pixelRatio = Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO);
  canvas.width = Math.max(1, Math.round(paper.clientWidth * pixelRatio));
  canvas.height = Math.max(1, Math.round(paper.clientHeight * pixelRatio));
  // 透明のままだと、保存したPNGの背景が、見るアプリによって黒くなるため
  context.fillStyle = PAPER_COLOR;
  context.fillRect(0, 0, canvas.width, canvas.height);
  isBlank = true;
};

// 画面の向きや大きさが変わったとき。描いたあとは作り直さない（絵が消えたり、ぼやけたりするため）。
// そのときは、CSSの object-fit: contain が、絵を切らずに収めて見せる
new ResizeObserver(() => {
  if (isBlank) {
    resetPaper();
  }
}).observe(paper);

// 画面上の位置を、キャンバスの画素の位置に直す。object-fit: contain で上下か左右に余白ができる分も引く
const toPaperPoint = (event) => {
  const rect = canvas.getBoundingClientRect();
  const fit = Math.min(rect.width / canvas.width, rect.height / canvas.height);
  const left = rect.left + (rect.width - canvas.width * fit) / 2;
  const top = rect.top + (rect.height - canvas.height * fit) / 2;
  return { x: (event.clientX - left) / fit, y: (event.clientY - top) / fit };
};

// ---- 描く ----

// どの指（またはマウス）が、いまどんな線を描いているか。指ごとに分けて持つので、何本の指でも同時に描ける
const strokes = new Map();

// ペン（スタイラス）のときだけ、筆圧で太さを変える。指とマウスは筆圧が取れないので、いつも同じ太さ
const widthFor = (event, baseWidth) => {
  if (event.pointerType === "pen" && event.pressure > 0) {
    return baseWidth * (0.4 + event.pressure * 1.2);
  }
  return baseWidth;
};

const beginStroke = (event) => {
  const point = toPaperPoint(event);
  const stroke = {
    color: inkColor(),
    baseWidth: LINE_WIDTHS[state.size - 1] * pixelRatio,
    // 最後に描いた太さ。線の終わりを、直前と同じ太さでのばすために覚えておく
    width: 0,
    last: point,
    mid: point,
  };
  stroke.width = widthFor(event, stroke.baseWidth);
  strokes.set(event.pointerId, stroke);

  // 動かさずに離しても点が残るよう、最初に丸を1つ描く
  context.fillStyle = stroke.color;
  context.beginPath();
  context.arc(point.x, point.y, stroke.width / 2, 0, Math.PI * 2);
  context.fill();
};

// 前の点と今の点の「中間の点」どうしを曲線でつなぐ。点を直線で結ぶより、角ばらずなめらかになる
const extendStroke = (stroke, event) => {
  const point = toPaperPoint(event);
  const mid = { x: (stroke.last.x + point.x) / 2, y: (stroke.last.y + point.y) / 2 };
  stroke.width = widthFor(event, stroke.baseWidth);
  context.strokeStyle = stroke.color;
  context.lineWidth = stroke.width;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  context.moveTo(stroke.mid.x, stroke.mid.y);
  context.quadraticCurveTo(stroke.last.x, stroke.last.y, mid.x, mid.y);
  context.stroke();
  stroke.last = point;
  stroke.mid = mid;
};

const endStroke = (pointerId) => {
  const stroke = strokes.get(pointerId);
  if (!stroke) {
    return;
  }
  strokes.delete(pointerId);
  // 中間の点で止まっている線を、最後の点までのばす
  context.strokeStyle = stroke.color;
  context.lineWidth = stroke.width;
  context.lineCap = "round";
  context.beginPath();
  context.moveTo(stroke.mid.x, stroke.mid.y);
  context.lineTo(stroke.last.x, stroke.last.y);
  context.stroke();
};

const pressStamp = (event) => {
  const image = stampImage();
  // 絵の読み込みが終わる前に押したときは、何もしない
  if (!image || !image.complete || image.naturalWidth === 0) {
    return false;
  }
  const point = toPaperPoint(event);
  const size = STAMP_SIZES[state.size - 1] * pixelRatio;
  context.drawImage(image, point.x - size / 2, point.y - size / 2, size, size);
  playNotes(SOUNDS.stamp);
  return true;
};

canvas.addEventListener("pointerdown", (event) => {
  // マウスは左ボタンだけ
  if (event.pointerType === "mouse" && event.button !== 0) {
    return;
  }
  // 「けす？」を出している間のタップは、取り消しの合図として使い、描かない
  if (dismissedPointerId === event.pointerId) {
    return;
  }
  // 「描いた紙」にするのは、実際に描けたときだけ。白紙の間は、画面の大きさに合わせて紙を作り直せるため
  if (state.tool === "stamp") {
    if (pressStamp(event)) {
      isBlank = false;
    }
    return;
  }
  // 紙の外へ出たあとも、この指の動きを受け取り続けるため
  canvas.setPointerCapture(event.pointerId);
  beginStroke(event);
  isBlank = false;
});

canvas.addEventListener("pointermove", (event) => {
  const stroke = strokes.get(event.pointerId);
  if (!stroke) {
    return;
  }
  // 速く動かすと、ブラウザは途中の点をまとめて1回で知らせる。途中の点も使うと、線がなめらかになる
  const events = event.getCoalescedEvents ? event.getCoalescedEvents() : [];
  for (const moved of events.length > 0 ? events : [event]) {
    extendStroke(stroke, moved);
  }
});

canvas.addEventListener("pointerup", (event) => {
  endStroke(event.pointerId);
});

// 着信や通知などで、ブラウザが操作を取り上げたとき
canvas.addEventListener("pointercancel", (event) => {
  endStroke(event.pointerId);
});

// 長押しでメニューが出ると、子どもが遊びに戻れなくなるため（「画像を保存」などのメニューも出さない）
canvas.addEventListener("contextmenu", (event) => {
  event.preventDefault();
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
  strokes.clear();
  resetPaper();
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

// ---- ほぞん（PNGを端末にダウンロードするだけ。通信はしない）----

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

saveButton.addEventListener("click", () => {
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
    showSaved();
    playNotes(SOUNDS.save);
  }, "image/png");
});

resetPaper();
render();
