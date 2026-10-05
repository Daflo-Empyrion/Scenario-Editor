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

"""Fusion structurelle GENERIQUE des YAML + revision CSV (demande
26/09/2026) : un PDA.yaml existant etait ecrase en aveugle (fusion
fichier) ou propose en REMPLACEMENT brut seulement (fusion dossier), et
la fusion CSV n'avait aucune fenetre. Desormais : unites cochees
(chapitres PDA par Id, cles racines, lignes CSV ajoutees/completees)."""
import types

import pytest
from PyQt6.QtCore import Qt

from core.csv_handler import CsvHandler, apply_csv_changes, plan_csv_merge
from core.workspace import apply_csv_changes_file, plan_csv_merge_file
from core.yaml_merge import (YamlUnit, analyze_yaml_merge, apply_yaml_units,
                             yaml_files_identical)

WORKING_PDA = """# chapitres de la copie de travail
Chapters:
  - Id: 111
    Title: TokA
    Tasks:
      - Name: T1
  - Id: 222
    Title: TokB
"""

SOURCE_PDA = """Chapters:
  - Id: 222
    Title: TokB
  - Id: 333
    Title: TokC
    Rewards:
      - Item: MedKit
NewSection:
  key: value
"""


@pytest.fixture
def pda_files(tmp_path):
    working = tmp_path / "PDA.yaml"
    source = tmp_path / "PDA_source.yaml"
    working.write_text(WORKING_PDA, encoding="utf-8")
    source.write_text(SOURCE_PDA, encoding="utf-8")
    return working, source


# ------------------------------------------------------------------ yaml core

def test_analyze_finds_new_chapter_and_root_key(pda_files):
    working, source = pda_files
    units = analyze_yaml_merge(working, source)
    chapter = next(u for u in units if u.kind == "item")
    assert chapter.root == "Chapters" and chapter.name == "333"
    assert chapter.detail == "TokC"                  # Title propose en detail
    key = next(u for u in units if u.kind == "key")
    assert key.name == "NewSection"
    assert all(isinstance(u, YamlUnit) for u in units)


def test_apply_inserts_and_preserves_comments(pda_files):
    working, source = pda_files
    units = analyze_yaml_merge(working, source)
    applied = apply_yaml_units(working, source, units)
    assert applied == 2
    text = working.read_text(encoding="utf-8")
    assert "# chapitres de la copie de travail" in text   # commentaire preserve
    assert "Id: 333" in text and "Item: MedKit" in text   # sous-arbre complet
    assert "NewSection:" in text
    assert "Id: 111" in text                              # contenu existant intact


def test_apply_is_idempotent(pda_files):
    working, source = pda_files
    units = analyze_yaml_merge(working, source)
    assert apply_yaml_units(working, source, units) == 2
    assert apply_yaml_units(working, source, units) == 0
    assert analyze_yaml_merge(working, source) == []


def test_identical_files_have_no_units(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("X:\n  - Id: 1\n", encoding="utf-8")
    b.write_text("X:\n  - Id: 1\n", encoding="utf-8")
    assert yaml_files_identical(a, b)
    assert analyze_yaml_merge(a, b) == []


def test_root_key_present_both_sides_never_modified(pda_files):
    """Copie de travail prioritaire : un element present des deux cotes avec
    un contenu DIFFERENT n'est jamais modifie (pas d'unite proposee)."""
    working, source = pda_files
    working.write_text(WORKING_PDA.replace("Title: TokB", "Title: Modifie"),
                       encoding="utf-8")
    units = [u for u in analyze_yaml_merge(working, source)
             if u.kind == "item" and u.name == "222"]
    assert units == []


def test_conflicting_blocks_by_name_identity(tmp_path):
    """Listes de blocs identifies par Name (playfield_static : POIs) --
    element absent propose, present jamais touche."""
    working = tmp_path / "pf.yaml"
    source = tmp_path / "pf_src.yaml"
    working.write_text(
        "PlayfieldType: Planet\nPOIs:\n  - GroupName: Base\n",
        encoding="utf-8")
    source.write_text(
        "PlayfieldType: Planet\nPOIs:\n"
        "  - GroupName: Base\n  - GroupName: R2XBase\n",
        encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    # POIs existe des deux cotes : seule l'entree absente est proposee
    assert [u.name for u in units] == ["R2XBase"]
    assert apply_yaml_units(working, source, units) == 1
    assert "R2XBase" in working.read_text(encoding="utf-8")
    assert "GroupName: Base\n" in working.read_text(encoding="utf-8")


def test_key_unit_detail_lists_all_block_names(tmp_path):
    """Colonne Détail d'une clé racine = TOUS les noms de la liste (ex :
    presets d'un playfield), plafonnee -- voir s'il n'y a que le preset
    'off' ou de la vraie configuration sans ouvrir le fichier."""
    working = tmp_path / "pf.yaml"
    source = tmp_path / "pf_src.yaml"
    working.write_text("PlayfieldType: Planet\n", encoding="utf-8")
    presets = "".join(
        f"  - Name: P{i}\n    Density: 0.5\n" for i in range(7))
    source.write_text("PlayfieldType: Planet\nPresets:\n" + presets,
                      encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    assert len(units) == 1 and units[0].kind == "key"
    assert units[0].detail == "P0, P1, P2, P3, P4 … (+2)"


def test_key_unit_detail_falls_back_without_list(tmp_path):
    """Cle racine sans liste de blocs (sous-cles simples) : le detail
    reste la premiere sous-cle."""
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("A: 1\n", encoding="utf-8")
    source.write_text("A: 1\nNewSection:\n  key: value\n", encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    assert units[0].detail == "key: value"


def test_chapters_identified_by_chapter_title(tmp_path):
    """Regression vecue (RE2 ATL) : les chapitres reels du PDA.yaml
    commencent par '- ChapterTitle: <token>' (pas d'Id) -- ils etaient
    tous juges non identifiables et la fenetre de fusion restait VIDE.
    Identite generique : la premiere cle de l'item lui-meme."""
    working = tmp_path / "PDA.yaml"
    source = tmp_path / "PDA_src.yaml"
    working.write_text(
        "Chapters:\n"
        "  - ChapterTitle: pda_aaa\n"
        "    Category: FAQ\n",
        encoding="utf-8")
    source.write_text(
        "Chapters:\n"
        "  - ChapterTitle: pda_aaa\n"
        "    Category: FAQ\n"
        "  - ChapterTitle: pda_bbb\n"
        "    Category: Tutorial\n"
        "    Tasks:\n"
        "      - Name: T1\n",
        encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    assert [u.name for u in units] == ["pda_bbb"]
    assert units[0].idkey == "ChapterTitle"
    assert units[0].detail == "Tutorial"          # Category en detail
    assert apply_yaml_units(working, source, units) == 1
    assert "pda_bbb" in working.read_text(encoding="utf-8")
    assert "Name: T1" in working.read_text(encoding="utf-8")


def test_duplicate_identities_in_source_are_skipped(tmp_path):
    """Liste dont plusieurs items partagent la meme '- Cle: valeur' :
    appariement non fiable -> ces items ne sont PAS proposes."""
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("List:\n  - Name: garde\n", encoding="utf-8")
    source.write_text(
        "List:\n"
        "  - Name: garde\n"
        "  - Name: dup\n"
        "  - Name: dup\n",
        encoding="utf-8")
    assert analyze_yaml_merge(working, source) == []


def test_apply_matches_identity_key_exactly(tmp_path):
    """Deux items de meme valeur sous des cles differentes : chaque unite
    est re-percée par SA cle d'identite (pas de mauvais item insere)."""
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("List:\n  - Name: garde\n", encoding="utf-8")
    source.write_text(
        "List:\n"
        "  - Name: garde\n"
        "  - Name: x\n"
        "  - Key: x\n",
        encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    assert {(u.idkey, u.name) for u in units} == {("Name", "x"),
                                                  ("Key", "x")}
    assert apply_yaml_units(working, source, units) == 2
    text = working.read_text(encoding="utf-8")
    assert text.count("- Name: x") == 1
    assert text.count("- Key: x") == 1


def test_illisible_yaml_no_units(tmp_path):
    working = tmp_path / "w.yaml"
    working.write_bytes(b"\x00\x01\x02pas du yaml")
    source = tmp_path / "s.yaml"
    source.write_text("A: 1\n", encoding="utf-8")
    assert analyze_yaml_merge(working, source) == []


# ------------------------------------------------------------------- csv core

CSV_WORKING = "Key,EN,FR\r\nkey1,Hello,\r\nkey2,World,Monde\r\n"
CSV_SOURCE = "Key,EN,FR\r\nkey1,Hello,Bonjour\r\nkey3,New,Nouveau\r\n"


def _csv_docs(tmp_path):
    handler = CsvHandler()
    working = tmp_path / "w.csv"
    source = tmp_path / "s.csv"
    working.write_text(CSV_WORKING, encoding="utf-8")
    source.write_text(CSV_SOURCE, encoding="utf-8")
    return handler, working, source


def test_plan_csv_merge_reports_added_and_completed(tmp_path):
    handler, working, source = _csv_docs(tmp_path)
    wdoc = handler.parse(handler.load(working))
    sdoc = handler.parse(handler.load(source))
    changes = plan_csv_merge(wdoc, sdoc)
    added = [c for c in changes if c.action == "added"]
    completed = [c for c in changes if c.action == "completed"]
    assert [c.key for c in added] == ["key3"]
    assert [c.key for c in completed] == ["key1"]
    assert completed[0].detail == "FR"


def test_apply_csv_changes_only_selected_rows(tmp_path):
    handler, working, source = _csv_docs(tmp_path)
    wdoc = handler.parse(handler.load(working))
    sdoc = handler.parse(handler.load(source))
    changes = plan_csv_merge(wdoc, sdoc)
    # on ne coche que la ligne "completed" (key1) : key3 ne doit PAS passer
    completed = next(c for c in changes if c.action == "completed")
    assert apply_csv_changes(wdoc, [completed]) == 1
    text = handler.serialize(wdoc)
    assert "key1,Hello,Bonjour" in text
    assert "key3" not in text


def test_plan_and_apply_csv_file_roundtrip(tmp_path):
    handler, working, source = _csv_docs(tmp_path)
    ws = types.SimpleNamespace(working_root=tmp_path)
    changes = plan_csv_merge_file(working, source)
    assert len(changes) == 2
    applied = apply_csv_changes_file(ws, working, changes)
    assert applied == 2
    text = working.read_text(encoding="utf-8")
    assert "key1,Hello,Bonjour" in text       # cellule vide completee
    assert "key3,New,Nouveau" in text         # ligne ajoutee
    assert "key2,World,Monde" in text         # existant intact
    # rejouer ne propose plus rien
    assert plan_csv_merge_file(working, source) == []


# -------------------------------------------------------------------- dialogues

def test_yaml_review_dialog_construction_and_selection(qapp, pda_files):
    from gui.yaml_merge_review_dialog import YamlMergeReviewDialog
    working, source = pda_files
    dlg = YamlMergeReviewDialog(working, source, "source", parent=None)
    assert not dlg.identical
    assert len(dlg.units) == 2
    assert len(dlg.selected_units()) == 2
    dlg._set_all_checks(False)
    assert dlg.selected_units() == []
    dlg.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
    assert len(dlg.selected_units()) == 1
    assert not dlg.replace_all


def test_yaml_review_dialog_identical(tmp_path):
    from gui.yaml_merge_review_dialog import YamlMergeReviewDialog
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("X: 1\n", encoding="utf-8")
    b.write_text("X: 1\n", encoding="utf-8")
    dlg = YamlMergeReviewDialog(a, b, "source", parent=None)
    assert dlg.identical
    assert not dlg.btn_apply.isEnabled()
    assert not dlg.btn_replace.isEnabled()


def test_yaml_review_dialog_only_conflicts_disables_apply(tmp_path):
    """Fichiers DIFFERENTS mais aucun element nouveau (ecarts internes
    seulement) : pas d'insertion possible, seul le remplacement explicite
    reste proposable."""
    from gui.yaml_merge_review_dialog import YamlMergeReviewDialog
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("X:\n  - Id: 1\n    Title: Un\n", encoding="utf-8")
    b.write_text("X:\n  - Id: 1\n    Title: Autre\n", encoding="utf-8")
    dlg = YamlMergeReviewDialog(a, b, "source", parent=None)
    assert not dlg.identical and dlg.units == []
    assert not dlg.btn_apply.isEnabled()
    assert dlg.btn_replace.isEnabled()


def test_csv_preview_dialog_construction_and_selection(qapp, tmp_path):
    from gui.csv_merge_preview_dialog import CsvMergePreviewDialog
    _, working, source = _csv_docs(tmp_path)
    dlg = CsvMergePreviewDialog(working, source, "source", parent=None)
    assert len(dlg.changes) == 2
    assert len(dlg.selected_changes()) == 2
    dlg._set_all_checks(False)
    assert dlg.selected_changes() == []
    dlg.table.item(0, dlg.COL_CHECK).setCheckState(Qt.CheckState.Checked)
    assert [c.key for c in dlg.selected_changes()] == [dlg.changes[0].key]


# ------------------------------------------------------- fusion de DOSSIER yaml

def test_folder_review_dialog_shows_generic_yaml_units(qapp, tmp_path):
    """Un dossier source contenant PDA.yaml deja present : la fenetre de
    revision propose desormais ses unites structurelles (et plus seulement
    un REMPLACEMENT brut), cochables et retournables."""
    from gui.folder_merge_review_dialog import FolderMergeReviewDialog
    source_root = tmp_path / "source"
    working = tmp_path / "working"
    (source_root / "Extras" / "PDA").mkdir(parents=True)
    (working / "Extras" / "PDA").mkdir(parents=True)
    (working / "Extras" / "PDA" / "PDA.yaml").write_text(
        WORKING_PDA, encoding="utf-8")
    (source_root / "Extras" / "PDA" / "PDA.yaml").write_text(
        SOURCE_PDA, encoding="utf-8")
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working))
    dlg = FolderMergeReviewDialog(main, source_root / "Extras" / "PDA",
                                  source_root, "source", parent=None)
    picks = dlg.selected_yaml_picks()
    assert len(picks) == 2
    plan, unit = picks[0]
    assert plan.dest.name == "PDA.yaml"
    assert {u.name for _, u in picks} == {"333", "NewSection"}
    # decocher toutes les unites -> plus rien en revision structurelle
    dlg._set_all_checks(False)
    assert dlg.selected_yaml_picks() == []


def test_yaml_picks_grouping_by_plan_after_qvariant_roundtrip(qapp, tmp_path):
    """Regression (vecu en fusion du dossier Playfields) : le regroupement
    par FilePlan dans main_window levait TypeError 'unhashable type' --
    les picks viennent d'un aller-retour QVariant (item.data) et FilePlan
    est desormais hashable (dataclass eq=False)."""
    from gui.folder_merge_review_dialog import FolderMergeReviewDialog
    source_root = tmp_path / "source"
    working = tmp_path / "working"
    (source_root / "Playfields").mkdir(parents=True)
    (working / "Playfields").mkdir(parents=True)
    (working / "Playfields" / "pf.yaml").write_text(WORKING_PDA,
                                                    encoding="utf-8")
    (source_root / "Playfields" / "pf.yaml").write_text(SOURCE_PDA,
                                                        encoding="utf-8")
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working))
    dlg = FolderMergeReviewDialog(main, source_root / "Playfields",
                                  source_root, "source", parent=None)
    by_plan = {}
    for plan, unit in dlg.selected_yaml_picks():
        by_plan.setdefault(plan, []).append(unit)   # plantait ici (TypeError)
    assert len(by_plan) == 1
    plan, units = next(iter(by_plan.items()))
    assert plan.dest.name == "pf.yaml"
    assert {u.name for u in units} == {"333", "NewSection"}


# ============================================================================
# Racines a SOUS-cles (vecu 05/10 : playfield_static — POIs: -> Random:/
# Fixed:/FixedPlayerStart: — le moteur ne descendait pas : 0 unite proposee
# pour les POIs d'histoire de Random EXP)
# ============================================================================

NESTED_W = """POIs:
    Random:
        - GroupName: NullPOI
          CountMinMax: [ 1, 1 ]
    FixedPlayerStart:
        - Type: SV_Player
          Name: Rescue Pod
"""

NESTED_S = """POIs:
    Random:
        - GroupName: NullPOI
          CountMinMax: [ 1, 1 ]
        - GroupName: MasperonAbyssalMission
          Faction: Abyssal
    Fixed:
        - Type: SV_Player
          Name: OtherPod
"""


def test_nested_root_proposes_missing_items(tmp_path):
    working = tmp_path / "playfield_static.yaml"
    source = tmp_path / "src.yaml"
    working.write_text(NESTED_W, encoding="utf-8")
    source.write_text(NESTED_S, encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    roots = {u.root for u in units}
    assert "POIs/Random" in roots
    # la sous-cle Fixed absente du working n'est PAS proposee (convention
    # du scenario hote : ex Fixed: chez REX = son propre pod de depart)
    assert not any(u.root and "Fixed" in u.root for u in units)
    names = {u.name for u in units}
    assert "MasperonAbyssalMission" in names


def test_nested_root_apply_and_idempotence(tmp_path):
    working = tmp_path / "playfield_static.yaml"
    source = tmp_path / "src.yaml"
    working.write_text(NESTED_W, encoding="utf-8")
    source.write_text(NESTED_S, encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    n = apply_yaml_units(working, source, units)
    assert n == 1
    txt = working.read_text(encoding="utf-8")
    assert "MasperonAbyssalMission" in txt
    assert "NullPOI" in txt
    assert "OtherPod" not in txt          # Fixed: de REX non cree
    # idempotent : re-analyse = plus rien, re-apply = 0
    units2 = analyze_yaml_merge(working, source)
    assert units2 == []
    assert apply_yaml_units(working, source, units2) == 0
