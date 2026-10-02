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

"""Fusion STRUCTURELLE de Sectors.yaml (tranche 2, demande 25/09) :
systemes/secteurs/lignes playfield proposes un a un et INSERTS dans le
fichier de la copie de travail (jamais d'ecrasement), commentaires et
mise en forme preserves via yamllite."""
import types

import pytest

from core.sectors_merge import analyze_sectors_merge, apply_structural_units

WORKING_YAML = """SolarSystems:
  - Name: Alpha
    Coordinates: [190, 15, 50]
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Ancienne, OldTemplate, '']
# --- commentaire de section Beta conserve chez la source
"""

SOURCE_YAML = """SolarSystems:
  - Name: Alpha
    Coordinates: [190, 15, 50]
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Ancienne, OldTemplate, '']
          - ['120,0,0', MaPlanete, TempX, '']
# --- commentaire de section Beta conserve chez la source
  - Name: Beta
    Coordinates: [42, 21, 7]
    Sectors:
      - Coordinates: [1, 2, 3]
        Playfields:
          - ['0,0,0', PlaneteBeta, TempX, '']
"""


@pytest.fixture
def yaml_paths(tmp_path):
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(WORKING_YAML, encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE_YAML, encoding="utf-8")
    return working, source


def test_analyze_finds_missing_units(yaml_paths):
    working, source = yaml_paths
    units = analyze_sectors_merge(working, source)
    kinds = {(u.kind, u.name) for u in units}
    assert ("playfield", "MaPlanete") in kinds
    assert ("system", "Beta") in kinds
    # le playfield deja present (Ancienne) n'est jamais propose
    assert ("playfield", "Ancienne") not in kinds


def test_apply_inserts_and_preserves(yaml_paths):
    working, source = yaml_paths
    units = analyze_sectors_merge(working, source)
    n = apply_structural_units(working, units, source)
    assert n == 2
    text = working.read_text(encoding="utf-8")
    # insertion du systeme Beta avec son commentaire source preserve
    assert "- Name: Beta" in text
    assert "# --- commentaire de section Beta conserve chez la source" in text
    assert "PlaneteBeta" in text
    # la ligne playfield inseree dans le secteur existant, l'ancienne garde
    assert "MaPlanete" in text and "Ancienne" in text
    # idempotent : une nouvelle analyse ne propose plus rien
    assert analyze_sectors_merge(working, source) == []


def test_apply_empty_units_writes_nothing(yaml_paths):
    working, source = yaml_paths
    before = working.read_bytes()
    assert apply_structural_units(working, [], source) == 0
    assert working.read_bytes() == before


def test_dialog_structural_section(qapp, yaml_paths, monkeypatch):
    """Le dialogue de revision affiche la section structurelle quand un
    Sectors.yaml est dans le plan, avec les unites cochees."""
    from PyQt6.QtCore import Qt
    from gui.folder_merge_review_dialog import FolderMergeReviewDialog
    working, source = yaml_paths
    # racines : working = <tmp>/working/Sectors/Sectors.yaml
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working.parent.parent))
    source_root = source.parent.parent
    (source_root / "Prefabs").mkdir(exist_ok=True)
    dlg = FolderMergeReviewDialog(main, source.parent, source_root,
                                  "source", parent=None)
    assert dlg.sectors_plan is not None
    units = dlg.selected_structural_units()
    assert {(u.kind, u.name) for u in units} == {
        ("playfield", "MaPlanete"), ("system", "Beta")}
    # tout decocher -> plus aucune unite selectionnee
    dlg._set_all_checks(False)
    assert dlg.selected_structural_units() == []
    dlg._set_all_checks(True)
    assert len(dlg.selected_structural_units()) == 2


def test_merge_preserves_system_coordinates_block(tmp_path):
    """Vecu 01-02/10 : les Coordinates de SYSTEME en bloc vertical sont le
    format que le jeu LIT (carte + chargement) — une conversion en flow
    rendait le Sectors.yaml inparsable par YamlDotNet du jeu (« Expected
    'SequenceStart', got 'MappingStart' »). Garde-fou anti-regression : le
    round-trip yamllite preserve le bloc vertical ET son commentaire."""
    from core.yamllite.parser import parse_yaml_file
    src = tmp_path / "Sectors.yaml"
    src.write_text(
        "SolarSystems:\n"
        "  - Name: Hyperion System\n"
        "    StarClass: S\n"
        "    Coordinates:\n"
        "      - 110  # original: 190\n"
        "      - 1\n"
        "      - 140\n"
        "    Sectors:\n"
        "      - Coordinates:\n"
        "          - 0\n"
        "          - 0\n"
        "          - 0\n"
        "        Playfields:\n"
        "          - ['0,0,0', Hyperion System, SunRandom, '']\n",
        encoding="utf-8")
    doc = parse_yaml_file(src)
    rendered = doc.render()
    assert "- 110  # original: 190" in rendered, \
        "le bloc vertical Coordinates et son commentaire doivent rester"
    assert "Coordinates:\n" in rendered or "- 110" in rendered


def test_normalize_system_coordinates_removed():
    """La normalisation flow (nuisible, vecu 02/10 : le jeu ne parsait plus
    le Sectors.yaml) a ete retiree du moteur."""
    import core.sectors_merge as m
    assert not hasattr(m, "normalize_system_coordinates"), \
        "normalize_system_coordinates ne doit plus exister"
