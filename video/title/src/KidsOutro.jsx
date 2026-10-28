import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { color, fontRounded } from "./theme.js";

// 絵コンテの #7（0:55〜1:00）。作った流れを左から右へ1つずつ出し、最後に守りの要点を2つ見せる
const STEPS = [
  { label: "Web", tint: color.primary },
  { label: "PWA", tint: color.accent3 },
  { label: "Android", tint: color.accent1 },
  { label: "Docker", tint: color.accent4 },
  { label: "AWS", tint: color.accent2 },
];
const POINTS = ["絵と声は 端末の中だけ", "鍵を置かない 自動デプロイ（OIDC）"];

export const KidsOutro = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const fadeOut = interpolate(frame, [durationInFrames - 15, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: color.bg,
        alignItems: "center",
        justifyContent: "center",
        fontFamily: fontRounded,
      }}
    >
      <div
        style={{ opacity: fadeOut, display: "flex", flexDirection: "column", alignItems: "center", gap: 90 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {STEPS.map((step, i) => {
            const s = spring({ frame: frame - i * 6, fps, config: { damping: 11 } });
            return (
              <div key={step.label} style={{ display: "flex", alignItems: "center", gap: 20 }}>
                {i > 0 && <span style={{ fontSize: 52, color: color.textSoft, opacity: s }}>→</span>}
                <div
                  style={{
                    transform: `scale(${s})`,
                    backgroundColor: step.tint,
                    color: "#ffffff",
                    fontSize: 52,
                    fontWeight: 800,
                    padding: "20px 32px",
                    borderRadius: 36,
                    border: `6px solid ${color.text}`,
                  }}
                >
                  {step.label}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20 }}>
          {POINTS.map((text, i) => {
            const t = interpolate(frame, [40 + i * 12, 55 + i * 12], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <div
                key={text}
                style={{
                  fontSize: 72,
                  fontWeight: 800,
                  color: color.text,
                  opacity: t,
                  transform: `translateY(${(1 - t) * 24}px)`,
                }}
              >
                {text}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
