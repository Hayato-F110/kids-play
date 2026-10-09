// 全画面で読み込む。消音ボタンの表示を、mute.js が持つ状態に合わせる。
import { isMuted, toggleMuted } from "./mute.js";

const button = document.querySelector("[data-mute-button]");
const label = document.querySelector("[data-mute-label]");

const render = () => {
  const muted = isMuted();
  // 見た目は aria-pressed だけで切り替える（base.css）。状態の置き場を1つにして、表示とのずれを防ぐため
  button.setAttribute("aria-pressed", String(muted));
  label.textContent = muted ? "おとを だす" : "おとを けす";
};

if (button && label) {
  // ボタンの「押した」は click で受ける。タッチ・マウスに加えてキーボードでも動くため。
  // 遊びの面（鍵盤、キャンバスなど）は、押している間の動きが要るので Pointer Events を使う
  button.addEventListener("click", () => {
    toggleMuted();
    render();
  });
  render();
}
