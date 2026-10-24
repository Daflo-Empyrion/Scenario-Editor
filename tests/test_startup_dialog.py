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

"""Retrait multiple dans la liste des projets recents (vecu 24/10/2026) :
plusieurs clics sur « Retirer de la liste » ne gardaient que le DERNIER
projet — tous les autres reapparaissaient au lancement suivant. Le
dialogue collecte desormais toutes les suppressions et le gestionnaire
les applique toutes."""

from pathlib import Path

from core import project_store
from core.project_store import ProjectRecord, load_recent_projects
from gui.startup_dialog import StartupDialog


def _records(base):
    def rec(name):
        return ProjectRecord(source_a=str(base / name),
                             working=str(base / name / "working"),
                             label=name)
    return rec("Alpha"), rec("Beta"), rec("Gamma")


def test_dialog_collects_every_removal(qapp):
    a, b, c = _records(Path("projets"))
    dlg = StartupDialog([a, b, c])
    dlg.list_widget.setCurrentRow(2)      # Gamma
    dlg._on_remove()
    dlg.list_widget.setCurrentRow(0)      # Alpha
    dlg._on_remove()
    assert dlg.list_widget.count() == 1
    assert dlg.list_widget.item(0).data(1000) is b
    assert {r.working for r in dlg.removed_projects} == {a.working, c.working}
    dlg.reject()


def test_multiple_removals_persist(qapp, tmp_path, monkeypatch):
    a, b, c = _records(tmp_path)
    monkeypatch.setattr(project_store, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(project_store, "CONFIG_FILE",
                        tmp_path / "cfg" / "projets_recents.json")
    for record in (a, b, c):
        project_store.add_recent_project(record)

    dlg = StartupDialog(project_store.load_recent_projects())
    dlg.list_widget.setCurrentRow(2)      # Alpha (ajoute en dernier -> rang 0 ?)
    dlg._on_remove()
    # on retire tout ce qui reste, un par un, comme l'utilisateur
    while dlg.list_widget.count():
        dlg.list_widget.setCurrentRow(0)
        dlg._on_remove()
    assert dlg.list_widget.count() == 0

    # meme chemin que show_startup_dialog : suppression AVANT fermeture
    for record in dlg.removed_projects:
        project_store.remove_project(record.working)
    assert load_recent_projects() == []
    dlg.reject()          # ne JAMAIS appeler exec() dans un test : boucle modale
