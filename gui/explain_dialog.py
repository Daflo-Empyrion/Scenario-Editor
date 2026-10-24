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
Popup « Expliquer avec IA » (clic droit dans les editeurs ECF, YAML, CSV).

Affiche d'abord les FAITS (core/explain.py : glossaire, valeur vanille,
tendance observee, valeurs recommandees), puis la reponse du moteur IA deja
configure dans l'application -- core.ai.router, exactement le meme chemin que
l'assistant et la traduction (aucun LLM local, aucun appel direct a un
fournisseur). L'appel part en arriere-plan : l'interface ne gele jamais.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTextBrowser, QVBoxLayout)

from core.explain import ExplainContext
from core.i18n import get_language, t
from gui.assistant_worker import AssistantWorker


class ExplainDialog(QDialog):
    """Fenetre non modale : on peut continuer a travailler pendant l'appel."""

    def __init__(self, ctx: ExplainContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._worker = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(t("explain.title"))
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        title = QLabel(ctx.title)
        title.setWordWrap(True)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        self.ctx_view = QTextBrowser()
        self.ctx_view.setPlainText("\n".join(ctx.context_lines()))
        self.ctx_view.setMaximumHeight(170)
        layout.addWidget(self.ctx_view)

        self.ai_view = QTextBrowser()
        self.ai_view.setOpenExternalLinks(True)
        layout.addWidget(self.ai_view, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.btn_again = QPushButton(t("explain.ask_again"))
        self.btn_again.clicked.connect(self._ask)
        btn_close = QPushButton(t("btn.close"))
        btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_again)
        buttons.addStretch(1)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        QTimer.singleShot(0, self._ask)

    def _ask(self) -> None:
        if self._worker is not None:
            return
        self.ai_view.clear()
        self.status.setText(t("explain.waiting"))
        self.btn_again.setEnabled(False)
        self._worker = AssistantWorker(self._ctx.messages(get_language()),
                                       min_class="", purpose="explain", parent=self)
        self._worker.delta.connect(self._on_delta)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_delta(self, text: str) -> None:
        self.ai_view.moveCursor(QTextCursor.MoveOperation.End)
        self.ai_view.insertPlainText(text)

    def _on_done(self, text: str, link: str, streamed: bool) -> None:
        self.ai_view.setMarkdown(text)
        self.status.setText(t("explain.answered_by", link=link) if link else "")
        self._finish()

    def _on_failed(self, error: str) -> None:
        self.status.setText(t("explain.failed", error=error))
        self._finish()

    def _finish(self) -> None:
        self._worker = None
        self.btn_again.setEnabled(True)

    def closeEvent(self, event):
        # Le thread ne doit jamais etre detruit en pleine requete (crash Qt) :
        # on le detache du dialogue et il se supprime lui-meme a la fin.
        worker = self._worker
        if worker is not None:
            self._worker = None
            worker.stop()
            worker.setParent(None)
            worker.finished.connect(worker.deleteLater)
        super().closeEvent(event)


def open_ai_explanation(parent, ctx: ExplainContext) -> ExplainDialog:
    """Ouvre (ou remplace) le popup d'explication attache a `parent`."""
    old = getattr(parent, "_explain_dialog", None)
    if old is not None:
        old.close()
    dialog = ExplainDialog(ctx, parent)
    parent._explain_dialog = dialog
    dialog.show()
    return dialog
