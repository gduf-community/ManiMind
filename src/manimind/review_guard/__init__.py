"""Create-only review-process guards layered beside the frozen publishers.

Nothing here edits or monkeypatches ``manimind.postproduce`` or
``manimind.review``; the frozen gates stay authoritative for release.  These
modules add the structural checks the old flow lacked:

* :mod:`.sanitize` -- reviewer-visible plan copies without prior judgments and
  a validator for everything reachable from a first-look packet.
* :mod:`.identity` -- one reviewer context per lesson/version/stage.
* :mod:`.report` -- fixed report status enum, playback coverage, skeleton and
  pre-submission checks (replacing per-reviewer ``review_tools.py``).
* :mod:`.gates` -- first-look and regression gates as separate entry points,
  plus a merge-stage combination.

State records written by this package declare writer, consumers, lifecycle and
invalidation like the rest of the project.
"""
