# Nonlinear Projectile Source Handoff

`plan.json` and `narration-draft.json` are portable test-only snapshots of the
current candidate's timing and semantic intent, not runtime approval records.
`native-clock-smoke.json` is the author's historical handoff, captured before
the v002 layout fix and subsequent two-sentence text revision in a native test:
301.5 seconds, 9045 frame steps, 55 focus windows. It is not a render report.

The test reuses the paced test's native ManimGL animation and updater harness,
redirects the frozen candidate import to the existing integrated fixture, and
uses mocked text/TeX geometry. Matching, area-piece rotation, shared physical
time, geometry sampling, waits and Scene.get_time execute; no camera renders.
The fixture does not establish real glyph layout, pixels, speech fit or review.

The coordinator owns the frozen revision contract and independent review. The
author supplies no approval. Production must use the actual frozen source
listed in plan.sources, never the test candidate as a production fallback.

Reproduce locally with:

```sh
manimgl_env/bin/python -m pytest tests/test_projectile_nonlinear.py tests/test_projectile_precise.py -q
```
