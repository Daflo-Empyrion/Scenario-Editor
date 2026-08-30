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
Panneau "Controle avant validation" -- partage par l'assistant de creation de
bloc/item (gui/add_block_dialog.py) et utilisable par les flux de duplication.
Affiche EN DIRECT (a chaque frappe) les obligations de creation verifiees dans
les vrais fichiers du scenario (voir core/ecf/creation_check.py) : enregistre-
ment (Id/Name uniques, casse), recette (collision Templates), localisation,
arbre technologique -- avec code couleur et blocage visuel des erreurs.

Le panneau ne valide rien lui-meme : l'appelant interroge has_blocking_errors()
juste avant d'accepter le dialogue (double controle, le back-end re-verifie
toujours au moment de la validation reelle).
"""
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.i18n import t
from core.ecf.creation_check import (
    CreationContext, CreationIssue, check_creation, has_blocking,
    SEVERITE_ERREUR, SEVERITE_AVERTISSEMENT, SEVERITE_INFO,
)

_SEVERITE_STYLE = {
    SEVERITE_ERREUR: ("#c62828", "[ERREUR]"),
    SEVERITE_AVERTISSEMENT: ("#b26a00", "[ATTENTION]"),
    SEVERITE_INFO: ("#2a6fb0", "[INFO]"),
}


class CreationCheckPanel(QWidget):
    """Liste coloree des problemes detectes pour la saisie en cours.

    `get_values` retourne (kind, id_value, name_value, properties) au moment
    du rafraichissement ; `check_template_collision` / `check_techtree_hint`
    sont les memes interrupteurs que check_creation()."""

    def __init__(self, target_doc, sibling_ecf_files: Optional[List[object]],
                 working_root: Optional[object], get_values: Callable,
                 check_template_collision: bool = True,
                 check_techtree_hint: bool = False, parent=None):
        super().__init__(parent)
        self._target_doc = target_doc
        self._get_values = get_values
        self._check_template_collision = check_template_collision
        self._check_techtree_hint = check_techtree_hint
        self._context = CreationContext(sibling_ecf_files, working_root)
        self._issues: List[CreationIssue] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        self.title = QLabel(f"<b>{t('createcheck.title')}</b>")
        layout.addWidget(self.title)
        self.body = QLabel()
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setWordWrap(True)
        layout.addWidget(self.body)
        self.refresh()

    @property
    def context(self) -> CreationContext:
        return self._context

    @property
    def issues(self) -> List[CreationIssue]:
        return self._issues

    def has_blocking_errors(self) -> bool:
        return has_blocking(self._issues)

    def refresh(self) -> None:
        kind, id_value, name_value, properties = self._get_values()
        self._issues = check_creation(
            self._target_doc, self._context, kind, id_value, name_value,
            properties=properties,
            check_template_collision=self._check_template_collision,
            check_techtree_hint=self._check_techtree_hint)
        self._render()

    def _render(self) -> None:
        if not self._issues:
            self.body.setText(f"<span style='color:#1a7f37;'>✔ "
                              f"{t('createcheck.all_ok')}</span>")
            self.setStyleSheet("")
            return
        parts = []
        for issue in self._issues:
            color, tag = _SEVERITE_STYLE[issue.severite]
            message = issue.message.replace("&", "&amp;").replace("<", "&lt;")
            parts.append(f"<span style='color:{color};'><b>{tag}</b> "
                         f"<b>{issue.obligation} :</b> {message}</span>")
        self.body.setText("<br>".join(parts))
        if has_blocking(self._issues):
            self.setStyleSheet("background:#fdecea; border:1px solid #c62828; "
                               "border-radius:6px;")
        else:
            self.setStyleSheet("background:#fff7e0; border:1px solid #d9a800; "
                               "border-radius:6px;")
