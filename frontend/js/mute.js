// 消音の状態を持つモジュール。全画面と全ミニアプリが、ここだけを通して状態を読み書きする。
// 保存するのは消音かどうかの1ビットだけ（子どもの情報は入れない）。

// ほかのアプリの保存と重ならないよう、前置きを付ける
const STORAGE_KEY = "kids-play:muted";

// 保存できない環境（プライベートウィンドウなど）でも遊べるよう、失敗しても例外を外に出さない
const load = () => {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
};

const save = (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    // 保存できなくても、この画面の間は変数の値で動く
  }
};

// export しない。外から直接書き換えられると、保存されないまま状態だけ変わるため
let muted = load();

export const isMuted = () => muted;

export const setMuted = (value) => {
  muted = Boolean(value);
  save(muted);
};

export const toggleMuted = () => {
  setMuted(!muted);
  return muted;
};
