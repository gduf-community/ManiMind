"""Canvas main stage: seek(t) teaching films rendered by HyperFrames.

- ``assets/``: browser-side engine owned by ManiMind (motion vocabulary, plane/arrows, KaTeX formulas
  with per-symbol continuous morphs) and the HyperFrames frame adapter. HyperFrames itself
  (tools/hyperframes, pinned) does capture, encoding and audio; nothing here re-implements it.
- ``project``: assemble a HyperFrames project from a scene directory.
- ``render``: lint/render with the pinned CLI and browser, determinism check, receipt.
- ``timing``: film clock (cues, captions) from voiced units' character times.

ManimGL remains the asset source for 3D, path-level shape morphs and LaTeX beyond KaTeX; its alpha
renders are composited into Canvas scenes. Easing/spring ideas follow vibe-knowledge (MIT, Berryxia).
"""
