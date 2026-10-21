// サーバー保存（FastAPI 版）を、保存のインターフェースの約束で確かめる。使い方：npm run test:server
//
// 本物の FastAPI を、空の一時 DB で起動して試す。uv が必要なので、ふだんの npm test には入れていない。
// 起動は 127.0.0.1 だけで待ち受け、DB は OS の一時フォルダに作って最後に消す（子どものデータの置き場所は使わない）
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, before } from "node:test";
import { fileURLToPath } from "node:url";

import { runStorageContract } from "./storage-contract.mjs";
import { createServerStorage } from "../frontend/js/storage/server.js";

const PORT = 8011;
const base = `http://127.0.0.1:${PORT}`;
const backend = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const workDir = mkdtempSync(join(tmpdir(), "kids-play-test-"));

let server;

const waitForServer = async () => {
  for (let i = 0; i < 100; i += 1) {
    try {
      const response = await fetch(`${base}/api/storage/status`);
      if ((await response.json()).enabled === true) {
        return;
      }
    } catch {
      // まだ起動していない
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("サーバーが起動しない");
};

// uv は中で Python（uvicorn）を動かす。Windows では uv を止めても Python が残るので、子のプロセスごと止める
const stopServer = () => {
  if (!server?.pid) {
    return;
  }
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    server.kill();
  }
};

before(async () => {
  // 前回の残りなど、別のサーバーがすでにいたら止める。古いサーバー（DB が消えたもの）に話しかけないため
  const alreadyRunning = await fetch(`${base}/api/storage/status`).then(
    () => true,
    () => false,
  );
  if (alreadyRunning) {
    throw new Error(`ポート ${PORT} がすでに使われている。前回のテストのサーバーが残っていないか確かめる`);
  }
  server = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "app.main:create_app_from_env",
      "--factory",
      "--host",
      "127.0.0.1",
      "--port",
      String(PORT),
    ],
    {
      cwd: backend,
      env: { ...process.env, KIDS_SERVER_STORAGE: "enabled", KIDS_DB_PATH: join(workDir, "test.sqlite3") },
      stdio: "ignore",
    },
  );
  await waitForServer();
});

after(() => {
  stopServer();
  rmSync(workDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
});

// テストごとに空から始める（約束のテストは、はじめが空であることを前提にしている）
runStorageContract("サーバー（FastAPI）", async () => {
  const storage = createServerStorage({ base });
  await storage.deleteAll();
  return storage;
});
