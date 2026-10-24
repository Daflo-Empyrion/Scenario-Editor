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

"""Fenetre flottante de l'assistant (Q8) : conversation, contexte joint
visible, flux en direct, arret, cout du mois.

Rien n'est ecrit dans le document ici : cette fenetre ne fait que parler.
Les propositions de modification arrivent avec les adaptateurs de surface
(revue + application cote editeur, jamais depuis cette fenetre).
"""
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QTextBrowser,
                             QVBoxLayout)

from core import settings
from core.ai import budget, router
from core.ai.assistant import prompts
from core.ai.assistant.changeset import ChangeSet
from core.ai.assistant.context import TabContext
from core.ai.assistant.dsml import strip as strip_dsml
from core.ai.assistant.session import Session
from core.ai.assistant.surfaces.base import problem_text
from core.i18n import get_language, t
from gui.assistant_worker import AssistantWorker, SurfaceWorker
from gui.window_geometry import track

_CONTEXT_BLOCK = re.compile(r"\[Contexte joint :.*?\[/Contexte joint\]\n*",
                            re.S)


def payload_with_context(question: str, context: TabContext) -> str:
    """Question telle qu'elle part : contexte d'abord, question ensuite."""
    block = context.prompt_block()
    return f"{block}\n\n{question}" if block else question


def display_text(content: str) -> str:
    """Retire le bloc de contexte (genere par nous) et tout balisage d'appel
    natif d'un historique ecrit avant le repli DSML."""
    return strip_dsml(_CONTEXT_BLOCK.sub("", content or "")).strip()


class _PromptEdit(QPlainTextEdit):
    submitted = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and \
                event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class AssistantDialog(QDialog):
    def __init__(self, parent=None, history_path=None, surface_provider=None):
        super().__init__(parent)
        self.setWindowTitle(t("assistant.title"))
        self.setMinimumSize(680, 480)
        self.resize(760, 600)
        track(self, "assistant")

        self._history_path = history_path
        self._surface_provider = surface_provider
        self._worker = None
        self._active_surface = None
        self._stream_text = ""
        self.session = Session()
        self._entries = []

        layout = QVBoxLayout(self)

        head = QHBoxLayout()
        self.join_check = QCheckBox(t("assistant.join_tab"))
        self.join_check.setChecked(True)
        self.join_check.toggled.connect(self._refresh_context)
        head.addWidget(self.join_check)
        head.addStretch()
        self.link_label = QLabel("")
        head.addWidget(self.link_label)
        layout.addLayout(head)

        self.context_label = QLabel("")
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view, 1)

        self.input = _PromptEdit()
        self.input.setFixedHeight(76)
        self.input.setPlaceholderText(t("assistant.palette_placeholder"))
        self.input.submitted.connect(self._send)
        layout.addWidget(self.input)

        buttons = QHBoxLayout()
        self.btn_send = QPushButton(t("assistant.send"))
        self.btn_send.setObjectName("primaryButton")
        self.btn_send.clicked.connect(self._send)
        buttons.addWidget(self.btn_send)
        self.btn_stop = QPushButton(t("assistant.stop"))
        self.btn_stop.setObjectName("secondaryButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        buttons.addWidget(self.btn_stop)
        self.btn_clear = QPushButton(t("assistant.clear"))
        self.btn_clear.setObjectName("secondaryButton")
        self.btn_clear.clicked.connect(self._clear)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch()
        self.cost_label = QLabel("")
        buttons.addWidget(self.cost_label)
        layout.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self._load(history_path)
        self._refresh_cost()

    # -- etat -----------------------------------------------------------------

    def _load(self, path) -> None:
        self._history_path = path
        self.session = Session.load(path) if path else Session()
        self.session.system = prompts.system_prompt(
            get_language(), tone=settings.get_groq_style())
        self._entries = [
            (m.get("role"), display_text(m.get("content") or ""))
            for m in self.session.messages
            if m.get("role") in ("user", "assistant")
            and display_text(m.get("content") or "")]
        self._render()
        self._refresh_context()

    def set_history_path(self, path) -> None:
        """Change de scenario : sauve l'ancien historique, recharge le nouveau."""
        if path == self._history_path:
            return
        self._save()
        self._load(path)

    def set_surface_provider(self, provider) -> None:
        self._surface_provider = provider
        self._refresh_context()

    def _surface(self):
        if not callable(self._surface_provider):
            return None
        try:
            return self._surface_provider()
        except Exception:  # noqa: BLE001 -- surface indisponible = chat simple
            return None

    def ask(self, question: str) -> None:
        self.input.setPlainText(question or "")
        self.input.setFocus()
        if (question or "").strip():
            self._send()

    # -- contexte -------------------------------------------------------------

    def _context(self) -> TabContext:
        if not self.join_check.isChecked():
            return TabContext("", "")
        surface = self._surface()
        if surface is None:
            return TabContext("", "")
        try:
            context = surface.context()
        except Exception:  # noqa: BLE001 -- jamais bloquer l'envoi
            return TabContext("", "")
        return context if isinstance(context, TabContext) else TabContext("", "")

    def _refresh_context(self) -> None:
        context = self._context()
        if not context.text:
            self.context_label.setText(t("assistant.context_none"))
            return
        text = t("assistant.context_summary", tab=context.label or "?",
                 chars=context.chars)
        if context.truncated:
            text += " · " + t("assistant.context_truncated")
        if context.redacted:
            text += " · " + t("assistant.context_redacted",
                              count=context.redacted)
        self.context_label.setText(text)

    # -- affichage ------------------------------------------------------------

    def _label(self, role: str) -> str:
        return t("assistant.you") if role == "user" else t("assistant.model")

    def _markdown(self) -> str:
        blocks = [f"**{self._label(role)}**\n\n{text}"
                  for role, text in self._entries]
        return "\n\n---\n\n".join(blocks)

    def _plain(self) -> str:
        parts = [f"{self._label(role)} :\n{text}"
                 for role, text in self._entries]
        if self._stream_text:
            parts.append(f"{self._label('assistant')} :\n{self._stream_text}")
        return "\n\n".join(parts)

    def _render(self) -> None:
        if not self._entries:
            self.view.setMarkdown("")
            return
        self.view.setMarkdown(self._markdown())
        self._scroll_bottom()

    def _scroll_bottom(self) -> None:
        self.view.moveCursor(QTextCursor.MoveOperation.End)

    # -- envoi ----------------------------------------------------------------

    def _send(self) -> None:
        if self._worker is not None:
            return
        question = self.input.toPlainText().strip()
        if not question:
            return
        if not router.configured():
            self._set_status(t("assistant.no_provider"), error=True)
            return
        self._refresh_context()
        context = self._context()
        surface = self._surface()
        action = surface.action() if surface is not None else None
        self.session.add_user(payload_with_context(question, context))
        self._entries.append(("user", question))
        self._stream_text = ""
        self.input.clear()
        self._set_status("")

        if action is not None and action.needs_tools:
            # Surface outillée (ECF, CSV) : outils + ChangeSet, reponse
            # complete (le SSE ne transporte pas les appels d'outils), donc
            # pas d'arret en cours d'appel.
            self._active_surface = surface
            self._set_busy(True, stoppable=False)
            self._worker = SurfaceWorker(self.session, action,
                                         surface.registry(), parent=self)
            self._worker.done.connect(self._on_surface_done)
            self._worker.failed.connect(self._on_failed)
            self._worker.start()
            return

        self._set_busy(True)
        history, truncated = self.session.fit()
        messages = ([{"role": "system", "content": self.session.system}]
                    + history)
        self._worker = AssistantWorker(messages, parent=self)
        self._worker.delta.connect(self._on_delta)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        if truncated:
            self._set_status(t("assistant.context_truncated"))

    def _stop(self) -> None:
        if self._worker is not None:
            self.btn_stop.setEnabled(False)
            stop = getattr(self._worker, "stop", None)
            if stop is not None:
                stop()

    def _on_delta(self, delta: str) -> None:
        self._stream_text += delta
        self.view.setPlainText(self._plain())
        self._scroll_bottom()

    def _on_done(self, text: str, link: str, streamed: bool) -> None:
        self._worker = None
        self._stream_text = ""
        if text:
            self.session.add_assistant(text)
            self._entries.append(("assistant", text))
        self._set_busy(False)
        self._render()
        self.link_label.setText(
            t("assistant.link_label", link=link) if link else "")
        self._refresh_cost()
        self._save()

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self._active_surface = None
        if self._stream_text:
            self.session.add_assistant(self._stream_text)
            self._entries.append(("assistant", self._stream_text))
            self._stream_text = ""
            self._render()
        self._set_busy(False)
        self._set_status(t("assistant.error", message=message), error=True)
        if self._entries:
            self._save()

    def _on_surface_done(self, answer) -> None:
        """Reponse complete (outils + ChangeSet) : affichee puis, si elle est
        valide, soumise a la revue -- jamais appliquee ici."""
        self._worker = None
        surface = self._active_surface
        self._active_surface = None
        text = (answer.text or "").strip()
        display = text or (answer.changeset.summary if answer.changeset else "")
        if display:
            self._entries.append(("assistant", display))
        self._set_busy(False)
        self._render()
        self.link_label.setText(
            t("assistant.link_label", link=answer.link) if answer.link else "")
        self._refresh_cost()
        self._save()
        if answer.problems:
            message = problem_text(answer.problems[0])
            if "boucle_outils_interrompue" in answer.problems \
                    and answer.tool_log:
                message += "\n" + ", ".join(answer.tool_log[-5:])
            self._set_status(message, error=True)
        if answer.changeset is None:
            return
        if answer.changeset_problems:
            self._set_status(
                problem_text(answer.changeset_problems[0]), error=True)
            return
        if surface is not None and answer.changeset.changes:
            from gui.assistant_review_dialog import review_changeset
            changeset = answer.changeset
            expand = getattr(surface, "expand", None)
            if callable(expand):
                try:
                    changeset = expand(changeset) or changeset
                except Exception:  # noqa: BLE001 -- la revue reste possible
                    changeset = answer.changeset
            kinds = getattr(surface, "kinds", None)
            dropped = 0
            if kinds is not None:
                kept = [c for c in changeset.changes if c.kind in kinds]
                dropped = len(changeset.changes) - len(kept)
                if dropped:
                    changeset = ChangeSet(
                        changes=kept,
                        summary="\n\n".join(part for part in (
                            changeset.summary,
                            t("assistant.review_dropped", count=dropped))
                            if part.strip()),
                        report=changeset.report)
            if not changeset.changes:
                self._set_status(
                    t("assistant.review_dropped", count=dropped) if dropped
                    else t("assistant.unsupported"), error=True)
                return
            review_changeset(changeset, surface.apply, self)

    def _clear(self) -> None:
        self.session.clear()
        self._entries = []
        self._stream_text = ""
        self.link_label.setText("")
        self._render()
        self._set_status(t("assistant.clear_done"))
        self._save()

    # -- divers ---------------------------------------------------------------

    def _set_busy(self, busy: bool, stoppable: bool = True) -> None:
        self.btn_send.setEnabled(not busy)
        self.btn_stop.setEnabled(busy and stoppable)
        if busy:
            self._set_status(t("assistant.thinking"))

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color: #d9534f;" if error else "")

    def _refresh_cost(self) -> None:
        if not settings.get_ai_paid_enabled():
            self.cost_label.setText("")
            return
        state = budget.summary()
        self.cost_label.setText(t("assistant.cost_label",
                                  spent=f"{state['total']:.4f}",
                                  cap=f"{state['cap']:.2f}"))

    def _save(self) -> None:
        if not self._history_path:
            return
        try:
            self.session.save(self._history_path)
        except OSError:
            pass  # historique non ecrit : jamais bloquant pour la conversation

    def closeEvent(self, event):
        if self._worker is not None:
            # SurfaceWorker (reponse complete) n'a pas d'arret : on ne bloque
            # pas, il finira dans une fenetre cachee.
            stop = getattr(self._worker, "stop", None)
            if stop is not None:
                stop()
                self._worker.wait(1500)
        self._save()
        super().closeEvent(event)
