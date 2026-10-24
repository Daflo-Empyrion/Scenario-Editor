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

"""Presets et catalogue des fournisseurs IA (core/ai/providers.py)."""
import pytest

from core import settings
from core.ai import client, providers


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")


def test_openrouter_provider_seeds_free_loop():
    provider = providers.new_provider("openrouter", key="sk-or")
    assert provider["base_url"] == "https://openrouter.ai/api/v1"
    assert provider["kind"] == "mixed"
    assert provider["models"] == providers.OPENROUTER_FREE_MODELS
    assert all(":free" in m for m in provider["models"])


def test_deepseek_direct_base_url_and_paid():
    provider = providers.new_provider("deepseek")
    assert provider["base_url"] == "https://api.deepseek.com"
    assert provider["kind"] == "paid"
    assert "deepseek-chat" in provider["models_order"]


def test_kind_tier():
    mixed = {"kind": "mixed"}
    assert providers.kind_tier(mixed, "x:free") == "free"
    assert providers.kind_tier(mixed, "x") == "paid"
    assert providers.kind_tier({"kind": "free"}, "x") == "free"
    assert providers.kind_tier({"kind": "paid"}, "x") == "paid"
    # un preset facture reste payant meme si l'UI dit 'free'
    assert providers.kind_tier({"preset": "deepseek", "kind": "free"},
                               "deepseek-chat") == "paid"
    assert providers.kind_tier({"preset": "openrouter", "kind": "free"},
                               "x") == "paid"
    assert providers.kind_tier({"preset": "openrouter"}, "x:free") == "free"


def test_local_detection():
    assert providers.is_local("http://127.0.0.1:8888/v1")
    assert providers.is_local("http://localhost:11434/v1")
    assert not providers.is_local("https://api.deepseek.com")


def test_model_prices_from_preset_and_catalog():
    deepseek = {"preset": "deepseek", "kind": "paid"}
    assert providers.model_prices(deepseek, "deepseek-chat") == (0.30, 1.20)
    assert providers.model_prices(deepseek, "inconnu") == (0.0, 0.0)
    catalog = {"preset": "openrouter", "kind": "mixed",
               "_catalog": {"m:free": {"price_in": 0.0, "price_out": 0.0}}}
    assert providers.model_prices(catalog, "m:free") == (0.0, 0.0)
    free = {"preset": "openrouter", "kind": "mixed"}
    assert providers.model_prices(free, providers.OPENROUTER_PAID_MODEL) == \
        providers.OPENROUTER_PAID_PRICE


def test_list_models_normalizes_pricing(monkeypatch):
    monkeypatch.setattr(client, "list_models", lambda base, key: [
        {"id": "free:free", "name": "Free", "context_length": 1000,
         "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "paid", "name": "Paid", "context_length": 2000,
         "pricing": {"prompt": "0.00000025", "completion": "0.000001"}},
    ])
    models = providers.list_models({"base_url": "https://x.test", "key": "k"})
    paid = next(m for m in models if m["id"] == "paid")
    assert paid["price_in"] == pytest.approx(0.25)
    assert paid["price_out"] == pytest.approx(1.0)


def test_account_info_openrouter(monkeypatch):
    monkeypatch.setattr(client, "key_info", lambda base, key: {
        "usage": 1.25, "limit_remaining": 8.75,
        "free_model_daily_requests": {"remaining": 40, "limit": 50}})
    text = providers.account_info({"preset": "openrouter",
                                   "base_url": "https://openrouter.ai/api/v1",
                                   "key": "k"})
    assert "1.25" in text and "8.75" in text and "40/50" in text
