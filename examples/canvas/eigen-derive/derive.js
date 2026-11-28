// 特征值求解推导 · Canvas 连续变形试验. Clock = window.DTIME (existing lesson's voice, absolute lesson time).
"use strict";

const DK = { bg: "#101416", ink: "#EEF1F4", muted: "#A5AFB3", green: "#58CFA9", yellow: "#F1CD68", pink: "#F08D85",
  dim: "#5E6B71" };
const LAM = String.raw`\color{#F08D85}\lambda`;

function deriveFormulas() {
  const f = {};
  const def = (id, x, y, size, build, color) => { f[id] = { x, y, size, color, tex: build(E.tag(id)) }; };
  const e1 = (p) => p("a2", "2") + p("ax", "x") + p("p", "{}+{}") + p("ay", "y") + p("eq", "{}={}") + p("lam", LAM) + p("rx", "x");
  const f2 = (p) => p("lp0", "(") + p("lam", LAM) + p("m1", "{}-{}") + p("one", "1") + p("rp0", ")") + p("lp", "(") + p("ix", "x")
    + p("imi", "{}-{}") + p("iy", "y") + p("rp", ")") + p("eq", "{}={}") + p("zero", "0");
  // phase 1: from Av = λv to the factored equation, one column at x = 1290
  def("def", 1290, 205, 64, (p) => p("A", "A") + "\\," + p("v1", "\\vec v") + p("eq", "{}={}") + p("lam", LAM) + "\\," + p("v2", "\\vec v"));
  def("vxy", 1290, 112, 36, (p) => p("v", "\\vec v") + p("eq", "{}={}") + p("xy", "(x,y)") + p("ne", "{}\\neq\\vec 0"), DK.muted);
  def("col", 1290, 205, 64, (p) => p("A", "A") + String.raw`\begin{pmatrix}${p("x1", "x")}\\${p("y1", "y")}\end{pmatrix}`
    + p("eq", "{}={}") + p("lam", LAM) + String.raw`\begin{pmatrix}${p("x2", "x")}\\${p("y2", "y")}\end{pmatrix}`);
  def("mat", 1290, 205, 64, (p) => String.raw`\begin{bmatrix}${p("m11", "2")}&${p("m12", "1")}\\${p("m21", "1")}&${p("m22", "2")}\end{bmatrix}`
    + String.raw`\begin{pmatrix}${p("x1", "x")}\\${p("y1", "y")}\end{pmatrix}` + p("eq", "{}={}") + p("lam", LAM)
    + String.raw`\begin{pmatrix}${p("x2", "x")}\\${p("y2", "y")}\end{pmatrix}`);
  def("e1", 1290, 338, 56, e1);
  def("e2", 1290, 428, 56, (p) => p("bx", "x") + p("p", "{}+{}") + p("b2", "2") + p("by", "y") + p("eq", "{}={}") + p("lam", LAM) + p("ry", "y"));
  def("s1", 1290, 548, 56, (p) => p("lp1", "(") + p("a2", "2") + p("ax", "x") + p("p1", "{}+{}") + p("ay", "y") + p("rp1", ")")
    + p("mi", "{}-{}") + p("lp2", "(") + p("bx", "x") + p("p2", "{}+{}") + p("b2", "2") + p("by", "y") + p("rp2", ")")
    + p("eq", "{}={}") + p("l1", LAM) + p("rx", "x") + p("mi2", "{}-{}") + p("l2", LAM) + p("ry", "y"));
  def("s2", 1290, 548, 56, (p) => p("sx", "x") + p("smi", "{}-{}") + p("sy", "y") + p("eq", "{}={}")
    + p("l1", LAM) + p("rx", "x") + p("mi2", "{}-{}") + p("l2", LAM) + p("ry", "y"));
  def("s3", 1290, 548, 56, (p) => p("sx", "x") + p("smi", "{}-{}") + p("sy", "y") + p("eq", "{}={}") + p("lam", LAM)
    + p("lp", "(") + p("ix", "x") + p("imi", "{}-{}") + p("iy", "y") + p("rp", ")"));
  def("f1", 1290, 662, 56, (p) => p("lam", LAM) + p("lp", "(") + p("ix", "x") + p("imi", "{}-{}") + p("iy", "y") + p("rp", ")")
    + p("mi", "{}-{}") + p("lp2", "(") + p("jx", "x") + p("jmi", "{}-{}") + p("jy", "y") + p("rp2", ")") + p("eq", "{}={}") + p("zero", "0"));
  def("f2", 1290, 662, 56, f2);
  // phase 2: the two facts on top, one column per case
  def("t1", 985, 150, 44, e1);
  def("t2", 1575, 150, 44, f2);
  def("c1", 1010, 292, 56, (p) => p("cx", "x") + p("ceq", "{}={}") + p("cy", "y"));
  def("c1n", 1010, 372, 36, (p) => p("a", "\\vec v\\neq\\vec 0") + p("b", "\\;\\Longrightarrow\\;") + p("c", "x\\neq 0"), DK.muted);
  def("c1a", 1010, 470, 56, e1);
  def("c1b", 1010, 470, 56, (p) => p("a2", "2") + p("ax", "x") + p("p", "{}+{}") + p("ay", "x") + p("eq", "{}={}") + p("lam", LAM) + p("rx", "x"));
  def("c1c", 1010, 470, 56, (p) => p("n3", "3") + p("ax", "x") + p("eq", "{}={}") + p("lam", LAM) + p("rx", "x"));
  def("c1d", 1010, 470, 64, (p) => p("lam", LAM) + p("eq", "{}={}") + p("n3", "3"));
  def("c1e", 1010, 570, 40, (p) => p("a", "\\vec v=x\\,(1,1)") + p("b", ",\\quad x\\neq 0"), DK.green);
  def("c2", 1575, 292, 56, (p) => p("cx", "x") + p("cne", "{}\\neq{}") + p("cy", "y"));
  def("c2l", 1575, 372, 48, (p) => p("lam", LAM) + p("eq", "{}={}") + p("one", "1"));
  def("c2a", 1575, 470, 56, e1);
  def("c2b", 1575, 470, 56, (p) => p("a2", "2") + p("ax", "x") + p("p", "{}+{}") + p("ay", "y") + p("eq", "{}={}") + p("one", "1") + p("rx", "x"));
  def("c2c", 1575, 470, 56, (p) => p("a2", "2") + p("ax", "x") + p("p", "{}+{}") + p("ay", "y") + p("eq", "{}={}") + p("rx", "x"));
  def("c2d", 1575, 470, 56, (p) => p("a2", "2") + p("ax", "x") + p("mi", "{}-{}") + p("mx", "x") + p("p", "{}+{}") + p("ay", "y")
    + p("eq", "{}={}") + p("zero", "0"));
  def("c2e", 1575, 470, 56, (p) => p("ax", "x") + p("p", "{}+{}") + p("ay", "y") + p("eq", "{}={}") + p("zero", "0"));
  def("c2f", 1575, 470, 64, (p) => p("ay", "y") + p("eq", "{}={}") + p("mi", "-") + p("ax", "x"));
  def("c2g", 1575, 570, 40, (p) => p("a", "\\vec v=x\\,(1,-1)") + p("b", ",\\quad x\\neq 0"), DK.yellow);
  return f;
}

function makeDeriveFilm(under, over, fxRoot) {
  const cu = under.getContext("2d"), co = over.getContext("2d");
  const C = window.DTIME.cues;
  const F = new E.Formulas(fxRoot);
  for (const [id, d] of Object.entries(deriveFormulas())) F.add(id, d.tex, { x: d.x, y: d.y, size: d.size, color: d.color || DK.ink });

  const swapAt = Math.max(C.swap, C.copy1 + 0.65), sub1At = Math.max(C.sub1, C.copy2 + 0.65);
  // morphs: [target, sources, at, dur, options]
  const MORPHS = [
    ["col", ["def"], C.col, 1.1, { map: { x1: "v1", y1: "v1", x2: "v2", y2: "v2" } }],
    ["mat", ["col"], C.mat, 1.0, { merge: { A: "m11" } }],
    ["e1", [{ id: "mat", keep: true }], C.row1 + 0.2, 1.1, { auto: false,
      map: { a2: "m11", ax: "x1", ay: "y1", eq: "eq", lam: "lam", rx: "x2" } }],
    ["e2", [{ id: "mat", keep: true }], C.row2 + 0.2, 1.1, { auto: false,
      map: { bx: "x1", b2: "m22", by: "y1", eq: "eq", lam: "lam", ry: "y2" } }],
    ["s1", [{ id: "e1", keep: true }, { id: "e2", keep: true }], C.sub, 1.2, { map: {
      p1: "e1:p", bx: "e2:bx", p2: "e2:p", b2: "e2:b2", by: "e2:by", l1: "e1:lam", l2: "e2:lam", ry: "e2:ry" } }],
    ["s2", ["s1"], C.left, 1.1, { map: { sx: "ax", smi: "mi", sy: "by" }, merge: { a2: "sx", bx: "sx", ay: "sy", b2: "sy" } }],
    ["s3", ["s2"], C.lamOut, 1.1, { map: { lam: "l1", ix: "rx", imi: "mi2", iy: "ry" }, merge: { l2: "lam" } }],
    ["f1", [{ id: "s3", keep: true }], C.move, 1.25, { map: { jx: { src: "sx", bow: -80 }, jmi: { src: "smi", bow: -80 },
      jy: { src: "sy", bow: -80 } } }],
    ["f2", ["f1"], C.factor + 0.2, 1.1, { map: { m1: "mi" }, merge: { jx: "ix", jmi: "imi", jy: "iy", lp2: "lp", rp2: "rp" } }],
    ["t1", ["e1"], C.phase2, 1.2, {}],
    ["t2", ["f2"], C.phase2 + 0.1, 1.2, {}],
    ["c1", [{ id: "t2", keep: true }], C.xeqy, 1.0, { auto: false, map: { cx: "ix", ceq: { src: "imi", cross: true }, cy: "iy" } }],
    ["c1a", [{ id: "t1", keep: true }], C.copy1, 0.6, {}],
    ["c1b", ["c1a", { id: "c1", keep: true }], swapAt, 1.0, { map: { ay: "c1:cx" } }],
    ["c1c", ["c1b"], C.combine, 1.0, { map: { n3: { src: "a2", cross: true } }, merge: { p: "n3", ay: "ax" } }],
    ["c1d", ["c1c"], C.solve3, 1.0, { map: { lam: { src: "lam", bow: 70 }, n3: { src: "n3", bow: 70 } } }],
    ["c2", [{ id: "t2", keep: true }], C.xney, 1.0, { auto: false, map: { cx: "ix", cne: { src: "imi", cross: true }, cy: "iy" } }],
    ["c2l", [{ id: "t2", keep: true }], C.lamOnly, 1.0, { auto: false, map: { lam: "lam", eq: { src: "m1", cross: true }, one: "one" } }],
    ["c2a", [{ id: "t1", keep: true }], C.copy2, 0.6, {}],
    ["c2b", ["c2a", { id: "c2l", keep: true }], sub1At, 1.0, { map: { one: "c2l:one" } }],
    ["c2c", ["c2b"], sub1At + 1.15, 0.8, { merge: { one: "rx" } }],
    ["c2d", ["c2c"], C.move2, 1.1, { map: { mx: { src: "rx", bow: -80 } } }],
    ["c2e", ["c2d"], C.xy0, 1.0, { merge: { a2: "ax", mi: "ax", mx: "ax" } }],
    ["c2f", ["c2e"], C.ynx, 1.1, { map: { ax: { src: "ax", bow: -70 }, mi: { src: "p", cross: true } } }],
  ];
  // written / faded entrances and fade exits [id, in, kind, out]
  const LIFE = { def: [C.start, "fade"], vxy: [C.vxy, "write"], c1n: [C.nz, "write"], c1e: [C.dir1 - 0.1, "write"],
    c2g: [C.dir2 - 0.3, "write"] };
  const OUT = { vxy: C.phase2, mat: C.phase2, e2: C.phase2, s3: C.phase2 };
  const life = {};
  for (const id of Object.keys(F.items)) life[id] = { in: Infinity, kind: "morph", out: OUT[id] ?? Infinity };
  for (const [id, [t, kind]] of Object.entries(LIFE)) Object.assign(life[id], { in: t, kind });
  for (const [to, srcs, at, dur] of MORPHS) {
    life[to].in = Math.min(life[to].in, at + dur);
    for (const s of srcs) if (typeof s === "string") life[s].out = Math.min(life[s].out, at);
  }

  // emphasis: [formula, parts, color, at, dur]
  const EMPH = [
    ["mat", ["m11", "m12"], DK.yellow, C.row1, 1.4], ["mat", ["m21", "m22"], DK.yellow, C.row2, 1.4],
    ["s3", ["lam"], DK.pink, C.lamSay, 1.2],
    ["f2", ["lp0", "lam", "m1", "one", "rp0"], DK.pink, C.prod, 1.6], ["f2", ["lp", "ix", "imi", "iy", "rp"], DK.green, C.prod + 0.3, 1.6],
    ["t2", ["lp", "ix", "imi", "iy", "rp"], DK.green, C.xeqy - 0.3, 1.4],
    ["c1c", ["ax", "rx"], DK.pink, C.divide, 1.3],
    ["t2", ["lp", "ix", "imi", "iy", "rp"], DK.green, C.fac2, 1.8], ["t2", ["lp0", "lam", "m1", "one", "rp0"], DK.pink, C.lamOnly - 0.3, 1.6],
    ["c1d", ["lam", "eq", "n3"], DK.green, C.both + 0.4, 1.6], ["c2f", ["ay", "eq", "mi", "ax"], DK.yellow, C.both + 0.7, 1.6],
  ];
  const caps = window.DTIME.captions.map(([start, end, text]) => ({ start, end,
    runs: highlight(text) }));
  function highlight(text) {
    const hl = { "特征值": DK.pink, "拉姆达": DK.pink };
    const runs = [];
    let i = 0;
    while (i < text.length) {
      const key = Object.keys(hl).find((w) => text.startsWith(w, i));
      const piece = key || text[i];
      const color = key ? hl[key] : DK.ink;
      if (runs.length && runs[runs.length - 1][1] === color) runs[runs.length - 1][0] += piece; else runs.push([piece, color]);
      i += piece.length;
    }
    return runs;
  }

  const A = [[2, 1], [1, 2]];
  const RING = Array.from({ length: 16 }, (_, i) => [1.25 * Math.cos(i * Math.PI / 8), 1.25 * Math.sin(i * Math.PI / 8)]);
  const PCAM = { cx: 370, cy: 610, unit: 52 };
  const D1 = [Math.SQRT1_2, Math.SQRT1_2], D2 = [Math.SQRT1_2, -Math.SQRT1_2];

  function plane(t) {
    const ctx = cu;
    ctx.save();
    M.roundRect(ctx, 40, 250, 660, 720, 22); ctx.clip();
    ctx.fillStyle = "#0C1013"; ctx.fillRect(40, 250, 660, 720);
    E.grid(ctx, PCAM, E.I, { alpha: 0.9, extent: 7, minor: "#1F2A30", axis: "#45525A" });
    const g = M.prog(t, C.dir1 + 0.2, 0.9), y = M.prog(t, C.dir2, 0.9);
    E.line(ctx, PCAM, D1, { color: DK.green, width: 3, alpha: 0.9 * g, reveal: g, glow: 12 });
    E.line(ctx, PCAM, D2, { color: DK.yellow, width: 3, alpha: 0.9 * y, reveal: y, glow: 12 });
    RING.forEach((v, i) => {
      const w = E.apply(A, v);
      const onG = i % 8 === 2, onY = i % 8 === 6;
      const lit = onG ? M.prog(t, C.dir1 + 0.5, 0.4) : onY ? M.prog(t, C.dir2 + 0.3, 0.4) : 0;
      const color = onG ? mixHex(DK.ink, DK.green, lit) : onY ? mixHex(DK.ink, DK.yellow, lit) : DK.ink;
      const dimOthers = (!onG && !onY) ? 1 - 0.5 * Math.max(M.prog(t, C.dir1, 0.6), 0) : 1;
      E.arrow(ctx, PCAM, [0, 0], w, { color, width: lit ? 4.5 : 3, head: 12, alpha: 0.55 * dimOthers + 0.45 * lit,
        glow: lit ? 8 : 0 });
    });
    ctx.restore();
    E.text(cu, "变换 A 之后的平面", 64, 282, { font: '400 24px "PingFang SC"', color: DK.muted, alpha: 0.9 });
    const [g1x, g1y] = E.toScreen(PCAM, E.scale(D1, 5.6)), [y1x, y1y] = E.toScreen(PCAM, E.scale(D2, -5.6));
    pill(cu, g1x - 64, g1y + 30, "λ = 3", DK.green, M.prog(t, C.pill3, 0.9));
    pill(cu, y1x + 64, y1y + 30, "λ = 1", DK.yellow, M.prog(t, C.pill1, 0.9));
  }

  function mixHex(a, b, k) {
    const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
    return "#" + [16, 8, 0].map((s) => Math.round((pa >> s & 255) + ((pb >> s & 255) - (pa >> s & 255)) * M.clamp(k))
      .toString(16).padStart(2, "0")).join("");
  }

  function pill(ctx, x, y, text, color, k) {
    if (k <= 0) return;
    ctx.save();
    ctx.translate(x, y); const s = 0.6 + 0.4 * M.spring(k); ctx.scale(s, s);
    ctx.font = "30px KaTeX_Main";
    const w = ctx.measureText(text).width + 30;
    const a = M.clamp(k * 3);
    ctx.fillStyle = M.rgba(DK.bg, 0.85 * a); ctx.strokeStyle = M.rgba(color, a); ctx.lineWidth = 2.5;
    M.roundRect(ctx, -w / 2, -23, w, 46, 23); ctx.fill(); ctx.stroke();
    ctx.fillStyle = M.rgba(color, a); ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(text, 0, 2);
    ctx.restore();
  }

  function partBox(id, pid) { const p = F.items[id].parts[pid]; return [p.cx - p.w / 2, p.cy - p.h / 2, p.cx + p.w / 2, p.cy + p.h / 2]; }

  function seek(tc) {
    const t = C.start + tc;
    F.reset();
    cu.clearRect(0, 0, 1920, 1080); co.clearRect(0, 0, 1920, 1080);
    cu.fillStyle = DK.bg; cu.fillRect(0, 0, 1920, 1080);
    plane(t);

    // ---- formulas ----
    const touched = new Set();
    for (const [to, srcs, at, dur, opts] of MORPHS) {
      if (t < at || t >= at + dur) continue;
      F.morph(to, srcs, (t - at) / dur, opts);
      touched.add(to);
      for (const s of srcs) touched.add(typeof s === "string" ? s : s.id);
    }
    for (const [id, L] of Object.entries(life)) {
      if (touched.has(id) || t < L.in || t >= L.out) continue;
      const k = (t - L.in) / 0.9;
      if (L.kind !== "morph" && k < 1) F.enter(id, k, L.kind);
      else F.items[id].div.style.opacity = "1";
      if (Number.isFinite(L.out) && L.out - t < 0.5) F.items[id].div.style.opacity = String(M.clamp((L.out - t) / 0.5));
    }
    for (const [id, pids, color, at, dur] of EMPH) {
      const k = M.pulse(t, at, 0.15, dur / 2.5) * (t < at + dur + 1.5 ? 1 : 0);
      if (k <= 0.01 || F.items[id].div.style.opacity === "0") continue;
      // colour in the DOM, glow as a canvas halo behind the glyphs (CSS text-shadow raster was history-dependent)
      for (const pid of pids) F.items[id].parts[pid].el.style.color = mixHex(DK.ink, color, Math.min(1, k * 1.4));
      const boxes = pids.map((pid) => partBox(id, pid));
      M.halo(cu, [Math.min(...boxes.map((b) => b[0])), Math.min(...boxes.map((b) => b[1])),
        Math.max(...boxes.map((b) => b[2])), Math.max(...boxes.map((b) => b[3]))], color, 0.5 * k, 6);
    }

    // ---- canvas marks around the algebra ----
    // the subtraction: a minus sign before the second equation and a rule under it
    const e2 = F.items.e2.box;
    const subA = M.prog(t, C.minus, 0.3) * (1 - M.prog(t, C.phase2, 0.5));
    E.kinetic(co, t, C.minus, "−", e2[0] - 120, (e2[1] + e2[3]) / 2, { font: "56px KaTeX_Main", alpha: subA, rise: 14 });
    M.stroke(cu, M.segment([[e2[0] - 150, e2[3] + 22], [e2[2] + 30, e2[3] + 22]], 0, M.easeOut(M.prog(t, C.minus + 0.25, 0.5))),
      DK.muted, 2, 0.8 * subA);
    // headings
    const h1 = 1 - M.prog(t, C.phase2, 0.5);
    E.kinetic(co, t, C.start + 0.2, "从定义出发，把方向解出来", 1290, 56, { font: '500 30px "PingFang SC"', color: DK.muted,
      align: "center", alpha: h1, rise: 10, stagger: 0.02 });
    E.kinetic(co, t, C.case1, "情况一：x = y", 1010, 228, { font: '500 30px "PingFang SC"', color: DK.green, align: "center", rise: 12 });
    E.kinetic(co, t, C.case2, "情况二：x ≠ y", 1575, 228, { font: '500 30px "PingFang SC"', color: DK.yellow, align: "center", rise: 12 });
    // a divider between the two facts on top and the cases
    M.stroke(cu, M.segment([[760, 205], [1860, 205]], 0.5 - 0.5 * M.easeOut(M.prog(t, C.phase2 + 0.6, 0.7)),
      0.5 + 0.5 * M.easeOut(M.prog(t, C.phase2 + 0.6, 0.7))), DK.dim, 1.5, 0.8);
    // "x ≠ 0": strike the x on both sides before dividing
    if (t > C.strike && t < C.solve3 + 0.6) {
      const a = 1 - M.prog(t, C.solve3, 0.4);
      for (const [i, pid] of ["ax", "rx"].entries()) {
        const [x0, y0, x1, y1] = partBox("c1c", pid);
        M.stroke(co, M.segment([[x0 - 4, y1 + 2], [x1 + 4, y0 - 2]], 0, M.easeOut(M.prog(t, C.strike + i * 0.15, 0.25))),
          DK.pink, 4, a);
      }
    }
    // "第二个因子非零": a small ≠ 0 under (x - y) on top
    const [fx0, fy0, fx1] = [partBox("t2", "lp")[0], partBox("t2", "lp")[1], partBox("t2", "rp")[2]];
    E.text(co, "≠ 0", (fx0 + fx1) / 2, fy0 - 20, { font: "28px KaTeX_Main", color: DK.green, align: "center",
      alpha: M.prog(t, C.nz2, 0.3) * (1 - M.prog(t, C.copy2, 0.5)) });
    // results land
    const r3 = F.items.c1d.box, r1 = F.items.c2f.box;
    M.ripple(co, t, C.three, (r3[0] + r3[2]) / 2, (r3[1] + r3[3]) / 2, DK.green, { r0: 40, r1: 90, dur: 0.8 });
    M.sparks(co, t, C.three, (r3[0] + r3[2]) / 2, (r3[1] + r3[3]) / 2, DK.green, { n: 10, r0: 50, r1: 100, seed: 4 });
    M.ripple(co, t, C.ynx + 1.1, (r1[0] + r1[2]) / 2, (r1[1] + r1[3]) / 2, DK.yellow, { r0: 40, r1: 90, dur: 0.8 });
    // both cases cover every nonzero vector
    const bothK = M.easeInOut(M.prog(t, C.both, 0.8));
    if (bothK > 0) {
      M.stroke(cu, M.segment([[860, 640], [1730, 640]], 0.5 - 0.5 * bothK, 0.5 + 0.5 * bothK), DK.muted, 2, 0.8);
      M.stroke(cu, [[860, 640], [860, 622]], DK.muted, 2, 0.8 * bothK); M.stroke(cu, [[1730, 640], [1730, 622]], DK.muted, 2, 0.8 * bothK);
    }
    E.kinetic(co, t, C.both + 0.3, "x = y 或 x ≠ y：已覆盖全部非零向量", 1295, 690, { font: '500 32px "PingFang SC"', color: DK.ink,
      align: "center", rise: 14, stagger: 0.025 });

    E.text(co, "线性代数 · 特征向量", 64, 56, { font: '500 28px "PingFang SC"', color: DK.muted });
    for (const cap of caps) M.caption(co, t, cap, { font: '500 40px "PingFang SC"', baseline: 1034, width: 1920, outline: 7,
      outlineColor: "#0A0D0E" });
    const fade = Math.max(1 - M.prog(t, C.start, 0.4), M.prog(t, C.end - 0.6, 0.6));
    if (fade > 0) { co.fillStyle = M.rgba(DK.bg, fade); co.fillRect(0, 0, 1920, 1080); }
    fxRoot.style.opacity = String(1 - fade);
    return true;
  }

  return { duration: C.end - C.start, seek };
}

window.makeDeriveFilm = makeDeriveFilm;

// Entry for the HyperFrames adapter (manimind/canvas/assets/adapter.js).
window.createFilm = () => makeDeriveFilm(document.getElementById("under"), document.getElementById("over"), document.getElementById("fx"));
