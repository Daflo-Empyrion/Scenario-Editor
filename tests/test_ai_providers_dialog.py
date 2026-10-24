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

"""Dialogue Fournisseurs IA : construction et chemin connecte (ajout de
presets, generation des maillons, budget, moteur actif). Aucun reseau."""
import pytest
from PyQt6 import sip

from core import settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    from core.ai import budget
    budget.reset()


def test_dialog_adds_openrouter_free_loop(qapp):
    from gui.ai_providers_dialog import AiProvidersDialog
    dialog = AiProvidersDialog()
    try:
        dialog._add_preset("openrouter")
        links = settings.get_ai_links()
        assert links
        assert all(link["tier"] == "free" for link in links)
        assert all(link["model"].endswith(":free") for link in links)
        assert settings.get_ai_providers()[0]["base_url"] == \
            "https://openrouter.ai/api/v1"
    finally:
        sip.delete(dialog)


def test_dialog_deepseek_direct_and_global_settings(qapp):
    from gui.ai_providers_dialog import AiProvidersDialog
    dialog = AiProvidersDialog()
    try:
        dialog._add_preset("deepseek")
        providers = settings.get_ai_providers()
        deepseek = next(p for p in providers if p["preset"] == "deepseek")
        assert deepseek["base_url"] == "https://api.deepseek.com"
        links = [link for link in settings.get_ai_links()
                 if link["provider"] == deepseek["id"]]
        assert links and links[0]["model"] == "deepseek-chat"
        assert links[0]["price_in"] == pytest.approx(0.30)
        assert links[0]["tier"] == "paid"

        dialog.paid_check.setChecked(True)
        dialog.cap_spin.setValue(5.0)
        assert settings.get_ai_paid_enabled() is True
        assert settings.get_ai_monthly_cap_usd() == pytest.approx(5.0)

        dialog.batch_check.setChecked(False)
        assert settings.get_ai_batch_enabled() is False
        dialog.use_check.setChecked(True)
        assert settings.get_translation_engine() == "ai"
    finally:
        sip.delete(dialog)


def test_dialog_remove_provider_drops_links(qapp):
    from gui.ai_providers_dialog import AiProvidersDialog
    dialog = AiProvidersDialog()
    try:
        dialog._add_preset("openrouter")
        assert settings.get_ai_links()
        dialog._remove_provider()
        assert settings.get_ai_links() == []
        assert settings.get_ai_providers() == []
    finally:
        sip.delete(dialog)
