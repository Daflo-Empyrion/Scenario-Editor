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
import sys
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


def test_console_command_frozen_uses_system_python(monkeypatch):
    """Version installee : le repli console vise le Python du SYSTEME (py),
    pas l'exe -- `EmpyrionScenarioEditor.exe -m pip` ne veut rien dire."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert argos_provider.pip_console_command().startswith("py -m pip")


def test_pip_output_splits_lines_and_captures():
    w = argos_provider._PipOutput(capture=True)
    w.write("ligne1\nlign")
    w.write("e2\n")
    assert w.getvalue() == "ligne1\nligne2\n"


def test_pip_output_forwards_clean_lines():
    got = []
    w = argos_provider._PipOutput(line_cb=got.append)
    w.write("  a \n b \n")
    w.write("sans retour")
    w.flush()
    assert got == ["a", "b", "sans retour"]


def test_pip_output_no_cb_is_harmless():
    w = argos_provider._PipOutput()  # ni callback ni capture
    w.write("x\n")
    w.flush()
    assert w.getvalue() == ""


def test_pip_inprocess_handles_system_exit(monkeypatch):
    """pip >= 26 : main() se termine par sys.exit (vecu avec --version).
    None = succes, int = code, texte = echec."""
    import pip._internal.cli.main as pip_main_module

    def fake_main(args):
        raise SystemExit(None)

    monkeypatch.setattr(pip_main_module, "main", fake_main)
    code, _ = argos_provider._pip_inprocess(["x"])
    assert code == 0

    def fake_main_fail(args):
        raise SystemExit("message d'erreur")

    monkeypatch.setattr(pip_main_module, "main", fake_main_fail)
    code, _ = argos_provider._pip_inprocess(["x"])
    assert code == 1

    monkeypatch.setattr(pip_main_module, "main", lambda args: 0)
    code, _ = argos_provider._pip_inprocess(["x"])
    assert code == 0


def test_install_engine_frozen_uses_inprocess_pip(monkeypatch, tmp_path):
    """Frozen : l'installation DOIT passer par pip in-process (un
    sous-processus `exe -m pip` relancerait l'application) avec --target
    vers le dossier de l'app."""
    site = tmp_path / "site"
    monkeypatch.setattr(argos_provider, "ARGOS_SITE_DIR", site)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(argos_provider, "is_engine_available", lambda: True)
    seen = {}

    def fake_pip(args, progress_cb=None, capture_stdout=False):
        seen["args"] = args
        assert "--target" in args and str(site) in args
        # roues uniquement : une compilation relancerait l'exe (build isolation)
        assert "--only-binary=:all:" in args
        return 0, ""

    monkeypatch.setattr(argos_provider, "_pip_inprocess", fake_pip)
    assert argos_provider.install_engine(progress_cb=lambda m: None)
    assert seen["args"][0] == "install"


def test_install_engine_frozen_failure_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(argos_provider, "ARGOS_SITE_DIR", tmp_path / "site")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(argos_provider, "_pip_inprocess",
                        lambda *a, **k: (1, ""))
    assert not argos_provider.install_engine(progress_cb=lambda m: None)


def test_estimate_frozen_uses_inprocess_dry_run(monkeypatch):
    """Frozen : l'estimation pilote le pip embarque (dry-run --report -),
    jamais `sys.executable -m pip`."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    report = json.dumps({"install": [
        {"download_info": {"url": "https://x/roue.whl"}}]})

    class FakeHead:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b""

        @property
        def headers(self):
            return {"Content-Length": "42"}

    monkeypatch.setattr(argos_provider.urllib.request, "urlopen",
                        lambda req, timeout=30: FakeHead())

    def fake_pip(args, progress_cb=None, capture_stdout=False):
        assert capture_stdout and "--dry-run" in args and "--report" in args
        return 0, report

    monkeypatch.setattr(argos_provider, "_pip_inprocess", fake_pip)
    assert argos_provider.estimate_engine_download_bytes() == 42


def test_estimate_frozen_pip_failure_returns_none(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(argos_provider, "_pip_inprocess",
                        lambda *a, **k: (1, ""))
    assert argos_provider.estimate_engine_download_bytes() is None


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
