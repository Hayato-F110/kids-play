// わたしのえほん：ページごとに絵を描いて声を録り、「よむ」で1ページめから順に見せて鳴らす（紙芝居）。
// 絵と声は、保存のインターフェース（docs/storage-interface.md）だけを通して保存する。どこにも送信しない。

import { playRecording } from "../../js/audio.js";
import { createPaint } from "../../js/paint.js";
import { createPaintTools } from "../../js/paint-tools.js";
import { createMemoryStorage } from "../../js/storage/memory.js";
import { MAX_PAGES } from "../../js/storage/validate.js";
import { createRecorder } from "./recorder.js";

// 保存先。9日目に IndexedDB 版へ差し替える（KIDS-31）。今はメモリなので、再読み込みで消える
const storage = createMemoryStorage();

// 描き終えてから保存するまでの間。線を引くたびに画像を作り直さないようにするため
const SAVE_DELAY_MS = 600;
// よむ：声のないページを見せておく時間と、声が終わってから次のページへ進むまでの間
const READ_PAGE_MS = 4000;
const READ_GAP_MS = 800;
// 満ちていく輪の円周（storybook.css の stroke-dasharray と同じ値）
const RING_LENGTH = 415;

const screen = document.querySelector("[data-screen]");
const announcer = document.querySelector("[data-announce]");
const shelfGrid = document.querySelector("[data-shelf-grid]");
const readButton = document.querySelector("[data-read]");
const backButton = document.querySelector("[data-back]");
const editNumber = document.querySelector("[data-edit-number]");
const paper = document.querySelector("[data-paper]");
const canvas = document.querySelector("[data-canvas]");
const voiceBadge = document.querySelector("[data-voice-badge]");
const recorderBox = document.querySelector("[data-recorder]");
const recordButton = document.querySelector("[data-record]");
const stopButton = document.querySelector("[data-stop]");
const retakeButton = document.querySelector("[data-retake]");
const listenButton = document.querySelector("[data-listen]");
const ring = document.querySelector("[data-ring]");
const readCanvas = document.querySelector("[data-read-canvas]");
const readDots = document.querySelector("[data-read-dots]");
const prevButton = document.querySelector("[data-prev]");
const nextButton = document.querySelector("[data-next]");

const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()));

// 読み上げに知らせる。中身の文字を変えたときだけ読み上げられるので、textContent を書き換える
const announce = (text) => {
  announcer.textContent = text;
};

const setView = (view) => {
  screen.dataset.view = view;
};

// SVG の部品を作る（innerHTML を使わないため）
const SVG_NS = "http://www.w3.org/2000/svg";
const createIcon = (viewBox, paths) => {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", viewBox);
  svg.setAttribute("aria-hidden", "true");
  for (const d of paths) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
};

// キャンバスの画素を、画面に出ている大きさに合わせる（ぼやけないように）
const fitCanvas = (target) => {
  const ratio = Math.min(window.devicePixelRatio || 1, 3);
  target.width = Math.max(1, Math.round(target.clientWidth * ratio));
  target.height = Math.max(1, Math.round(target.clientHeight * ratio));
};

// 絵を、キャンバスの真ん中に、切らず・伸ばさずに収めて描く
const drawPicture = async (target, blob) => {
  const context = target.getContext("2d");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, target.width, target.height);
  if (!blob) {
    return;
  }
  try {
    const bitmap = await createImageBitmap(blob);
    const fit = Math.min(target.width / bitmap.width, target.height / bitmap.height);
    const width = bitmap.width * fit;
    const height = bitmap.height * fit;
    context.drawImage(bitmap, (target.width - width) / 2, (target.height - height) / 2, width, height);
    bitmap.close();
  } catch {
    // 読めない絵は白い紙のまま見せる。子どもの画面にはエラーを出さない
  }
};

// ===== ほんだな =====

const createPageButton = (page, index) => {
  const button = document.createElement("button");
  button.className = "btn page";
  button.type = "button";
  button.setAttribute("aria-label", `${index + 1}ぺーじめ${page.voice ? " こえ あり" : ""}`);

  // 絵は、ほんだなに並べて大きさが決まってから描く（renderShelf）
  const picture = document.createElement("canvas");
  picture.className = "page__pic";

  const number = document.createElement("span");
  number.className = "page__num";
  number.textContent = String(index + 1);

  button.append(picture, number);
  if (page.voice) {
    const voice = document.createElement("span");
    voice.className = "page__voice";
    voice.append(createIcon("0 0 24 24", ["M5 10v4M9.5 6v12M14.5 8v8M19 11v2"]));
    button.append(voice);
  }
  button.addEventListener("click", () => openEditor(page.id, index));
  return button;
};

const createNewPageButton = (index) => {
  const button = document.createElement("button");
  button.className = "page-new";
  button.type = "button";
  button.setAttribute("aria-label", "あたらしい ぺーじ");
  button.append(createIcon("0 0 48 48", ["M24 10v28M10 24h28"]));
  button.addEventListener("click", () => openEditor(null, index));
  return button;
};

const renderShelf = async () => {
  const pages = await storage.listPages();
  const items = pages.map(createPageButton);
  if (pages.length < MAX_PAGES) {
    items.push(createNewPageButton(pages.length));
  }
  // まだ使っていない枠。あと何ページ描けるかを、数字ではなく枠の数で見せる
  while (items.length < MAX_PAGES) {
    const slot = document.createElement("div");
    slot.className = "page-slot";
    slot.setAttribute("aria-hidden", "true");
    items.push(slot);
  }
  shelfGrid.replaceChildren(...items);
  // 紙の形が枠と違っても、絵を切らずに収める（端に描いたものも見えるように）
  for (const [index, picture] of [...shelfGrid.querySelectorAll(".page__pic")].entries()) {
    fitCanvas(picture);
    drawPicture(picture, pages[index].picture);
  }
  // ページがないときは「よむ」をうすくする（押せないことを、失敗ではなく形で伝える）
  readButton.disabled = pages.length === 0;
};

// ===== ページを作る =====

// いま作っているページ。id は、はじめて保存したときに保存先が付ける
const editing = { id: null, voice: null, voiceMs: 0 };

const paintTools = createPaintTools(document.querySelector("[data-tools]"));

let saveTimer = 0;
// 保存を1つずつ順に行う。前の保存が終わる前に次を始めると、新しいページが2つできてしまうため
let saving = Promise.resolve();

const saveNow = () => {
  clearTimeout(saveTimer);
  saving = saving.then(async () => {
    const picture = paint.isBlank() ? null : await paint.toBlob();
    // 何も描かず、何も録っていない新しいページは保存しない
    if (!editing.id && !picture && !editing.voice) {
      return;
    }
    try {
      const saved = await storage.savePage({
        ...(editing.id ? { id: editing.id } : {}),
        picture,
        voice: editing.voice,
        voiceMs: editing.voiceMs,
      });
      editing.id = saved.id;
    } catch {
      // 保存できなくても、子どもの画面にはエラーを出さない（ほんだなに戻ったときに並ばないだけ）
    }
  });
  return saving;
};

const saveSoon = () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveNow, SAVE_DELAY_MS);
};

const paint = createPaint({ paper, canvas, getTool: paintTools.getTool, onChange: saveSoon });

// ---- きく（録った声を確かめる）----

let stopListening = null;

const setListening = (stop) => {
  stopListening = stop;
  listenButton.setAttribute("aria-pressed", String(Boolean(stop)));
};

const endListening = () => {
  const stop = stopListening;
  setListening(null);
  stop?.();
};

listenButton.addEventListener("click", async () => {
  if (stopListening) {
    endListening();
    return;
  }
  if (!editing.voice) {
    return;
  }
  const stop = await playRecording(editing.voice, () => {
    if (stopListening === stop) {
      setListening(null);
    }
  });
  if (stop) {
    setListening(stop);
  }
});

// ---- 録音 ----

const canRecord = Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);

const recorder = createRecorder({
  getUserMedia: (constraints) => navigator.mediaDevices.getUserMedia(constraints),
  MediaRecorder: window.MediaRecorder,
  onChange: (state) => {
    if (state === "recorded") {
      editing.voice = recorder.result.blob;
      editing.voiceMs = recorder.result.ms;
      saveNow();
    }
    renderRecorder();
  },
});

// 録音の場所に出すもの。とりなおしの録音が途中で終わっても、前の声は残っているので「録ったあと」に戻す
const recorderView = () => {
  if (recorder.state === "asking" || recorder.state === "recording") {
    return recorder.state;
  }
  if (editing.voice) {
    return "recorded";
  }
  if (!canRecord || recorder.state === "unavailable") {
    return "unavailable";
  }
  return "idle";
};

const updateRing = () => {
  // SVG の属性ではなく style に書く。storybook.css の初期値（空の輪）は、属性より強く効いてしまうため
  ring.style.strokeDashoffset = String(RING_LENGTH * (1 - recorder.progress()));
  if (recorder.state === "recording") {
    requestAnimationFrame(updateRing);
  }
};

const renderRecorder = () => {
  const view = recorderView();
  // 押せないときは disabled にする（見た目だけでなく、キーボードと読み上げでも押せないように）
  recordButton.disabled = view === "unavailable" || view === "asking";
  if (view !== recorderBox.dataset.state) {
    announce(view === "recording" ? "ろくおんちゅう" : "");
  }
  recorderBox.dataset.state = view;
  screen.classList.toggle("is-recording", view === "recording");
  voiceBadge.hidden = !editing.voice;
  if (view === "recording") {
    updateRing();
  }
};

recordButton.addEventListener("click", () => {
  if (canRecord) {
    recorder.start();
  }
});

stopButton.addEventListener("click", () => {
  recorder.stop();
});

// とりなおす：すぐに新しい録音を始める。新しい声が録れたら、前の声と入れ替わる
retakeButton.addEventListener("click", () => {
  endListening();
  if (canRecord) {
    recorder.start();
  }
});

// ---- 場面の行き来 ----

const openEditor = async (id, index) => {
  const page = id ? await storage.getPage(id) : null;
  editing.id = page ? page.id : null;
  editing.voice = page ? page.voice : null;
  editing.voiceMs = page ? page.voiceMs : 0;
  editNumber.textContent = String(index + 1);
  recorder.reset();
  setView("edit");
  renderRecorder();
  // 紙が画面に出て、大きさが決まってから描き直す
  await nextFrame();
  if (page?.picture) {
    await paint.load(page.picture);
  } else {
    paint.clear();
  }
};

// ページを作る・よむ場面を離れるとき：録音と声を止める（録音中の声は残さない）
const leaveScene = () => {
  recorder.cancel();
  endListening();
  stopReading();
};

backButton.addEventListener("click", async () => {
  const fromEdit = screen.dataset.view === "edit";
  leaveScene();
  if (fromEdit) {
    await saveNow();
  }
  setView("shelf");
  renderShelf();
});

// 画面が隠れたら（ほかのアプリへ切り替え、画面を消す）、録音と声を止める。
// 見ていない間に録音が続かないようにするため（T-06）
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    leaveScene();
    renderRecorder();
  }
});

// ===== よむ =====

const reading = { pages: [], index: 0, stop: null, timer: 0, token: 0 };

const stopReading = () => {
  // 番号を進めてから止める。止めたときの「鳴り終わった」の知らせで、次のページへ進まないようにするため
  reading.token += 1;
  clearTimeout(reading.timer);
  const stop = reading.stop;
  reading.stop = null;
  stop?.();
  screen.classList.remove("is-speaking");
};

const advance = () => {
  if (reading.index < reading.pages.length - 1) {
    showReadPage(reading.index + 1);
  }
};

const showReadPage = async (index) => {
  stopReading();
  const token = reading.token;
  reading.index = index;
  const page = reading.pages[index];

  for (const [i, dot] of [...readDots.children].entries()) {
    dot.classList.toggle("is-current", i === index);
  }
  announce(`${index + 1}ぺーじめ`);
  prevButton.disabled = index === 0;
  nextButton.disabled = index === reading.pages.length - 1;
  readCanvas.setAttribute("aria-label", `${index + 1}ぺーじめの え`);

  fitCanvas(readCanvas);
  await drawPicture(readCanvas, page.picture);
  if (token !== reading.token) {
    return;
  }

  // 声がない、または鳴らせない（消音中など）ときは、絵をしばらく見せてから次へ
  const stop = page.voice
    ? await playRecording(page.voice, () => {
        if (token === reading.token) {
          screen.classList.remove("is-speaking");
          reading.timer = setTimeout(advance, READ_GAP_MS);
        }
      })
    : null;
  if (token !== reading.token) {
    stop?.();
    return;
  }
  if (stop) {
    reading.stop = stop;
    screen.classList.add("is-speaking");
  } else {
    reading.timer = setTimeout(advance, READ_PAGE_MS);
  }
};

readButton.addEventListener("click", async () => {
  const pages = await storage.listPages();
  if (pages.length === 0) {
    return;
  }
  reading.pages = pages;
  const dots = pages.map(() => {
    const dot = document.createElement("span");
    dot.className = "read__dot";
    return dot;
  });
  readDots.replaceChildren(...dots);
  setView("read");
  await nextFrame();
  showReadPage(0);
});

prevButton.addEventListener("click", () => {
  if (reading.index > 0) {
    showReadPage(reading.index - 1);
  }
});

nextButton.addEventListener("click", advance);

renderShelf();
