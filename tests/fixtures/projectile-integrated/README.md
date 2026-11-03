Deterministic source/data fixtures for the supervised integrated lesson.

`frozen_candidate.py` is a read-only snapshot of the actual legacy utility
dependency at `outputs/sol61-visual-first-20261024-v1/candidate.py`. It is test
input, never a production fallback. The tracked legacy full/landing sources
remain the production implementation; tests redirect only the frozen utility
import, so test collection does not need ignored outputs or runtime files.

Plan, draft and revision contract are snapshots of this handoff's intent, not
measured evidence or approval. Writer: supervised visual author. Consumers:
offline regression tests. Lifecycle: this fixture revision. Invalidation: any
corresponding source, timing, plan, draft or contract change. Geometry smoke
uses native vector objects and an in-memory clock/filesystem; it does not
compile TeX, rasterize text, render pixels, generate speech, or approve release.
