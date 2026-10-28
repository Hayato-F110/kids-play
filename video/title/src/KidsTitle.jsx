import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { color, fontRounded } from "./theme.js";

const TITLE = "キッズあそびランド";
const LETTER_COLORS = [color.primary, color.accent2, color.accent1, color.accent3, color.accent4];

const STAMPS = [
  { file: "stamps/star.svg", x: 180, y: 140, delay: 30, size: 200 },
  { file: "stamps/heart.svg", x: 1540, y: 120, delay: 36, size: 190 },
  { file: "stamps/flower.svg", x: 120, y: 800, delay: 42, size: 200 },
  { file: "stamps/sun.svg", x: 1600, y: 790, delay: 48, size: 210 },
];

const Stamp = ({ file, x, y, delay, size }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame: frame - delay, fps, config: { damping: 9 } });
  // ゆっくり揺らして、止まった絵に見えないようにする（激しい動きにはしない）
  const sway = Math.sin((frame - delay) / 12) * 4;
  return (
    <Img
      src={staticFile(file)}
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        height: size,
        transform: `scale(${pop}) rotate(${sway}deg)`,
      }}
    />
  );
};

export const KidsTitle = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const iconPop = spring({ frame, fps, config: { damping: 10 } });
  const subtitleIn = interpolate(frame, [60, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // 最後の0.5秒で背景色へ溶かし、次の場面へのつなぎを編集ソフトに任せなくてよいようにする
  const fadeOut = interpolate(frame, [durationInFrames - 15, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: color.bg }}>
      <AbsoluteFill style={{ opacity: fadeOut }}>
        {STAMPS.map((s) => (
          <Stamp key={s.file} {...s} />
        ))}
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
          <Img
            src={staticFile("icons/icon.svg")}
            style={{ width: 300, height: 300, transform: `scale(${iconPop})` }}
          />
          <div
            style={{
              marginTop: 40,
              fontFamily: fontRounded,
              fontSize: 150,
              fontWeight: 800,
              letterSpacing: 6,
              display: "flex",
            }}
          >
            {[...TITLE].map((ch, i) => {
              // 1文字ずつ、ぽんっと跳ねて出す
              const s = spring({ frame: frame - 12 - i * 3, fps, config: { damping: 8 } });
              return (
                <span
                  key={i}
                  style={{
                    color: LETTER_COLORS[i % LETTER_COLORS.length],
                    display: "inline-block",
                    transform: `translateY(${(1 - s) * 120}px) scale(${s})`,
                  }}
                >
                  {ch}
                </span>
              );
            })}
          </div>
          <div
            style={{
              marginTop: 30,
              fontFamily: fontRounded,
              fontSize: 52,
              fontWeight: 700,
              color: color.textSoft,
              opacity: subtitleIn,
              transform: `translateY(${(1 - subtitleIn) * 20}px)`,
            }}
          >
            Web ・ PWA ・ Android ・ AWS
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
