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

"""Flux SSE du routeur : evenements start/delta, repli avant tout fragment,
interdiction du payant en flux (pas d'usage en SSE, donc pas de decompte)."""
import pytest

from core import settings
from core.ai import budget, client, router
from core.engine_errors import EngineUnavailableError, QuotaExhaustedError


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    budget.reset()
    router.reset_link_states()
    yield
    budget.reset()
    router.reset_link_states()


def _provider(pid, kind="free"):
    return {"id": pid, "label": pid.upper(), "key": "k",
            "base_url": f"https://{pid}.test/v1", "kind": kind}


def _link(pid, model, tier="free", caps=None):
    link = {"provider": pid, "model": model, "tier": tier,
            "price_in": 0.0, "price_out": 0.0, "enabled": True}
    if caps is not None:
        link["caps"] = caps
    return link


def _setup(providers, links, paid=False):
    settings.set_ai_providers(providers)
    settings.set_ai_links(links)
    settings.set_ai_paid_enabled(paid)


def _deltas(events):
    return [payload for kind, payload in events if kind == "delta"]


def test_stream_yields_start_then_deltas(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])

    def fake_stream(base, key, model, messages, **kwargs):
        yield "Bonjour"
        yield " !"

    monkeypatch.setattr(client, "stream_chat", fake_stream)
    events = list(router.stream_with_link([{"role": "user", "content": "x"}]))
    assert events[0][0] == "start"
    assert events[0][1].model == "m1"
    assert _deltas(events) == ["Bonjour", " !"]
    assert router.last_link_label() == "P1 / m1"


def test_stream_refuses_when_only_paid_links_exist(monkeypatch):
    _setup([_provider("p1", "paid")], [_link("p1", "m1", "paid")], paid=True)
    with pytest.raises(EngineUnavailableError, match="flux"):
        list(router.stream_with_link([{"role": "user", "content": "x"}]))


def test_stream_falls_over_before_the_first_delta(monkeypatch):
    _setup([_provider("p1"), _provider("p2")],
           [_link("p1", "m1"), _link("p2", "m2")])

    def fake_stream(base, key, model, messages, **kwargs):
        if model == "m1":
            raise QuotaExhaustedError("quota", retry_after=1)
        yield "ok"

    monkeypatch.setattr(client, "stream_chat", fake_stream)
    events = list(router.stream_with_link([{"role": "user", "content": "x"}]))
    assert events[0][1].model == "m2"
    assert _deltas(events) == ["ok"]


def test_stream_error_after_first_delta_is_raised(monkeypatch):
    _setup([_provider("p1")], [_link("p1", "m1")])

    def fake_stream(base, key, model, messages, **kwargs):
        yield "debut"
        raise EngineUnavailableError("coupure")

    monkeypatch.setattr(client, "stream_chat", fake_stream)
    with pytest.raises(EngineUnavailableError, match="coupure"):
        list(router.stream_with_link([{"role": "user", "content": "x"}]))


def test_stream_applies_the_capability_filter():
    _setup([_provider("p1")],
           [_link("p1", "m1", caps={"tools": False})])
    with pytest.raises(EngineUnavailableError, match="flux"):
        list(router.stream_with_link([{"role": "user", "content": "x"}],
                                     require_tools=True))


def test_stream_skips_a_link_that_answers_nothing(monkeypatch):
    _setup([_provider("p1"), _provider("p2")],
           [_link("p1", "m1"), _link("p2", "m2")])

    def fake_stream(base, key, model, messages, **kwargs):
        if model == "m1":
            return  # generateur vide -> StopIteration des le premier next()
        yield "ok"

    monkeypatch.setattr(client, "stream_chat", fake_stream)
    events = list(router.stream_with_link([{"role": "user", "content": "x"}]))
    assert events[0][1].model == "m2"
