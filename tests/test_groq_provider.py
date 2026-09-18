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

"""Moteur GROQ (LLM en ligne compatible OpenAI, demande 18/09/2026) :
provider core/groq_provider.py (cle dans settings locaux, User-Agent
obligatoire -- Cloudflare bloque sinon, vecu reel sur Felo), radio dans le
sous-menu Moteur, assistant avec liens cliquables. Tout le reseau est
MOCKE ici : aucun appel reel."""

import json
import urllib.error

import pytest

from core import groq_provider, settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Settings isoles (la cle et le modele n'atteignent jamais le vrai
    settings.json) + throttle desactive (sinon chaque appel attendrait
    MIN_INTERVAL_S) + etat de limites remis a zero."""
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(groq_provider, "MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(groq_provider, "_cooldown_until", 0.0)
    monkeypatch.setattr(groq_provider, "_last_call", 0.0)
    monkeypatch.setattr(groq_provider, "_last_limits", None)
    settings.set_groq_api_key("gsk_test_key")
    settings.set_groq_model("qwen/qwen3.8-27b")


def _fake_response(payload):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode()

    return R()


def test_is_configured(monkeypatch):
    assert groq_provider.is_configured() is True
    settings.set_groq_api_key("")
    assert groq_provider.is_configured() is False


def test_translate_payload_and_extraction(monkeypatch):
    captured = {}

    def fake_post(payload, timeout=60.0):
        captured.update(payload)
        return {"choices": [{"message": {"content": "Les générateurs sont "
                                         "surchargés."}}]}

    monkeypatch.setattr(groq_provider, "_post", fake_post)
    out = groq_provider.translate("The generators are overloaded.",
                                  "en", "fr")
    assert out == "Les générateurs sont surchargés."
    assert captured["model"] == "qwen/qwen3.8-27b"
    assert captured["messages"][0]["role"] == "system"
    assert "French" in captured["messages"][0]["content"]
    assert captured["messages"][1]["content"] == "The generators are overloaded."


def test_translate_errors_are_clear(monkeypatch):
    def http_error(code, body):
        return urllib.error.HTTPError(
            "url", code, "err", {},
            _fake_response({"error": {"message": body}}))

    with pytest.raises(RuntimeError, match="refus"):
        monkeypatch.setattr(groq_provider, "_post",
                            lambda p, timeout=60: (_ for _ in ()).throw(
                                http_error(401, "bad key")))
        groq_provider.translate("x", "en", "fr")

    with pytest.raises(RuntimeError, match="[Ll]imite de debit"):
        monkeypatch.setattr(groq_provider, "_post",
                            lambda p, timeout=60: (_ for _ in ()).throw(
                                http_error(429, "rate limited")))
        groq_provider.translate("x", "en", "fr")

    with pytest.raises(RuntimeError, match="[Rr]eseau"):
        monkeypatch.setattr(groq_provider, "_post",
                            lambda p, timeout=60: (_ for _ in ()).throw(
                                urllib.error.URLError("offline")))
        groq_provider.translate("x", "en", "fr")

    with pytest.raises(RuntimeError, match="[Rr]eponse Groq inattendue"):
        monkeypatch.setattr(groq_provider, "_post",
                            lambda p, timeout=60: {"nope": True})
        groq_provider.translate("x", "en", "fr")


def test_parse_duration():
    assert groq_provider._parse_duration("2m59.56s") == pytest.approx(179.56)
    assert groq_provider._parse_duration("7.66s") == pytest.approx(7.66)
    assert groq_provider._parse_duration("6m0s") == 360.0
    assert groq_provider._parse_duration("") == 0.0
    assert groq_provider._parse_duration(None) == 0.0


def test_throttle_spaces_consecutive_calls(monkeypatch):
    monkeypatch.setattr(groq_provider, "MIN_INTERVAL_S", 0.15)
    monkeypatch.setattr(groq_provider, "_cooldown_until", 0.0)
    import time as _time
    t0 = _time.monotonic()
    groq_provider._throttle()
    groq_provider._throttle()
    assert _time.monotonic() - t0 >= 0.15


def _http_429_with_headers():
    return urllib.error.HTTPError(
        "url", 429, "Too Many Requests",
        {"retry-after": "30",
         "x-ratelimit-reset-tokens": "7.66s"},
        _fake_response({"error": {"message": "Rate limit reached"}}))


def test_429_sets_cooldown_and_announces_delay(monkeypatch):
    import time as _time
    monkeypatch.setattr(groq_provider, "_post",
                        lambda p, timeout=60: (_ for _ in ()).throw(
                            _http_429_with_headers()))
    with pytest.raises(RuntimeError, match="30s"):
        groq_provider.translate("x", "en", "fr")
    # cooldown pose : les appels suivants attendront automatiquement
    assert groq_provider._cooldown_until > _time.monotonic()


def test_capture_limits_and_progress_text():
    class FakeResp:
        headers = {"x-ratelimit-limit-requests": "14400",
                   "x-ratelimit-limit-tokens": "8000",
                   "x-ratelimit-remaining-requests": "970",
                   "x-ratelimit-remaining-tokens": "6123",
                   "x-ratelimit-reset-tokens": "7.66s"}

    assert groq_provider.limits_text() == ""  # rien avant un appel
    groq_provider._capture_limits(FakeResp())
    text = groq_provider.limits_text()
    assert "970" in text and "6123" in text and "7.66s" in text


def test_user_agent_always_sent(monkeypatch):
    """SANS User-Agent la passerelle bloque avant l'API (vecu reel sur
    Felo : Cloudflare 1010) -- l'en-tete doit etre present."""
    headers_seen = {}

    class R:
        def __init__(self, headers, payload):
            self.headers, self.payload = headers, payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}]}).encode()

    def fake_urlopen(req, timeout=60):
        headers_seen.update(dict(req.header_items()))
        return R(req.headers, None)

    monkeypatch.setattr(groq_provider.urllib.request, "urlopen", fake_urlopen)
    groq_provider.translate("x", "en", "fr")
    assert any(h.lower() == "user-agent" for h in headers_seen)


def test_list_models_filters_non_text(monkeypatch):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"data": [
                {"id": "qwen/qwen3.8-27b"},
                {"id": "whisper-large-v3"},
                {"id": "meta-llama/llama-prompt-guard-2-86m"},
                {"id": "groq/compound"},
            ]}).encode()

    monkeypatch.setattr(groq_provider.urllib.request, "urlopen",
                        lambda req, timeout=30: R())
    models = groq_provider.list_models()
    assert models == ["qwen/qwen3.8-27b"]


def test_list_models_fallback_on_error(monkeypatch):
    def boom(req, timeout=30):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(groq_provider.urllib.request, "urlopen", boom)
    assert groq_provider.list_models() == groq_provider.KNOWN_MODELS


@pytest.fixture()
def groq_pipeline(tmp_path, monkeypatch):
    """translate_text branche sur le moteur 'groq' : glossaire/memoires
    isoles (le texte 'Hello world' est piege par le glossaire REEL de la
    machine -- entrees auto-alimentees -> 'Bonjour le monde' AVANT le
    moteur)."""
    from core import glossary as g
    from core import settings as core_settings
    from core import vanilla_memory
    import core.translation_memory as tm
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)
    monkeypatch.setattr(core_settings, "get_translation_engine",
                        lambda: "groq")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: True)
    monkeypatch.setattr(tm, "get_cached", lambda *a: None)
    monkeypatch.setattr(vanilla_memory, "get_vanilla_cached",
                        lambda text, target: None)


def _llm_spy(monkeypatch):
    """Remplace le LLM par un 'traducteur' factice qui conserve les jetons
    XXTAG a l'identique et entoure les fragments textes ; capture les appels
    whole-cell et fragments."""
    import re as _re
    from core import groq_provider as gp
    calls = {"whole": [], "frag": []}

    def fake_whole(protected, target_code):
        calls["whole"].append(protected)
        parts = _re.split(r"(XXTAG\d+XX)", protected, flags=_re.IGNORECASE)
        return "".join(p if _re.fullmatch(r"XXTAG\d+XX", p, _re.I)
                       else (f"[FR]{p}[/FR]" if p else "") for p in parts)

    def fake_frag(text, src, tgt):
        calls["frag"].append(text)
        return f"[F]{text}[/F]"

    monkeypatch.setattr(gp, "translate_whole", fake_whole)
    monkeypatch.setattr(gp, "translate", fake_frag)
    return calls


def test_whole_cell_single_call_preserves_skeleton(groq_pipeline, monkeypatch):
    """Mode cellule entiere : UNE requete Groq pour toute la cellule
    (demande 18/09/2026), jetons XXTAG conserves, balises restorees aux
    memes places, aucun passage par les fragments."""
    from core import translation
    calls = _llm_spy(monkeypatch)
    out = translation.translate_text(
        "[b]Hello world[/b] and [c]goodbye[/c]", target="fr",
        store_in_memory=False)
    # le fake 'traduit' trivialement chaque fragment (wrapping) : le
    # VRAI LLM produirait ' et ' naturellement -- l'important est la
    # STRUCTURE : 4 balises restorees a leur place exacte
    assert out == ("[b][FR]Hello world[/FR][/b][FR] and [/FR]"
                   "[c][FR]goodbye[/FR][/c]")
    assert len(calls["whole"]) == 1
    assert calls["frag"] == []  # le mode fragments n'est jamais utilise
    assert "XXTAG0XX" in calls["whole"][0]


def test_whole_cell_plain_text_also_single_call(groq_pipeline, monkeypatch):
    """Meme sans aucune balise : la phrase complete part d'un bloc (c'est
    tout l'interet -- contexte linguistique complet)."""
    from core import translation
    calls = _llm_spy(monkeypatch)
    out = translation.translate_text("The reactor overheated twice.",
                                     target="fr", store_in_memory=False)
    assert out == "[FR]The reactor overheated twice.[/FR]"
    assert len(calls["whole"]) == 1 and calls["frag"] == []


def test_whole_cell_falls_back_to_fragments_on_divergence(groq_pipeline,
                                                          monkeypatch):
    """Si le LLM 'bave' (jeton perdu/reecrit), la cellule repasse par le
    pipeline fragments : structure garantie, jamais de fichier corrompu."""
    from core import translation
    from core import groq_provider as gp
    calls = _llm_spy(monkeypatch)

    def baving_whole(protected, target_code):
        calls["whole"].append(protected)
        return "[FR]Hello world, mais sans les jetons[/FR]"  # squelette perdu

    monkeypatch.setattr(gp, "translate_whole", baving_whole)
    out = translation.translate_text("[b]Hello world[/b]", target="fr",
                                     store_in_memory=False)
    assert out == "[b][F]Hello world[/F][/b]"  # fragments au secours
    assert len(calls["whole"]) == 1 and calls["frag"] == ["Hello world"]


def test_translate_text_engine_groq(groq_pipeline, monkeypatch):
    from core import translation
    from core import groq_provider as gp
    monkeypatch.setattr(gp, "translate_whole",
                        lambda protected, target: "[FR]" + protected + "[/FR]")
    out = translation.translate_text("[b]Hello world[/b]", target="fr",
                                     store_in_memory=False)
    # le jeton de la reponse est restaure en balise originale
    assert out == "[FR][b]Hello world[/b][/FR]"


def test_translate_text_groq_blocked_without_online_permission(monkeypatch):
    """Groq est EN LIGNE : la permission 'Traduction en ligne' le bloque
    aussi (confidentialite, comme Google)."""
    from core import settings as core_settings
    from core import translation, vanilla_memory
    import core.translation_memory as tm
    monkeypatch.setattr(core_settings, "get_translation_engine",
                        lambda: "groq")
    monkeypatch.setattr(core_settings, "get_online_translation_enabled",
                        lambda: False)
    monkeypatch.setattr(tm, "get_cached", lambda *a: None)
    monkeypatch.setattr(vanilla_memory, "get_vanilla_cached",
                        lambda text, target: None)
    with pytest.raises(RuntimeError, match="[Tt]raduction en ligne"):
        translation.translate_text("Hello", target="fr", store_in_memory=False)


def test_dialog_model_combo_roundtrip(qapp, tmp_path, monkeypatch):
    """L'assistant affiche le modele courant, sauvegarde la cle et persiste
    le modele choisi."""
    from gui.theme import apply_theme
    from gui.groq_setup_dialog import GroqSetupDialog
    apply_theme(qapp)
    d = GroqSetupDialog()
    try:
        assert d.key_edit.text() == "gsk_test_key"
        assert d.model_combo.currentText() == "qwen/qwen3.8-27b"
        d.model_combo.setCurrentText("openai/gpt-oss-20b")
        assert settings.get_groq_model() == "openai/gpt-oss-20b"
        d.key_edit.setText("  gsk_new  ")
        d._verify()
        assert settings.get_groq_api_key() == "gsk_new"
    finally:
        d.close()
