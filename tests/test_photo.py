"""Test for planted error 3: the wrong breaker in a photo (Member A, Day 5).

Member C's photo check must flag the EQ-BRK-05 nameplate (shows 400 A) against the
approved submittal (630 A), and the alert feed must show it.
Run from the project root:  python3 -m pytest tests/ -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.alerts import photo_alerts  # noqa: E402
from src.graph.build_graph import build_graph  # noqa: E402
from src.vision.reality_delta import cached_results  # noqa: E402


@pytest.fixture(scope="module")
def breaker_photo():
    results = [r for r in cached_results() if r["equipment_id"] == "EQ-BRK-05"]
    assert results, "no photo result for EQ-BRK-05"
    return results[0]


def test_breaker_photo_is_flagged_as_a_mismatch(breaker_photo):
    assert breaker_photo["status"] == "MISMATCH"
    assert breaker_photo["extracted"]["rating_value"] == 400
    assert breaker_photo["expected"]["rating_value"] == 630


def test_photo_is_compared_with_the_real_submittal():
    # the value the photo is checked against must be the submittal in our data
    G = build_graph()
    sub = G.nodes["SUB-006"]
    assert sub["equipment_id"] == "EQ-BRK-05" and sub["rating_value"] == 630


def test_breaker_photo_shows_up_in_the_alert_feed():
    alerts = {a["id"]: a for a in photo_alerts()}
    assert "PHOTO-PH-05" in alerts
    assert alerts["PHOTO-PH-05"]["severity"] == "high"
    assert alerts["PHOTO-PH-05"]["equipment_id"] == "EQ-BRK-05"
