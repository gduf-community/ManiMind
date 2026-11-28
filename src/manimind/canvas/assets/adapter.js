// HyperFrames frame adapter for ManiMind seek(t) films.
//
// HyperFrames renders by seeking a paused GSAP timeline registered in window.__timelines.
// This adapter registers one timeline whose single tween drives a clock, and every update calls
// the film's pure seek(t). The film is built lazily on the first seek, after HyperFrames has
// waited for document fonts, so KaTeX layout is measured with real fonts.
//
// A scene defines window.createFilm = () => ({ duration, seek(t) }) and lists the fonts it
// measures with in scene.json; the assembled index.html calls ManimindCanvas.register(...).
"use strict";

window.ManimindCanvas = {
  // offset: film time of the composition's t = 0 (a check project renders only a span of the film).
  register({ compositionId = "root", duration, fonts = [], offset = 0 }) {
    for (const f of fonts) document.fonts.load(f);  // HyperFrames waits for these before capture
    // Pin every 2D canvas to the CPU rasterizer before any scene code asks for a context. Chrome otherwise
    // starts a canvas in software and promotes it to the GPU after some frames, so a worker's first
    // frame was antialiased differently from the same frame drawn later (fixture check, 2026-11-28).
    // getContext returns this same context to the scene's later getContext("2d") calls.
    for (const c of document.querySelectorAll("canvas")) c.getContext("2d", { willReadFrequently: true });
    let film = null;
    const clock = { t: 0 };
    const draw = () => {
      film = film || window.createFilm();
      film.seek(clock.t + offset);
    };
    window.__timelines = window.__timelines || {};
    const tl = gsap.timeline({ paused: true });
    tl.to(clock, { t: duration, duration, ease: "none", onStart: draw, onUpdate: draw });
    window.__timelines[compositionId] = tl;
    return tl;
  },
};
