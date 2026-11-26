"""Every environment-dependent test registered in conftest must still exist, so skips cannot go stale."""

from pathlib import Path
import re

import conftest

ROOT = Path(__file__).resolve().parents[1]


def registered():
    ids = list(conftest.LOCAL_MEDIA)
    for entry in conftest.REQUIREMENTS.values():
        if entry:
            ids.extend(entry[1])
    return ids


def test_registered_tests_exist_and_are_unique():
    ids = registered()
    assert len(ids) == len(set(ids))
    for nodeid in ids:
        path, name = nodeid.split("::")
        source = (ROOT / path).read_text(encoding="utf-8")
        assert re.search(rf"^def {re.escape(name)}\(", source, re.M), nodeid


def test_local_media_paths_stay_inside_untracked_outputs():
    assert all(path.startswith("outputs/") for path in conftest.LOCAL_MEDIA.values())
