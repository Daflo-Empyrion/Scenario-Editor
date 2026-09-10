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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  Aucune garantie.
#
# Tests du provider de traduction hors ligne Argos (core/argos_provider.py)
# -- SANS reseau ni installation reelle : l'index et les telechargements
# sont simules (fakes urlopen/HEAD).

import json
from pathlib import Path

import core.settings as settings
from core import argos_provider


def test_translation_engine_setting_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    assert settings.get_translation_engine() == "google"  # defaut
    settings.set_translation_engine("argos")
    assert settings.get_translation_engine() == "argos"
    settings.set_translation_engine("autre")  # valeur invalide ignoree
    assert settings.get_translation_engine() == "argos"


def test_console_command_targets_app_dir():
    cmd = argos_provider.pip_console_command()
    assert "pip" in cmd and "argostranslate" in cmd
    assert "--target" in cmd
    assert str(argos_provider.engine_target_dir()) in cmd


def test_available_pairs_parses_official_index(monkeypatch):
    payload = [
        {"from_code": "fr", "to_code": "en", "from_name": "French",
         "to_name": "English", "links": ["https://x/translate-fr_en-1_9.argosmodel"]},
        {"from_code": "de", "to_code": "en", "from_name": "German",
         "to_name": "English", "links": []},  # sans lien : ignore
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(argos_provider.urllib.request, "urlopen",
                        lambda req, timeout=30: FakeResponse())
    pairs = argos_provider.available_pairs()
    assert len(pairs) == 1
    assert pairs[0]["from_code"] == "fr" and pairs[0]["to_code"] == "en"
    assert pairs[0]["link"].endswith(".argosmodel")


def test_translate_offline_raises_without_engine(monkeypatch):
    # argostranslate non importable : translate_offline doit lever (jamais
    # retourner silencieusement du vide -- l'appelant retombe en ligne)
    monkeypatch.setitem(__import__("sys").modules, "argostranslate", None)
    import importlib
    try:
        argos_provider.translate_offline("texte", "fr", "en")
        assert False, "devait lever"
    except Exception:
        pass


def test_dispatch_prefers_argos_when_configured(tmp_path, monkeypatch):
    """engine=argos + paire installee -> translate_text sert le chemin hors
    ligne (simule par un monkeypatch de translate_offline)."""
    import core.translation as tr
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(tr, "_AVAILABLE", True)
    settings.set_translation_engine("argos")
    calls = []
    monkeypatch.setattr(argos_provider, "translate_offline",
                        lambda text, source, target: calls.append(text) or "OFFLINE")
    try:
        result = tr.translate_text("bonjour", target="en")
        assert result == "OFFLINE" and calls == ["bonjour"]
    finally:
        settings.set_translation_engine("google")


def test_dispatch_falls_back_when_argos_missing(tmp_path, monkeypatch):
    """engine=argos mais paire absente -> retombee sur le chemin en ligne
    (ici : deep-translator appele, simule)."""
    import core.translation as tr
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(tr, "_AVAILABLE", True)
    monkeypatch.setattr(settings, "get_online_translation_enabled", lambda: True)
    monkeypatch.setattr(tr, "protect_segments", lambda text: (text, []))
    monkeypatch.setattr(tr, "restore_segments", lambda text, segs: text)
    settings.set_translation_engine("argos")

    class FakeTranslator:
        def __init__(self, source, target):
            pass

        def translate(self, text):
            return "hello"

    monkeypatch.setattr(tr, "GoogleTranslator", FakeTranslator)
    monkeypatch.setattr(argos_provider, "translate_offline",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("absente")))
    result = tr.translate_text("bonjour", target="en", source="fr")
    assert result == "hello"
    settings.set_translation_engine("google")


def test_argos_pair_missing_and_online_disabled_clear_message(tmp_path, monkeypatch):
    """engine=argos + paire absente + traduction en ligne desactivee : le
    message combine les DEUX causes (retour du 10/09/2026 : le message
    "Google non active" apparaissait a tort, sans parler d'Argos)."""
    import core.translation as tr
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(tr, "_AVAILABLE", True)
    monkeypatch.setattr(settings, "get_online_translation_enabled", lambda: False)
    settings.set_translation_engine("argos")
    monkeypatch.setattr(argos_provider, "translate_offline",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("paire fr->de non installee")))
    try:
        tr.translate_text("texte", target="de")
        assert False, "devait lever"
    except RuntimeError as e:
        assert "hors ligne impossible" in str(e)
        assert "Argos" in str(e) and "en ligne est desactivee" in str(e)
    settings.set_translation_engine("google")


def test_online_error_page_never_returned_as_translation(tmp_path, monkeypatch):
    """Google peut renvoyer sa page d'erreur HTML 500 comme 'traduction' :
    doit lever une erreur propre, jamais rendre le garbage (retour du
    10/09/2026)."""
    import core.translation as tr
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(tr, "_AVAILABLE", True)
    monkeypatch.setattr(settings, "get_online_translation_enabled", lambda: True)
    monkeypatch.setattr(tr, "protect_segments", lambda text: (text, []))
    monkeypatch.setattr(tr, "restore_segments", lambda text, segs: text)
    settings.set_translation_engine("google")

    class FakeTranslator:
        def __init__(self, source, target):
            pass

        def translate(self, text):
            return "Error 500 (Server Error)!!1500.That's an error."

    monkeypatch.setattr(tr, "GoogleTranslator", FakeTranslator)
    try:
        # texte UNIQUE : la memoire de traduction persistante servirait sinon
        # une ancienne traduction sans passer par Google
        tr.translate_text(f"phrase unique {tmp_path}", target="en", source="fr")
        assert False, "devait lever"
    except RuntimeError as e:
        assert "page d'erreur" in str(e)
