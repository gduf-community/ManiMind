# Derivative Visual Test Inputs

Fresh topic `derivative-local-20261028`, not a revision or an approved film.

`plan.json` and `narration-draft-v001.json` are versioned test inputs. The lead's
project copies live under `runtime/projects/derivative-local-20261028/`. Tests read
only these tracked fixtures, source and existing native libraries, never ignored
runtime/outputs or another lesson's candidate.

`native-clock-contract.json` is a reproducible harness timing snapshot, not a
render report or readable-pixel evidence. Its events and windows are compared
against a new native execution on every test run.

Native clock tests use `tests/lesson_native_harness.py`: real ManimGL animations,
interpolation, geometry and updaters at 30 fps; text, numbers and TeX are vector
placeholders. Separate optional native TeX checks verify real token selectors,
formula compilation and actual glyph transforms/cleanup, not rendered scene
pixels. Neither test path is a visual or narration approval.

The bounded scene is 234 seconds / 7020 frames. No renderer, SSH, speech worker,
publication or independent review is invoked by this authoring handoff.

Source: [OpenStax Calculus Volume 1, section 3.1](https://openstax.org/books/calculus-volume-1/pages/3-1-defining-the-derivative).
All coordinates, concrete square-function algebra at a=1, common-scale zoom
and absolute-value counterexample are authored for this topic; no textbook
figure, old output candidate or complete previous lesson is imported.
