// どうぶつタッチ：動物を押すと、動いて鳴く。正解も順番もない。

import { playNotes } from "../../js/audio.js";

// 鳴き声は録音を使わず、波の形と高さの変化だけで作る（素材のルール：音は Web Audio API で生成）。
// at と dur は秒、freq は Hz。配列は「この高さを順に通る」という意味
const CRIES = {
  // わん わん：高いところから急に下がる短い音を2回
  dog: [
    { type: "square", freq: [480, 220], at: 0, dur: 0.13, gain: 0.45 },
    { type: "square", freq: [480, 220], at: 0.22, dur: 0.13, gain: 0.45 },
  ],
  // にゃー：上がってから下がる、なめらかな音
  cat: [{ type: "triangle", freq: [650, 950, 600], dur: 0.5, gain: 0.8 }],
  // もー：低く長い音が少しずつ下がる
  cow: [{ type: "sawtooth", freq: [150, 135, 120], dur: 0.9, gain: 0.45 }],
  // ぴよ ぴよ ぴよ：高く短い音が上がる
  chick: [
    { type: "sine", freq: [1800, 2600], at: 0, dur: 0.08, gain: 0.5 },
    { type: "sine", freq: [1800, 2600], at: 0.14, dur: 0.08, gain: 0.5 },
    { type: "sine", freq: [1800, 2600], at: 0.28, dur: 0.08, gain: 0.5 },
  ],
  // けろ けろ：短い音2つの組を2回
  frog: [
    { type: "square", freq: [300, 420], at: 0, dur: 0.09, gain: 0.35 },
    { type: "square", freq: [300, 420], at: 0.12, dur: 0.09, gain: 0.35 },
    { type: "square", freq: [300, 420], at: 0.34, dur: 0.09, gain: 0.35 },
    { type: "square", freq: [300, 420], at: 0.46, dur: 0.09, gain: 0.35 },
  ],
  // めー：ふるえる音（ビブラート）
  sheep: [
    { type: "triangle", freq: [500, 460], dur: 0.7, gain: 0.7, vibrato: { rate: 9, depth: 28 } },
  ],
};

const play = (button) => {
  const cry = CRIES[button.dataset.animal];
  if (cry) {
    playNotes(cry);
  }

  // 連打したとき、動きを最初からやり直す。
  // クラスを外してすぐ付けるだけでは、ブラウザが「変化なし」とまとめてしまうので、
  // 間に大きさを読んで、外した状態をいったん確定させる
  button.classList.remove("is-playing");
  void button.offsetWidth;
  button.classList.add("is-playing");
};

for (const button of document.querySelectorAll("[data-animal]")) {
  // 押した瞬間に反応させたいので、click ではなく pointerdown を使う（タッチとマウスの両方に届く）
  button.addEventListener("pointerdown", (event) => {
    // マウスは左ボタンだけ
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    play(button);
  });

  // キーボード（Enter、スペース）で押したときは pointerdown が来ない。
  // そのときの click は detail が 0 になるので、それだけを拾う（二重に鳴らさないため）
  button.addEventListener("click", (event) => {
    if (event.detail === 0) {
      play(button);
    }
  });

  button.addEventListener("animationend", () => {
    button.classList.remove("is-playing");
  });
}
