// 長押しの部品（hold.js）のテスト。時計は偽物を渡し、待たずに時間を進める
import assert from "node:assert/strict";
import { test } from "node:test";

import { createHold } from "../frontend/apps/storybook/hold.js";

// 偽の時計：advance(ms) で時間を進め、そのあいだの「次の描画」を順に呼ぶ
const createClock = () => {
  let time = 0;
  let frames = [];
  return {
    now: () => time,
    requestFrame: (callback) => {
      frames.push(callback);
      return frames.length;
    },
    cancelFrame: () => {
      frames = [];
    },
    advance(ms, step = 16) {
      for (let passed = 0; passed < ms; passed += step) {
        time += step;
        const due = frames;
        frames = [];
        for (const callback of due) callback();
      }
    },
  };
};

const setup = (ms = 2000, options = {}) => {
  const clock = createClock();
  const log = { done: 0, progress: [], cancel: 0 };
  const hold = createHold({
    ...options,
    ms,
    now: clock.now,
    requestFrame: clock.requestFrame,
    cancelFrame: clock.cancelFrame,
    onProgress: (value) => log.progress.push(value),
    onDone: () => {
      log.done += 1;
    },
    onCancel: () => {
      log.cancel += 1;
    },
  });
  return { clock, log, hold };
};

test("長押し：決めた時間まで押し続けると、1回だけ終わりの合図が出る", () => {
  const { clock, log, hold } = setup(2000);
  hold.start();
  clock.advance(1900);
  assert.equal(log.done, 0);
  clock.advance(200);
  assert.equal(log.done, 1);
  clock.advance(2000);
  assert.equal(log.done, 1);
  assert.equal(hold.active, false);
});

test("長押し：途中で離すと終わらず、取り消しの合図が出る", () => {
  const { clock, log, hold } = setup(2000);
  hold.start();
  clock.advance(1000);
  hold.cancel();
  clock.advance(3000);
  assert.equal(log.done, 0);
  assert.equal(log.cancel, 1);
  assert.equal(hold.active, false);
});

test("長押し：進み具合は 0 から 1 へ増え、1 を超えない", () => {
  const { clock, log, hold } = setup(2000);
  hold.start();
  clock.advance(2100);
  assert.equal(log.progress[0], 0);
  assert.equal(log.progress.at(-1), 1);
  for (let i = 1; i < log.progress.length; i += 1) {
    assert.ok(log.progress[i] >= log.progress[i - 1]);
  }
  assert.ok(log.progress.every((value) => value >= 0 && value <= 1));
});

test("長押し：押していないときの取り消しは、何もしない", () => {
  const { log, hold } = setup();
  hold.cancel();
  assert.equal(log.cancel, 0);
});

test("長押し：終わった直後のタップは「長押しのあと」と分かる。次のタップからは普通に戻る", () => {
  const { clock, hold } = setup(2000);
  hold.start();
  clock.advance(2100);
  // 指を離したときに出る click を、ページを開く操作として扱わないため
  assert.equal(hold.consumeClick(), true);
  assert.equal(hold.consumeClick(), false);
});

test("長押し：途中で離したあとのタップは、普通のタップ", () => {
  const { clock, hold } = setup(2000);
  hold.start();
  clock.advance(300);
  hold.cancel();
  assert.equal(hold.consumeClick(), false);
});

// 輪が見えてから離したのは「消すのをやめた」操作で、ページを開くつもりのタップではないため
test("長押し：consumeAfter を超えて押してから離したタップも、長押しのあとと分かる", () => {
  const { clock, hold } = setup(2000, { consumeAfter: 0.1 });
  hold.start();
  clock.advance(600);
  hold.cancel();
  assert.equal(hold.consumeClick(), true);
  assert.equal(hold.consumeClick(), false);
});

test("長押し：consumeAfter に届く前に離したタップは、普通のタップ", () => {
  const { clock, hold } = setup(2000, { consumeAfter: 0.1 });
  hold.start();
  clock.advance(100);
  hold.cancel();
  assert.equal(hold.consumeClick(), false);
});

test("長押し：押している間にもう一度押しても、始め直さない（2本指など）", () => {
  const { clock, log, hold } = setup(2000);
  hold.start();
  clock.advance(1500);
  hold.start();
  clock.advance(600);
  assert.equal(log.done, 1);
});
