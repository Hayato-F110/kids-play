import { Composition } from "remotion";
import { KidsTitle } from "./KidsTitle.jsx";

// 絵コンテの #1（0:00〜0:05）。仕上がりの動画と同じ 1920×1080・30fps にする
export const Root = () => (
  <Composition
    id="KidsTitle"
    component={KidsTitle}
    durationInFrames={150}
    fps={30}
    width={1920}
    height={1080}
  />
);
