import { Config } from "@remotion/cli/config";

Config.setEntryPoint("./src/index.js");
// 素材はコピーせず、アプリの自作SVGをそのまま読む（同じ絵を2か所に置かないため）
Config.setPublicDir("../../frontend/assets");
