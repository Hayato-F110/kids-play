// 描く部品。紙（キャンバス）、ペンの線、スタンプを受け持つ。
// おえかきとえほんが同じ道具で描けるよう、描く処理をここに集める。道具のボタンや保存は、使う側の画面が持つ。

// 太さ（スタンプのときは大きさ）の3段階。CSSのpxで書き、画素の比を掛けて使う
const LINE_WIDTHS = [4, 10, 22];
const STAMP_SIZES = [48, 80, 120];
export const SIZE_STEPS = LINE_WIDTHS.length;
// 画素を増やしすぎると、高精細な端末でメモリを使いすぎるため
const MAX_PIXEL_RATIO = 3;
const PAPER_COLOR = "#ffffff";

/**
 * 紙に描けるようにする。
 * @param {{
 *   paper: HTMLElement,
 *   canvas: HTMLCanvasElement,
 *   getTool: () => {tool: "pen" | "stamp", color: string, size: number, stampImage: HTMLImageElement | null},
 *   onStamp?: () => void,
 *   shouldIgnore?: (event: PointerEvent) => boolean,
 * }} options getTool は、いま持っている道具（color は CSS の色、size は 1〜SIZE_STEPS）。
 *   onStamp はスタンプを押せたとき、shouldIgnore は描かずに捨てるタップを決めるときに呼ぶ
 */
export const createPaint = ({ paper, canvas, getTool, onStamp = () => {}, shouldIgnore = () => false }) => {
  const context = canvas.getContext("2d");

  // キャンバスの画素と、CSSのpxの比。紙を作り直したときに決まる
  let pixelRatio = 1;
  // まだ何も描いていない紙かどうか。白紙の間だけ、画面の大きさに合わせて紙を作り直す
  let isBlank = true;

  // ---- 紙 ----

  // 紙を、いまの画面の大きさで作り直す（中身は白紙になる）
  const resetPaper = () => {
    pixelRatio = Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO);
    canvas.width = Math.max(1, Math.round(paper.clientWidth * pixelRatio));
    canvas.height = Math.max(1, Math.round(paper.clientHeight * pixelRatio));
    // 透明のままだと、保存したPNGの背景が、見るアプリによって黒くなるため
    context.fillStyle = PAPER_COLOR;
    context.fillRect(0, 0, canvas.width, canvas.height);
    isBlank = true;
  };

  // 画面の向きや大きさが変わったとき。描いたあとは作り直さない（絵が消えたり、ぼやけたりするため）。
  // そのときは、CSSの object-fit: contain が、絵を切らずに収めて見せる
  new ResizeObserver(() => {
    if (isBlank) {
      resetPaper();
    }
  }).observe(paper);

  // 画面上の位置を、キャンバスの画素の位置に直す。object-fit: contain で上下か左右に余白ができる分も引く
  const toPaperPoint = (event) => {
    const rect = canvas.getBoundingClientRect();
    const fit = Math.min(rect.width / canvas.width, rect.height / canvas.height);
    const left = rect.left + (rect.width - canvas.width * fit) / 2;
    const top = rect.top + (rect.height - canvas.height * fit) / 2;
    return { x: (event.clientX - left) / fit, y: (event.clientY - top) / fit };
  };

  // ---- 描く ----

  // どの指（またはマウス）が、いまどんな線を描いているか。指ごとに分けて持つので、何本の指でも同時に描ける
  const strokes = new Map();

  // ペン（スタイラス）のときだけ、筆圧で太さを変える。指とマウスは筆圧が取れないので、いつも同じ太さ
  const widthFor = (event, baseWidth) => {
    if (event.pointerType === "pen" && event.pressure > 0) {
      return baseWidth * (0.4 + event.pressure * 1.2);
    }
    return baseWidth;
  };

  const beginStroke = (event, tool) => {
    const point = toPaperPoint(event);
    const stroke = {
      color: tool.color,
      baseWidth: LINE_WIDTHS[tool.size - 1] * pixelRatio,
      // 最後に描いた太さ。線の終わりを、直前と同じ太さでのばすために覚えておく
      width: 0,
      last: point,
      mid: point,
    };
    stroke.width = widthFor(event, stroke.baseWidth);
    strokes.set(event.pointerId, stroke);

    // 動かさずに離しても点が残るよう、最初に丸を1つ描く
    context.fillStyle = stroke.color;
    context.beginPath();
    context.arc(point.x, point.y, stroke.width / 2, 0, Math.PI * 2);
    context.fill();
  };

  // 前の点と今の点の「中間の点」どうしを曲線でつなぐ。点を直線で結ぶより、角ばらずなめらかになる
  const extendStroke = (stroke, event) => {
    const point = toPaperPoint(event);
    const mid = { x: (stroke.last.x + point.x) / 2, y: (stroke.last.y + point.y) / 2 };
    stroke.width = widthFor(event, stroke.baseWidth);
    context.strokeStyle = stroke.color;
    context.lineWidth = stroke.width;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(stroke.mid.x, stroke.mid.y);
    context.quadraticCurveTo(stroke.last.x, stroke.last.y, mid.x, mid.y);
    context.stroke();
    stroke.last = point;
    stroke.mid = mid;
  };

  const endStroke = (pointerId) => {
    const stroke = strokes.get(pointerId);
    if (!stroke) {
      return;
    }
    strokes.delete(pointerId);
    // 中間の点で止まっている線を、最後の点までのばす
    context.strokeStyle = stroke.color;
    context.lineWidth = stroke.width;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(stroke.mid.x, stroke.mid.y);
    context.lineTo(stroke.last.x, stroke.last.y);
    context.stroke();
  };

  const pressStamp = (event, tool) => {
    const image = tool.stampImage;
    // 絵の読み込みが終わる前に押したときは、何もしない
    if (!image || !image.complete || image.naturalWidth === 0) {
      return false;
    }
    const point = toPaperPoint(event);
    const size = STAMP_SIZES[tool.size - 1] * pixelRatio;
    context.drawImage(image, point.x - size / 2, point.y - size / 2, size, size);
    onStamp();
    return true;
  };

  canvas.addEventListener("pointerdown", (event) => {
    // マウスは左ボタンだけ
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    if (shouldIgnore(event)) {
      return;
    }
    const tool = getTool();
    // 「描いた紙」にするのは、実際に描けたときだけ。白紙の間は、画面の大きさに合わせて紙を作り直せるため
    if (tool.tool === "stamp") {
      if (pressStamp(event, tool)) {
        isBlank = false;
      }
      return;
    }
    // 紙の外へ出たあとも、この指の動きを受け取り続けるため
    canvas.setPointerCapture(event.pointerId);
    beginStroke(event, tool);
    isBlank = false;
  });

  canvas.addEventListener("pointermove", (event) => {
    const stroke = strokes.get(event.pointerId);
    if (!stroke) {
      return;
    }
    // 速く動かすと、ブラウザは途中の点をまとめて1回で知らせる。途中の点も使うと、線がなめらかになる
    const events = event.getCoalescedEvents ? event.getCoalescedEvents() : [];
    for (const moved of events.length > 0 ? events : [event]) {
      extendStroke(stroke, moved);
    }
  });

  canvas.addEventListener("pointerup", (event) => {
    endStroke(event.pointerId);
  });

  // 着信や通知などで、ブラウザが操作を取り上げたとき
  canvas.addEventListener("pointercancel", (event) => {
    endStroke(event.pointerId);
  });

  // 長押しでメニューが出ると、子どもが遊びに戻れなくなるため（「画像を保存」などのメニューも出さない）
  canvas.addEventListener("contextmenu", (event) => {
    event.preventDefault();
  });

  resetPaper();

  return {
    // 白紙に戻す（描いている途中の線も捨てる）
    clear: () => {
      strokes.clear();
      resetPaper();
    },
  };
};
