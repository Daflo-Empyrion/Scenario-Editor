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

"""Glossaire terminologique (core/glossary.py) + memoire de traduction
alimentee a la VALIDATION seulement + memoire VANILLE
(core/vanilla_memory.py) -- phase 1 et 2 de l'aide a la traduction."""

import json

import pytest


@pytest.fixture(autouse=True)
def _isolate_glossary(tmp_path, monkeypatch):
    """Isole le glossaire du fichier reel de la machine."""
    from core import glossary as g
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)



from core import glossary, translation_memory, vanilla_memory


@pytest.fixture()
def glossary_file(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(glossary, "_cache", None)
    return tmp_path / "glossary.json"


def test_glossary_add_and_apply(glossary_file):
    glossary.add_entry("Warp Drive", "moteur de distorsion")
    text, repl = glossary.apply_glossary(
        "Engage the warp drive now, warp drive offline.")
    assert "XXGLOS" in text
    restored = glossary.restore_glossary(text, repl)
    assert restored == "Engage the moteur de distorsion now, moteur de distorsion offline."


def test_glossary_case_insensitive_longest_first(glossary_file):
    glossary.add_entry("Warp", "warp FR")
    glossary.add_entry("Warp Drive", "moteur de distorsion")
    text, repl = glossary.apply_glossary("The warp drive is on")
    restored = glossary.restore_glossary(text, repl)
    # le terme le plus long gagne : 'Warp Drive' ne doit pas etre decoupe
    assert "warp FR drive" not in restored.lower()
    assert "moteur de distorsion" in restored


def test_glossary_disabled_not_applied(glossary_file):
    glossary.add_entry("Warp Drive", "moteur de distorsion")
    glossary.set_enabled("Warp Drive", False)
    text, repl = glossary.apply_glossary("Engage the warp drive")
    assert "XXGLOS" not in text
    assert repl == []


def test_glossary_forbidden_characters(glossary_file):
    assert not glossary.add_entry("[b]bad[/b]", "x")
    assert not glossary.add_entry("ok", "{bad}")
    assert glossary.add_entry("ok", "bon")


def test_auto_feed_threshold(glossary_file):
    assert glossary.auto_feed_ok("Warp Drive")           # 2 mots
    assert not glossary.auto_feed_ok("a b c d e f g")    # 7 mots
    assert not glossary.auto_feed_ok("")


def test_vanilla_memory_build_and_lookup(tmp_path, monkeypatch):
    from pathlib import Path
    csv_path = tmp_path / "Localization.csv"
    csv_path.write_text(
        "KEY,English,Français\n"
        "ItemName-1,Iron Ore,Minerai de fer\n"
        "ItemName-2,Empty\n",
        encoding="utf-8")
    monkeypatch.setattr(vanilla_memory, "VANILLA_MEMORY_FILE",
                        tmp_path / "vanilla_memory.json")

    class FakeSettings:
        pass
    monkeypatch.setattr(vanilla_memory.settings, "get_vanilla_content_path",
                        lambda: str(tmp_path))
    n = vanilla_memory.build_from_vanilla()
    assert n == 1
    assert vanilla_memory.get_vanilla_cached("Iron Ore", "fr") == "Minerai de fer"
    assert vanilla_memory.get_vanilla_cached("Inexistant", "fr") is None
    assert vanilla_memory.get_vanilla_cached("Iron Ore", "en") is None  # seulement en->fr


def test_translate_text_store_in_memory_false(monkeypatch):
    """store_in_memory=False : la memoire n'est PAS alimentee automatiquement
    -- l'alimentation se fait a la validation (appel store() de l'UI)."""
    from core import translation, settings as core_settings
    import core.translation_memory as tm
    stores = []
    monkeypatch.setattr(tm, "store", lambda *a: stores.append(a))
    monkeypatch.setattr(translation, "_AVAILABLE", True)
    monkeypatch.setattr(core_settings, "get_translation_engine", lambda: "google")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled", lambda: True)

    class FakeTranslator:
        def __init__(self, source, target):
            pass

        def translate(self, text):
            return "Bonjour"
    monkeypatch.setattr(translation, "GoogleTranslator", FakeTranslator)

    out = translation.translate_text("Hello", target="fr", store_in_memory=False)
    assert out == "Bonjour"
    assert stores == []  # pas d'alimentation automatique


def test_translate_text_consults_memory_first(monkeypatch):
    """La memoire utilisateur (et vanille) est consultee AVANT le moteur :
    un cache hit court-circuite l'appel moteur."""
    from core import translation, settings as core_settings
    import core.translation_memory as tm
    calls = []
    monkeypatch.setattr(tm, "get_cached", lambda text, source, target: "TRAD MÉMORISÉE")
    monkeypatch.setattr(translation, "_AVAILABLE", True)

    def boom(*a, **k):
        calls.append(1)
        raise AssertionError("le moteur ne doit pas etre appele sur cache hit")
    monkeypatch.setattr(translation, "GoogleTranslator", boom)
    monkeypatch.setattr(core_settings, "get_translation_engine", lambda: "google")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled", lambda: True)

    assert translation.translate_text("Hello", target="fr",
                                      store_in_memory=False) == "TRAD MÉMORISÉE"
    assert calls == []
