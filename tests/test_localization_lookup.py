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


# --------------------- colonnes alias + fusion scenario/vanilla (30/08/2026)
def test_french_column_alias_recognized():
    """Les Localization.csv de SCENARIO ecrivent souvent l'en-tete en
    anglais ('French') au lieu du vanilla ('Français') : la colonne FR doit
    quand meme etre lue -- sinon les fiches restaient en anglais (bug
    signale par l'utilisateur le 30/08/2026)."""
    from core.localization_lookup import _parse_csv_text, LocalizationIndex
    text = "KEY,English,French\nMyInfo,Hello world,Bonjour le monde\n"
    index = LocalizationIndex(_parse_csv_text(text))
    assert index.get("MyInfo", "fr") == "Bonjour le monde"
    assert index.get("MyInfo", "en") == "Hello world"


def test_scenario_english_only_row_does_not_mask_vanilla_french():
    """Fusion COLONNE PAR COLONNE : une ligne scenario ne fournissant que
    l'anglais ne doit pas ecraser la traduction francaise de la ligne
    vanilla de la meme cle."""
    from core.localization_lookup import LocalizationIndex
    vanilla = {"MyInfo": {"English": "Hello", "Français": "Bonjour"}}
    scenario = {"MyInfo": {"English": "Hello (scenario)"}}
    merged = dict(vanilla)
    for key, row in scenario.items():  # meme logique que build_localization_index
        base = merged.get(key)
        filled = dict(base)
        for col, val in row.items():
            if val and val.strip():
                filled[col] = val
        merged[key] = filled
    index = LocalizationIndex(merged)
    assert index.get("MyInfo", "fr") == "Bonjour"          # herite du vanilla
    assert index.get("MyInfo", "en") == "Hello (scenario)"  # scenario prioritaire


def test_scenario_french_still_wins_over_vanilla():
    from core.localization_lookup import LocalizationIndex
    merged = {"MyInfo": {"English": "Hello (scenario)", "Français": "Bonjour perso"}}
    index = LocalizationIndex(merged)
    assert index.get("MyInfo", "fr") == "Bonjour perso"


def test_build_localization_index_merges_cell_wise(tmp_path):
    """Bout-en-bout : un scenario dont le Localization.csv (en-tetes
    anglais) ne fournit que l'anglais pour une cle vanilla conserve la
    traduction francaise du pack."""
    from core.localization_lookup import build_localization_index
    root = tmp_path / "scenario"
    (root / "Extras").mkdir(parents=True)
    (root / "Extras" / "Localization.csv").write_text(
        "KEY,English,French\nFuelTankMSLarge,My custom tank name,\n",
        encoding="utf-8")
    index = build_localization_index(root)
    # Nom fourni par le scenario (anglais) : pris tel quel.
    assert index.get("FuelTankMSLarge", "en") == "My custom tank name"
    # Francais absent du scenario mais PRESENT dans le pack vanilla :
    # 'Réservoir de carburant v2' doit resurface.
    assert index.get("FuelTankMSLarge", "fr") == "Réservoir de carburant v2"
