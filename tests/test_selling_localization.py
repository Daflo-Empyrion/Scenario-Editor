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

"""Localisation de SellingText (v1.10.0, demande utilisateur) : le jeu
accepte une CLE de Localization.csv comme valeur de SellingText (mecanisme
documente dans le TraderNPCConfig.ecf vanille : # SellingText:
"trwDefaultSellingText"). Tests : generation de cle, creation/mise a jour
de Extras/Localization.csv, preservation des traductions existantes,
garde anti-doublon."""

import json

import pytest

from core.csv_handler import parse_csv_text
from core.selling_localization import (build_key, ensure_localization_entry,
                                       key_exists_in,
                                       localization_csv_path)


@pytest.fixture
def ecf_path(tmp_path):
    """Simule <scenario>/Content/Configuration/TraderNPCConfig.ecf."""
    p = tmp_path / "Content" / "Configuration" / "TraderNPCConfig.ecf"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ Trader Name: X }", encoding="utf-8")
    return p


def test_build_key_sanitizes():
    assert build_key("QuantumSTAR") == "scn_Selling_QuantumSTAR"
    assert build_key("Aunt Mary's") == "scn_Selling_AuntMarys"
    assert build_key("  Tr-a-d-er  ") == "scn_Selling_Trader"
    with pytest.raises(ValueError):
        build_key("")


def test_localization_csv_path_layout(ecf_path):
    loc = localization_csv_path(ecf_path)
    assert loc == ecf_path.parent.parent / "Extras" / "Localization.csv"


def test_ensure_creates_file_and_row(ecf_path):
    loc = localization_csv_path(ecf_path)
    assert not loc.exists()
    result = ensure_localization_entry(ecf_path, "scn_Selling_QuantumSTAR",
                                       "Hi, I am trader <NAME>.")
    assert result == "created"
    assert loc.exists()
    doc = parse_csv_text(loc.read_text(encoding="utf-8"))
    assert doc.header[0] == "KEY" and doc.header[1] == "English"
    assert doc.header[3] == "Français"  # en-tete canonique vanille
    assert doc.rows[0][0] == "scn_Selling_QuantumSTAR"
    assert doc.rows[0][1] == "Hi, I am trader <NAME>."


def test_ensure_appends_preserving_translations(ecf_path):
    loc = localization_csv_path(ecf_path)
    ensure_localization_entry(ecf_path, "scn_Selling_A", "Texte A")
    # traduction FR deja faite par l'utilisateur pour une autre cle
    doc = parse_csv_text(loc.read_text(encoding="utf-8"))
    doc.rows[0][3] = "Texte A (FR)"
    from core.csv_handler import render_csv
    loc.write_text(render_csv(doc), encoding="utf-8")

    result = ensure_localization_entry(ecf_path, "scn_Selling_B", "Texte B")
    assert result == "created"
    doc = parse_csv_text(loc.read_text(encoding="utf-8"))
    assert doc.rows[0][0] == "scn_Selling_A"
    assert doc.rows[0][3] == "Texte A (FR)"  # traduction PRESERVEE
    assert doc.rows[1][0] == "scn_Selling_B"


def test_ensure_existing_key_with_translation_untouched(ecf_path):
    result = ensure_localization_entry(ecf_path, "scn_Selling_A", "Texte A")
    assert result == "created"
    result = ensure_localization_entry(ecf_path, "scn_Selling_A",
                                       "Autre texte")
    assert result == "exists"
    doc = parse_csv_text(localization_csv_path(ecf_path).read_text(
        encoding="utf-8"))
    assert doc.rows[0][1] == "Texte A"  # jamais ecraser une traduction


def test_ensure_existing_key_empty_english_filled(ecf_path):
    loc = localization_csv_path(ecf_path)
    loc.parent.mkdir(parents=True, exist_ok=True)
    loc.write_text(
        'KEY,English,Français\nscn_Selling_A,,Déjà traduit en FR\n',
        encoding="utf-8")
    result = ensure_localization_entry(ecf_path, "scn_Selling_A", "Texte A")
    assert result == "updated"
    doc = parse_csv_text(loc.read_text(encoding="utf-8"))
    assert doc.rows[0][1] == "Texte A"
    assert doc.rows[0][2] == "Déjà traduit en FR"  # la FR existante intacte


def test_ensure_requires_key_and_text(ecf_path):
    with pytest.raises(ValueError):
        ensure_localization_entry(ecf_path, "", "Texte")
    with pytest.raises(ValueError):
        ensure_localization_entry(ecf_path, "scn_Selling_A", "   ")


def test_key_exists_in(ecf_path, tmp_path):
    loc = localization_csv_path(ecf_path)
    assert key_exists_in(loc, "scn_Selling_A") is False
    ensure_localization_entry(ecf_path, "scn_Selling_A", "Texte A")
    assert key_exists_in(loc, "scn_Selling_A") is True
    assert key_exists_in(tmp_path / "absent.csv", "x") is False


def test_localization_path_prefers_existing_root_file(ecf_path, tmp_path):
    """Vecu 20/09/2026 (RE2 ATL) : la localisation du scenario peut vivre
    a la RACINE (<scenario>/Extras/) et non sous Content/ -- un fichier
    existant doit gagner, sinon on cree un second fichier que le jeu
    ignorerait peut-etre."""
    root = tmp_path / "scenario"
    (root / "Extras").mkdir(parents=True)
    root_loc = root / "Extras" / "Localization.csv"
    root_loc.write_text("KEY,English\nold,ancien\n", encoding="utf-8")
    # aucun Content/Extras existant : la racine existante gagne
    assert localization_csv_path(ecf_path, root=root) == root_loc


def test_localization_path_content_extras_when_exists(ecf_path, tmp_path):
    (ecf_path.parent.parent / "Extras").mkdir(parents=True, exist_ok=True)
    content_loc = localization_csv_path(ecf_path)
    content_loc.parent.mkdir(parents=True, exist_ok=True)
    content_loc.write_text("KEY,English\nx,y\n", encoding="utf-8")
    assert localization_csv_path(ecf_path) == content_loc


def test_localization_path_creates_at_root_when_root_given(ecf_path, tmp_path):
    root = tmp_path / "scenario"
    root.mkdir(parents=True)
    # rien n'existe nulle part : creation dans Extras du scenario
    assert localization_csv_path(ecf_path, root=root) == \
        root / "Extras" / "Localization.csv"


def test_ensure_uses_root_location(ecf_path, tmp_path):
    root = tmp_path / "scenario"
    root.mkdir(parents=True)
    (root / "Extras").mkdir(parents=True)
    root_loc = root / "Extras" / "Localization.csv"
    root_loc.write_text("KEY,English\nold,ancien\n", encoding="utf-8")
    ensure_localization_entry(ecf_path, "scn_Selling_X", "Texte X",
                              root=root)
    # la cle est dans le FICHIER RACINE existant, pas dans un nouveau
    doc = parse_csv_text(root_loc.read_text(encoding="utf-8"))
    assert doc.rows[-1][0] == "scn_Selling_X"
    assert not (ecf_path.parent.parent / "Extras" / "Localization.csv").exists()
