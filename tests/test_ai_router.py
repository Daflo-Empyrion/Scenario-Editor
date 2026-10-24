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

"""Routeur IA (core/ai/router.py) : ordre des maillons, boucle free,
cooldowns, payant opt-in et plafond, permission en ligne, lots."""
import pytest

from core import settings
from core.ai import budget, client, router
from core.engine_errors import (AuthError, EngineUnavailableError,
                                QuotaExhaustedError)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    budget.reset()
    router.reset_link_states()
    yield
    budget.reset()
    router.reset_link_states()


def _provider(pid, kind="free", base=None):
    return {"id": pid, "label": pid.upper(), "key": "k",
            "base_url": base or f"https://{pid}.test/v1", "kind": kind}


def _link(pid, model, tier="free", price_in=0.0, price_out=0.0):
    return {"provider": pid, "model": model, "tier": tier,
            "price_in": price_in, "price_out": price_out, "enabled": True}


def _setup(providers, links, paid=False, cap=0.0):
    settings.set_ai_providers(providers)
    settings.set_ai_links(links)
    settings.set_ai_paid_enabled(paid)
    settings.set_ai_monthly_cap_usd(cap)


def _answer(content="ok", usage=None):
    return {"content": content, "usage": usage or {}, "tool_calls": []}


def test_free_links_tried_in_order_with_loop(monkeypatch):
    _setup([_provider("p1"), _provider("p2")],
           [_link("p1", "m1"), _link("p2", "m2")])
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        if model == "m1":
            raise QuotaExhaustedError("quota", retry_after=1)
        return _answer("Bonjour")

    monkeypatch.setattr(client, "chat", fake_chat)
    assert router.complete([{"role": "user", "content": "Hello"}]) == "Bonjour"
    assert calls == ["m1", "m2"]
    assert "P2" in router.last_link_label()


def test_paid_disabled_by_default(monkeypatch):
    _setup([_provider("p1", "paid")],
           [_link("p1", "m1", "paid", 1.0, 2.0)])
    monkeypatch.setattr(client, "chat",
                        lambda *a, **k: _answer("ne doit pas partir"))
    with pytest.raises(EngineUnavailableError, match="Aucun fournisseur"):
        router.complete([{"role": "user", "content": "x"}])


def test_free_quota_falls_to_paid_when_enabled(monkeypatch):
    """Limite free OpenRouter (globale au compte FREE, pas aux credits) :
    le tier payant reste essayable -- c'est le repli free -> payant."""
    _setup([_provider("p1", "mixed"), _provider("p2", "paid")],
           [_link("p1", "free:free", "free"),
            _link("p2", "paid", "paid", 1.0, 2.0)], paid=True, cap=10.0)
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        if model == "free:free":
            raise QuotaExhaustedError("rate limit", retry_after=1)
        return _answer("Payant", {"cost": 0.1})

    monkeypatch.setattr(client, "chat", fake_chat)
    assert router.complete([{"role": "user", "content": "x"}]) == "Payant"
    assert calls == ["free:free", "paid"]
    assert budget.spent("p2") == 0.1


def test_paid_runs_when_enabled_and_records_cost(monkeypatch):
    _setup([_provider("p1", "paid")],
           [_link("p1", "m1", "paid", 1.0, 2.0)], paid=True, cap=10.0)
    monkeypatch.setattr(client, "chat", lambda *a, **k: _answer(
        "Bonjour", {"prompt_tokens": 100, "completion_tokens": 50,
                    "cost": 0.5}))
    assert router.complete([{"role": "user", "content": "Hello"}]) == "Bonjour"
    assert budget.spent("p1") == 0.5
    assert budget.summary()["remaining"] == 9.5


def test_paid_blocked_when_cap_reached(monkeypatch):
    _setup([_provider("p1", "paid")],
           [_link("p1", "m1", "paid", 1.0, 2.0)], paid=True, cap=0.001)
    monkeypatch.setattr(client, "chat",
                        lambda *a, **k: _answer("ne doit pas partir"))
    with pytest.raises(EngineUnavailableError, match="plafond"):
        router.complete([{"role": "user", "content": "Hello"}])
    assert budget.spent("p1") == 0.0


def test_paid_without_price_is_skipped(monkeypatch):
    _setup([_provider("p1", "paid")],
           [_link("p1", "m1", "paid", 0.0, 0.0)], paid=True, cap=10.0)
    monkeypatch.setattr(client, "chat",
                        lambda *a, **k: _answer("ne doit pas partir"))
    with pytest.raises(EngineUnavailableError, match="tarif"):
        router.complete([{"role": "user", "content": "Hello"}])


def test_empty_response_falls_to_next_link(monkeypatch):
    """Modele a raisonnement qui epuise max_tokens et renvoie content="":
    maillon ecarte, pas une traduction vide."""
    _setup([_provider("p1"), _provider("p2")],
           [_link("p1", "m1"), _link("p2", "m2")])
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        return _answer("" if model == "m1" else "Bonjour")

    monkeypatch.setattr(client, "chat", fake_chat)
    assert router.complete([{"role": "user", "content": "x"}]) == "Bonjour"
    assert calls == ["m1", "m2"]


def test_unavailable_model_falls_to_next_link(monkeypatch):
    """403 'modele reserve a un autre acces' = maillon suivant, pas une
    erreur d'authentification qui coupe toute l'IA."""
    _setup([_provider("p1"), _provider("p2")],
           [_link("p1", "m1"), _link("p2", "m2")])
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        if model == "m1":
            raise client.ModelUnavailableError("Modele indisponible (403)")
        return _answer("Bonjour")

    monkeypatch.setattr(client, "chat", fake_chat)
    assert router.complete([{"role": "user", "content": "x"}]) == "Bonjour"
    assert calls == ["m1", "m2"]


def test_auth_error_never_falls_back(monkeypatch):
    _setup([_provider("p1"), _provider("p2")],
           [_link("p1", "m1"), _link("p2", "m2")])
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        raise AuthError("Cle refusee (401).")

    monkeypatch.setattr(client, "chat", fake_chat)
    with pytest.raises(AuthError, match="refusee"):
        router.complete([{"role": "user", "content": "x"}])
    assert calls == ["m1"]


def test_offline_permission_keeps_local_links(monkeypatch):
    settings.set_online_translation_enabled(False)
    _setup([_provider("remote"), _provider("local", base="http://127.0.0.1:1/v1")],
           [_link("remote", "m1"), _link("local", "m2")])
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        return _answer("Local")

    monkeypatch.setattr(client, "chat", fake_chat)
    assert router.configured() is True
    assert router.has_local_links() is True
    assert router.complete([{"role": "user", "content": "x"}]) == "Local"
    assert calls == ["m2"]


def test_link_cooldown_skips_dead_model(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])
    calls = []

    def fake_chat(base, key, model, messages, **kwargs):
        calls.append(model)
        raise EngineUnavailableError("panne")

    monkeypatch.setattr(client, "chat", fake_chat)
    with pytest.raises(EngineUnavailableError):
        router.complete([{"role": "user", "content": "x"}])
    with pytest.raises(EngineUnavailableError):
        router.complete([{"role": "user", "content": "y"}])
    assert calls == ["m1"]  # en repos : pas de second appel


def test_translation_prompts_and_target_language(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])
    seen = {}

    def fake_chat(base, key, model, messages, **kwargs):
        seen["messages"] = messages
        return _answer("[FR]Bonjour[/FR]")

    monkeypatch.setattr(client, "chat", fake_chat)
    out = router.translate_whole("XXTAG0XX Hello", "fr")
    assert out == "[FR]Bonjour[/FR]"
    assert "French" in seen["messages"][0]["content"]
    assert "XXTAG" in seen["messages"][0]["content"]
    assert seen["messages"][1]["content"] == "XXTAG0XX Hello"


def test_translate_batch_parses_cells(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])
    monkeypatch.setattr(client, "chat", lambda *a, **k: _answer(
        "<CELL0>Bonjour</CELL0>\n<CELL1>Salut</CELL1>"))
    assert router.translate_batch(["Hello", "Hi"], "fr") == [
        "Bonjour", "Salut"]


def test_translate_batch_returns_none_on_missing_cell(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])
    monkeypatch.setattr(client, "chat",
                        lambda *a, **k: _answer("<CELL0>Bonjour</CELL0>"))
    assert router.translate_batch(["Hello", "Hi"], "fr") == ["Bonjour", None]


# --- Capacites d'assistant (Q35/D3) ---------------------------------------

def _capped_link(pid, model, caps, tier="free"):
    link = _link(pid, model, tier)
    link["caps"] = caps
    return link


def test_min_class_filters_links_that_declare_less(monkeypatch):
    _setup([_provider("p1")], [_capped_link("p1", "m1", {"class": "normal"})])
    with pytest.raises(EngineUnavailableError, match="capacite requise"):
        router.chat_with_link([{"role": "user", "content": "x"}],
                              min_class="strong")


def test_min_class_accepts_a_link_that_declares_it(monkeypatch):
    _setup([_provider("p1")], [_capped_link("p1", "m1", {"class": "strong"})])
    monkeypatch.setattr(client, "chat", lambda *a, **k: _answer("ok"))
    result, candidate = router.chat_with_link(
        [{"role": "user", "content": "x"}], min_class="strong")
    assert result["content"] == "ok"
    assert candidate.model == "m1"


def test_undeclared_capability_is_treated_as_normal(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])
    monkeypatch.setattr(client, "chat", lambda *a, **k: _answer("ok"))
    router.chat_with_link([{"role": "user", "content": "x"}],
                          min_class="light")
    with pytest.raises(EngineUnavailableError):
        router.chat_with_link([{"role": "user", "content": "x"}],
                              min_class="strong")


def test_require_tools_skips_a_link_declaring_it_cannot(monkeypatch):
    _setup([_provider("p1")], [_capped_link("p1", "m1", {"tools": False})])
    with pytest.raises(EngineUnavailableError, match="outils"):
        router.chat_with_link([{"role": "user", "content": "x"}], tools=[],
                              require_tools=True)


def test_require_tools_tries_a_link_with_unknown_capability(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])
    monkeypatch.setattr(client, "chat", lambda *a, **k: _answer("ok"))
    result, _ = router.chat_with_link([{"role": "user", "content": "x"}],
                                      tools=[], require_tools=True)
    assert result["content"] == "ok"
