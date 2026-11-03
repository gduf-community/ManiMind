# Independent Wave Lesson Sources v003

Historical test baseline after the voiced retiming revision: the three
wave_*_visual.py files in this directory are exact source exports from local
commit 00f4fe1. Their hashes are checked against source-freeze-v003.json.
Baseline clock tests execute these snapshots, not newer production scenes with
old plans. They are test inputs, never runtime fallback modules or new approval.
Current production import/isolation checks still inspect examples/ sources;
new voiced-clock tests must use their matching versioned data separately.

Current production inputs are these data snapshots plus each lesson's own
examples/wave_*_visual.py, examples/wave_unit_shared.py and the unchanged pure
examples/wave_unit_model.py. The v001/v002 snapshots and historical aggregate
examples/wave_unit_visual.py remain unchanged and are not production imports.

The source split preserves all three lesson clocks, formation methods, model,
science, teaching notes and intact narration text. Reading separates the time
label from the wavelength span. Superposition removes the overlap-only sum
before time resumes, and removes the velocity caption with its arrows.

The new narration-draft-v002.json files preserve every unit.text. Only S04/r2
is split into r2a (approach) and r2b (fully-flat result). The superposition scene
holds that fully-flat state for six additional real reading seconds, with the
physical clock frozen at t=3s, before introducing velocity arrows. Its duration
is 158s rather than 152s; motion itself is not stretched. The original v001
draft snapshots are historical inputs, not the selected v003 narration drafts.

Each watch-v003.json records only that lesson's real understanding_render input
set and its plan. It does not include another lesson's source, plan, narration,
watch file or the aggregate unit freeze. Shared base/model/core/context inputs
still invalidate every dependent lesson when they change. An aggregate freeze
is a handoff snapshot, not an extra common production dependency.

Tests rebuild context-v003 under tmp_path from tracked data and test independent
hash invalidation using synthetic hold edits only in temporary copies. They do
not retime production, render, generate speech or grant approval. All three
lessons need a new v003 render and independent visual review after this split;
no historical approval is inherited.

Writer: 01a1817c-7136-79a3-9ca8-6b508ab35228. Consumers: lead and offline tests.
Lifecycle: this source split and exact data revision. Any changed bound input
requires a new per-lesson attempt/watch record; shared changes require all
dependent lessons to be reconsidered. No review report is authored here.
