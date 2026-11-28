// 特征向量 · Canvas 样片（静音预览）. See ../storyboard.md.
// CUES is the only clock: after voicing, replace it from the narration's forced alignment.
"use strict";

const VOICED = typeof window.TIMING === "object" && window.TIMING !== null;
const CUES = VOICED ? window.TIMING.cues : {
  morph3Dur: 2.4, morph4Dur: 3.4, yellowSay: 25.3, recombine: 42.2,
  gridIn: 0.0, titleIn: 0.35, subtitleIn: 1.4, titleOut: 4.0, arrowsIn: 4.3,
  pan: 4.9, matrixIn: 5.3, basisIn: 5.7, morph1: 6.4, colLink: 10.35,
  rewind2: 13.0, raysIn: 13.9, morph2: 14.8, dimOthers: 17.8, greenLine: 17.9, yellowLine: 18.35, breathe: 19.4,
  clear3: 22.0, rewind3: 22.1, morph3: 22.9, formulaIn: 26.6, flyA: 26.9, flyV1: 27.3, flyL: 27.8, flyV2: 28.2,
  nameV: 29.9, nameL: 31.6,
  clear4: 34.5, rewind4: 34.6, uIn: 35.4, split: 36.8, morph4: 39.2, land: 43.4, eqIn: 44.0,
  summary: 48.5, line1: 49.1, line2: 51.3, chips: 52.6, fadeOut: 57.0, end: 58.0,
};

const NARRATION = [  // silent preview: estimated windows (~4.3 chars/s), shown as captions
  [0.8, 4.9, "特征向量，是变换里不改方向的那些箭头。"],
  [5.3, 11.6, "矩阵二一一二作用在整个平面上，每个点、每支箭头都跟着变。"],
  [13.3, 21.0, "大多数箭头离开了原来的直线，转了向。但有两条直线上的箭头，始终没有离开。"],
  [22.3, 33.6, "绿线上的箭头被拉长到三倍，黄线上的长度不变。写成式子，就是 A v 等于 λ v。v 是特征向量，λ 是特征值。"],
  [34.8, 46.6, "任意向量都能沿这两条线拆开。变换时，绿色分量乘三，黄色分量不动，拼回来，正好就是变换后的结果。"],
  [48.8, 54.4, "特征向量找的是变换保留的直线，特征值是线上的倍数。"],
];

const K = { bg: "#101416", ink: "#EEF1F4", muted: "#A5AFB3", green: "#58CFA9", yellow: "#F1CD68", pink: "#F08D85",
  blue: "#72C9D8", dim: "#5E6B71" };
const A = [[2, 1], [1, 2]];
const D1 = [Math.SQRT1_2, Math.SQRT1_2], D2 = [Math.SQRT1_2, -Math.SQRT1_2];
const RING = Array.from({ length: 16 }, (_, i) => {
  const th = (i * Math.PI) / 8;
  return { i, th, v: [1.6 * Math.cos(th), 1.6 * Math.sin(th)], eigen: i % 8 === 2 ? "green" : i % 8 === 6 ? "yellow" : null };
});
const U = [1.5, 0.5], V1 = [1, 1], V2 = [0.5, -0.5];

const mix = (a, b, k) => {
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
  const c = [16, 8, 0].map((s) => Math.round((pa >> s & 255) + ((pb >> s & 255) - (pa >> s & 255)) * M.clamp(k)));
  return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
};
const angleDiff = (a, b) => { let d = b - a; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; return d; };
const MATH = (px, italic = false) => `${italic ? "italic " : ""}${px}px ${italic ? "KaTeX_Math" : "KaTeX_Main"}`;
const ZH = (px, w = 500) => `${w} ${px}px "PingFang SC"`;

function captionRows() {
  if (VOICED) return window.TIMING.captions;  // [start, end, text] timed from the spoken characters
  const rows = [];
  for (const [t0, t1, text] of NARRATION) {
    const parts = text.split(/(?<=[，。])/).map((s) => s.replace(/[，。]$/, "")).filter(Boolean);
    const merged = [];
    for (const p of parts) {
      if (merged.length && merged[merged.length - 1].length + p.length <= 15) merged[merged.length - 1] += "  " + p;
      else merged.push(p);
    }
    const total = merged.reduce((s, m) => s + m.length, 0);
    let cursor = t0;
    for (const m of merged) {
      const span = ((t1 - t0) * m.length) / total;
      rows.push([cursor, cursor + span - 0.04, m]);
      cursor += span;
    }
  }
  return rows;
}

function captionChunks() {
  const hl = { "特征向量": K.green, "特征值": K.pink };
  const out = [];
  for (const [start, end, m] of captionRows()) {
    const runs = [];
    let i = 0;
    while (i < m.length) {
      const key = Object.keys(hl).find((w) => m.startsWith(w, i));
      const piece = key || m[i];
      const color = key ? hl[key] : K.ink;
      if (runs.length && runs[runs.length - 1][1] === color) runs[runs.length - 1][0] += piece;
      else runs.push([piece, color]);
      i += piece.length;
    }
    out.push({ start, end, runs });
  }
  return out;
}

function makeEigenFilm(canvas, fxRoot) {
  const ctx = canvas.getContext("2d");
  const C = CUES;
  const F = new E.Formulas(fxRoot);
  F.add("matrix", String.raw`\htmlId{mA}{A}=\begin{bmatrix}\htmlId{c11}{2}&\htmlId{c12}{1}\\\htmlId{c21}{1}&\htmlId{c22}{2}\end{bmatrix}`,
    { x: 1540, y: 300, size: 72 });
  F.add("def", String.raw`\htmlId{fA}{A}\,\htmlId{fv1}{\color{${K.green}}\vec v}\;\htmlId{feq}{=}\;\htmlId{fl}{\color{${K.pink}}\lambda}\,\htmlId{fv2}{\color{${K.green}}\vec v}`,
    { x: 1540, y: 600, size: 96 });
  F.add("decomp", String.raw`\htmlId{eA}{A\vec u}\;\htmlId{eq}{=}\;\htmlId{e3}{\color{${K.green}}3\,\vec v_1}\;\htmlId{ep}{+}\;\htmlId{ev2}{\color{${K.yellow}}\vec v_2}`,
    { x: 1540, y: 520, size: 70 });
  const caps = captionChunks();
  const capStyle = { font: ZH(40), baseline: 1034, width: 1920, outline: 7, outlineColor: "#0A0D0E" };

  const kAt = (t) => E.track(t, 0, [
    [C.morph1, 4.0, 1], [C.rewind2, 0.8, 0], [C.morph2, 3.0, 1],
    [C.breathe, 1.3, 0.35], [C.breathe + 1.3, 1.3, 1],
    [C.rewind3, 0.6, 0], [C.morph3, C.morph3Dur, 1], [C.rewind4, 0.6, 0], [C.morph4, C.morph4Dur, 1],
  ]);
  // camera: centred for the title, then left of the formula panel; pushes in for the decomposition
  const camAt = (t) => ({
    cx: E.track(t, 960, [[C.pan, 1.3, 760], [C.clear4 + 0.1, 1.3, 640], [C.summary, 1.0, 760]]),
    cy: E.track(t, 560, [[C.clear4 + 0.1, 1.3, 610], [C.summary, 1.0, 560]]),
    unit: E.track(t, 88, [[C.clear4 + 0.1, 1.3, 128], [C.summary, 1.0, 88]]),
  });

  function title(t) {
    const out = M.easeInOut(M.prog(t, C.titleOut, 0.8));
    const a = 1 - out;
    if (a <= 0) return;
    // soft backdrop so the title reads over the grid
    ctx.save();
    const g = ctx.createRadialGradient(960, 500, 40, 960, 500, 620);
    g.addColorStop(0, M.rgba(K.bg, 0.9 * a)); g.addColorStop(1, M.rgba(K.bg, 0));
    ctx.fillStyle = g; ctx.fillRect(0, 0, 1920, 1080);
    ctx.translate(M.lerp(960, 300, out), M.lerp(470, 70, out));
    const s = M.lerp(1, 0.3, out); ctx.scale(s, s);
    E.kinetic(ctx, t, C.titleIn, "特征向量", 0, 0, { font: ZH(136, 600), align: "center", alpha: a, stagger: 0.09, rise: 46 });
    E.text(ctx, "变换之后，仍在原来直线上的向量", 0, 112, { font: ZH(38, 400), color: K.muted, align: "center",
      alpha: a * M.easeOut(M.prog(t, C.subtitleIn, 0.6)) });
    ctx.restore();
  }

  function chrome(t) {
    E.text(ctx, "线性代数 · 特征向量", 110, 70, { font: ZH(30), color: K.muted, alpha: M.prog(t, C.titleOut + 0.5, 0.5) });
    if (!VOICED) E.text(ctx, "静音预览 · 讲稿草稿未配音", 1810, 70, { font: ZH(22, 400), color: K.dim, align: "right", alpha: 0.9 });
  }

  function panel(t, a) {
    if (a <= 0) return;
    ctx.save();
    const g = ctx.createLinearGradient(1170, 0, 1330, 0);
    g.addColorStop(0, M.rgba(K.bg, 0)); g.addColorStop(1, M.rgba(K.bg, 0.9 * a));
    ctx.fillStyle = g; ctx.fillRect(1170, 0, 750, 1080);
    ctx.restore();
  }

  function pill(x, y, text, color, k) {
    if (k <= 0) return;
    ctx.save();
    ctx.translate(x, y); const s = 0.6 + 0.4 * M.spring(k); ctx.scale(s, s);
    ctx.font = MATH(34, false);
    const w = ctx.measureText(text).width + 34;
    ctx.fillStyle = M.rgba(K.bg, 0.85 * M.clamp(k * 3)); ctx.strokeStyle = M.rgba(color, M.clamp(k * 3)); ctx.lineWidth = 2.5;
    M.roundRect(ctx, -w / 2, -26, w, 52, 26); ctx.fill(); ctx.stroke();
    ctx.fillStyle = M.rgba(color, M.clamp(k * 3)); ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, 0, 2);
    ctx.restore();
  }

  function seek(t) {
    F.reset();
    ctx.clearRect(0, 0, 1920, 1080);
    ctx.fillStyle = K.bg; ctx.fillRect(0, 0, 1920, 1080);
    const cam = camAt(t);
    const k = kAt(t);
    const m = E.lerpMat(E.I, A, k);
    const toS = (p) => E.toScreen(cam, p);
    const S5 = M.easeInOut(M.prog(t, C.summary, 0.8));  // summary dimming

    // ---- plane ----
    const gridA = 1 - 0.7 * S5;
    if (k > 0.001) E.grid(ctx, cam, E.I, { alpha: 0.22 * gridA, minor: "#1E282D", axis: "#323D42" });
    E.grid(ctx, cam, m, { alpha: gridA, reveal: M.prog(t, C.gridIn, 1.6) });

    // eigen lines: revealed in S2, faint during S4, bright in the summary
    const lineA = (t0) => M.prog(t, t0, 0.4) * (1 - 0.6 * M.prog(t, C.clear4, 0.6)) + 0.6 * S5 * M.prog(t, t0, 0.4);
    E.line(ctx, cam, D1, { color: K.green, width: 3.5, alpha: 0.9 * lineA(C.greenLine), reveal: M.prog(t, C.greenLine, 0.9), glow: 14 });
    E.line(ctx, cam, D2, { color: K.yellow, width: 3.5, alpha: 0.9 * lineA(C.yellowLine), reveal: M.prog(t, C.yellowLine, 0.9), glow: 14 });

    // ---- S2: original directions and turning arcs ----
    const clear3 = 1 - M.prog(t, C.clear3, 0.5);
    for (const r of RING) {
      const others = r.eigen ? 1 : 1 - 0.75 * M.prog(t, C.dimOthers, 0.6);
      const ray = M.prog(t, C.raysIn + r.i * 0.03, 0.5);
      E.segment(ctx, cam, [0, 0], E.scale(r.v, 1.55), { color: K.muted, width: 2, alpha: 0.45 * others * clear3 * ray,
        dash: [8, 9], grow: ray });
      if (!r.eigen && t > C.morph2) {
        const cur = E.apply(m, r.v);
        E.arc(ctx, cam, r.i % 2 ? 0.95 : 1.2, r.th, r.th + angleDiff(r.th, Math.atan2(cur[1], cur[0])),
          { color: K.pink, width: 3, alpha: 0.75 * others * clear3 });
      }
    }

    // ---- ring arrows ----
    const goneS4 = 1 - M.prog(t, C.clear4, 0.5);
    for (const r of RING) {
      const grow = M.easeOut(M.prog(t, C.arrowsIn + r.i * 0.035, 0.5));
      let color = K.ink, alpha = 0.88 * grow;
      if (r.eigen) {
        const lk = M.prog(t, r.eigen === "green" ? C.greenLine : C.yellowLine, 0.4);
        color = mix(K.ink, r.eigen === "green" ? K.green : K.yellow, lk);
        alpha *= goneS4;
      } else {
        alpha *= (1 - 0.75 * M.prog(t, C.dimOthers, 0.6)) * clear3;
      }
      E.arrow(ctx, cam, [0, 0], E.apply(m, r.v), { color, width: r.eigen && t > C.greenLine ? 5.5 : 4, head: 15, alpha,
        glow: r.eigen && t > C.greenLine ? 10 : 0 });
    }
    for (const r of RING.filter((x) => x.eigen)) {
      const t0 = r.eigen === "green" ? C.greenLine : C.yellowLine;
      const [x, y] = toS(E.apply(m, r.v));
      M.ripple(ctx, t, t0 + 0.25, x, y, r.eigen === "green" ? K.green : K.yellow, { r1: 46, rings: 1, dur: 0.7 });
    }

    // ---- S1: basis vectors with ticking coordinates ----
    const basisA = 1 - M.prog(t, C.rewind2, 0.4);
    [[[1, 0], K.pink, C.basisIn], [[0, 1], K.blue, C.basisIn + 0.2]].forEach(([e, color, t0]) => {
      const grow = M.easeOut(M.prog(t, t0, 0.5));
      const tip = E.apply(m, e);
      E.arrow(ctx, cam, [0, 0], tip, { color, width: 7, head: 20, alpha: basisA, grow, glow: 8 });
      const [x, y] = toS(tip);
      E.text(ctx, `(${E.fmt(tip[0])}, ${E.fmt(tip[1])})`, x + 16, y - 26, { font: MATH(30), color,
        alpha: basisA * M.prog(t, t0 + 0.4, 0.3) });
      M.ripple(ctx, t, C.colLink, x, y, color, { r1: 40, rings: 1, dur: 0.6 });
    });

    // ---- S3: stretch counters ----
    const ticker = M.prog(t, C.morph3 - 0.2, 0.3) * goneS4;
    if (ticker > 0) {
      const g = E.apply(m, RING[2].v), y = E.apply(m, RING[14].v);
      const [gx, gy] = toS(g), [yx, yy] = toS(y);
      E.text(ctx, `×${E.fmt(1 + 2 * k)}`, gx + 22, gy + 6, { font: MATH(40), color: K.green, alpha: ticker, glow: 8 });
      E.text(ctx, "×1.0", yx + 20, yy + 18, { font: MATH(40), color: K.yellow, alpha: ticker,
        glow: 8 + 22 * M.pulse(t, C.yellowSay, 0.1, 0.7) });
      M.ripple(ctx, t, C.yellowSay, yx, yy, K.yellow, { r1: 44, rings: 1, dur: 0.7 });
    }

    // ---- S4: decomposition ----
    const s4 = M.prog(t, C.uIn, 0.3) * (1 - S5);
    if (s4 > 0) {
      const ghostU = 1 - 0.75 * M.prog(t, C.morph4, 0.5);
      E.arrow(ctx, cam, [0, 0], U, { color: K.ink, width: 6, head: 19, alpha: s4 * ghostU, grow: M.easeOut(M.prog(t, C.uIn, 0.5)) });
      const [ux, uy] = toS(U);
      E.text(ctx, "u", ux + 14, uy - 4, { font: MATH(42, true), color: K.ink, alpha: s4 * ghostU * M.prog(t, C.uIn + 0.4, 0.3) });
      const guide = M.easeInOut(M.prog(t, C.split, 0.5));
      const guideA = s4 * (1 - M.prog(t, C.morph4, 0.5));
      E.segment(ctx, cam, U, V1, { color: K.muted, width: 2, dash: [7, 8], alpha: 0.7 * guideA, grow: guide });
      E.segment(ctx, cam, U, V2, { color: K.muted, width: 2, dash: [7, 8], alpha: 0.7 * guideA, grow: guide });
      const g1 = E.scale(V1, 1 + 2 * k);
      E.arrow(ctx, cam, [0, 0], g1, { color: K.green, width: 6.5, head: 19, alpha: s4, glow: 10,
        grow: M.easeOut(M.prog(t, C.split + 0.6, 0.5)) });
      E.arrow(ctx, cam, g1, E.add(g1, V2), { color: K.yellow, width: 6.5, head: 19, alpha: s4, glow: 10,
        grow: M.easeOut(M.prog(t, C.split + 1.1, 0.5)) });
      const lab = s4 * M.prog(t, C.split + 1.5, 0.3);
      const [m1x, m1y] = toS(E.scale(g1, 0.5)), [m2x, m2y] = toS(E.add(g1, E.scale(V2, 0.5)));
      const counting = M.prog(t, C.morph4 - 0.2, 0.3);
      E.text(ctx, counting > 0 ? `×${E.fmt(1 + 2 * k)}` : "v₁", m1x - 34, m1y - 30, { font: counting > 0 ? MATH(36) : MATH(38, true),
        color: K.green, alpha: lab, align: "right", glow: 6 });
      E.text(ctx, counting > 0 ? "×1.0" : "v₂", m2x + 16, m2y - 24, { font: counting > 0 ? MATH(36) : MATH(38, true),
        color: K.yellow, alpha: lab, glow: 6 });
      // "拼回来": the yellow piece flashes where it joins the green one
      const [jx, jy] = toS(g1);
      M.ripple(ctx, t, C.recombine, jx, jy, K.yellow, { r1: 38, rings: 1, dur: 0.6 });
      // the directly transformed u rides along and always meets the recombined tip
      const direct = E.apply(m, U);
      if (t > C.morph4) {
        ctx.save(); ctx.setLineDash([10, 9]);
        E.arrow(ctx, cam, [0, 0], direct, { color: K.ink, width: 3, head: 15, alpha: 0.75 * s4 });
        ctx.restore();
        const [dx, dy] = toS(direct);
        E.text(ctx, `(${E.fmt(direct[0])}, ${E.fmt(direct[1])})`, dx + 22, dy + 32, { font: MATH(32), color: K.ink,
          alpha: s4 * M.prog(t, C.morph4, 0.3) });
        M.ripple(ctx, t, C.land, dx, dy, K.ink, { r1: 70, dur: 0.8 });
        M.sparks(ctx, t, C.land, dx, dy, K.ink, { n: 12, r0: 24, r1: 80, seed: 11 });
      }
    }

    // ---- summary pills on the lines ----
    const [p1x, p1y] = toS(E.scale(D1, 4.9)), [p2x, p2y] = toS(E.scale(D2, -4.6));
    pill(p1x - 70, p1y + 6, "λ = 3", K.green, M.prog(t, C.chips, 0.9));
    pill(p2x + 70, p2y + 6, "λ = 1", K.yellow, M.prog(t, C.chips + 0.25, 0.9));

    // ---- right panel ----
    panel(t, M.prog(t, C.matrixIn - 0.3, 0.6));
    const matA = M.prog(t, C.matrixIn, 0.3) * (1 - M.prog(t, C.clear4, 0.5));
    if (matA > 0) {
      F.show("matrix", { opacity: matA, scale: 0.85 + 0.15 * M.spring(M.prog(t, C.matrixIn, 0.9)) });
      const link = M.prog(t, C.colLink, 0.35) * (1 - M.prog(t, C.rewind2, 0.6));
      const glow = M.pulse(t, C.colLink, 0.1, 0.8);
      for (const [pid, color] of [["c11", K.pink], ["c21", K.pink], ["c12", K.blue], ["c22", K.blue]]) {
        F.part("matrix", pid, { color: mix(K.ink, color, link) });
      }
      M.halo(ctx, F.box("matrix", "c11", "c21"), K.pink, 0.45 * glow * matA, 8);
      M.halo(ctx, F.box("matrix", "c12", "c22"), K.blue, 0.45 * glow * matA, 8);
    }
    // definition: parts fly in from where they come from on screen
    const defA = M.prog(t, C.formulaIn, 0.2) * (1 - S5);
    if (defA > 0) {
      const up = M.easeInOut(M.prog(t, C.clear4, 0.8));
      F.show("def", { opacity: defA, dy: -400 * up, scale: 1 - 0.36 * up });
      const greenTip = toS(E.scale(RING[2].v, 3));
      const tick = [greenTip[0] + 60, greenTip[1] + 6];
      const fly = (pid, t0, src) => {
        const kk = M.easeInOut(M.prog(t, t0, 0.7));
        const [cx, cy] = F.centre("def", pid);
        F.part("def", pid, { opacity: M.prog(t, t0, 0.12), dx: (src[0] - cx) * (1 - kk), dy: (src[1] - cy) * (1 - kk),
          scale: 0.7 + 0.3 * kk });
        M.halo(ctx, F.box("def", pid), pid === "fl" ? K.pink : pid === "fA" ? K.ink : K.green,
          0.5 * M.pulse(t, t0 + 0.7, 0.05, 0.5) * (1 - up), 8);
      };
      fly("fA", C.flyA, F.centre("matrix", "mA"));
      fly("fv1", C.flyV1, greenTip);
      F.part("def", "feq", { opacity: M.prog(t, C.flyV1 + 0.3, 0.3) });
      fly("fl", C.flyL, tick);
      fly("fv2", C.flyV2, greenTip);
      // names: "特征向量" under v, "特征值" above λ, each with a hand-drawn underline
      const nameA = 1 - M.prog(t, C.clear4, 0.4);
      const [vx, vy] = F.centre("def", "fv1"), [lx, ly] = F.centre("def", "fl");
      E.kinetic(ctx, t, C.nameV, "特征向量", vx, vy + 96, { font: ZH(40), color: K.green, align: "center", alpha: nameA, rise: 18 });
      M.stroke(ctx, M.segment([[vx - 82, vy + 128], [vx + 82, vy + 126]], 0, M.easeOut(M.prog(t, C.nameV + 0.3, 0.4))),
        K.green, 3, nameA);
      M.stroke(ctx, M.segment([[vx, vy + 52], [vx, vy + 70]], 0, M.prog(t, C.nameV, 0.2)), K.green, 2, 0.6 * nameA);
      E.kinetic(ctx, t, C.nameL, "特征值", lx, ly - 104, { font: ZH(40), color: K.pink, align: "center", alpha: nameA, rise: -18 });
      M.stroke(ctx, M.segment([[lx - 62, ly - 72], [lx + 62, ly - 74]], 0, M.easeOut(M.prog(t, C.nameL + 0.3, 0.4))),
        K.pink, 3, nameA);
    }
    // decomposition result
    const decA = M.prog(t, C.eqIn, 0.2) * (1 - S5);
    if (decA > 0) {
      F.show("decomp", { opacity: decA });
      ["eA", "eq", "e3", "ep", "ev2"].forEach((pid, i) => {
        const kk = M.prog(t, C.eqIn + i * 0.14, 0.8);
        F.part("decomp", pid, { opacity: M.prog(t, C.eqIn + i * 0.14, 0.12), dy: 26 * (1 - Math.min(1, M.spring(kk))),
          scale: 0.75 + 0.25 * M.spring(kk) });
      });
    }

    // summary type
    E.kinetic(ctx, t, C.line1, "特征向量", 1280, 400, { font: ZH(66, 600), color: K.green });
    E.text(ctx, "变换保留的直线", 1282, 472, { font: ZH(40, 400), color: K.ink, alpha: M.easeOut(M.prog(t, C.line1 + 0.5, 0.5)) });
    E.kinetic(ctx, t, C.line2, "特征值", 1280, 610, { font: ZH(66, 600), color: K.pink });
    E.text(ctx, "线上的倍数", 1282, 682, { font: ZH(40, 400), color: K.ink, alpha: M.easeOut(M.prog(t, C.line2 + 0.5, 0.5)) });
    pill(1530, 683, "3", K.green, M.prog(t, C.chips, 0.9));
    pill(1600, 683, "1", K.yellow, M.prog(t, C.chips + 0.25, 0.9));

    title(t);
    chrome(t);
    for (const cap of caps) M.caption(ctx, t, cap, capStyle);

    const fade = M.prog(t, C.fadeOut, C.end - C.fadeOut);
    if (fade > 0) { ctx.fillStyle = M.rgba(K.bg, fade); ctx.fillRect(0, 0, 1920, 1080); fxRoot.style.opacity = String(1 - fade); }
    else fxRoot.style.opacity = "1";
    return true;
  }

  return { duration: C.end, seek };
}

window.makeEigenFilm = makeEigenFilm;

// Entry for the HyperFrames adapter (manimind/canvas/assets/adapter.js).
window.createFilm = () => makeEigenFilm(document.getElementById("c"), document.getElementById("fx"));
