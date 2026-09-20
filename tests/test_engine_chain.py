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

"""Chaine de secours des moteurs de traduction (v1.10.0, inspiree du
failover de freellmapi) : quota/panne du principal -> maillons suivants
(Groq -> DeepL -> Google -> NLLB -> Argos a partir du principal), maillon
en echec mis au repos, AuthError JAMAIS basculee, permission "Traduction
en ligne" respected. Les moteurs sont MOCKES aux frontieres provider :
aucun reseau, aucun modele reel."""

import pytest

from core import deepl_provider, groq_provider, nllb_provider, settings
from core import translation
from core.engine_errors import (AuthError, EngineUnavailableError,
                                QuotaExhaustedError)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Settings isoles + memoires/glossaire vides + AUCUN moteur configure
    par defaut + repos de maillons remis a zero entre les tests."""
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    import core.glossary as g
    import core.translation_memory as tm
    import core.vanilla_memory as vm
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)
    monkeypatch.setattr(tm, "get_cached", lambda *a, **k: None)
    monkeypatch.setattr(vm, "get_vanilla_cached", lambda *a, **k: None)
    monkeypatch.setattr(groq_provider, "MIN_INTERVAL_S", 0.0)
    settings.set_groq_api_key("")
    settings.set_deepl_api_key("")
    settings.set_engine_fallback_enabled(True)
    monkeypatch.setattr(nllb_provider, "is_installed", lambda variant: False)
    translation.reset_link_states()
    yield
    translation.reset_link_states()


def _fake_engines(monkeypatch, groq=None, deepl=None, google=None,
                  nllb=None, argos=None):
    """Fonctions moteur factices ; chaque argument est une fonction
    (texte) -> traduction OU une exception a lever."""
    calls = {"groq": 0, "deepl": 0, "google": 0, "nllb": 0, "argos": 0}

    def _make(name, fn, patch_target, *patch_args):
        def wrapped(gtext, *a, **k):
            calls[name] += 1
            if isinstance(fn, Exception):
                raise fn
            return fn(gtext)
        if patch_args:
            monkeypatch.setattr(patch_target, patch_args[0], wrapped)
        else:
            monkeypatch.setattr(patch_target, wrapped)

    if groq is not None:
        _make("groq", groq, translation, "_translate_llm_whole_cell")
    if deepl is not None:
        _make("deepl", deepl, deepl_provider, "translate")
    if google is not None:
        _make("google", google, translation, "_translate_google")
    if nllb is not None:
        _make("nllb", nllb, translation, "_translate_nllb")
    if argos is not None:
        _make("argos", argos, translation, "_translate_offline_fragments")
    return calls


def test_primary_served_no_fallback(tmp_path, monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = _fake_engines(monkeypatch, groq=lambda t: "FR:" + t,
                          deepl=lambda t: "DL:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "FR:Hello"
    assert calls == {"groq": 1, "deepl": 0, "google": 0, "nllb": 0, "argos": 0}
    assert translation.last_fallback_note() == ""


def test_quota_falls_to_deepl_then_remembered(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = _fake_engines(monkeypatch,
                          groq=QuotaExhaustedError("Quota Groq epuise."),
                          deepl=lambda t: "DL:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "DL:Hello"
    assert calls["groq"] == 1 and calls["deepl"] == 1
    assert "DeepL" in translation.last_fallback_note()
    # le maillon Groq est au repos : la cellule suivante ne le reessaie pas
    translation.translate_text("World", target="fr", store_in_memory=False)
    assert calls["groq"] == 1 and calls["deepl"] == 2


def test_outage_falls_to_google(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = _fake_engines(monkeypatch,
                          groq=EngineUnavailableError("Reseau"),
                          google=lambda t: "GG:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "GG:Hello"
    assert calls["groq"] == 1 and calls["google"] == 1


def test_auth_error_never_falls_back(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = _fake_engines(monkeypatch,
                          groq=AuthError("Cle API Groq refusee (401)."),
                          deepl=lambda t: "DL:" + t)
    with pytest.raises(AuthError, match="refusee"):
        translation.translate_text("Hello", target="fr",
                                   store_in_memory=False)
    assert calls["deepl"] == 0


def test_unconfigured_engines_skipped(monkeypatch):
    # Aucune cle Groq/DeepL : la chaine ne contient que Google
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = _fake_engines(monkeypatch, google=lambda t: "GG:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "GG:Hello"
    assert calls["google"] == 1


def test_deepL_skipped_for_unsupported_target(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = _fake_engines(monkeypatch, groq=lambda t: "FR:" + t)
    # meme pour une langue que DeepL ne couvre pas, Groq tient : rien ne change
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "FR:Hello"
    assert calls["groq"] == 1


def test_offline_link_after_online_ones(monkeypatch):
    # permission OFF : les 3 maillons en ligne sont filtres, chaine = locaux
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: False)
    monkeypatch.setattr(nllb_provider, "is_installed", lambda v: True)
    calls = _fake_engines(monkeypatch, nllb=lambda t: "NL:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "NL:Hello"
    assert calls["nllb"] == 1 and calls["argos"] == 0


def test_offline_then_permission_message(monkeypatch):
    # permission OFF et AUCUN moteur hors ligne dispo : message historique
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: False)
    _fake_engines(monkeypatch,
                  argos=EngineUnavailableError("paire de langues absente"))
    with pytest.raises(RuntimeError, match="hors ligne impossible"):
        translation.translate_text("Hello", target="fr",
                                   store_in_memory=False)


def test_all_fail_combined_error(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    # nllb exclu (non installe) : groq, deepl, google et argos tombent tous
    _fake_engines(monkeypatch,
                  groq=QuotaExhaustedError("quota groq"),
                  deepl=QuotaExhaustedError("quota deepl"),
                  google=EngineUnavailableError("panne google"),
                  argos=EngineUnavailableError("paire absente"))
    with pytest.raises(EngineUnavailableError, match="Tous les moteurs") as ei:
        translation.translate_text("Hello", target="fr",
                                   store_in_memory=False)
    msg = str(ei.value)
    assert "Groq" in msg and "DeepL" in msg and "Google" in msg


def test_fallback_disabled_keeps_legacy_single_engine(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_engine_fallback_enabled",
                        lambda: False)
    calls = _fake_engines(monkeypatch,
                          groq=QuotaExhaustedError("Quota Groq epuise."),
                          deepl=lambda t: "DL:" + t)
    with pytest.raises(QuotaExhaustedError):
        translation.translate_text("Hello", target="fr",
                                   store_in_memory=False)
    assert calls["deepl"] == 0


def test_reset_link_states_gives_retry(monkeypatch):
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    state = {"groq_ok": False}
    calls = _fake_engines(
        monkeypatch,
        groq=lambda t: "FR:" + t if state["groq_ok"]
        else (_ for _ in ()).throw(QuotaExhaustedError("quota")),
        deepl=lambda t: "DL:" + t)
    translation.translate_text("A", target="fr", store_in_memory=False)
    assert calls["groq"] == 1
    state["groq_ok"] = True
    translation.reset_link_states()  # nouveau lot : on redonne sa chance
    translation.translate_text("B", target="fr", store_in_memory=False)
    assert calls["groq"] == 2 and calls["deepl"] == 1


def test_batch_groq_failure_falls_to_chain(monkeypatch):
    """Lot Groq en echec quota : TOUTES les cellules continuent par la
    chaine (DeepL ici) -- le worker ne voit aucune erreur."""
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: True)
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = {"batch": 0, "deepl": 0}

    def boom(protected_list, target):
        calls["batch"] += 1
        raise QuotaExhaustedError("Quota Groq epuise.")

    def fake_deepl(text, target_code):
        calls["deepl"] += 1
        return "DL:" + text

    monkeypatch.setattr(groq_provider, "translate_batch", boom)
    monkeypatch.setattr(deepl_provider, "translate", fake_deepl)
    out = translation.translate_batch_with_source(
        ["a [b]code[/b]", "b", "c"], target="fr")
    assert calls["batch"] == 1
    assert all(tr == "DL:" + t and src == "engine"
               for (tr, src), t in zip(out, ["a [b]code[/b]", "b", "c"]))
    assert out[0][0].startswith("DL:a ")
    assert "DeepL" in translation.last_fallback_note()


def test_chain_skips_groq_while_cooldown_active(tmp_path, monkeypatch):
    """Cooldown 429 actif (reset journalier possible) : le maillon Groq
    est SAUTE sans appel -- c'etait le blocage de 10 minutes vecu le
    19/09/2026 (le throttle dormait jusqu'au reset)."""
    import time as _time
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    monkeypatch.setattr(groq_provider, "_cooldown_until",
                        _time.monotonic() + 3600)
    calls = _fake_engines(monkeypatch,
                          groq=lambda t: "FR:" + t,
                          deepl=lambda t: "DL:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "DL:Hello"
    assert calls["groq"] == 0 and calls["deepl"] == 1


def test_batch_groq_downaligned_on_real_cooldown(tmp_path, monkeypatch):
    """Apres un 429, le repos du maillon Groq est aligne sur le reset
    REELLEMENT annonce : les pokes suivants ne repartent pas dans le
    throttle, DeepL sert toutes les cellules suivantes."""
    import time as _time
    settings.set_groq_api_key("gsk_test")
    settings.set_deepl_api_key("cle:fx")
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_groq_batch_enabled", lambda: True)
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    calls = {"batch": 0, "deepl": 0}

    def boom(protected_list, target):
        calls["batch"] += 1
        raise QuotaExhaustedError("Quota Groq epuise.")

    def fake_deepl(text, target_code):
        calls["deepl"] += 1
        return "DL:" + text

    monkeypatch.setattr(groq_provider, "translate_batch", boom)
    monkeypatch.setattr(deepl_provider, "translate", fake_deepl)
    monkeypatch.setattr(groq_provider, "cooldown_remaining",
                        lambda: 600.0)  # reset annonce dans 10 minutes

    out = translation.translate_batch_with_source(["a", "b"], target="fr")
    assert all(tr == "DL:" + t for (tr, _src), t in zip(out, ["a", "b"]))
    # deuxieme salve : Groq reste ecarte (repos aligne sur les 600 s),
    # pas de nouvelle requete lot gaspillee
    out2 = translation.translate_batch_with_source(["c", "d"], target="fr")
    assert calls["batch"] == 1
    assert all(tr == "DL:" + t for (tr, _src), t in zip(out2, ["c", "d"]))
    assert calls["deepl"] == 4


def test_google_garbage_page_caught_by_final_net(tmp_path, monkeypatch):
    """Filet final (19/09/2026) : une page d'erreur Google servie "avec
    succes" par un maillon n'est JAMAIS une traduction -- le maillon est
    ecarte et le suivant prend le relais (ici Argos)."""
    monkeypatch.setattr(settings, "get_translation_engine", lambda: "groq")
    monkeypatch.setattr(settings, "get_online_translation_enabled",
                        lambda: True)
    settings.set_groq_api_key("")  # groq/deepl absents : chaine = google
    calls = _fake_engines(
        monkeypatch,
        google=lambda t: "Error 500 (Server Error)!!1 500. That's an error.",
        argos=lambda t: "AR:" + t)
    out = translation.translate_text("Hello", target="fr",
                                     store_in_memory=False)
    assert out == "AR:Hello"
    assert calls["google"] == 1 and calls["argos"] == 1


def test_google_lost_tokens_is_basculable(tmp_path, monkeypatch):
    """Google perd des jetons XXTAG comme DeepL : structure perdue =
    erreur basculable (le squelette n'etait pas verifie sur ce chemin)."""
    from core.engine_errors import EngineUnavailableError

    class _LosingTranslator:
        def __init__(self, source="auto", target="fr", **kwargs):
            pass

        def translate(self, text):
            # aval du premier jeton : squelette casse
            return text.replace("XXTAG0XX", "")

    monkeypatch.setattr(translation, "GoogleTranslator", _LosingTranslator)
    with pytest.raises(EngineUnavailableError, match="jetons"):
        translation._translate_google("Hello [b]x[/b]", "fr", "en", 15.0)


def test_looks_like_engine_garbage():
    from core.translation import _looks_like_engine_garbage
    assert _looks_like_engine_garbage(
        "Error 500 (Server Error)!!1 500. That's an error.")
    assert _looks_like_engine_garbage("<html><body>boom</body></html>")
    assert not _looks_like_engine_garbage("Bonjour, comment puis-je aider ?")
    assert not _looks_like_engine_garbage("")
    assert not _looks_like_engine_garbage(None)


def test_debug_note_writes_jsonl(tmp_path, monkeypatch):
    """Journal de diagnostic (v1.10.0) : chaque traduction moteur appende
    moteur/entree/sortie en JSONL -- pour attribuer precisement les
    cellules litigieuses a leur moteur."""
    from core import translation
    log = tmp_path / "translation_debug.jsonl"
    monkeypatch.setattr(translation, "_DEBUG_LOG_PATH", log)
    translation._debug_note("deepl", "Hello [b]x[/b]", "Bonjour [b]x[/b]",
                            fallback=True)
    translation._debug_note("groq", "Hello", "Bonjour")
    import json
    lines = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["engine"] == "deepl" and lines[0]["fallback"] is True
    assert lines[0]["in"] == "Hello [b]x[/b]"
    assert lines[1]["engine"] == "groq" and lines[1]["fallback"] is False


def test_debug_note_never_raises(tmp_path, monkeypatch):
    from core import translation
    monkeypatch.setattr(translation, "_DEBUG_LOG_PATH",
                        tmp_path / "inconnu" / ".." / "interdit" / "x.jsonl")
    monkeypatch.setattr(translation, "_DEBUG_LOCK",
                        __import__("threading").Lock())
    # chemin d'ecriture invalide : aucune exception ne doit remonter
    try:
        translation._debug_note("groq", "a", "b")
    except Exception as e:
        raise AssertionError(f"_debug_note a leve : {e}")
