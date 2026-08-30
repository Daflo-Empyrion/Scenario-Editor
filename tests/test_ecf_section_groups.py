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

"""
Tests de EcfDocument.scan_section_groups_and_labels -- bug reel signale par
l'utilisateur (29/08/2026) : le format combine sur une seule ligne
('#====Pistols HHW01===', reel dans ItemsConfig.ecf) n'etait pas du tout
reconnu, contrairement au format 3-lignes (separateur/titre/separateur).
"""
from core.ecf.parser import parse_ecf_text


def test_three_line_format_still_detected():
    """Non-regression : le format existant (Containers.ecf reel) doit
    continuer de fonctionner exactement comme avant."""
    text = (
        "# ==================================================================\n"
        "# Gigas\n"
        "# ==================================================================\n"
        "{ Block Id: 1, Name: Test\n}\n"
    )
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    assert groups == {0: "Gigas"}


def test_combined_single_line_format_detected():
    """Bug reel corrige : format sur une seule ligne, exact exemple donne
    par l'utilisateur."""
    text = "#====Pistols HHW01===\n{ Item Id: 1, Name: Pistol\n}\n"
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    assert groups == {0: "Pistols HHW01"}


def test_combined_single_line_format_with_dashes():
    text = "#---Rifles---\n{ Item Id: 1, Name: Rifle\n}\n"
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    assert groups == {0: "Rifles"}


def test_combined_single_line_format_with_space_after_hash():
    text = "# ====Pistols====\n{ Item Id: 1, Name: Pistol\n}\n"
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    assert groups == {0: "Pistols"}


def test_pure_separator_line_alone_is_not_a_combined_title():
    """Une ligne de separateurs PURE (aucun titre, deja geree par le motif
    3-lignes quand elle EST accompagnee d'un titre sur la ligne suivante) ne
    doit jamais etre prise pour un titre combine a elle seule."""
    text = "# ====================\n{ Block Id: 1, Name: Test\n}\n"
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    assert groups == {}


def test_normal_comment_not_detected_as_group():
    text = "# Ceci est juste un commentaire normal\n{ Block Id: 1, Name: Test\n}\n"
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    assert groups == {}


def test_double_hash_block_label_unaffected_by_combined_pattern():
    """L'etiquette de bloc ('## Titre') reste geree separement, jamais
    confondue avec un titre de groupe combine."""
    text = "## GolemSwamp\n{ Block Id: 1, Name: Test\n}\n"
    doc = parse_ecf_text(text)
    groups, labels = doc.scan_section_groups_and_labels()
    assert groups == {}
    assert list(labels.values()) == ["GolemSwamp"]


def test_combined_format_round_trip_preserves_file_byte_for_byte():
    """La detection ne doit jamais modifier le contenu -- verification par
    round-trip (ecriture identique a la lecture)."""
    text = "#====Pistols HHW01===\n{ Item Id: 1, Name: Pistol\n  Material: metal\n}\n"
    doc = parse_ecf_text(text)
    doc.scan_section_groups_and_labels()
    assert doc.render() == text


def test_multiple_combined_groups_in_same_file():
    text = (
        "#====Pistols====\n"
        "{ Item Id: 1, Name: Pistol\n}\n"
        "#====Rifles====\n"
        "{ Item Id: 2, Name: Rifle\n}\n"
    )
    doc = parse_ecf_text(text)
    groups, _ = doc.scan_section_groups_and_labels()
    titles = sorted(groups.values())
    assert titles == ["Pistols", "Rifles"]
