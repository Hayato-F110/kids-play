// ESLint の設定。フロントエンド（ブラウザで動く ES Modules）を対象にする。
// 整形は Prettier に任せ、ここでは「まちがい」と「危ない書き方」だけを見る。

import js from "@eslint/js";
import nounsanitized from "eslint-plugin-no-unsanitized";
import globals from "globals";
import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    files: ["frontend/**/*.js"],
    plugins: { js, nounsanitized },
    extends: ["js/recommended"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: globals.browser,
    },
    rules: {
      // XSS対策：文字列をHTMLとして解釈させる書き方（innerHTML、insertAdjacentHTML など）を禁止する。
      // 画面の書き換えは textContent と createElement で行う（CLAUDE.md のコーディング規約）
      "nounsanitized/property": "error",
      "nounsanitized/method": "error",

      // 文字列をコードとして実行する書き方を禁止する
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-script-url": "error",

      // コーディング規約：const 優先、var は使わない、比較は === で行う
      "prefer-const": "error",
      "no-var": "error",
      eqeqeq: "error",
    },
  },
  {
    // 補助スクリプトは Node で動く。ブラウザの中で動かす部分（page.evaluate など）があるので、両方の名前を許す
    files: ["scripts/**/*.mjs"],
    plugins: { js },
    extends: ["js/recommended"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.node, ...globals.browser },
    },
    rules: {
      "prefer-const": "error",
      "no-var": "error",
      eqeqeq: "error",
    },
  },
  {
    // Service Worker は、ページとは別の場所で動く。使える名前（self、caches、clients）がページと違う
    files: ["frontend/sw.js"],
    languageOptions: {
      sourceType: "script",
      globals: globals.serviceworker,
    },
  },
]);
