"""
Outils d'edition partages entre les editeurs de la copie de travail (CSV, ECF...) :
  - copier / couper / coller / supprimer sur une selection de cellules (comme un
    tableur : Ctrl+C/X/V/Suppr, compatible avec un simple copier-coller depuis/vers
    Excel puisque le format utilise des tabulations entre colonnes)
  - une petite fenetre de mise en forme BBCode (couleur + gras/italique/souligne) avec
    une palette de couleurs reduite, pour habiller une portion de texte selectionnee
    sans avoir a taper les balises a la main.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QTableWidget, QTableWidgetItem, QDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QMenu,
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt


# ------------------------------------------------------------------
# Copier / couper / coller / supprimer sur un QTableWidget
# ------------------------------------------------------------------

def copy_selection(table: QTableWidget) -> None:
    """Copie la selection dans le presse-papier, format tabule (compatible Excel)."""
    ranges = table.selectedRanges()
    if not ranges:
        return
    r = ranges[0]
    lines = []
    for row in range(r.topRow(), r.bottomRow() + 1):
        cols = []
        for col in range(r.leftColumn(), r.rightColumn() + 1):
            item = table.item(row, col)
            cols.append(item.text() if item else "")
        lines.append("\t".join(cols))
    QApplication.clipboard().setText("\n".join(lines))


def cut_selection(table: QTableWidget) -> None:
    """Copie puis vide les cellules editables de la selection (ne supprime jamais une
    cellule non-editable, ex: la colonne 'Cle' d'un tableau de proprietes ECF)."""
    copy_selection(table)
    _clear_selection(table)


def delete_selection(table: QTableWidget) -> None:
    """Vide le contenu des cellules editables de la selection, sans toucher au
    presse-papier."""
    _clear_selection(table)


def _clear_selection(table: QTableWidget) -> None:
    for r in table.selectedRanges():
        for row in range(r.topRow(), r.bottomRow() + 1):
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                item = table.item(row, col)
                if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    item.setText("")


def paste_into_selection(table: QTableWidget, allow_new_rows: bool = True) -> None:
    """Colle le contenu du presse-papier (tabule) a partir de la cellule active,
    en ecrasant uniquement les cellules editables ; ajoute des lignes si necessaire
    et autorise (allow_new_rows)."""
    text = QApplication.clipboard().text()
    if not text:
        return
    rows_data = [line.split('\t') for line in text.split('\n')]
    if rows_data and rows_data[-1] == ['']:
        rows_data.pop()

    ranges = table.selectedRanges()
    if ranges:
        start_row, start_col = ranges[0].topRow(), ranges[0].leftColumn()
    else:
        start_row, start_col = max(table.currentRow(), 0), max(table.currentColumn(), 0)

    for i, row_vals in enumerate(rows_data):
        r = start_row + i
        if r >= table.rowCount():
            if not allow_new_rows:
                break
            table.insertRow(r)
        for j, val in enumerate(row_vals):
            c = start_col + j
            if c >= table.columnCount():
                continue
            item = table.item(r, c)
            if item is None:
                item = QTableWidgetItem("")
                table.setItem(r, c, item)
            if item.flags() & Qt.ItemFlag.ItemIsEditable:
                item.setText(val)


def install_clipboard_shortcuts(table: QTableWidget, allow_new_rows: bool = True) -> None:
    """Attache Ctrl+C / Ctrl+X / Ctrl+V / Suppr au tableau donne."""
    QShortcut(QKeySequence.StandardKey.Copy, table, activated=lambda: copy_selection(table))
    QShortcut(QKeySequence.StandardKey.Cut, table, activated=lambda: cut_selection(table))
    QShortcut(QKeySequence.StandardKey.Paste, table, activated=lambda: paste_into_selection(table, allow_new_rows))
    QShortcut(QKeySequence(Qt.Key.Key_Delete), table, activated=lambda: delete_selection(table))


def add_clipboard_menu_actions(menu: QMenu, table: QTableWidget, allow_new_rows: bool = True) -> None:
    """Ajoute Copier/Couper/Coller/Supprimer a un menu contextuel existant."""
    menu.addAction("Copier", lambda: copy_selection(table))
    menu.addAction("Couper", lambda: cut_selection(table))
    menu.addAction("Coller", lambda: paste_into_selection(table, allow_new_rows))
    menu.addAction("Supprimer le contenu", lambda: delete_selection(table))


# ------------------------------------------------------------------
# Mise en forme BBCode (couleur + gras/italique/souligne) avec palette reduite
# ------------------------------------------------------------------

BBCODE_COLORS = [
    ("Rouge", "#FF0000"),
    ("Vert", "#00CC00"),
    ("Bleu", "#0066FF"),
    ("Jaune", "#FFCC00"),
    ("Orange", "#FF8800"),
    ("Violet", "#9900CC"),
    ("Cyan", "#00CCCC"),
    ("Rose", "#FF66CC"),
    ("Blanc", "#FFFFFF"),
    ("Gris", "#999999"),
]


class BBCodeToolDialog(QDialog):
    """Petite fenetre d'edition avec palette de couleurs et boutons de style (gras,
    italique, souligne) : selectionne du texte a la souris dans la zone d'edition,
    clique une couleur ou un style pour l'entourer des balises BBCode correspondantes."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mise en forme BBCode")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selectionne une portion de texte ci-dessous, puis clique une "
                                 "couleur ou un style pour l'appliquer :"))

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(100)
        layout.addWidget(self.text_edit)

        style_row = QHBoxLayout()
        for label, tag in [("Gras", "b"), ("Italique", "i"), ("Souligne", "u")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, t=tag: self._wrap_selection(f"[{t}]", f"[/{t}]"))
            style_row.addWidget(btn)
        style_row.addStretch()
        layout.addLayout(style_row)

        layout.addWidget(QLabel("Couleurs :"))
        palette_row = QHBoxLayout()
        for name, hexcode in BBCODE_COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 22)
            btn.setToolTip(name)
            text_color = "#000000" if hexcode == "#FFFFFF" else "#FFFFFF"
            btn.setStyleSheet(f"background-color: {hexcode}; border: 1px solid #555; color: {text_color};")
            btn.clicked.connect(lambda checked, c=hexcode: self._wrap_selection(f"[color={c}]", "[/color]"))
            palette_row.addWidget(btn)
        palette_row.addStretch()
        layout.addLayout(palette_row)

        buttons = QHBoxLayout()
        btn_apply = QPushButton("Appliquer a la cellule")
        btn_apply.clicked.connect(self.accept)
        buttons.addWidget(btn_apply)
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def _wrap_selection(self, open_tag: str, close_tag: str):
        cursor = self.text_edit.textCursor()
        selected = cursor.selectedText().replace('\u2029', '\n')
        if not selected:
            self._flash_hint("Selectionne d'abord une portion de texte dans la zone ci-dessus.")
            return
        cursor.insertText(f"{open_tag}{selected}{close_tag}")

    def _flash_hint(self, text: str):
        from PyQt6.QtWidgets import QToolTip
        from PyQt6.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), text)

    def result_text(self) -> str:
        return self.text_edit.toPlainText()


def open_bbcode_tool(parent_widget, current_text: str) -> Optional[str]:
    """Ouvre la fenetre de mise en forme BBCode. Retourne le nouveau texte si
    l'utilisateur valide, sinon None."""
    dialog = BBCodeToolDialog(current_text, parent_widget)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.result_text()
    return None
