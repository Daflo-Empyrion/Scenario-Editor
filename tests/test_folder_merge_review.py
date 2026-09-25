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

"""Revision de fusion de dossier (demande 25/09/2026) : plan coche fichier
par fichier (les non-ECF etaient copies en aveugle) + DEPENDANCES
Sectors -> Playfields -> POIs proposees avant validation."""
import types

import pytest

from core.merge_dependencies import (STATUS_ECF, STATUS_NEW,
                                     STATUS_OVERWRITE, plan_folder_merge)
from core.workspace import merge_folder_into_working


@pytest.fixture
def trees(tmp_path):
    """Scenario source avec Sectors.yaml referencant le template TempX
    (playfield_static avec POI R2XBase) + copie de travail SANS TempX."""
    source = tmp_path / "source"
    working = tmp_path / "working"
    (source / "Sectors").mkdir(parents=True)
    (source / "Playfields" / "TempX").mkdir(parents=True)
    (source / "Prefabs").mkdir(parents=True)
    (working / "Content" / "Configuration").mkdir(parents=True)
    (working / "Sectors").mkdir(parents=True)
    (working / "Sectors" / "Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Alpha\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', Ancienne, OldTemplate, '']\n",
        encoding="utf-8")
    (working / "Prefabs").mkdir(parents=True)
    (source / "Content" / "Configuration").mkdir(parents=True)
    (source / "Content" / "Configuration" / "BlocksConfig.ecf").write_text(
        "{ Block Id: 412, Name: HullTest\n  Volume: 80\n}\n", encoding="utf-8")
    (source / "Sectors" / "Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Alpha\n"
        "    Sectors:\n"
        "      - Coordinates: [0, 0, 0]\n"
        "        Playfields:\n"
        "          - ['0,0,0', MaPlanete, TempX, '']\n",
        encoding="utf-8")
    (source / "Playfields" / "TempX" / "playfield_static.yaml").write_text(
        "PlayfieldType: Planet\n"
        "POIs:\n"
        "  - GroupName: R2XBase\n",
        encoding="utf-8")
    (source / "Playfields" / "TempX" / "playfield_dynamic.yaml").write_text(
        "PlayfieldType: Planet\n", encoding="utf-8")
    (source / "Prefabs" / "R2XBase.epb").write_bytes(b"\x00EPB")
    (source / "Prefabs" / "DejaLa.epb").write_bytes(b"\x00EPB")
    (working / "Prefabs" / "DejaLa.epb").write_bytes(b"\x00EPB")
    (working / "Content" / "Configuration" / "BlocksConfig.ecf").write_text(
        "{ Block Id: 412, Name: HullTest\n}\n", encoding="utf-8")
    return source, working


def test_plan_statuses_and_dependencies(trees):
    source, working = trees
    plan = plan_folder_merge(source / "Sectors", source, working)
    # Sectors.yaml existe des deux cotes -> REMPLACEMENT (decoche)
    sectors = next(p for p in plan.files
                   if p.rel.endswith("Sectors.yaml"))
    assert sectors.status == STATUS_OVERWRITE and sectors.checked is False
    assert sectors.diff_summary.startswith("+")
    # dependances : dossier TempX (2 fichiers) + POI manquant uniquement
    playfield_files = [d for d in plan.dependencies
                       if d.reason_i18n == "mergeplan.dep_playfield"]
    pois = [d for d in plan.dependencies
            if d.reason_i18n == "mergeplan.dep_poi"]
    assert {d.dest.name for d in playfield_files} == {
        "playfield_static.yaml", "playfield_dynamic.yaml"}
    assert [d.dest.name for d in pois] == ["R2XBase.epb"]
    assert all(not d.dest.exists() for d in plan.dependencies)


def test_plan_new_and_ecf_statuses(trees):
    source, working = trees
    plan = plan_folder_merge(source / "Content", source, working)
    ecf = next(p for p in plan.files if p.rel.endswith(".ecf"))
    assert ecf.status == STATUS_ECF            # existe des deux cotes


def test_merge_only_files_respects_selection(trees):
    """only_files : la fusion n'ecrit QUE les fichiers valides dans la
    fenetre de revision (les remplacements decoches ne passent pas)."""
    source, working = trees
    plan = plan_folder_merge(source / "Sectors", source, working)
    sectors = next(p for p in plan.files if p.rel.endswith("Sectors.yaml"))
    before = (working / "Sectors" / "Sectors.yaml").read_text(
        encoding="utf-8")
    merge_folder_into_working(
        types.SimpleNamespace(working_root=working), source / "Sectors",
        source, "source", only_files=set())     # selection vide
    assert (working / "Sectors" / "Sectors.yaml").read_text(
        encoding="utf-8") == before             # rien n'a ete ecrase


def test_dialog_construction_and_selection(qapp, trees, monkeypatch):
    """Regle projet : construction testee ; la selection retourne les bons
    chemins source et les dependances cochees."""
    from gui.folder_merge_review_dialog import FolderMergeReviewDialog
    source, working = trees
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working))
    dlg = FolderMergeReviewDialog(main, source / "Sectors", source,
                                  "source", parent=None)
    assert dlg.tree.topLevelItemCount() >= 2     # Sectors.yaml + dependances
    # securite : le REMPLACEMENT du Sectors.yaml est decoche par defaut
    assert dlg.selected_merge_files() == []
    from PyQt6.QtCore import Qt
    from core.merge_dependencies import FilePlan
    sector_item = None
    n_units = 0
    for i in range(dlg.tree.topLevelItemCount()):
        it = dlg.tree.topLevelItem(i)
        data = it.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, FilePlan) and data.rel.endswith("Sectors.yaml"):
            sector_item = it
        elif hasattr(data, "kind"):
            n_units += 1
    assert sector_item is not None and n_units >= 1  # tranche 2 active
    assert sector_item.checkState(0) == Qt.CheckState.Unchecked
    sector_item.setCheckState(0, Qt.CheckState.Checked)
    sel_merge = dlg.selected_merge_files()
    assert len(sel_merge) == 1 and sel_merge[0].name == "Sectors.yaml"
    sel_deps = dlg.selected_dependencies()
    assert {d.dest.name for d in sel_deps} == {
        "playfield_static.yaml", "playfield_dynamic.yaml", "R2XBase.epb"}
    # tout decocher -> plus rien a fusionner
    dlg._set_all_checks(False)
    assert dlg.selected_merge_files() == [] and dlg.selected_dependencies() == []
