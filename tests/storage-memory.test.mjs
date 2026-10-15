// メモリ版の保存先（再読み込みで消える）を、保存のインターフェースの約束で確かめる
import { runStorageContract } from "./storage-contract.mjs";
import { createMemoryStorage } from "../frontend/js/storage/memory.js";

runStorageContract("メモリ", () => createMemoryStorage());
