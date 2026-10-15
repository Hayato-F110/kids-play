// 録音の部品。マイクを使う時間をできるだけ短くし、録った声はこの画面のメモリにだけ置く。
// マイクと MediaRecorder は外から渡す（テストでは偽物に差し替え、本物の声を使わずに確かめるため）。
//
// 状態：idle（録る前）→ asking（マイクの許可を待つ）→ recording → recorded（声がある）
//       許可されなかった・マイクがないときは unavailable（画面は録音ボタンをうすくするだけ）

import { MAX_VOICE_MS } from "../../js/storage/validate.js";

/**
 * @param {{
 *   getUserMedia: (constraints: MediaStreamConstraints) => Promise<MediaStream>,
 *   MediaRecorder: typeof MediaRecorder,
 *   now?: () => number,
 *   setTimer?: (fn: () => void, ms: number) => unknown,
 *   clearTimer?: (id: unknown) => void,
 *   onChange?: (state: string) => void,
 * }} deps
 */
export const createRecorder = ({
  getUserMedia,
  MediaRecorder,
  now = () => performance.now(),
  setTimer = (fn, ms) => setTimeout(fn, ms),
  clearTimer = (id) => clearTimeout(id),
  onChange = () => {},
}) => {
  let state = "idle";
  let result = null;
  let stream = null;
  let mediaRecorder = null;
  let startedAt = 0;
  let timer = null;
  // start のたびに増やす。許可を待つ間に cancel されたとき、遅れて届いたマイクを使わずに手放すため
  let attempt = 0;

  const setState = (next) => {
    state = next;
    onChange(next);
  };

  // マイクを手放す。ブラウザの「マイク使用中」の表示もこれで消える（T-06）
  const releaseMicrophone = () => {
    if (stream) {
      for (const track of stream.getTracks()) {
        track.stop();
      }
      stream = null;
    }
    if (timer !== null) {
      clearTimer(timer);
      timer = null;
    }
  };

  const start = async () => {
    if (state === "asking" || state === "recording") {
      return;
    }
    attempt += 1;
    const myAttempt = attempt;
    result = null;
    setState("asking");

    let given;
    try {
      // 録音ボタンを押したときだけ、ここでマイクを求める（C-10）。カメラは求めない
      given = await getUserMedia({ audio: true, video: false });
    } catch {
      setState("unavailable");
      return;
    }
    if (myAttempt !== attempt) {
      for (const track of given.getTracks()) {
        track.stop();
      }
      return;
    }
    stream = given;

    const chunks = [];
    const recorder = new MediaRecorder(stream);
    mediaRecorder = recorder;
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    });
    recorder.addEventListener("stop", () => {
      const ms = Math.min(now() - startedAt, MAX_VOICE_MS);
      releaseMicrophone();
      if (mediaRecorder === recorder) {
        mediaRecorder = null;
      }
      // cancel で止めたときは、声を残さない
      if (myAttempt !== attempt || chunks.length === 0) {
        setState("idle");
        return;
      }
      const type = chunks[0].type || recorder.mimeType || "audio/webm";
      result = { blob: new Blob(chunks, { type }), ms: Math.round(ms) };
      setState("recorded");
    });

    startedAt = now();
    recorder.start();
    // 30秒で止める。保存の規則（MAX_VOICE_MS）と同じ値を使う
    timer = setTimer(() => {
      timer = null;
      stop();
    }, MAX_VOICE_MS);
    setState("recording");
  };

  const stop = () => {
    if (state !== "recording" || !mediaRecorder) {
      return;
    }
    mediaRecorder.stop();
  };

  // とりなおす：前の声を捨てて、録る前に戻る
  const reset = () => {
    if (state === "recording" || state === "asking") {
      cancel();
      return;
    }
    result = null;
    setState("idle");
  };

  // 画面を離れるとき：録音中なら声を残さず止め、マイクを手放す
  const cancel = () => {
    attempt += 1;
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    releaseMicrophone();
    mediaRecorder = null;
    result = null;
    if (state !== "idle") {
      setState("idle");
    }
  };

  return {
    get state() {
      return state;
    },
    get result() {
      return result;
    },
    // 録音中の進み具合（0〜1）。満ちていく輪に使う。数字は画面に出さない
    progress: () => (state === "recording" ? Math.min((now() - startedAt) / MAX_VOICE_MS, 1) : 0),
    start,
    stop,
    reset,
    cancel,
  };
};
