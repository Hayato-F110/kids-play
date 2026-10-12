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

// Service Worker（sw.js）を登録する。ファイルを端末に保存し、電波がなくても遊べるようにするため。
// PC内のサーバー（localhost）では登録しない。作業中のファイルより、保存した古いファイルが先に出て、確認を誤るため。
// 6日目のAndroidアプリ（Capacitor）も localhost で動くが、ファイルがアプリに入っているので、登録は要らない。
// PC内で試すときだけ、URLの末尾に ?sw を付ける
const isLocal = ["localhost", "127.0.0.1"].includes(location.hostname);
const wantsWorker = !isLocal || new URLSearchParams(location.search).has("sw");
if ("serviceWorker" in navigator && wantsWorker) {
  // main.js から見た位置で指定する（どのフォルダのページから読まれても、同じ sw.js を指す）
  navigator.serviceWorker.register(new URL("../sw.js", import.meta.url)).catch(() => {
    // 登録できなくても、電波があれば遊べる。子どもの画面にはエラーを出さない
  });
}
