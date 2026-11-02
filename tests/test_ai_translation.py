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

"""Branchement du moteur IA UNIQUE (31/10, les moteurs Google/DeepL/Argos/
NLLB et Groq direct sont supprimes) : structure XXTAG preservee, erreurs
remontees (le routeur IA gere ses maillons lui-meme), mode lots."""
import pytest

from core import settings, translation
from core.ai import budget, router
from core.engine_errors import QuotaExhaustedError


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    import core.glossary as g
    import core.translation_memory as tm
    import core.vanilla_memory as vm
    monkeypatch.setattr(g, "GLOSSARY_FILE", tmp_path / "glossary.json")
    monkeypatch.setattr(g, "_cache", None)
    monkeypatch.setattr(tm, "get_cached", lambda *a, **k: None)
    monkeypatch.setattr(vm, "get_vanilla_cached", lambda *a, **k: None)
    monkeypatch.setattr(translation, "_DEBUG_LOG_PATH",
                        tmp_path / "translation_debug.jsonl")
    settings.set_ai_providers([{
        "id": "p1", "label": "P1", "key": "k", "kind": "free",
        "base_url": "https://p1.test/v1"}])
    settings.set_ai_links([{
        "provider": "p1", "model": "m1", "tier": "free",
        "price_in": 0.0, "price_out": 0.0, "enabled": True}])
    settings.set_online_translation_enabled(True)
    budget.reset()
    router.reset_link_states()
    yield
    budget.reset()
    router.reset_link_states()


def test_ai_engine_preserves_structure(monkeypatch):
    import re

    def fake_whole(protected, target):
        parts = re.split(r"(XXTAG\d+XX)", protected, flags=re.IGNORECASE)
        return "".join(p if re.fullmatch(r"XXTAG\d+XX", p, re.I)
                       else (f"[FR]{p}[/FR]" if p else "") for p in parts)

    monkeypatch.setattr(router, "translate_whole", fake_whole)
    monkeypatch.setattr(router, "translate", lambda text, src, tgt: f"[F]{text}[/F]")
    out = translation.translate_text("[b]Hello world[/b]", target="fr",
                                     store_in_memory=False)
    assert out == "[b][FR]Hello world[/FR][/b]"


def test_ai_failure_propagates(monkeypatch):
    """Plus de chaine de secours (31/10) : une erreur IA (quota/panne) remonte
    -- c'est le ROUTEUR qui gere le secours entre fournisseurs ; la cellule
    suivante retente normalement."""
    def boom(*args, **kwargs):
        raise QuotaExhaustedError("quota IA", retry_after=1)

    monkeypatch.setattr(router, "translate_whole", boom)
    with pytest.raises(QuotaExhaustedError):
        translation.translate_text("Hello", target="fr", store_in_memory=False)

    def ok(protected, target):
        return protected

    monkeypatch.setattr(router, "translate_whole", ok)
    assert translation.translate_text("Hello", target="fr",
                                      store_in_memory=False) == "Hello"


def test_batch_failure_falls_to_whole_cell(monkeypatch):
    """Un lot IA en echec (429 transitoire) : les cellules continuent une a
    une (mode cellule entiere), jamais de fichier corrompu."""
    def boom_batch(texts, target):
        raise QuotaExhaustedError("429 free", retry_after=1)

    monkeypatch.setattr(router, "translate_batch", boom_batch)
    monkeypatch.setattr(router, "translate_whole",
                        lambda protected, target: "[FR]" + protected + "[/FR]")
    out = translation.translate_batch_with_source(["a", "b"], target="fr")
    assert [tr for tr, _src in out] == ["[FR]a[/FR]", "[FR]b[/FR]"]


def test_worker_batch_matches_ai_setting(monkeypatch):
    from gui import translation_worker
    monkeypatch.setattr(settings, "get_ai_batch_enabled", lambda: True)
    assert translation_worker.batch_engine_enabled() is True
    monkeypatch.setattr(settings, "get_ai_batch_enabled", lambda: False)
    assert translation_worker.batch_engine_enabled() is False


def test_ai_batch_uses_router(monkeypatch):
    calls = {}

    def fake_batch(texts, target):
        calls["texts"] = list(texts)
        return ["FR:" + text for text in texts]

    monkeypatch.setattr(router, "translate_batch", fake_batch)
    out = translation.translate_batch_with_source(["a", "b"], target="fr")
    assert calls["texts"] == ["a", "b"]
    assert [tr for tr, _src in out] == ["FR:a", "FR:b"]


def test_online_permission_gates_remote_only(monkeypatch):
    """La permission 'Traduction en ligne' bloque le chemin IA sauf si un
    maillon LOCAL est configure (aucune donnee ne sort)."""
    settings.set_online_translation_enabled(False)
    from core.engine_errors import EngineUnavailableError
    with pytest.raises((EngineUnavailableError, RuntimeError)):
        translation.translate_text("Hello", target="fr", store_in_memory=False)
    settings.set_online_translation_enabled(True)
