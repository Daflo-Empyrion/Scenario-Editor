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

"""Bouton « Comprendre le module » : mécanisme partagé par tous les
dialogues à paramètres sensibles. Le contenu vit dans une clé i18n
HTML (<key>), rendue avec les paramètres fournis ; chaque module décrit
ses conséquences réelles (formules, garde-fous, limites moteur)."""

from PyQt6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout

from core.i18n import t
from gui.theme import icon


def add_info_button(layout, info_key: str, parent=None) -> QPushButton:
    """Ajoute le bouton info dans `layout` ; clic = fenêtre de lecture
    (HTML = traduction de `info_key`). Test : patcher
    gui.module_info.show_module_info et cliquer."""
    btn = QPushButton(icon("fa5s.question-circle", "#4a7dfc"),
                      t("module.info"))
    btn.setToolTip(t("module.info.tip"))
    btn.setObjectName("secondaryButton")
    btn.clicked.connect(lambda: show_module_info(btn, info_key))
    layout.addWidget(btn)
    return btn


def show_module_info(parent, info_key: str) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(t("module.info"))
    lay = QVBoxLayout(dlg)
    tb = QTextBrowser()
    tb.setHtml(t(info_key))
    lay.addWidget(tb)
    btn = QPushButton(t("btn.close"))
    btn.setObjectName("secondaryButton")
    btn.clicked.connect(dlg.accept)
    lay.addWidget(btn)
    from gui.window_geometry import track
    track(dlg, "module_info_" + info_key.replace(".", "_"), (800, 680))
    dlg.exec()
