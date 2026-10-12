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
"""Fusion YAML LIGNE A LIGNE (demande 07/10 : SolarSystemConfig/RandomPresets
fusionnait sans aucune vue des differences entre blocs presents des deux
cotes) : unites 'modified' avec YamlLineRow (identique / modifiee avant-
apres / ajoutee / supprimable), coches par ligne, application ciblee
yamllite, idempotence, commentaires preserved. Dialogues testes en
construction (crash natif PyQt6.11 sinon)."""

import pytest

from core import settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")


# YAML d'essai dans l'esprit SolarSystemConfig/RandomPresets :
# le bloc commun « Systeme Test » porte une valeur CHANGEE (Faction),
# une feuille AJOUTEE par la source (NewProp), une feuille working SEUL
# (OldProp) et une sous-liste de scalaires dont une valeur change.
WORKING_YAML = """SpaceSystems:
- Name: Systeme Test
  Faction: Faction A
  OldProp: 1
  Coordinates:
  - 0.5
  - 0.5
  CommentLine: garde-moi
- Name: Systeme B
  Faction: Faction B

OtherKey:
  SubProp: x
"""

SOURCE_YAML = """SpaceSystems:
- Name: Systeme Test
  Faction: Faction B
  NewProp: 42
  Coordinates:
  - 0.7
  - 0.5
  CommentLine: garde-moi # note
- Name: Systeme B
  Faction: Faction B
- Name: Systeme C
  Faction: Faction C

OtherKey:
  SubProp: x
"""


@pytest.fixture()
def yml_pair(tmp_path):
    working = tmp_path / "SolarSystemConfig.yaml"
    source = tmp_path / "source.yaml"
    working.write_text(WORKING_YAML, encoding="utf-8")
    source.write_text(SOURCE_YAML, encoding="utf-8")
    return working, source


def _modified_units(units):
    return [u for u in units if u.kind == "modified"]


# ------------------------------------------------------------------ analyse

def test_analyze_finds_modified_blocks(yml_pair):
    from core.yaml_merge import analyze_yaml_merge
    working, source = yml_pair
    units = analyze_yaml_merge(working, source)
    kinds = {u.kind for u in units}
    assert "modified" in kinds
    mod = _modified_units(units)
    # un modified pour le bloc « Systeme Test », pas pour « Systeme B »
    # (identique) ni pour « Systeme C » (absent -> unite 'item')
    names = [u.name for u in mod]
    assert "Systeme Test" in names
    assert "Systeme B" not in names
    assert any(u.kind == "item" and u.name == "Systeme C" for u in units)


def test_rows_states_and_defaults(yml_pair):
    from core.yaml_merge import analyze_yaml_merge
    working, source = yml_pair
    units = analyze_yaml_merge(working, source)
    mod = next(u for u in _modified_units(units) if u.name == "Systeme Test")
    by_state = {}
    for row in mod.rows:
        by_state.setdefault(row.state, []).append(row)
    # Faction changee : DECOCHÉE par defaut (copie de travail prioritaire)
    changed_keys = [r.path[-1][1] for r in by_state.get("changed", [])
                    if r.path[-1][0] == "key"]
    assert "Faction" in changed_keys
    faction_row = next(r for r in by_state["changed"]
                       if r.path[-1] == ("key", "Faction"))
    assert faction_row.checked is False
    assert "Faction A" in faction_row.before
    assert "Faction B" in faction_row.after
    # OldProp : working seul -> supprimable DECOCHÉE (miroir non implicite)
    old_row = next(r for r in mod.rows
                   if r.path[-1] == ("key", "OldProp"))
    assert old_row.state == "remove" and old_row.checked is False
    # NewProp : ajoutee par la source -> COCHÉE (rien ne se perd)
    new_row = next(r for r in mod.rows if r.path[-1] == ("key", "NewProp"))
    assert new_row.state == "add" and new_row.checked is True
    # liste verticale de scalaires (Coordinates) : TOUTES les lignes
    # candidats, sans appariement — 0.7 absent -> ajout COCHÉ, 0.5 déjà
    # là -> ajout DECOCHÉ, les deux working -> suppression DECOCHÉE
    scalar_adds = [r for r in mod.rows
                   if r.state == "add" and r.path[-1][0] in ("index", "sib")]
    scalar_removes = [r for r in mod.rows
                      if r.state == "remove"
                      and r.path[-1][0] in ("index", "sib")]
    assert not [r for r in mod.rows if r.state == "changed"
                and r.path[-1][0] in ("index", "sib")]
    add_07 = next(r for r in scalar_adds if "0.7" in r.after)
    add_05 = next(r for r in scalar_adds if "- 0.5" in r.after)
    assert add_07.checked is True and add_05.checked is False
    assert len(scalar_removes) == 2 \
        and all(not r.checked for r in scalar_removes)
    # CommentLine : commentaire different chez la source -> modifiée
    # (visible, décochée) ; la comparaison est sémantique
    comment_row = next(r for r in mod.rows
                       if r.path[-1] == ("key", "CommentLine"))
    assert comment_row.state == "changed" and comment_row.checked is False
    # detail compact neutre
    assert mod.detail  # ex : « 2↔ 1+ 1− »


def test_no_modified_unit_for_identical_files(tmp_path):
    from core.yaml_merge import analyze_yaml_merge
    same = tmp_path / "a.yaml"
    same.write_text("Key:\n  Prop: 1\n", encoding="utf-8")
    other = tmp_path / "b.yaml"
    other.write_text("Key:\n  Prop: 1\n", encoding="utf-8")
    assert analyze_yaml_merge(same, other) == []


# --------------------------------------------------------------- application

def test_apply_checked_rows_only(yml_pair):
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working, source = yml_pair
    units = analyze_yaml_merge(working, source)
    mod = next(u for u in _modified_units(units) if u.name == "Systeme Test")
    # TOUT decocher puis ne cocher QUE la valeur de Faction : la fusion
    # n'applique exactement que les lignes choisies
    for row in mod.rows:
        row.checked = row.state == "changed" \
            and row.path[-1] == ("key", "Faction")
    assert apply_yaml_units(working, source, [mod]) == 1
    text = working.read_text(encoding="utf-8")
    assert "Faction: Faction B" in text
    assert "NewProp" not in text           # ajout non cochée : absente
    assert "OldProp: 1" in text            # suppression non cochée
    assert "0.7" not in text.split("Systeme B")[0]  # scalaire non cochée
    assert "CommentLine: garde-moi" in text  # intacte


def test_apply_remove_and_scalar_when_checked(yml_pair):
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working, source = yml_pair
    units = analyze_yaml_merge(working, source)
    mod = next(u for u in _modified_units(units) if u.name == "Systeme Test")
    for row in mod.rows:
        if row.state != "same":
            row.checked = True
    assert apply_yaml_units(working, source, [mod]) >= 1
    text = working.read_text(encoding="utf-8")
    assert "OldProp" not in text            # remove cochee : effacee
    assert "Faction: Faction B" in text
    assert "NewProp: 42" in text
    bloc = text.split("Systeme B")[0]
    assert "0.7" in bloc and "0.5" in bloc  # scalaires alignés sur source


def test_apply_is_idempotent(tmp_path):
    """Mapping pur : tout adopter (valeurs, ajouts, suppressions) ->
    re-analyse VIDE (comparaison semantique : valeur + commentaire)."""
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text(
        "Bloc:\n  Faction: A\n  OldProp: 1\n  Note: garde-moi\n",
        encoding="utf-8")
    source.write_text(
        "Bloc:\n  Faction: B\n  NewProp: 42\n  Note: garde-moi # note\n",
        encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    for unit in units:
        for r in unit.rows:
            if r.state != "same":
                r.checked = True
    assert apply_yaml_units(working, source, units) > 0
    snapshot = working.read_text(encoding="utf-8")
    units2 = analyze_yaml_merge(working, source)
    assert units2 == []
    assert apply_yaml_units(working, source, []) == 0
    assert working.read_text(encoding="utf-8") == snapshot


def test_replace_subtree_leaf_vs_branch(tmp_path):
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("Bloc:\n  Prop: feuille\n  Autre: 1\n", encoding="utf-8")
    source.write_text("Bloc:\n  Prop:\n    A: 1\n    B: 2\n  Autre: 1\n",
                      encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    mod = _modified_units(units)
    assert mod, "la difference feuille/branche doit produire une unite"
    row = next(r for r in mod[0].rows if r.state == "changed")
    assert row.replace_subtree is True and row.checked is False
    row.checked = True
    assert apply_yaml_units(working, source, mod) == 1
    text = working.read_text(encoding="utf-8")
    assert "A: 1" in text and "B: 2" in text and "Autre: 1" in text


def test_identical_file_yields_nothing(tmp_path):
    from core.yaml_merge import analyze_yaml_merge
    working = tmp_path / "w.yaml"
    working.write_text("A: 1\n", encoding="utf-8")
    assert analyze_yaml_merge(working, working) == []


# ----------------------------------------------------------------- dialogues

def test_line_dialog_builds_and_edits_rows(qapp, yml_pair):
    from core.yaml_merge import analyze_yaml_merge
    from gui.yaml_line_merge_dialog import YamlLineMergeDialog
    working, source = yml_pair
    units = analyze_yaml_merge(working, source)
    mod = next(u for u in _modified_units(units) if u.name == "Systeme Test")
    dlg = YamlLineMergeDialog(mod, working, source)
    dlg.show()
    try:
        # lignes identiques visibles par defaut (« tout montrer »)
        assert dlg.tree.topLevelItemCount() >= 1
        assert dlg.selected_count() >= 1        # les ajoutes cochés
        # cocher tout -> toutes les actionables
        dlg._set_all(True)
        assert dlg.selected_count() == sum(
            1 for r in mod.rows if r.state != "same")
        assert dlg.removal_count() >= 1
        dlg._set_all(False)
        assert dlg.selected_count() == 0
        # filtre identiques
        dlg.hide_same.setChecked(True)
        hidden = [i.isHidden() for i, r in dlg._items if r.state == "same"]
        assert all(hidden)
    finally:
        dlg.close()
        dlg.deleteLater()


def test_scalar_seq_all_lines_independent(tmp_path):
    """Vecu 07/10 (PlanetLists) : PAS d'appariement dans les listes de
    scalaires — l'appariement (par index puis par valeur) donnait des
    « identique » trompeurs (commentaires differents : « # 6 - Trading
    Stations » vs « # 6 - Alien »). TOUTES les lignes s'affichent de
    leur cote, cochables : source = ajout (cochee SAUF valeur deja
    presente), working = suppression (decochee)."""
    from core.yaml_merge import analyze_yaml_merge
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text(
        "Bloc:\n  PlanetLists:\n  - 'Gas'\n  - 'Ocean'\n"
        "  - 'Snow'\n  - 'Old'\n", encoding="utf-8")
    source.write_text(
        "Bloc:\n  PlanetLists:\n  - 'Gas'\n  - 'Hot'\n  - 'Ocean'\n"
        "  - 'Plasma'\n  - 'Snow'\n", encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    mod = _modified_units(units)
    assert mod, "difference de liste doit produire une unite modified"
    rows = [r for r in mod[0].rows if r.path[-1][0] in ("index", "sib")]
    assert not [r for r in rows if r.state in ("same", "changed")], \
        "aucun appariement : chaque ligne est un candidat independant"
    adds = [r for r in rows if r.state == "add"]
    removes = [r for r in rows if r.state == "remove"]
    assert len(adds) == 5 and len(removes) == 4
    assert all(not r.checked for r in removes)
    by_value = {r.after: r.checked for r in adds}
    # deja presentes telles quelles -> DECOCHÉES (sinon doublons) ;
    # nouvelles -> cochées ; tout reste cochable librement
    assert by_value == {"  - 'Gas'": False, "  - 'Hot'": True,
                        "  - 'Ocean'": False, "  - 'Plasma'": True,
                        "  - 'Snow'": False}


def test_apply_multiple_adds_same_scalar_list(tmp_path):
    """Regression : deux ajouts dans la MEME liste — le test positionnel
    sautait le 2e (index decales par le 1er append)."""
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("Bloc:\n  L:\n  - A\n", encoding="utf-8")
    source.write_text("Bloc:\n  L:\n  - A\n  - B\n  - C\n", encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    mod = _modified_units(units)
    assert apply_yaml_units(working, source, mod) == 2
    text = working.read_text(encoding="utf-8")
    assert "- B" in text and "- C" in text


def test_remove_duplicate_scalar_targets_the_checked_line(tmp_path):
    """Regression : YamlEntry.__eq__ compare par VALEUR — cocher la
    suppression du 2e doublon « Alpha » doit retirer CETTE occurrence,
    pas le premier venu (sinon la liste se reordonne silencieusement)."""
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text(
        "Bloc:\n  L:\n  - Alpha\n  - Beta\n  - Alpha\n", encoding="utf-8")
    source.write_text(
        "Bloc:\n  L:\n  - Alpha\n  - Beta\n  - Alpha\n  - Gamma\n",
        encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    mod = _modified_units(units)[0]
    # liste VERTICALE (format Empyrion) : segments ('sib', 'L', i)
    target = next(r for r in mod.rows
                  if r.state == "remove"
                  and r.path[-1] == ("sib", "L", 2))
    target.checked = True
    assert apply_yaml_units(working, source, [mod]) == 2   # remove + Gamma
    lines = [l.strip() for l in
             working.read_text(encoding="utf-8").splitlines()]
    assert lines.index("- Alpha") < lines.index("- Beta") \
        < lines.index("- Gamma")


def test_apply_replace_via_add_and_remove_unequal(tmp_path):
    """Remplacer une valeur dans une liste decalee = cocher l'ajout
    source ET la suppression working (le choix de l'utilisateur)."""
    from core.yaml_merge import analyze_yaml_merge, apply_yaml_units
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("Bloc:\n  L:\n  - 'OceanOld'\n  - 'Snow'\n",
                       encoding="utf-8")
    source.write_text("Bloc:\n  L:\n  - 'OceanNew'\n  - 'Hot'\n"
                      "  - 'Snow'\n", encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    mod = _modified_units(units)[0]
    for row in mod.rows:
        if row.state == "add" and "Ocean" in row.after:
            row.checked = True          # ajouter la forme source
        elif row.state == "remove" and "Ocean" in row.before:
            row.checked = True          # retirer la vieille forme
        else:
            row.checked = False
    assert apply_yaml_units(working, source, [mod]) == 2
    text = working.read_text(encoding="utf-8")
    assert "OceanNew" in text and "OceanOld" not in text
    assert "Snow" in text               # non coché : intact
    assert "Hot" not in text            # ajout non coché : absent


def test_scalar_seq_equal_counts_also_independent(tmp_path):
    """Meme nombre d'items : PAS de regime special — meme modele ligne a
    ligne (Coordinates y compris : remplacer = cocher l'ajout et la
    suppression)."""
    from core.yaml_merge import analyze_yaml_merge
    working = tmp_path / "w.yaml"
    source = tmp_path / "s.yaml"
    working.write_text("Bloc:\n  C:\n  - 0.5\n  - 0.5\n", encoding="utf-8")
    source.write_text("Bloc:\n  C:\n  - 0.7\n  - 0.5\n", encoding="utf-8")
    units = analyze_yaml_merge(working, source)
    mod = _modified_units(units)
    assert mod
    rows = [r for r in mod[0].rows if r.path[-1][0] in ("index", "sib")]
    adds = [r for r in rows if r.state == "add"]
    removes = [r for r in rows if r.state == "remove"]
    assert len(adds) == 2 and len(removes) == 2
    add_07 = next(r for r in adds if "0.7" in r.after)
    add_05 = next(r for r in adds if "- 0.5" in r.after)
    assert add_07.checked is True      # 0.7 absent du working
    assert add_05.checked is False     # 0.5 deja la : decochee
    assert all(not r.checked for r in removes)


def test_line_dialog_deep_rows_context_tree(qapp):
    """Vecu en reel (SolarSystemConfig) : des lignes a PROFONDEUR 2
    (sous-mapping du bloc) plantaient la construction de l'arbre de
    contexte (recursion sur un chemin vide, IndexError)."""
    from pathlib import Path

    from core.yaml_merge import YamlLineRow, YamlUnit
    from gui.yaml_line_merge_dialog import YamlLineMergeDialog
    unit = YamlUnit(
        kind="modified", root="GenerationParams", name="GenerationParams",
        path=(("key", "GenerationParams"),),
        rows=(
            YamlLineRow("same", (("key", "PlanetTypes"),
                                 ("key", "Dummy")),
                        "  Dummy: A", "  Dummy: A"),
            YamlLineRow("changed", (("key", "PlanetTypes"),
                                    ("key", "Dummy")),
                        "  Dummy: A", "  Dummy: B"),
            YamlLineRow("changed", (("sib", "Coordinates", 0),),
                        "  - 0.5", "  - 0.7"),
            YamlLineRow("same", (("key", "Top"),), "  Top: 1", "  Top: 1"),
        ))
    dlg = YamlLineMergeDialog(unit, Path("w.yaml"), Path("s.yaml"))
    dlg.show()
    try:
        # deux groupes de contexte de premier niveau (PlanetTypes et la
        # ligne scalaire sib sans contexte), le changed imbrique vit
        # SOUS le contexte PlanetTypes
        assert dlg.tree.topLevelItemCount() >= 2
        dlg._set_all(True)
        assert dlg.selected_count() == 2        # seulement les changed
        assert dlg.removal_count() == 0
    finally:
        dlg.close()
        dlg.deleteLater()


def test_line_dialog_rows_not_editable_and_doubleclick_toggles(qapp, yml_pair):
    """Vecu 07/10 : QTreeWidgetItem editable par defaut — le double-clic
    ouvrait un editeur de texte au lieu de cocher. Plus d'edition ;
    double-clic sur la ligne = toggle de la coche."""
    from PyQt6.QtCore import Qt

    from core.yaml_merge import analyze_yaml_merge
    from gui.yaml_line_merge_dialog import YamlLineMergeDialog
    working, source = yml_pair
    units = analyze_yaml_merge(working, source)
    mod = next(u for u in _modified_units(units) if u.name == "Systeme Test")
    dlg = YamlLineMergeDialog(mod, working, source)
    dlg.show()
    try:
        actionable = [(i, r) for i, r in dlg._items if r.state != "same"]
        assert actionable
        for item, _row in actionable:
            assert not (item.flags() & Qt.ItemFlag.ItemIsEditable), \
                "edition de texte : le double-clic n'ouvre plus d'editeur"
        item, row = actionable[0]
        row.checked = False
        item.setCheckState(dlg.COL_CHECK, Qt.CheckState.Unchecked)
        dlg._on_double_clicked(item, dlg.COL_STATE)     # clic hors case
        assert row.checked is True
        dlg._on_double_clicked(item, dlg.COL_STATE)
        assert row.checked is False
        dlg._on_double_clicked(item, dlg.COL_CHECK)     # case : natif seul
        assert row.checked is False
    finally:
        dlg.close()
        dlg.deleteLater()


def test_review_dialog_modified_defaults_and_selection(qapp, yml_pair):
    from core.yaml_merge import analyze_yaml_merge, yaml_files_identical
    from gui.yaml_merge_review_dialog import YamlMergeReviewDialog
    from PyQt6.QtCore import Qt
    working, source = yml_pair

    def _fake_analyze(self):
        if yaml_files_identical(self.working_yaml, self.source_yaml):
            return True, []
        return False, analyze_yaml_merge(self.working_yaml, self.source_yaml)

    from gui import yaml_merge_review_dialog as mod_dialog
    original = mod_dialog.YamlMergeReviewDialog._analyze
    mod_dialog.YamlMergeReviewDialog._analyze = _fake_analyze
    try:
        dlg = YamlMergeReviewDialog(working, source, "source.yaml")
        dlg.show()
        try:
            modified_items = []
            for i in range(dlg.tree.topLevelItemCount()):
                item = dlg.tree.topLevelItem(i)
                unit = item.data(0, Qt.ItemDataRole.UserRole)
                if unit.kind == "modified":
                    modified_items.append(item)
            assert modified_items
            # l'etat de la coche REFLETE les lignes : ici une ajoutée
            # cochée par defaut -> l'unite apparait cochée
            item = modified_items[0]
            unit = item.data(0, Qt.ItemDataRole.UserRole)
            assert (item.checkState(0) == Qt.CheckState.Checked) \
                == any(r.checked for r in unit.rows)
            # decocher l'unite decoche toutes ses lignes (l'etat ne
            # change pas -> pas de signal -> repasser par Unchecked)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            assert all(not r.checked for r in unit.rows
                       if r.state != "same")
            assert dlg.pending_removals() == 0
            # cocher l'unite coche TOUTES ses lignes (dont les
            # suppressions miroir -- confirmeées avant application)
            item.setCheckState(0, Qt.CheckState.Checked)
            assert all(r.checked for r in unit.rows if r.state != "same")
            assert dlg.pending_removals() >= 1
        finally:
            dlg.close()
            dlg.deleteLater()
    finally:
        mod_dialog.YamlMergeReviewDialog._analyze = original
