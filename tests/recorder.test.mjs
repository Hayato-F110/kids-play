// 録音の部品のテスト。マイクと MediaRecorder は偽物に差し替える（本物の声は使わない）
import assert from "node:assert/strict";
import { test } from "node:test";

import { createRecorder } from "../frontend/apps/storybook/recorder.js";
import { MAX_VOICE_MS } from "../frontend/js/storage/validate.js";

// 偽物の部品と、テストから操作するための入口をまとめて作る
const setup = ({ allow = true, chunks = ["voice"], failOn = null, delayStop = false } = {}) => {
  const calls = { getUserMedia: [], trackStops: 0 };
  let clock = 0;
  let timer = null;
  // 録音ごとに別のマイク（stream）を渡す。どの録音のマイクが止められたかを区別するため
  const streams = [];
  const createStream = () => {
    const stream = {
      stopped: 0,
      getTracks: () => [{ stop: () => ((stream.stopped += 1), (calls.trackStops += 1)) }],
    };
    streams.push(stream);
    return stream;
  };
  const pendingStops = [];

  class FakeMediaRecorder extends EventTarget {
    constructor() {
      super();
      if (failOn === "create") {
        throw new Error("NotSupportedError");
      }
      this.mimeType = "audio/webm";
      this.state = "inactive";
    }
    start() {
      if (failOn === "start") {
        throw new Error("InvalidStateError");
      }
      this.state = "recording";
    }
    stop() {
      this.state = "inactive";
      // 本物のブラウザでは、止めた合図（stop）は少し遅れて届く
      if (delayStop) {
        pendingStops.push(() => this.finish());
        return;
      }
      this.finish();
    }
    finish() {
      for (const chunk of chunks) {
        const event = new Event("dataavailable");
        event.data = new Blob([chunk], { type: "audio/webm" });
        this.dispatchEvent(event);
      }
      this.dispatchEvent(new Event("stop"));
    }
  }

  const changes = [];
  const recorder = createRecorder({
    getUserMedia: async (constraints) => {
      calls.getUserMedia.push(constraints);
      if (!allow) {
        throw new Error("NotAllowedError");
      }
      return createStream();
    },
    MediaRecorder: FakeMediaRecorder,
    now: () => clock,
    setTimer: (fn, ms) => {
      timer = { fn, ms };
      return 1;
    },
    clearTimer: () => {
      timer = null;
    },
    onChange: (state) => changes.push(state),
  });

  return {
    recorder,
    calls,
    changes,
    advance: (ms) => {
      clock += ms;
    },
    fireTimer: () => {
      clock += timer.ms;
      timer.fn();
    },
    hasTimer: () => timer !== null,
    streams,
    flushStops: () => pendingStops.splice(0).forEach((fn) => fn()),
  };
};

test("はじめは idle。録音ボタンを押すまでマイクを求めない（C-10）", () => {
  const { recorder, calls } = setup();
  assert.equal(recorder.state, "idle");
  assert.equal(calls.getUserMedia.length, 0);
});

test("start で、音だけを求めて録音が始まる（カメラは求めない）", async () => {
  const { recorder, calls, changes } = setup();
  await recorder.start();
  assert.equal(recorder.state, "recording");
  assert.deepEqual(calls.getUserMedia, [{ audio: true, video: false }]);
  assert.deepEqual(changes, ["asking", "recording"]);
});

test("stop で録音が止まり、声と長さが残る。マイクを手放す", async () => {
  const { recorder, calls, advance } = setup();
  await recorder.start();
  advance(1500);
  recorder.stop();
  assert.equal(recorder.state, "recorded");
  assert.equal(recorder.result.ms, 1500);
  assert.equal(recorder.result.blob.type, "audio/webm");
  assert.equal(await recorder.result.blob.text(), "voice");
  assert.equal(calls.trackStops, 1);
});

test(`${MAX_VOICE_MS / 1000}秒で自動で止まる。長さは上限を超えない`, async () => {
  const { recorder, fireTimer, calls } = setup();
  await recorder.start();
  fireTimer();
  assert.equal(recorder.state, "recorded");
  assert.equal(recorder.result.ms, MAX_VOICE_MS);
  assert.equal(calls.trackStops, 1);
});

test("止めたあとは、30秒のタイマーが残らない", async () => {
  const { recorder, hasTimer } = setup();
  await recorder.start();
  recorder.stop();
  assert.equal(hasTimer(), false);
});

test("録音中の進み具合（0〜1）が分かる。満ちていく輪に使う", async () => {
  const { recorder, advance } = setup();
  assert.equal(recorder.progress(), 0);
  await recorder.start();
  advance(MAX_VOICE_MS / 2);
  assert.equal(recorder.progress(), 0.5);
});

test("マイクを許可されなかったら unavailable。例外を外に出さない", async () => {
  const { recorder } = setup({ allow: false });
  await recorder.start();
  assert.equal(recorder.state, "unavailable");
  assert.equal(recorder.result, null);
});

test("録音中にもう一度 start しても、マイクを二重に求めない", async () => {
  const { recorder, calls } = setup();
  await recorder.start();
  await recorder.start();
  assert.equal(calls.getUserMedia.length, 1);
});

test("とりなおす（reset）で idle に戻り、前の声を捨てる", async () => {
  const { recorder } = setup();
  await recorder.start();
  recorder.stop();
  recorder.reset();
  assert.equal(recorder.state, "idle");
  assert.equal(recorder.result, null);
});

test("録音中に画面を離れたら（cancel）、声を残さずマイクを手放す", async () => {
  const { recorder, calls, hasTimer } = setup();
  await recorder.start();
  recorder.cancel();
  assert.equal(recorder.state, "idle");
  assert.equal(recorder.result, null);
  assert.equal(calls.trackStops, 1);
  assert.equal(hasTimer(), false);
});

test("何も録れていなければ（データが空）、idle に戻る", async () => {
  const { recorder } = setup({ chunks: [] });
  await recorder.start();
  recorder.stop();
  assert.equal(recorder.state, "idle");
  assert.equal(recorder.result, null);
});

for (const failOn of ["create", "start"]) {
  test(`録音の準備に失敗しても（${failOn}）、マイクを手放して unavailable になる`, async () => {
    const { recorder, calls, hasTimer } = setup({ failOn });
    await recorder.start();
    assert.equal(recorder.state, "unavailable");
    assert.equal(calls.trackStops, 1);
    assert.equal(hasTimer(), false);
  });
}

test("止めた直後に録り直しても、前の録音の遅れた合図で、新しい録音のマイクを止めない", async () => {
  const { recorder, streams, flushStops, hasTimer } = setup({ delayStop: true });
  await recorder.start();
  recorder.cancel();
  await recorder.start();
  flushStops();
  assert.equal(recorder.state, "recording");
  assert.equal(streams[0].stopped, 1);
  assert.equal(streams[1].stopped, 0);
  assert.equal(hasTimer(), true);
});

test("許可を待つ間に cancel したあと、遅れて届いた拒否で unavailable にしない", async () => {
  let reject;
  const recorder = createRecorder({
    getUserMedia: () => new Promise((_, no) => (reject = no)),
    MediaRecorder: class {},
  });
  const starting = recorder.start();
  recorder.cancel();
  reject(new Error("NotAllowedError"));
  await starting;
  assert.equal(recorder.state, "idle");
});
