// Smallest scene exercising the engine: a moving arrow on a plane and a KaTeX per-symbol morph.
"use strict";
window.createFilm = () => {
  const ctx = document.getElementById("c").getContext("2d");
  const F = new E.Formulas(document.getElementById("fx"));
  const p = E.tag("a"), q = E.tag("b");
  F.add("a", p("x", "x") + p("eq", "{}={}") + p("y", "y"), { x: 960, y: 300, size: 64 });
  F.add("b", q("y", "y") + q("eq", "{}={}") + q("x", "x"), { x: 960, y: 300, size: 64 });
  const cam = { cx: 960, cy: 700, unit: 80 };
  return {
    duration: 1.0,
    seek(t) {
      F.reset();
      ctx.fillStyle = "#101416"; ctx.fillRect(0, 0, 1920, 1080);
      E.grid(ctx, cam, E.lerpMat(E.I, [[2, 1], [1, 2]], M.smooth(t)), { extent: 6 });
      E.arrow(ctx, cam, [0, 0], [Math.cos(3 * t), Math.sin(3 * t)], { color: "#58CFA9", glow: 8 });
      F.morph("b", ["a"], M.clamp((t - 0.2) / 0.6), { map: { x: { src: "x", bow: 60 }, y: { src: "y", bow: 60 } } });
      return true;
    },
  };
};
