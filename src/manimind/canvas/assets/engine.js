// Engine for seek(t) teaching films: a 2D plane with a camera, linear maps, arrows, kinetic text,
// and KaTeX formulas whose parts can move independently. Every draw is a pure function of t:
// the canvas is cleared and every DOM formula is reset on each seek.
"use strict";

const E = {};

// ---------- linear algebra on the plane ----------
E.I = [[1, 0], [0, 1]];
E.apply = (m, [x, y]) => [m[0][0] * x + m[0][1] * y, m[1][0] * x + m[1][1] * y];
E.lerpMat = (a, b, k) => a.map((row, i) => row.map((v, j) => v + (b[i][j] - v) * k));
E.add = (a, b) => [a[0] + b[0], a[1] + b[1]];
E.scale = (a, s) => [a[0] * s, a[1] * s];
E.len = (a) => Math.hypot(a[0], a[1]);

// A piecewise track: start value, then segments [t0, dur, to, ease] applied in order.
E.track = (t, start, segments) => {
  let v = start;
  for (const [t0, dur, to, ease] of segments) {
    if (t <= t0) break;
    const k = (ease || M.easeInOut)(M.clamp((t - t0) / dur));
    v = v + (to - v) * k;
  }
  return v;
};

// ---------- camera ----------
E.toScreen = (cam, [x, y]) => [cam.cx + x * cam.unit, cam.cy - y * cam.unit];

E.grid = (ctx, cam, m, { alpha = 1, extent = 14, reveal = 1, minor = "#26323A", axis = "#5E6B71", width = 1.4 } = {}) => {
  if (alpha <= 0 || reveal <= 0) return;
  const o = E.toScreen(cam, [0, 0]);
  ctx.save();
  if (reveal < 1) {
    ctx.beginPath(); ctx.arc(o[0], o[1], 2300 * M.easeOut(reveal), 0, Math.PI * 2); ctx.clip();
  }
  ctx.lineCap = "butt";
  for (let i = -extent; i <= extent; i++) {
    for (const dir of [0, 1]) {
      const a = dir ? [i, -extent] : [-extent, i];
      const b = dir ? [i, extent] : [extent, i];
      const p = E.toScreen(cam, E.apply(m, a)), q = E.toScreen(cam, E.apply(m, b));
      ctx.strokeStyle = M.rgba(i === 0 ? axis : minor, alpha);
      ctx.lineWidth = i === 0 ? width * 1.6 : width;
      ctx.beginPath(); ctx.moveTo(...p); ctx.lineTo(...q); ctx.stroke();
    }
  }
  ctx.restore();
};

E.arrow = (ctx, cam, from, to, { color = "#EEF1F4", width = 5, head = 17, alpha = 1, glow = 0, grow = 1 } = {}) => {
  if (alpha <= 0 || grow <= 0) return;
  const tip = E.add(from, E.scale([to[0] - from[0], to[1] - from[1]], grow));
  const a = E.toScreen(cam, from), b = E.toScreen(cam, tip);
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (L < 1) return;
  const ux = (b[0] - a[0]) / L, uy = (b[1] - a[1]) / L;
  const h = Math.min(head, L * 0.6);
  const base = [b[0] - ux * h, b[1] - uy * h];
  ctx.save();
  ctx.globalAlpha = M.clamp(alpha);
  if (glow) { ctx.shadowColor = color; ctx.shadowBlur = glow; }
  ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...base); ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(...b);
  ctx.lineTo(base[0] - uy * h * 0.52, base[1] + ux * h * 0.52);
  ctx.lineTo(base[0] + uy * h * 0.52, base[1] - ux * h * 0.52);
  ctx.closePath(); ctx.fill();
  ctx.restore();
};

// Infinite line through the origin along `dir`, revealed outward from the origin.
E.line = (ctx, cam, dir, { color, width = 3, alpha = 1, reveal = 1, glow = 0, dash = null } = {}) => {
  if (alpha <= 0 || reveal <= 0) return;
  const s = 16 * M.easeOut(reveal);
  const a = E.toScreen(cam, E.scale(dir, -s)), b = E.toScreen(cam, E.scale(dir, s));
  ctx.save();
  if (dash) ctx.setLineDash(dash);
  ctx.strokeStyle = M.rgba(color, alpha); ctx.lineWidth = width; ctx.lineCap = "round";
  if (glow) { ctx.shadowColor = M.rgba(color, alpha); ctx.shadowBlur = glow; }
  ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke();
  ctx.restore();
};

E.segment = (ctx, cam, a, b, { color, width = 2, alpha = 1, dash = null, grow = 1 } = {}) => {
  if (alpha <= 0 || grow <= 0) return;
  const p = E.toScreen(cam, a), q = E.toScreen(cam, E.add(a, E.scale([b[0] - a[0], b[1] - a[1]], grow)));
  ctx.save();
  if (dash) ctx.setLineDash(dash);
  ctx.strokeStyle = M.rgba(color, alpha); ctx.lineWidth = width; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(...p); ctx.lineTo(...q); ctx.stroke();
  ctx.restore();
};

// Arc around the origin at radius r (world units) between two angles (radians, math orientation).
E.arc = (ctx, cam, r, a0, a1, { color, width = 3, alpha = 1 } = {}) => {
  if (alpha <= 0 || Math.abs(a1 - a0) < 0.01) return;
  const o = E.toScreen(cam, [0, 0]);
  ctx.save();
  ctx.strokeStyle = M.rgba(color, alpha); ctx.lineWidth = width; ctx.lineCap = "round";
  ctx.beginPath(); ctx.arc(o[0], o[1], r * cam.unit, -a0, -a1, a1 > a0); ctx.stroke();
  ctx.restore();
};

E.text = (ctx, str, x, y, { font, color = "#EEF1F4", alpha = 1, align = "left", baseline = "middle", glow = 0 } = {}) => {
  if (alpha <= 0) return;
  ctx.save();
  ctx.font = font; ctx.textAlign = align; ctx.textBaseline = baseline;
  ctx.fillStyle = M.rgba(color, alpha);
  if (glow) { ctx.shadowColor = M.rgba(color, alpha); ctx.shadowBlur = glow; }
  ctx.fillText(str, x, y);
  ctx.restore();
};

// Kinetic type: each character springs up into place, staggered.
E.kinetic = (ctx, t, t0, str, x, y, { font, color = "#EEF1F4", alpha = 1, stagger = 0.07, rise = 34, align = "left",
  colors = null } = {}) => {
  if (t < t0 || alpha <= 0) return;
  ctx.save();
  ctx.font = font; ctx.textBaseline = "middle"; ctx.textAlign = "left";
  const chars = [...str];
  const widths = chars.map((c) => ctx.measureText(c).width);
  const total = widths.reduce((a, b) => a + b, 0);
  let cx = align === "center" ? x - total / 2 : align === "right" ? x - total : x;
  chars.forEach((c, i) => {
    const local = t - t0 - i * stagger;
    const k = M.spring(M.clamp(local / 0.8));
    const a = alpha * M.clamp(local / 0.14);
    if (a > 0) {
      ctx.save();
      ctx.translate(cx + widths[i] / 2, y + rise * (1 - Math.min(1, k)));
      const s = 0.7 + 0.3 * k;
      ctx.scale(s, s);
      ctx.fillStyle = M.rgba(colors ? colors[i] : color, a);
      ctx.fillText(c, -widths[i] / 2, 0);
      ctx.restore();
    }
    cx += widths[i];
  });
  ctx.restore();
  return total;
};

// Number label that is a pure function of a value (so it "ticks" while the value moves).
E.fmt = (v, d = 1) => (Math.abs(v) < 0.5 * Math.pow(10, -d) ? 0 : v).toFixed(d);

// ---------- KaTeX formulas in the DOM ----------
// Tag parts with E.tag(formulaId)(partId, tex) so ids stay unique across formulas; parts must not nest.
E.tag = (fid) => (pid, tex) => `\\htmlId{${fid}--${pid}}{${tex}}`;

E.Formulas = class {
  constructor(root) { this.root = root; this.items = {}; }

  add(id, tex, { x, y, size = 64, color = "#EEF1F4", align = "center" }) {
    const div = document.createElement("div");
    div.className = "fx";
    div.style.fontSize = `${size}px`;
    div.style.color = color;
    katex.render(tex, div, { trust: (c) => c.command === "\\htmlId", strict: false, throwOnError: true });
    this.root.appendChild(div);
    const r = div.getBoundingClientRect();
    const left = align === "left" ? x : x - r.width / 2, top = y - r.height / 2;
    div.style.left = `${left}px`; div.style.top = `${top}px`;
    const parts = {};
    for (const el of div.querySelectorAll("[id]")) {
      const pr = el.getBoundingClientRect();
      const pid = el.id.includes("--") ? el.id.split("--").slice(1).join("--") : el.id;
      parts[pid] = { el, cx: pr.left + pr.width / 2, cy: pr.top + pr.height / 2, w: pr.width, h: pr.height,
        color: getComputedStyle(el).color };
    }
    this.items[id] = { div, parts, x, y, w: r.width, h: r.height, size, color,
      box: [left, top, left + r.width, top + r.height] };
    return this.items[id];
  }

  reset() {
    for (const item of Object.values(this.items)) {
      item.div.style.opacity = "0";
      item.div.style.transform = "none";
      item.div.style.color = item.color;
      for (const p of Object.values(item.parts)) {
        p.el.style.opacity = "1"; p.el.style.transform = "none"; p.el.style.color = p.color; p.el.style.textShadow = "";
      }
    }
  }

  // Entrance: "write" brings parts in left to right; "fade" fades the whole formula; k in 0..1.
  enter(id, k, kind = "write") {
    const item = this.items[id];
    item.div.style.opacity = "1";
    if (kind === "fade") { item.div.style.opacity = String(M.clamp(k)); return; }
    item.div.style.color = M.rgba(item.color, M.smooth((k - 0.3) / 0.7));
    const parts = Object.values(item.parts).sort((a, b) => a.cx - b.cx);
    parts.forEach((p, i) => {
      const local = M.clamp((k * (1 + 0.5) - (i / Math.max(1, parts.length)) * 0.5) / 1);
      const s = M.spring(local);
      p.el.style.opacity = String(M.clamp(local * 4));
      p.el.style.transform = `translate(0px, ${16 * (1 - Math.min(1, s))}px) scale(${0.75 + 0.25 * s})`;
    });
  }

  // Continuous morph into formula `toId` from one or more sources at progress k (0..1).
  // sources: [{id, keep}] (keep = the source stays on screen, e.g. copying a line down).
  // map: {targetPart: "src" | "srcFormula:src" | {src, bow, cross}}; unmapped target parts appear late,
  // a target part whose id exists in the first source maps to it automatically.
  // merge: {"srcFormula:src" | "src": targetPart} source parts that fly into a target part while fading.
  morph(toId, sources, k, { map = {}, merge = {}, auto = true } = {}) {
    const B = this.items[toId];
    const e = M.easeInOut(k);
    const srcs = sources.map((s) => (typeof s === "string" ? { id: s } : s));
    const first = srcs[0].id;
    const resolve = (ref) => {
      const [fid, pid] = ref.includes(":") ? ref.split(":") : [first, ref];
      return { fid, pid, part: this.items[fid].parts[pid] };
    };
    const used = new Set();
    const lateA = M.smooth((e - 0.45) / 0.55);
    B.div.style.opacity = "1"; B.div.style.transform = "none";
    B.div.style.color = M.rgba(B.color, lateA);
    for (const [pid, p] of Object.entries(B.parts)) {
      let spec = map[pid];
      if (spec === undefined && auto && this.items[first].parts[pid]) spec = pid;
      if (spec === null || spec === undefined) {
        p.el.style.opacity = String(lateA);
        p.el.style.transform = `scale(${0.7 + 0.3 * lateA})`;
        continue;
      }
      const o = typeof spec === "string" ? { src: spec } : spec;
      const { fid, pid: spid, part: s } = resolve(o.src);
      if (!s) throw new Error(`morph ${toId}: missing source part ${o.src}`);
      used.add(`${fid}:${spid}`);
      const ratio = this.items[fid].size / B.size;
      const [dx, dy] = [s.cx - p.cx, s.cy - p.cy];
      const L = Math.hypot(dx, dy) || 1;
      const bow = (o.bow || 0) * Math.sin(Math.PI * e);
      const ox = dx * (1 - e) + (-dy / L) * bow, oy = dy * (1 - e) + (dx / L) * bow;
      const sc = ratio + (1 - ratio) * e;
      p.el.style.transform = `translate(${ox}px, ${oy}px) scale(${sc})`;
      p.el.style.opacity = o.cross ? String(M.smooth(e / 0.6)) : "1";
      if (o.cross && !srcs.find((x) => x.id === fid).keep) {  // the source glyph travels and fades: 2 turns into 3
        s.el.style.opacity = String(1 - M.smooth(e / 0.6));
        s.el.style.transform = `translate(${-dx * e + (-dy / L) * bow}px, ${-dy * e + (dx / L) * bow}px)`;
        used.add(`${fid}:${spid}:cross`);
      }
    }
    for (const src of srcs) {
      const A = this.items[src.id];
      A.div.style.opacity = "1"; A.div.style.transform = "none";
      A.div.style.color = M.rgba(A.color, src.keep ? 1 : 1 - M.smooth(e / 0.5));
      for (const [pid, s] of Object.entries(A.parts)) {
        const key = `${src.id}:${pid}`;
        if (src.keep) { if (!used.has(`${key}:cross`)) { s.el.style.opacity = "1"; s.el.style.transform = "none"; } continue; }
        if (used.has(`${key}:cross`)) continue;
        if (used.has(key)) { s.el.style.opacity = "0"; continue; }
        const into = merge[key] !== undefined ? merge[key] : (src.id === first ? merge[pid] : undefined);
        if (into !== undefined) {
          const t = B.parts[into];
          s.el.style.transform = `translate(${(t.cx - s.cx) * e}px, ${(t.cy - s.cy) * e}px)`;
          s.el.style.opacity = String(1 - M.smooth((e - 0.55) / 0.45));
        } else {
          s.el.style.opacity = String(1 - M.smooth(e / 0.45));
          s.el.style.transform = `translate(0px, ${-10 * e}px)`;
        }
      }
    }
  }

  show(id, { opacity = 1, dx = 0, dy = 0, scale = 1 } = {}) {
    const d = this.items[id].div;
    d.style.opacity = String(M.clamp(opacity));
    d.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
  }

  // No CSS glow here on purpose: draw glows with M.halo on a canvas under the formulas (see docs/canvas.md).
  part(id, pid, { opacity = 1, dx = 0, dy = 0, scale = 1, color = null } = {}) {
    const p = this.items[id].parts[pid];
    p.el.style.opacity = String(M.clamp(opacity));
    p.el.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
    if (color) p.el.style.color = color;
  }

  centre(id, pid) { const p = this.items[id].parts[pid]; return [p.cx, p.cy]; }

  // Rest-position box [x0, y0, x1, y1] of one part, or of several parts together.
  box(id, ...pids) {
    const ps = pids.map((pid) => this.items[id].parts[pid]);
    return [Math.min(...ps.map((p) => p.cx - p.w / 2)), Math.min(...ps.map((p) => p.cy - p.h / 2)),
      Math.max(...ps.map((p) => p.cx + p.w / 2)), Math.max(...ps.map((p) => p.cy + p.h / 2))];
  }
};

window.E = E;
