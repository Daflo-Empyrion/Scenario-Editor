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

"""Budget IA : cumul mensuel, plafonds, ecriture differee, reset."""
import pytest

from core import settings
from core.ai import budget


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    budget.reset()
    yield
    budget.reset()


def test_cap_required_and_accumulation():
    settings.set_ai_monthly_cap_usd(0)
    assert budget.can_spend("p1", 0.0) is False
    settings.set_ai_monthly_cap_usd(10.0)
    assert budget.can_spend("p1", 1.0) is True
    budget.record("p1", 3.5)
    assert budget.spent("p1") == 3.5
    assert budget.can_spend("p1", 7.0) is False
    assert budget.can_spend("p1", 6.0) is True
    budget.flush()
    assert settings.get_ai_spend()["total"] == 3.5


def test_provider_cap_overrides_global():
    settings.set_ai_monthly_cap_usd(50.0)
    settings.set_ai_providers([{"id": "p1", "cap_usd": 2.0}])
    assert budget.cap("p1") == 2.0
    assert budget.cap("autre") == 50.0


def test_month_rollover_resets_counter():
    settings.set_ai_spend({"month": "2000-01", "total": 9.0,
                           "providers": {"p1": 9.0}})
    budget.reset()
    assert budget.spent() == 0.0


def test_reset_spend_persists_zero():
    settings.set_ai_monthly_cap_usd(5.0)
    budget.record("p1", 1.0)
    budget.reset_spend()
    assert budget.spent() == 0.0
    assert settings.get_ai_spend()["total"] == 0.0
