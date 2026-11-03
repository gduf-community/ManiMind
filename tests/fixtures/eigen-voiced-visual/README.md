# Eigen Reading-Only v002 Handoff

## Frozen Interface

- Workspace: /Users/pengweitai/Projects/ManiMind
- Scene: examples/eigen_voiced_visual.py
- Class: EigenDirectionsVoicedLesson
- Renderer PYTHONPATH: src and examples (already provided by the native renderer).
- Plan: runtime/projects/eigen-directions-20261028/plan-voiced-v002.json
- Contract: runtime/projects/eigen-directions-20261028/revision-contract-voiced-v002.json
- Actual native clock: 254 seconds, 30 fps, 7620 frames.
- Original scene: examples/eigen_visual.py / EigenDirectionsLesson, 210 seconds.
- Only read() and the bounded construct() cue loop are overridden. All eight
  original chapter methods, geometry, formula selectors, matching transforms,
  movement run_time values, intermediate formulas, positions and paths are inherited.
- No base module globals are changed. The original tear_down still records
  eigen-motion.json; its writer label describes the reused original updaters.

| Cue | Actual Start | Actual End | Duration |
| --- | ---: | ---: | ---: |
| transform | 0 | 29 | 29 |
| directions | 29 | 57 | 28 |
| equations | 57 | 91 | 34 |
| equal | 91 | 125 | 34 |
| other | 125 | 160 | 35 |
| decompose | 160 | 206 | 46 |
| rotation | 206 | 234 | 28 |
| summary | 234 | 254 | 20 |

## Measurement and Scope

measured-speech-v001.json freezes the 27 ORIGINAL segment dictionaries, full
local WAV frame counts, rates, formats, SHA256 values and receipt SHA256 values.
All WAV bytes and header measurements were checked against the actual receipts.
No word-count duration estimate, new TTS, trimming, stretch, gain or movement
retiming was used. The existing narration draft fixture has exactly the same
27 segments as the actual approved narration and speech plan.

Case policy: max(original read duration, ceil(full measured WAV seconds + 0.5)).
This extends exactly 17 named static reads. Other reads and all movement focus
durations remain unchanged. It is a local lesson choice, not a workflow default.
Both the existing scheduler defaults (0.12-second edges, 0.25-second gap) and
more conservative 0.25-second edges fit all 27 complete takes in the measured
v002 focus windows. This proves interval capacity only, not semantic visibility
or listening quality.

The v001 baseline video was hash-checked and ffprobe measured:
210 seconds, 6300 frames, 1920x1080, 30 fps.
SHA256: d2ebebb3dc365d95791ce94fb723935765e854796a82a6a94618ec3ba21676f2
The eight-unit contract protects teaching functions, seven individual semantic
transitions, whole-plane/rotation/component motion, nonzero/real conditions and
a common coordinate scale. Decoration is not a hard constraint.

## Files and Verification

- plan-voiced-v002.json: media-independent copy of the new long-term plan.
- revision-contract-voiced-v002.json: copy of the eight-topic baseline inventory.
- measured-speech-v001.json: measured original take metadata, not runtime media.
- native-clock-contract.json: actual native helper observations of all chapters,
  focus windows, events, seven symbol transitions and every play interval.
- tests/test_eigen_voiced_visual.py: fixture-only tests, requiring no runtime
  project files, WAVs or baseline video. It passes the base module to the
  original native helper so inherited semantic() receives test glyphs.
- All original play durations, labels, transition formulas and centers match.
  After removing only consecutive identical samples, every native trajectory
  and relative frame time matches the old scene. Original mathematical
  invariants are also rerun against v002.
- The plan's 99 review_times are suggested sampling times mapped from original
  times and measured v002 focus/transition times, NOT pixel review findings.

Run from the workspace:

```sh
PYTHONPATH=src manimgl_env/bin/python -m pytest -q \
  tests/test_eigen_voiced_visual.py tests/test_eigen_visual.py \
  tests/test_content_regression.py tests/test_semantic_focus.py
```

Final verification: 70 passed, no skips, 4 dependency warnings (50.83 seconds).
This includes the unchanged original lesson's real-TeX checks, not GL rendering.

Frozen SHA256:
- Original source: 9b28098232167167d994e346f6ea2ad61172936de0244d17f8d9acb7d0b5f2e1
- Wrapper: 99d1edb7cd934c82ad27e9bea64957e8373b1e0845619da0c47db448730964cc
- New test: 1cc54ab0a482643f918b34d468727275c8b9334926592a36254d881de49d367b
- New plan: 544f8d15f37c8b754624d5d163a9e309652f65310a920b199871970b4b04e02d
- New contract: a64d0b524d884be66dc66545804991af0f8d7d924107c2f4298a4362b4f4c91c

98 pre-existing protected inputs, including the original source/helper/catalog,
old plans/narration and every existing speech directory file, were hash-checked
unchanged at handoff. Existing raw media and failed attempts are retained.

## Ownership and Next Gate

The author owns this wrapper, new plan/contract and test fixtures until source
freeze. The lead consumes them to render a NEW version. All frozen budgets and
observations expire if source, plan, baseline, speech PCM/receipt, focus,
typography or native runtime changes. Scene samples are per-execution state;
test glyph patches are in-memory, restored after each helper run.

The independent blind reviewer must inspect v002 actual pixels. A DIFFERENT
reviewer context then compares actual v001/v002 pixels against every contract
feature, with before/during/after evidence for each process. Only that reviewer
may write:
runtime/sessions/knowledge-trio-voice-20261028/review-eigen-regression-v002.json

No v002 render, pixel approval, regression pass, narration approval, audio
approval or publication was performed by this author. Do not reuse v001 approval
as v002 approval. After both visual gates, the lead revalidates the unchanged
original script, actual rendered focus timing, complete WAV alignment and
listening before any voiced release. Existing takes establish measured budgets;
the current publisher also binds each take to its original TTS plan. They cannot
be silently relabeled as receipts for a new visual-source plan. The coordinator
must prepare current approved speech inputs or implement a separately audited
provenance-preserving reuse path; this authoring handoff authorizes neither SSH
nor inference. The report path is intent only, not an author-written review.
