"""WP-25: app.py renders end to end (acceptance: a non-technical presenter can
complete the demo). Uses Streamlit's in-process AppTest — no browser. Skipped
when the [demo] extra isn't installed, so core CI is unaffected."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="requires the [demo] extra (streamlit)")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app.py"
PAGES = ["Five Planes", "DIP Contracts", "Journeys", "Ledger", "Router", "Reuse"]


def test_app_boots_without_exception():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception


def test_every_page_renders_without_exception():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    for page in PAGES:
        at = at.sidebar.radio[0].set_value(page).run()
        assert not list(at.exception), (page, list(at.exception))
