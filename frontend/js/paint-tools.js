// 道具のボタン（色、太さ、スタンプ、ペンとスタンプの切り替え）。おえかきとえほんで同じものを使う。
// ボタンの並びと見た目は HTML と draw.css が持ち、ここは「いま持っている道具」を覚えて表示を合わせる。

import { SIZE_STEPS } from "./paint.js";

/**
 * @param {HTMLElement} tools data-tools の箱。data-tool、data-color、data-size に最初の道具を書いておく
 * @returns {{getTool: () => {tool: "pen" | "stamp", color: string, size: number, stampImage: HTMLImageElement | null}}}
 *   getTool は paint.js の createPaint にそのまま渡せる
 */
export const createPaintTools = (tools) => {
  const sizeCycleButton = tools.querySelector("[data-size-cycle]");
  const switchButton = tools.querySelector("[data-switch]");

  // いま持っている道具。画面の表示は、すべてここから作る（render）
  const state = {
    tool: tools.dataset.tool,
    color: tools.dataset.color,
    size: Number(tools.dataset.size),
    stamp: "star",
  };

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

  render();

  return {
    getTool: () => ({ tool: state.tool, color: inkColor(), size: state.size, stampImage: stampImage() }),
  };
};
