# Wave Unit Data Snapshots

The root data files remain the immutable v001 handoff. Current tests use the
additive v002/ snapshots, which add author_context and bind the shared Dot-fill
and axis-end-label repair. v001 media and independent reviews are not replaced.

These are tracked, non-media teaching inputs for the three fresh wave lessons.
They are exact copies of the author handoff bound by source-freeze-v001.json,
not independent approval, measured render output, narration timing or student
evidence. The editor-owned unit.json is an unchanged input snapshot; its original
writer remains the curriculum editor. The lesson plans, narration drafts and
scientific brief identify their actual author_agent explicitly.

Tests load plans and narration only from this directory. They build context-v003
in pytest tmp_path from the unit snapshot and tracked catalogue using the current
curriculum builder, then verify its provenance. They never require an existing
runtime/ tree, copy machine-specific context paths, or skip a missing runtime.
Plans retain production-relative source paths to document the original handoff;
the tests resolve their data snapshots here instead of executing ignored files.

The shared implementation is examples/wave_unit_model.py; the three native scene
classes are in examples/wave_unit_visual.py. A model-only import needs no ManimGL
or NumPy. The simulated scene clock checks mark/focus/cue boundaries but is not
real-render evidence. The frozen runtime inputs are not modified while the lead
renders: fixture or test changes do not authorize visual-source changes.

Writer of these exact snapshots: author agent
01a1817c-7136-79a3-9ca8-6b508ab35228. Consumers: offline tests and maintainers.
Lifecycle: this handoff revision. Source, model, plan or facts changes require
an explicit new coordinated snapshot/freeze, never an approval-field shortcut.
