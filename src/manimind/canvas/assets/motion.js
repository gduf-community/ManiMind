// Motion vocabulary for a seek(t) layer. Every function is a pure function of its arguments:
// no Date, no unseeded randomness, no state carried between frames.
// Easing/spring ideas follow vibe-knowledge (MIT, Berryxia).
"use strict";

const M = {};

M.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
M.lerp = (a, b, k) => a + (b - a) * k;
M.prog = (t, t0, dur) => M.clamp((t - t0) / dur);
M.easeOut = (x) => 1 - Math.pow(1 - M.clamp(x), 3);
M.easeInOut = (x) => { x = M.clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
M.smooth = (x) => { x = M.clamp(x); return x * x * x * (x * (6 * x - 15) + 10); };
// Damped spring 0 -> 1 with a small overshoot.
M.spring = (x, damping = 6.5, freq = 1.15) => x <= 0 ? 0 : 1 - Math.exp(-damping * x) * Math.cos(2 * Math.PI * freq * x);
// Visibility envelope: fades in at t0 over fi, out at t1 over fo.
M.window = (t, t0, t1, fi = 0.2, fo = 0.3) => Math.min(M.prog(t, t0, fi), 1 - M.prog(t, t1, fo));
// Soft pulse: 0 before t0, rises in `rise`, decays with time constant `decay`.
M.pulse = (t, t0, rise = 0.12, decay = 0.6) => {
  if (t <= t0) return 0;
  const x = t - t0;
  return x < rise ? M.smooth(x / rise) : Math.exp(-(x - rise) / decay);
};

M.rng = (seed) => () => {  // mulberry32
  seed |= 0; seed = seed + 0x6D2B79F5 | 0;
  let r = Math.imul(seed ^ seed >>> 15, 1 | seed);
  r = r + Math.imul(r ^ r >>> 7, 61 | r) ^ r;
  return ((r ^ r >>> 14) >>> 0) / 4294967296;
};

M.rgba = (hex, a) => {
  const v = parseInt(hex.slice(1), 16);
  return `rgba(${v >> 16 & 255},${v >> 8 & 255},${v & 255},${M.clamp(a)})`;
};

// Point at arc-length fraction s along a polyline.
M.along = (pts, s) => {
  const lens = [];
  let total = 0;
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); lens.push(d); total += d; }
  let target = M.clamp(s) * total;
  for (let i = 0; i < lens.length; i++) {
    if (target <= lens[i] || i === lens.length - 1) {
      const k = lens[i] ? M.clamp(target / lens[i]) : 0;
      return [M.lerp(pts[i][0], pts[i + 1][0], k), M.lerp(pts[i][1], pts[i + 1][1], k)];
    }
    target -= lens[i];
  }
  return pts[pts.length - 1];
};

// Sub-path between arc-length fractions a..b.
M.segment = (pts, a, b, n = 24) => {
  const out = [];
  for (let i = 0; i <= n; i++) out.push(M.along(pts, M.lerp(a, b, i / n)));
  return out;
};

M.stroke = (ctx, pts, color, width, alpha = 1, glow = 0) => {
  if (pts.length < 2 || alpha <= 0) return;
  let length = 0;
  for (let i = 1; i < pts.length; i++) length += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  if (length < 0.5) return;  // a zero-length path with round caps would leave a dot
  ctx.save();
  ctx.lineCap = "round"; ctx.lineJoin = "round";
  ctx.strokeStyle = M.rgba(color, alpha); ctx.lineWidth = width;
  if (glow) { ctx.shadowColor = M.rgba(color, alpha); ctx.shadowBlur = glow; }
  ctx.beginPath(); ctx.moveTo(...pts[0]);
  for (const p of pts.slice(1)) ctx.lineTo(...p);
  ctx.stroke();
  ctx.restore();
};

// A glowing head travelling along `pts` (0..s), leaving a fading trail of `trail` (fraction of path).
M.comet = (ctx, pts, s, color, { trail = 0.45, width = 6, head = 7, alpha = 1 } = {}) => {
  if (s <= 0 || alpha <= 0) return;
  const tail = Math.max(0, s - trail);
  const steps = 18;
  for (let i = 0; i < steps; i++) {  // tapering, fading trail
    const a = M.lerp(tail, s, i / steps), b = M.lerp(tail, s, (i + 1) / steps);
    const k = (i + 1) / steps;
    M.stroke(ctx, M.segment(pts, a, b, 4), color, width * (0.35 + 0.65 * k), alpha * k * k * 0.9, 10 * k);
  }
  const [x, y] = M.along(pts, s);
  ctx.save();
  ctx.fillStyle = M.rgba("#FFFFFF", alpha);
  ctx.shadowColor = M.rgba(color, alpha); ctx.shadowBlur = 26;
  ctx.beginPath(); ctx.arc(x, y, head, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = M.rgba(color, alpha * 0.9); ctx.shadowBlur = 0;
  ctx.beginPath(); ctx.arc(x, y, head * 0.55, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
};

// Expanding rings from (x, y), starting at t0.
M.ripple = (ctx, t, t0, x, y, color, { r0 = 10, r1 = 70, dur = 0.9, rings = 2, gap = 0.16, width = 3 } = {}) => {
  for (let i = 0; i < rings; i++) {
    const k = M.prog(t, t0 + i * gap, dur);
    if (k <= 0 || k >= 1) continue;
    const r = M.lerp(r0, r1, M.easeOut(k));
    ctx.save();
    ctx.strokeStyle = M.rgba(color, (1 - k) * (i ? 0.5 : 0.85));
    ctx.lineWidth = width * (1 - 0.6 * k);
    ctx.shadowColor = M.rgba(color, 0.6 * (1 - k)); ctx.shadowBlur = 12;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }
};

// Short rays bursting out of (x, y): seeded directions, grow then retract.
M.sparks = (ctx, t, t0, x, y, color, { n = 12, r0 = 30, r1 = 92, dur = 0.7, seed = 3 } = {}) => {
  const k = M.prog(t, t0, dur);
  if (k <= 0 || k >= 1) return;
  const rnd = M.rng(seed);
  for (let i = 0; i < n; i++) {
    const ang = (i / n) * Math.PI * 2 + (rnd() - 0.5) * 0.35;
    const reach = M.lerp(r0, r1 * (0.75 + 0.5 * rnd()), M.easeOut(k));
    const len = 22 * Math.sin(Math.PI * k) * (0.7 + 0.6 * rnd());
    const a = [x + Math.cos(ang) * (reach - len), y + Math.sin(ang) * (reach - len)];
    const b = [x + Math.cos(ang) * reach, y + Math.sin(ang) * reach];
    M.stroke(ctx, [a, b], color, 3.2, 1 - k * k, 8);
  }
};

// Soft glowing halo behind a box (used on the "under" layer so the math stays crisp on top).
M.halo = (ctx, box, color, alpha, pad = 12) => {
  if (alpha <= 0) return;
  const [x0, y0, x1, y1] = box;
  ctx.save();
  ctx.fillStyle = M.rgba(color, alpha * 0.55);
  ctx.shadowColor = M.rgba(color, alpha); ctx.shadowBlur = 34;
  M.roundRect(ctx, x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, 14);
  ctx.fill();
  ctx.restore();
};

M.roundRect = (ctx, x, y, w, h, r) => {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
};

// Text that springs in: scale from `from` and rises `rise` px; anchor = centre-left/centre per align.
M.popText = (ctx, t, t0, text, x, y, { font, color, alpha = 1, from = 0.55, rise = 14, align = "center", glow = 0 } = {}) => {
  const k = M.spring(M.prog(t, t0, 0.9));
  const a = alpha * M.prog(t, t0, 0.12);
  if (a <= 0) return;
  ctx.save();
  ctx.translate(x, y + rise * (1 - Math.min(1, k)));
  const s = from + (1 - from) * k;
  ctx.scale(s, s);
  ctx.font = font; ctx.textAlign = align; ctx.textBaseline = "middle";
  ctx.fillStyle = M.rgba(color, a);
  if (glow) { ctx.shadowColor = M.rgba(color, a * 0.8); ctx.shadowBlur = glow; }
  ctx.fillText(text, 0, 0);
  ctx.restore();
};

// Odometer digit: value v (e.g. 4.0 .. 9.0) shown as one rolling digit at (x, y) (left-aligned).
// The roll happens in the last `roll` part of each unit, so digits rest most of the time.
M.rollingDigit = (ctx, v, x, y, { font, color, alpha = 1, height = 46, roll = 0.4 } = {}) => {
  const base = Math.floor(v + 1e-6);
  const frac = v - base;
  const k = M.smooth((frac - (1 - roll)) / roll);
  ctx.save();
  ctx.beginPath(); ctx.rect(x - 4, y - height / 2, height, height); ctx.clip();
  ctx.font = font; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  for (const [d, dy, a] of [[base, -k * height, 1 - k], [base + 1, (1 - k) * height, k]]) {
    if (a <= 0.001) continue;
    ctx.fillStyle = M.rgba(color, alpha * a);
    ctx.fillText(String(d), x, y + dy);
  }
  ctx.restore();
};

// Vertical curly brace from (x, y0) down to (x, y1), bulging right by `bulge`; drawn up to fraction s.
M.bracePoints = (x, y0, y1, bulge = 16, n = 60) => {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    // ends curl out to half the bulge, a pointed tip reaches the full bulge at the middle
    const curl = M.smooth(Math.min(u, 1 - u) / 0.09);
    const tip = Math.pow(Math.max(0, 1 - Math.abs(u - 0.5) / 0.07), 2);
    pts.push([x + bulge * 0.5 * curl + bulge * 0.5 * tip, M.lerp(y0, y1, u)]);
  }
  return pts;
};

// Highlighter band behind characters, growing as each character is spoken.
// chars: [{x0, x1, t}] in reading order; the band reaches char i's right edge `dur` after its time.
M.markerBand = (ctx, t, chars, y0, y1, color, alpha, { dur = 0.16, skew = 6 } = {}) => {
  let right = null;
  for (const c of chars) {
    const k = M.easeOut(M.prog(t, c.t, dur));
    if (k <= 0) break;
    right = M.lerp(c.x0, c.x1, k);
  }
  if (right === null) return;
  const left = chars[0].x0 - 6;
  ctx.save();
  ctx.fillStyle = M.rgba(color, alpha);
  ctx.beginPath();
  ctx.moveTo(left + skew, y0); ctx.lineTo(right + 6 + skew, y0);
  ctx.lineTo(right + 6, y1); ctx.lineTo(left, y1); ctx.closePath();
  ctx.fill();
  ctx.restore();
};

// Point on a quadratic arc from a to b that bows by `bow` px (perpendicular, to the left of a->b).
M.arc = (a, b, k, bow = -80) => {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
  const c = [mx - dy / L * bow, my + dx / L * bow];
  const u = 1 - k;
  return [u * u * a[0] + 2 * u * k * c[0] + k * k * b[0], u * u * a[1] + 2 * u * k * c[1] + k * k * b[1]];
};

// Caption line with coloured keyword runs, outlined for legibility; fades and rises in.
M.caption = (ctx, t, cap, { font, baseline, width, outline, outlineColor }) => {
  if (t < cap.start || t >= cap.end) return;
  const kin = M.easeOut((t - cap.start) / 0.14);
  const a = Math.min(kin, M.clamp((cap.end - t) / 0.1));
  ctx.save();
  ctx.font = font; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  const total = cap.runs.reduce((s, r) => s + ctx.measureText(r[0]).width, 0);
  let x = (width - total) / 2;
  const y = baseline + 10 * (1 - kin);
  for (const [text, color] of cap.runs) {
    ctx.lineJoin = "round";
    ctx.strokeStyle = M.rgba(outlineColor, a * 0.9); ctx.lineWidth = outline;
    ctx.strokeText(text, x, y);
    ctx.fillStyle = M.rgba(color, a);
    ctx.fillText(text, x, y);
    x += ctx.measureText(text).width;
  }
  ctx.restore();
};

window.M = M;
