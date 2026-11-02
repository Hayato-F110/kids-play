// ルールセット（main-require-ci）の試験用。CI が赤の PR を main に入れられないことを確かめるため、わざと失敗させる。
// この PR はマージせずに閉じる
import { test } from "node:test";
import assert from "node:assert/strict";

test("わざと失敗する", () => {
  assert.equal(1, 2);
});
