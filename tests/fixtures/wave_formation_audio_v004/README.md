# Formation v004 Original-Audio Timing Data

Tracked, non-media inputs for an independent offline test. scene.py/shared_source.py
are source snapshots, not production imports. plan.json is the authorized v004
input. narration.json preserves every original unit/ref exactly. timings.json
copies all real clause/word estimates, WAV hashes and durations; its software
identity and source list are deliberately reduced to actual representative
entries. This test subset must NEVER enter a production provenance gate.

The original full timing file was verified read-only by verify_production_timings,
with evidence SHA256:
90cf3bc542b52c2ea06301cde8d7e3eb89f069df56bc17361d58aa4abddbc441.
No WAV, runtime tree, inference, video or font IO is needed by these tests.
Zero-duration words remain uncertain and are not acoustic interval evidence.
expected.json records all five intact-WAV placements and 16 positive-word
state checks, not listening approval.

F04's bottom position is explicitly a historical sample at t=14s; the current
solid particle is already back at t=16s. Actual new pixels and an independent
regression must check this equivalent expression. Original 104.64s speech is
not trimmed, resynthesized or sped up.

Writer: 01a1817c-7136-79a3-9ca8-6b508ab35228. Consumers: offline tests and lead.
Lifecycle: this source/text/timing revision. Changed inputs require a new
snapshot; v003 data and historical reviews remain unchanged. This grants no
visual, narration, listening, regression or publication approval.
