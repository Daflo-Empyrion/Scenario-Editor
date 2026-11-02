"""Gabarit de dialogue web (gui/web_dialog.py) : pont de base."""
from gui.web_dialog import WebBridge


def test_bridge_push_reset_emits(qapp):
    seen = []
    b = WebBridge()
    b.data_changed.connect(seen.append)
    b.push_reset()
    assert seen == [""]
