"""
Tests du module generique de traduction au clic droit
(gui/translate_context_menu.py) -- reutilisable sur n'importe quel
QLineEdit/QTextEdit, comble l'ecart laisse par les dialogues plus recents
(assistant de mission PDA, creation de bloc...) qui n'avaient pas ce menu
contrairement aux editeurs ECF/YAML/CSV/TXT plus anciens.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QTextEdit, QMenu, QDialog

from gui.translate_context_menu import install_translate_context_menu


def test_install_sets_custom_context_menu_policy(qapp):
    field = QLineEdit("Hello")
    install_translate_context_menu(field)
    assert field.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_install_connects_signal(qapp):
    field = QLineEdit("Hello")
    install_translate_context_menu(field)
    assert field.receivers(field.customContextMenuRequested) > 0


def test_works_on_line_edit_and_text_edit(qapp):
    """Ne doit jamais lever d'exception, meme sur un champ vide -- la
    fonction gere silencieusement ce cas (voir docstring)."""
    line_edit = QLineEdit()
    text_edit = QTextEdit()
    install_translate_context_menu(line_edit)
    install_translate_context_menu(text_edit)


def test_ignores_unsupported_widget_types(qapp):
    from PyQt6.QtWidgets import QLabel
    label = QLabel("Not a text field")
    install_translate_context_menu(label)  # ne doit pas lever d'exception


def test_full_translate_flow_replaces_line_edit_content(qapp, monkeypatch):
    from gui.csv_edit_widget import TranslationResultDialog
    from core import translation

    field = QLineEdit("Hello world")
    install_translate_context_menu(field)
    field.selectAll()

    def fake_menu_exec(self, *args, **kwargs):
        for action in self.actions():
            if action.menu():
                for sub_action in action.menu().actions():
                    return sub_action
        return None
    monkeypatch.setattr(QMenu, "exec", fake_menu_exec)

    monkeypatch.setattr(translation, "is_available", lambda: True)
    monkeypatch.setattr(translation, "translate_text", lambda text, target: "Texte traduit")

    def fake_dialog_exec(self):
        self.accepted_replace = True
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(TranslationResultDialog, "exec", fake_dialog_exec)

    field.customContextMenuRequested.emit(field.rect().center())
    assert field.text() == "Texte traduit"


def test_declining_dialog_leaves_field_unchanged(qapp, monkeypatch):
    from gui.csv_edit_widget import TranslationResultDialog
    from core import translation

    field = QLineEdit("Hello world")
    install_translate_context_menu(field)
    field.selectAll()

    def fake_menu_exec(self, *args, **kwargs):
        for action in self.actions():
            if action.menu():
                for sub_action in action.menu().actions():
                    return sub_action
        return None
    monkeypatch.setattr(QMenu, "exec", fake_menu_exec)
    monkeypatch.setattr(translation, "is_available", lambda: True)
    monkeypatch.setattr(translation, "translate_text", lambda text, target: "Texte traduit")
    monkeypatch.setattr(TranslationResultDialog, "exec",
                         lambda self: QDialog.DialogCode.Rejected)

    field.customContextMenuRequested.emit(field.rect().center())
    assert field.text() == "Hello world"
