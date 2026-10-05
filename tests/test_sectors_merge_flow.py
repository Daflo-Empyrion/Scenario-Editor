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

"""Garde-fou fusion Sectors.yaml (gui/sectors_merge_flow.py) : un
Sectors.yaml ne passe JAMAIS par la fusion YAML generique (vecu 04/10 :
« Duplicate playfield name 'Zeyhines' », 5 doublons) — detection + revue
FINE (arbre systeme/secteur/ligne, demande 04/10) + scan
post-application."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QWidget

from core.sectors_merge import FineRequest, analyze_sectors_merge
from gui.sectors_merge_flow import (SectorsFineDialog, is_sectors_yaml,
                                    open_sectors_merge)

WORKING = """SolarSystems:
  - Name: Alpha
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Alpha Sun, SunRandom, '']
"""

SOURCE = """SolarSystems:
  - Name: Beta
    Sectors:
      - Coordinates: [0, 0, 0]
        Playfields:
          - ['0,0,0', Beta Sun, Sun, '']
          - ['2,0,0', BetaA, Desert, '']
      - Coordinates: [5, 0, 0]
        Playfields:
          - ['0,0,0', BetaB, Ocean, '']
"""


def _make_pair(tmp_path):
    working = tmp_path / "working" / "Sectors" / "Sectors.yaml"
    working.parent.mkdir(parents=True)
    working.write_text(WORKING, encoding="utf-8")
    source = tmp_path / "source" / "Sectors" / "Sectors.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE, encoding="utf-8")
    return working, source


def test_is_sectors_yaml(tmp_path):
    assert is_sectors_yaml(tmp_path / "Sectors" / "Sectors.yaml")
    assert is_sectors_yaml(tmp_path / "Sectors" / "sectors.YAML")
    assert not is_sectors_yaml(tmp_path / "Extras" / "PDA.yaml")


def test_flow_reject_keeps_file(qapp, tmp_path, monkeypatch):
    """Annuler la revue n'ecrit RIEN (regle projet : bouton Annuler)."""
    working, source = _make_pair(tmp_path)
    monkeypatch.setattr("gui.sectors_merge_flow.SectorsFineDialog.exec",
                        lambda self: QDialog.DialogCode.Rejected)
    parent = QWidget()
    assert open_sectors_merge(parent, None, working, source) is False
    assert working.read_text(encoding="utf-8") == WORKING


def test_flow_applies_whole_selection(qapp, tmp_path, monkeypatch):
    """OK de la revue avec TOUT coché : Beta insere entier, backup CENTRAL
    (pas de .bak dans Sectors/), scan post-application sans alerte."""
    from gui.msgboxes import info
    working, source = _make_pair(tmp_path)
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)

    class FakeDlg:
        def __init__(self, units, deps=(), missing=(), duplicates=None,
                     parent=None):
            self.chk_fix_dups = None
            assert units, "des unites doivent etre proposees"

        def exec(self):
            return 1

        def selections(self):
            return [FineRequest("Beta", "[0, 0, 0]", None),
                    FineRequest("Beta", "[5, 0, 0]", None)]

        def checked_deps(self):
            return []
    monkeypatch.setattr("gui.sectors_merge_flow.SectorsFineDialog", FakeDlg)
    # les tests n'ecrivent JAMAIS dans le vrai dossier de backups
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda p, kind="sectors": tmp_path / "backup.yaml")
    parent = QWidget()
    assert open_sectors_merge(parent, None, working, source) is True
    txt = working.read_text(encoding="utf-8")
    assert "- Name: Beta" in txt and "Beta Sun" in txt and "BetaB" in txt
    assert "Alpha Sun" in txt
    assert not list(working.parent.glob("*.bak"))


def test_flow_partial_selection(qapp, tmp_path, monkeypatch):
    """Selection partielle : une seule ligne de Beta — le systeme est
    insere avec les secteurs CHOISIS seulement (soleil compris)."""
    from gui.msgboxes import info
    working, source = _make_pair(tmp_path)
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)

    class FakeDlg:
        def __init__(self, units, deps=(), missing=(), duplicates=None,
                     parent=None):
            self.chk_fix_dups = None

        def exec(self):
            return 1

        def selections(self):
            return [FineRequest("Beta", "[0, 0, 0]", None)]

        def checked_deps(self):
            return []
    monkeypatch.setattr("gui.sectors_merge_flow.SectorsFineDialog", FakeDlg)
    # les tests n'ecrivent JAMAIS dans le vrai dossier de backups
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda p, kind="sectors": tmp_path / "backup.yaml")
    parent = QWidget()
    assert open_sectors_merge(parent, None, working, source) is True
    txt = working.read_text(encoding="utf-8")
    assert "Beta Sun" in txt and "BetaA" in txt
    assert "BetaB" not in txt          # secteur non coche


# ---------------------------------------------------------------------------
# Dialogue FIN : arbre, tri-state, selections (demande 04/10)
# ---------------------------------------------------------------------------

def _fine_units(tmp_path):
    working, source = _make_pair(tmp_path)
    return analyze_sectors_merge(working, source, detailed=True), working


def test_fine_dialog_tree_and_selections(qapp, tmp_path):
    units, _ = _fine_units(tmp_path)
    dlg = SectorsFineDialog(units)
    assert dlg.tree.parent() is not None      # ajoute au layout (vecu 04/10)
    # 1 top-level (Beta) + groupe deps absent ; Beta a 2 secteurs
    assert dlg.tree.topLevelItemCount() == 1
    beta = dlg.tree.topLevelItem(0)
    assert beta.childCount() == 2
    sec0 = beta.child(0)
    assert sec0.childCount() == 2             # Beta Sun + BetaA
    # tout coche par defaut -> selections = secteurs entiers (rows=None)
    reqs = dlg.selections()
    assert all(r.rows is None for r in reqs)
    assert {(r.system, r.coordinates) for r in reqs} == {
        ("Beta", "[0, 0, 0]"), ("Beta", "[5, 0, 0]")}
    # decocher UNE ligne -> parent partiel, selections = sous-ensemble
    sec0.child(1).setCheckState(0, Qt.CheckState.Unchecked)
    assert sec0.checkState(0) == Qt.CheckState.PartiallyChecked
    assert beta.checkState(0) == Qt.CheckState.PartiallyChecked
    reqs = dlg.selections()
    by_coords = {r.coordinates: r.rows for r in reqs}
    assert by_coords["[0, 0, 0]"] == ("Beta Sun",)
    assert by_coords["[5, 0, 0]"] is None


def test_fine_dialog_cascade_and_empty(qapp, tmp_path):
    units, _ = _fine_units(tmp_path)
    dlg = SectorsFineDialog(units)
    beta = dlg.tree.topLevelItem(0)
    # decocher le systeme : cascade sur tous les descendants
    beta.setCheckState(0, Qt.CheckState.Unchecked)
    for i in range(beta.childCount()):
        sec = beta.child(i)
        assert sec.checkState(0) == Qt.CheckState.Unchecked
        for j in range(sec.childCount()):
            assert sec.child(j).checkState(0) == Qt.CheckState.Unchecked
    assert dlg.selections() == []
    # recocher le systeme : tout revient
    beta.setCheckState(0, Qt.CheckState.Checked)
    assert beta.child(0).checkState(0) == Qt.CheckState.Checked


def test_fine_dialog_conflict_rows_disabled(qapp, tmp_path):
    """Les lignes deja presentes dans le working sont GRISEES (non
    cochables) et jamais dans selections()."""
    working, source = _make_pair(tmp_path)
    # le working contient deja 'BetaA' (autre systeme) : conflit global
    working.write_text(
        "SolarSystems:\n"
        "  - Name: Alpha\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Alpha Sun, SunRandom, '']\n"
        "          - ['1,0,0', BetaA, Desert, '']\n",
        encoding="utf-8")
    units = analyze_sectors_merge(working, source, detailed=True)
    dlg = SectorsFineDialog(units)
    beta = dlg.tree.topLevelItem(0)
    sec0 = beta.child(0)
    row_flags = [(sec0.child(j).text(1),
                  bool(sec0.child(j).flags() & Qt.ItemFlag.ItemIsUserCheckable),
                  sec0.child(j).checkState(0))
                 for j in range(sec0.childCount())]
    by_name = {n: (chk, st) for n, chk, st in row_flags}
    assert by_name["BetaA"] == (False, Qt.CheckState.Unchecked)  # grisee
    assert by_name["Beta Sun"] == (True, Qt.CheckState.Checked)
    # selection par defaut : BetaA jamais demande
    for r in dlg.selections():
        if r.rows is not None:
            assert "BetaA" not in r.rows


def test_fine_dialog_with_deps(qapp, tmp_path):
    """Les lignes deps (PlayfieldTypeDep, sans attribut .kind) ne font plus
    planter selections() a l'OK de la fenetre (vecu 04/10 : AttributeError
    des qu'une dependance Playfields/<Type> etait proposee)."""
    from core.sectors_merge import PlayfieldTypeDep
    units, _ = _fine_units(tmp_path)
    dep = PlayfieldTypeDep(name='TempX',
                           source_path=tmp_path / 'source' / 'Playfields' / 'TempX')
    dlg = SectorsFineDialog(units, deps=(dep,))
    group = dlg.tree.topLevelItem(dlg.tree.topLevelItemCount() - 1)
    assert group.childCount() == 1
    # cocher/decocher une dep : ne plante pas et ne pollue pas la selection
    group.child(0).setCheckState(0, Qt.CheckState.Unchecked)
    reqs = dlg.selections()
    assert reqs, "les unites du systeme Beta restent proposees"
    assert all(r.system == 'Beta' for r in reqs)
