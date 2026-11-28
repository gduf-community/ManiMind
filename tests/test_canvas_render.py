import json
from pathlib import Path

from manimind.canvas import render

FIXTURE = Path(__file__).parent / "fixtures/canvas/tiny"


def test_hyperframes_renders_the_fixture_and_frames_do_not_depend_on_render_order(tmp_path):
    receipt = render.render(FIXTURE, tmp_path / "r", check="0.0:1.0")
    assert receipt["determinism"]["identical"] and receipt["determinism"]["frames"] == 30
    assert receipt["versions"]["hyperframes"] == "0.9.43"
    assert receipt["versions"]["browser_version"]
    saved = json.loads((tmp_path / "r/receipt.json").read_text(encoding="utf-8"))
    assert saved["film"]["sha256"] == receipt["film"]["sha256"]
