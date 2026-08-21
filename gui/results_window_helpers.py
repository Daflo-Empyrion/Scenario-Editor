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
Petit utilitaire partage par les fenetres de resultats (verifications,
comparaison de scenario...) -- export vers un fichier texte, utilise de la
meme facon partout plutot que duplique dans chaque dialogue.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox

from core.i18n import t


def export_text_to_file(parent: QWidget, default_filename: str, content: str,
                         title_key: str = "results_export.title",
                         done_title_key: str = "results_export.done_title",
                         done_msg_key: str = "results_export.done_msg") -> Optional[Path]:
    """Ouvre un selecteur "Enregistrer sous", ecrit `content` dedans en UTF-8, et
    confirme par un message. Retourne le chemin choisi, ou None si annule ou en
    cas d'erreur d'ecriture. Reutilise par toutes les fenetres de resultats
    (verifications, comparaison de scenario) pour un comportement identique
    partout plutot que duplique dans chaque dialogue."""
    path_str, _ = QFileDialog.getSaveFileName(parent, t(title_key), default_filename, "Texte (*.txt)")
    if not path_str:
        return None
    path = Path(path_str)
    try:
        path.write_text(content, encoding='utf-8')
    except OSError as e:
        QMessageBox.critical(parent, t("err.title"), f"{t('results_export.error')} :\n{e}")
        return None
    QMessageBox.information(parent, t(done_title_key), t(done_msg_key, path=str(path)))
    return path
