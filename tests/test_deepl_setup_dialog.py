# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Assistant DeepL (gui/deepl_setup_dialog.py) : construction complete du
dialogue (le chemin reel a crashe en v1.10.0 -- addWidget sur une
QHBoxLayout, TypeError en slot = crash natif PyQt6), cas "moteur" et
persistence de la cle. Tout le reseau est MOCKE."""

import pytest

from core import deepl_provider, settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    settings.set_deepl_api_key("")


def test_dialog_builds_and_shows_state(qapp, tmp_path, monkeypatch):
    from gui.deepl_setup_dialog import DeepLSetupDialog
    dlg = DeepLSetupDialog()
    dlg.show()
    try:
        # sans cle : case moteur grisee avec info-bulle
        assert not dlg.use_check.isEnabled()
        assert dlg.key_edit.text() == ""
        assert dlg.verify_status.text() == ""
    finally:
        dlg.close()
        dlg.deleteLater()


def test_dialog_use_as_engine_roundtrip(qapp, tmp_path, monkeypatch):
    from gui.deepl_setup_dialog import DeepLSetupDialog
    settings.set_deepl_api_key("cle:fx")
    dlg = DeepLSetupDialog()
    try:
        assert dlg.use_check.isEnabled()
        assert dlg.key_edit.text() == "cle:fx"
        # cocher la case -> moteur deepl persiste ; decocher -> google
        dlg.use_check.setChecked(True)
        assert settings.get_translation_engine() == "deepl"
        dlg.use_check.setChecked(False)
        assert settings.get_translation_engine() == "google"
    finally:
        dlg.close()
        dlg.deleteLater()


def test_dialog_verify_requires_key(qapp, tmp_path, monkeypatch):
    """Verifier sans cle : message inline, AUCUN appel reseau."""
    import gui.deepl_setup_dialog as mod
    from gui.deepl_setup_dialog import DeepLSetupDialog

    def boom(*a, **k):
        raise AssertionError("aucun reseau attendu sans cle")
    monkeypatch.setattr(mod, "_fetch_usage", boom)
    dlg = DeepLSetupDialog()
    try:
        dlg.key_edit.setText("")
        dlg._verify()
        assert "cle" in dlg.verify_status.text().lower()
    finally:
        dlg.close()
        dlg.deleteLater()


def test_dialog_verify_ok_shows_quota(qapp, tmp_path, monkeypatch):
    import gui.deepl_setup_dialog as mod
    from gui.deepl_setup_dialog import DeepLSetupDialog
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(mod, "_fetch_usage",
                        lambda: {"character_count": 1234,
                                 "character_limit": 500000})
    dlg = DeepLSetupDialog()
    try:
        dlg.key_edit.setText("cle:fx")
        dlg._verify()
        assert "1 234" in dlg.verify_status.text() or "1234" in dlg.verify_status.text()
        assert "500000" in dlg.verify_status.text() or "500 000" in dlg.verify_status.text()
    finally:
        dlg.close()
        dlg.deleteLater()
