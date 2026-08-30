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

import zipfile
from pathlib import Path

import core.localization_lookup as ll


_VANILLA_CSV = (
    "KEY,English,Deutsch,Français\n"
    "HitPoints,Hit points,Lebenspunkte,Points dommages\n"
    "FuelTankMSLarge,Fuel Tank (Medium),Treibstofftank,Réservoir de carburant v2\n"
    "OnlyEnglish,Only in English,,\n"
)


def _make_vanilla_pack(path: Path) -> Path:
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr(ll.LOCALIZATION_PACK_NOTICE_MEMBER, "notice")
        zf.writestr(ll.LOCALIZATION_PACK_CSV_MEMBER, _VANILLA_CSV)
    return path


def test_parse_csv_text_builds_key_indexed_dict():
    idx = ll._parse_csv_text(_VANILLA_CSV)
    assert idx["HitPoints"]["Français"] == "Points dommages"
    assert idx["HitPoints"]["English"] == "Hit points"


def test_parse_csv_text_ignores_blank_rows():
    text = _VANILLA_CSV + "\n,,,\n"
    idx = ll._parse_csv_text(text)
    assert "" not in idx


def test_build_index_uses_vanilla_pack(tmp_path, monkeypatch):
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    idx = ll.build_localization_index(None)
    assert idx.get("HitPoints", "fr") == "Points dommages"
    assert idx.get("FuelTankMSLarge", "fr") == "Réservoir de carburant v2"


def test_get_falls_back_to_english_when_target_language_empty(tmp_path, monkeypatch):
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    idx = ll.build_localization_index(None)
    assert idx.get("OnlyEnglish", "fr") == "Only in English"


def test_get_returns_none_for_missing_key(tmp_path, monkeypatch):
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    idx = ll.build_localization_index(None)
    assert idx.get("DoesNotExist", "fr") is None


def test_get_returns_none_for_none_key(tmp_path, monkeypatch):
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    idx = ll.build_localization_index(None)
    assert idx.get(None, "fr") is None


def test_scenario_csv_overrides_vanilla(tmp_path, monkeypatch):
    """Le Localization.csv du scenario doit l'emporter sur le pack vanilla en
    cas de meme cle (voir docstring du module)."""
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    scenario_root = tmp_path / "scenario"
    extras_dir = scenario_root / "Extras"
    extras_dir.mkdir(parents=True)
    (extras_dir / "Localization.csv").write_text(
        "KEY,English,Français\nHitPoints,Custom hit points,Points de vie modifies\n", encoding='utf-8')

    idx = ll.build_localization_index(scenario_root)
    assert idx.get("HitPoints", "fr") == "Points de vie modifies"
    # Une cle absente du scenario doit toujours retomber sur le vanilla.
    assert idx.get("FuelTankMSLarge", "fr") == "Réservoir de carburant v2"


def test_missing_scenario_csv_falls_back_silently(tmp_path, monkeypatch):
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    idx = ll.build_localization_index(tmp_path / "scenario_sans_extras")
    assert idx.get("HitPoints", "fr") == "Points dommages"


def test_localization_pack_path_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ll, '__file__', str(tmp_path / "nonexistent_pkg" / "localization_lookup.py"))
    assert ll.localization_pack_path() is None


def test_build_index_empty_when_no_sources(monkeypatch):
    monkeypatch.setattr(ll, "localization_pack_path", lambda: None)
    idx = ll.build_localization_index(None)
    assert idx.get("HitPoints", "fr") is None


# ---------------------------------------------------------------------------
# write_scenario_localization_entries -- demande explicite de l'utilisateur
# (session du 29/08/2026) : donner un nom affiche traduit a un bloc/item
# nouvellement duplique.
# ---------------------------------------------------------------------------

def test_write_creates_file_when_absent(tmp_path):
    ll.write_scenario_localization_entries(
        tmp_path, {"NewBlockCopy": {"English": "New Block Copy", "Français": "Nouveau Bloc"}})

    csv_path = tmp_path / "Extras" / "Localization.csv"
    assert csv_path.is_file()
    idx = ll.build_localization_index(tmp_path)
    assert idx.get("NewBlockCopy", "fr") == "Nouveau Bloc"
    assert idx.get("NewBlockCopy", "en") == "New Block Copy"


def test_write_preserves_existing_entries(tmp_path):
    ll.write_scenario_localization_entries(
        tmp_path, {"First": {"English": "First EN", "Français": "Premier"}})
    ll.write_scenario_localization_entries(
        tmp_path, {"Second": {"English": "Second EN", "Français": "Second"}})

    idx = ll.build_localization_index(tmp_path)
    assert idx.get("First", "fr") == "Premier"
    assert idx.get("Second", "fr") == "Second"


def test_write_updates_existing_key_without_duplicating_row(tmp_path):
    ll.write_scenario_localization_entries(
        tmp_path, {"Key1": {"English": "Old", "Français": "Ancien"}})
    ll.write_scenario_localization_entries(
        tmp_path, {"Key1": {"English": "New", "Français": "Nouveau"}})

    csv_path = tmp_path / "Extras" / "Localization.csv"
    lines = csv_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 2  # en-tete + une seule ligne Key1
    idx = ll.build_localization_index(tmp_path)
    assert idx.get("Key1", "fr") == "Nouveau"


def test_write_preserves_other_language_columns_on_existing_file(tmp_path):
    """Ecrire une nouvelle cle ne doit jamais faire perdre les colonnes
    d'autres langues (ex: Deutsch) deja presentes dans le fichier."""
    csv_path = tmp_path / "Extras" / "Localization.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "KEY,English,Deutsch,Français\nExisting,Existing EN,Existing DE,Existant\n", encoding='utf-8')

    ll.write_scenario_localization_entries(
        tmp_path, {"NewKey": {"English": "New EN", "Français": "Nouveau"}})

    content = csv_path.read_text(encoding='utf-8')
    assert "Existing DE" in content  # colonne allemande preservee


def test_write_does_not_touch_vanilla_pack(tmp_path, monkeypatch):
    """Ecrire dans le scenario ne doit jamais toucher au pack vanilla
    (fichier distribue en lecture seule, voir docstring du module)."""
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)
    original_pack_bytes = pack_path.read_bytes()

    ll.write_scenario_localization_entries(
        tmp_path, {"NewKey": {"English": "New EN", "Français": "Nouveau"}})

    assert pack_path.read_bytes() == original_pack_bytes


def test_written_entry_overrides_vanilla_on_same_key(tmp_path, monkeypatch):
    """Coherent avec la priorite scenario > vanilla deja etablie (voir
    build_localization_index)."""
    pack_path = _make_vanilla_pack(tmp_path / "localization_vanilla.pak")
    monkeypatch.setattr(ll, "localization_pack_path", lambda: pack_path)

    ll.write_scenario_localization_entries(
        tmp_path, {"HitPoints": {"English": "Custom HP", "Français": "PV personnalises"}})

    idx = ll.build_localization_index(tmp_path)
    assert idx.get("HitPoints", "fr") == "PV personnalises"
