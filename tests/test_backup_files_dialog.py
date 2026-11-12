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

"""Dialogue « Sauvegardes automatiques » : liste par type, restauration vers
un fichier choisi (l'actuel est sauvegarde), menage."""
import os
import time
from pathlib import Path


def _bak(folder: Path, name: str, content: str = "x", age_days: float = 1) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(content, encoding="utf-8")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))
    return path


def _dialog(tmp_path, monkeypatch):
    import gui.backup_files_dialog as M
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    return M, M.BackupFilesDialog(None, root=tmp_path)


def test_lists_backups_grouped_by_kind(qapp, tmp_path, monkeypatch):
    _bak(tmp_path / "corpus", "Localization-20261112-121530.csv.bak")
    _bak(tmp_path / "corpus", "PDA-20261112-121531.csv.bak")
    _bak(tmp_path / "difficulty", "Desert-20261112-121532.yaml.bak")
    M, dialog = _dialog(tmp_path, monkeypatch)
    assert dialog.tree.topLevelItemCount() == 2
    kinds = [dialog.tree.topLevelItem(i).text(0)
             for i in range(dialog.tree.topLevelItemCount())]
    assert kinds == ["corpus", "difficulty"]
    corpus = dialog.tree.topLevelItem(0)
    assert corpus.childCount() == 2
    assert corpus.child(0).text(2)                 # taille affichee


def test_restore_writes_the_chosen_destination(qapp, tmp_path, monkeypatch):
    backup = _bak(tmp_path / "corpus",
                  "Localization-20261112-121530.csv.bak",
                  content="ancienne version")
    M, dialog = _dialog(tmp_path, monkeypatch)
    target = tmp_path / "scenario" / "Localization.csv"
    target.parent.mkdir()
    target.write_text("actuelle", encoding="utf-8")
    monkeypatch.setattr(M.QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(target), ""))
    monkeypatch.setattr(M, "ask_yes_no", lambda *a, **k: True)
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0).child(0))
    dialog._restore()
    assert target.read_text(encoding="utf-8") == "ancienne version"
    assert backup.is_file()                       # la sauvegarde reste en place


def test_restore_cancelled_writes_nothing(qapp, tmp_path, monkeypatch):
    _bak(tmp_path / "corpus", "PDA-20261112-121530.csv.bak", content="vieux")
    M, dialog = _dialog(tmp_path, monkeypatch)
    target = tmp_path / "PDA.csv"
    target.write_text("actuelle", encoding="utf-8")
    monkeypatch.setattr(M.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0).child(0))
    dialog._restore()
    assert target.read_text(encoding="utf-8") == "actuelle"


def test_restore_needs_a_selected_file(qapp, tmp_path, monkeypatch):
    _bak(tmp_path / "corpus", "PDA-20261112-121530.csv.bak")
    M, dialog = _dialog(tmp_path, monkeypatch)
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))   # le type, pas un fichier
    assert dialog._selected_file() is None
    assert not dialog.btn_restore.isEnabled()
