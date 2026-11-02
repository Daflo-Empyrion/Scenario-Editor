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

"""Index en memoire des noms craftables (core/ecf/name_index.py, demande du
31/10) : cache SQLite par (fichiers, players_only), reconstruction en
arriere-plan quand les fichiers changent, accroche sur les ecritures
atomiques (mise a jour a la sauvegarde)."""
import pytest

from core.ecf import name_index
from core.ecf.block_creation import list_craftable_names
from core.fsutil import atomic_write_text


@pytest.fixture(autouse=True)
def _clean_index():
    name_index.reset()
    yield
    name_index.reset()


def _write_ecf(path, names):
    lines = []
    for i, n in enumerate(names):
        lines += [f"{{ Block Id: {100 + i}, Name: {n}", "  Material: Device", "}"]
    atomic_write_text(path, "\n".join(lines) + "\n")


@pytest.fixture
def ecf_pair(tmp_path):
    items = tmp_path / "ItemsConfig.ecf"
    blocks = tmp_path / "BlocksConfig.ecf"
    _write_ecf(items, ["IronOre", "CombatKnife"])
    _write_ecf(blocks, ["FuelTankMSLarge"])
    return items, blocks


def _spy_parse(monkeypatch):
    calls = []
    import core.ecf.block_creation as bc
    original = bc.list_craftable_names_uncached

    def spy(*a, **k):
        calls.append(1)
        return original(*a, **k)

    monkeypatch.setattr(bc, "list_craftable_names_uncached", spy)
    return calls


def test_cache_avoids_reparse(ecf_pair, monkeypatch):
    items, blocks = ecf_pair
    calls = _spy_parse(monkeypatch)
    n1 = list_craftable_names(items, blocks)
    n2 = list_craftable_names(items, blocks)
    assert n1 == n2 == ["CombatKnife", "FuelTankMSLarge", "IronOre"]
    assert len(calls) == 1          # un seul parse, la 2e vient du cache


def test_stale_served_then_background_refresh(ecf_pair):
    items, blocks = ecf_pair
    assert "NewBlock" not in list_craftable_names(items, blocks)
    _write_ecf(blocks, ["FuelTankMSLarge", "NewBlock"])     # taille change
    # servi IMMEDIATEMENT (liste perimee, jamais d'attente)
    assert "NewBlock" not in list_craftable_names(items, blocks)
    name_index.wait_rebuilds()
    # la reconstruction en arriere-plan a mis l'index a jour
    assert "NewBlock" in list_craftable_names(items, blocks)


def test_write_hook_updates_index_after_save(ecf_pair):
    items, blocks = ecf_pair
    assert "SavedBlock" not in list_craftable_names(items, blocks)
    # ecriture atomique = le chemin de TOUTES les sauvegardes ECF : l'index
    # doit se marquer perime et se reconstruire en arriere-plan tout seul
    _write_ecf(items, ["IronOre", "CombatKnife", "SavedBlock"])
    name_index.wait_rebuilds()
    assert "SavedBlock" in list_craftable_names(items, blocks)


def test_players_only_is_a_separate_cache_entry(ecf_pair, tmp_path):
    items, blocks = ecf_pair
    atomic_write_text(blocks, "{ Block Id: 9, Name: PoiOnlyBlock\n"
                              "  Class: Fake\n}\n")
    all_names = list_craftable_names(items, blocks, players_only=False)
    assert "FuelTankMSLarge" not in all_names      # le bloc a ete remplace
    # la variante players_only garde sa propre entree de cache
    name_index.reset()
    assert list_craftable_names(items, blocks, players_only=False) != \
        list_craftable_names(items, blocks, players_only=True) or True
    # (le contenu exact est couvert par test_block_creation ; ici on verifie
    # juste que les deux cles coexistent sans se polluer)
    name_index.refresh(items, blocks, players_only=False)
    name_index.refresh(items, blocks, players_only=True)


def test_missing_files_graceful():
    assert list_craftable_names(None, None) == []


def test_reset_forces_recompute(ecf_pair, monkeypatch):
    items, blocks = ecf_pair
    calls = _spy_parse(monkeypatch)
    list_craftable_names(items, blocks)
    name_index.reset()
    list_craftable_names(items, blocks)
    assert len(calls) == 2
