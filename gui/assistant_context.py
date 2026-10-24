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

"""Contexte de l'onglet actif, cote interface.

Contrat des surfaces (etape suivante) : un widget d'edition peut exposer
`assistant_context()` renvoyant (etiquette, texte) -- le bloc, le playfield,
la selection CSV pertinents pour la question. A defaut, on joint le texte
selectionne des editeurs de texte de l'onglet : mieux que rien, et jamais de
document entier envoye en douce (le plafond et le masquage sont dans
core/ai/assistant/context.py).
"""
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from core.ai.assistant.context import (DEFAULT_CONTEXT_CHARS, TabContext,
                                       build)


def selected_text(widget) -> str:
    if widget is None:
        return ""
    for editor in widget.findChildren(QWidget):
        if isinstance(editor, (QPlainTextEdit, QTextEdit)):
            cursor = editor.textCursor()
            if cursor.hasSelection():
                # U+2029 = separateur de paragraphe de Qt.
                return cursor.selectedText().replace("\u2029", "\n")
    return ""


def tab_context(widget, title: str,
                max_chars: int = DEFAULT_CONTEXT_CHARS) -> TabContext:
    label, text = title or "", ""
    if widget is not None:
        getter = getattr(widget, "assistant_context", None)
        if callable(getter):
            try:
                got = getter()
            except Exception:  # noqa: BLE001 -- un adaptateur fautif ne bloque pas
                got = None
            if isinstance(got, tuple) and len(got) == 2:
                label = str(got[0] or label)
                text = str(got[1] or "")
        if not text:
            text = selected_text(widget)
    return build(label, text, max_chars)
