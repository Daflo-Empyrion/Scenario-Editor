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

"""Tests de la sonde d'ecriture de la destination (gui/new_project_dialog.py),
ajoutee apres l'audit du 30/08/2026 : sans elle, une destination non
inscriptible (permissions Windows, parent inexistant, parent qui est un
fichier) n'echouait qu'APRES la copie -- plusieurs minutes perdues sur un
gros scenario et une copie partielle laissee sur disque."""
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

from gui.new_project_dialog import NewProjectDialog


@pytest.fixture
def source_dir(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    return source


def _make_dialog(source_dir) -> NewProjectDialog:
    dlg = NewProjectDialog()
    dlg.edit_a.setText(str(source_dir))
    return dlg


def test_destination_probe_passes_and_cleans_up(qapp, source_dir, tmp_path):
    """Destination creable : aucune erreur, et le dossier feuille sonde est
    RETIRE pour que create_working_copy() puisse le recreer (il refuse un
    dossier deja existant)."""
    dlg = _make_dialog(source_dir)
    dest = tmp_path / "nouveau" / "dossier" / "copie"
    assert dlg._destination_write_error(dest) is None
    assert not dest.exists()          # la sonde nettoie la feuille...
    assert (tmp_path / "nouveau").exists()  # ...mais garde les parents crees


def test_destination_probe_fails_when_parent_is_a_file(qapp, source_dir, tmp_path):
    """Un composant du chemin est un fichier existant : la creation du dossier
    echoue (FileExistsError sous Windows, NotADirectoryError sous Linux) --
    doit etre signale, pas laisse exploser pendant la copie."""
    dlg = _make_dialog(source_dir)
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("pas un dossier", encoding="utf-8")
    dest = blocker / "sub" / "copie"
    error = dlg._destination_write_error(dest)
    assert error is not None
    assert "blocker.txt" in error or "dest" in error or error  # message traduit non vide


def test_destination_probe_fails_on_readonly_dir(qapp, source_dir, tmp_path, monkeypatch):
    """Ecriture impossible dans le parent : la sonde retourne le message
    traduit. Simule en faisant echouer mkdir (l'attribut lecture seule Windows
    n'empeche PAS d'ecrire dans un dossier, on ne peut donc pas s'appuyer sur
    lui pour un test fiable multi-plate-forme)."""
    dlg = _make_dialog(source_dir)
    dest = tmp_path / "verrouille" / "copie"

    def _boom(*a, **k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "mkdir", _boom)
    error = dlg._destination_write_error(dest)
    assert error is not None
    assert "Permission denied" in error


def test_accept_rejects_unwritable_destination(qapp, source_dir, tmp_path, monkeypatch):
    """Parcours complet du dialogue : une destination non inscriptible declenche
    l'avertissement et REFUSE d'accepter (pas de dest_path)."""
    dlg = _make_dialog(source_dir)
    blocker = tmp_path / "fichier.txt"
    blocker.write_text("", encoding="utf-8")
    dlg.edit_dest.setText(str(blocker / "sub" / "copie"))

    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok)
    dlg._on_accept()

    assert len(warnings) == 1
    assert dlg.dest_path is None  # jamais renseigne si la validation echoue


def test_accept_accepts_writable_destination(qapp, source_dir, tmp_path, monkeypatch):
    dlg = _make_dialog(source_dir)
    dlg.edit_dest.setText(str(tmp_path / "bonne" / "copie"))

    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: pytest.fail("aucun avertissement attendu"))
    dlg._on_accept()

    assert dlg.dest_path == tmp_path / "bonne" / "copie"
