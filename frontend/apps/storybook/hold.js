// 長押しの部品。押し続けた時間を数え、決めた時間に届いたら1回だけ知らせる。
// 消す操作を長押しにするのは、子どもがページを開くつもりのタップで、うっかり消さないようにするため（docs/design.md）。
// 時計（now、requestFrame）は差し替えられるようにして、テストで待たずに時間を進められるようにする

/**
 * @param {{
 *   ms: number,
 *   consumeAfter?: number,
 *   onProgress?: (value: number) => void,
 *   onDone?: () => void,
 *   onCancel?: () => void,
 *   now?: () => number,
 *   requestFrame?: (callback: () => void) => number,
 *   cancelFrame?: (id: number) => void,
 * }} options
 */
export const createHold = ({
  ms,
  // この進み具合より長く押してから離したときも、そのあとの click を食べる。
  // 輪が見えてから離すのは「消すのをやめた」操作で、ページを開くつもりではないため
  consumeAfter = 1,
  onProgress = () => {},
  onDone = () => {},
  onCancel = () => {},
  now = () => performance.now(),
  requestFrame = (callback) => requestAnimationFrame(callback),
  cancelFrame = (id) => cancelAnimationFrame(id),
}) => {
  let startedAt = 0;
  let frame = 0;
  let active = false;
  let progress = 0;
  // 長押しが終わったあと、指を離したときに出る click を1回だけ食べる
  let justDone = false;

  const tick = () => {
    const value = Math.min(1, (now() - startedAt) / ms);
    progress = value;
    onProgress(value);
    if (value >= 1) {
      active = false;
      justDone = true;
      onDone();
      return;
    }
    frame = requestFrame(tick);
  };

  return {
    get active() {
      return active;
    },

    start() {
      if (active) {
        return;
      }
      active = true;
      justDone = false;
      progress = 0;
      startedAt = now();
      onProgress(0);
      frame = requestFrame(tick);
    },

    cancel() {
      if (!active) {
        return;
      }
      active = false;
      cancelFrame(frame);
      justDone = progress >= consumeAfter;
      onCancel();
    },

    // click のときに呼ぶ。長押しの直後なら true を返す（そのタップではページを開かない）
    consumeClick() {
      const value = justDone;
      justDone = false;
      return value;
    },
  };
};
