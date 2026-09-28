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

"""Persistance du scenario B dans les projets recents (vecu 26/09/2026) :
changer (ou retirer) le scenario B ne mettait a jour que la memoire --
au lancement suivant, le projet se rouvrait avec l'ANCIEN scenario B de
la creation. Desormais le gestionnaire re-ecrit la fiche du projet."""
import pytest
from PyQt6.QtWidgets import QFileDialog

from core import project_store
from core.project_store import ProjectRecord, load_recent_projects


@pytest.fixture
def workspaces(tmp_path):
    """Scenario A + copie de travail + deux scenarios B (ancien/nouveau),
    chacun avec un fichier pour que scan_scenario les inventorie."""
    def make(name):
        d = tmp_path / name
        (d / "Content" / "Configuration").mkdir(parents=True)
        (d / "Content" / "Configuration" / "BlocksConfig.ecf").write_text(
            "{ Block Id: 1, Name: " + name + "\r\n}\r\n", encoding="utf-8",
            newline="")
        return d
    return make("A"), make("B_old"), make("B_new"), make("working")


def _open_window(qapp, source_a, working, source_b_old, monkeypatch, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)
    # projets_recents.json ISOLE du vrai dossier utilisateur
    monkeypatch.setattr(project_store, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(project_store, "CONFIG_FILE",
                        tmp_path / "cfg" / "projets_recents.json")
    window = MainWindow()
    window.workspace = Workspace(
        source_a=scan_scenario(source_a), source_a_root=source_a,
        working=scan_scenario(working), working_root=working,
        source_b=scan_scenario(source_b_old), source_b_root=source_b_old)
    project_store.add_recent_project(ProjectRecord(
        source_a=str(source_a), working=str(working),
        source_b=str(source_b_old)))
    return window


def test_changing_scenario_b_persists(qapp, tmp_path, monkeypatch, workspaces):
    source_a, b_old, b_new, working = workspaces
    window = _open_window(qapp, source_a, working, b_old, monkeypatch,
                          tmp_path)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(b_new)))
    monkeypatch.setattr("gui.main_window.ask_yes_no", lambda *a, **k: True)

    window._open_or_change_scenario_b()

    rec = next(r for r in load_recent_projects()
               if r.working == str(working))
    assert rec.source_b == str(b_new)


def test_removing_scenario_b_persists_none(qapp, tmp_path, monkeypatch,
                                           workspaces):
    source_a, b_old, b_new, working = workspaces
    window = _open_window(qapp, source_a, working, b_old, monkeypatch,
                          tmp_path)
    monkeypatch.setattr("gui.main_window.ask_yes_no", lambda *a, **k: True)

    window._remove_scenario_b()

    rec = next(r for r in load_recent_projects()
               if r.working == str(working))
    assert rec.source_b is None
