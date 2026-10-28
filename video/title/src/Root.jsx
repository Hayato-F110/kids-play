import { Composition } from "remotion";
import { KidsOutro } from "./KidsOutro.jsx";
import { KidsTitle } from "./KidsTitle.jsx";

// どちらも仕上がりの動画と同じ 1920×1080・30fps・5秒にする
const common = { durationInFrames: 150, fps: 30, width: 1920, height: 1080 };

export const Root = () => (
  <>
    {/* 絵コンテの #1（0:00〜0:05） */}
    <Composition id="KidsTitle" component={KidsTitle} {...common} />
    {/* 絵コンテの #7（0:55〜1:00） */}
    <Composition id="KidsOutro" component={KidsOutro} {...common} />
  </>
);
