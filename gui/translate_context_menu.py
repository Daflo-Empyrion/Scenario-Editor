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
Traduction au clic droit, generique pour n'importe quel QLineEdit/QTextEdit --
avant ce module, chaque editeur (ECF, YAML, CSV, TXT) reimplementait sa
propre version de ce menu contextuel. Les dialogues plus recents (assistant
de mission PDA, creation de bloc...) utilisaient de simples champs de texte
sans ce menu -- ce module comble cet ecart avec UNE SEULE fonction a appeler
par champ, plutot que de dupliquer la logique une fois de plus.

Agit sur la selection si elle existe, sinon sur tout le contenu du champ.
Reutilise TranslationResultDialog (fenetre de revue avant remplacement,
meme comportement que partout ailleurs dans l'application)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QTextEdit, QMessageBox, QMenu, QDialog

from core.i18n import t
from core import translation


def install_translate_context_menu(field) -> None:
    """A appeler une fois sur un QLineEdit ou QTextEdit pour lui ajouter
    'Traduire vers...' a son clic droit, en plus du menu standard
    (couper/copier/coller). Idempotent au sens ou chaque appel ajoute son
    propre gestionnaire -- ne pas appeler deux fois sur le meme champ."""
    is_line_edit = isinstance(field, QLineEdit)
    if not is_line_edit and not isinstance(field, QTextEdit):
        return

    def handler(pos, field=field, is_line_edit=is_line_edit):
        menu = field.createStandardContextMenu()
        if is_line_edit:
            selected = field.selectedText()
            full_text = field.text()
        else:
            selected = field.textCursor().selectedText().replace('\u2029', '\n')
            full_text = field.toPlainText()
        text_to_translate = selected if selected.strip() else full_text
        if not text_to_translate.strip():
            menu.exec(field.mapToGlobal(pos))
            return

        menu.addSeparator()
        translate_menu = menu.addMenu(t("ctx.translate_to"))
        lang_actions = {}
        for label, code in translation.COMMON_LANGUAGES:
            a = translate_menu.addAction(label)
            lang_actions[a] = code

        chosen = menu.exec(field.mapToGlobal(pos))
        if chosen not in lang_actions:
            return
        _do_translate(field, is_line_edit, bool(selected.strip()), text_to_translate, lang_actions[chosen])

    field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    field.customContextMenuRequested.connect(handler)


def _do_translate(field, is_line_edit: bool, was_selection: bool, text: str, target_lang: str) -> None:
    if not translation.is_available():
        QMessageBox.warning(field, t("trans.unavailable_title"),
                             t("trans.unavailable_msg", error=translation.get_import_error()))
        return
    try:
        translated = translation.translate_text(text, target=target_lang)
    except Exception as e:
        QMessageBox.critical(field, t("trans.error_title"), t("trans.error_msg", error=e))
        return

    from gui.csv_edit_widget import TranslationResultDialog
    dialog = TranslationResultDialog(text, translated, field)
    if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.accepted_replace:
        return
    result = dialog.result_text()

    if is_line_edit:
        if was_selection:
            field.insert(result)  # remplace la selection active
        else:
            field.setText(result)
    else:
        if was_selection:
            cursor = field.textCursor()
            cursor.insertText(result)
        else:
            field.setPlainText(result)
