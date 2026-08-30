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
Boites de confirmation a boutons EXPLICITES traduits par core.i18n
(i18n_strings.json) -- demande explicite de l'utilisateur (30/08/2026,
apres l'audit i18n) : les boutons de confirmation doivent suivre LA MEME
chaine de traduction que tout le reste de l'application, jamais les
boutons standards internes de Qt.

Avant : QMessageBox.question(..., Yes | No) laissait Qt dessiner ses
propres boutons, traduits (ou non) par le mecanisme SEPARATE des fichiers
qtbase_<lang>.qm de Qt -- d'ou des boutons restes en anglais.

Remplacer TOUTE utilisation de QMessageBox.question dans l'application par
ask_yes_no() : meme rendu (icone question, titre, texte), boutons crees
par l'application avec t("btn.yes")/t("btn.no").

Le traducteur Qt (core/qt_translator.py) reste actif UNIQUEMENT pour les
boites internes NON personnalisables : QInputDialog (OK/Cancel) et
QDialogButtonBox (playfield/new project) -- hors de portee de i18n.
"""
from PyQt6.QtWidgets import QMessageBox

from core.i18n import t


def ask_yes_no(parent, title: str, text: str) -> bool:
    """Pose une question Oui/Non avec des boutons APPLICATION (libelles
    t("btn.yes")/t("btn.no")) -- retourne True si Oui. Bouton par defaut =
    Non (une validation accidentelle par Entree ne doit jamais declencher
    l'action ; coherent avec l'ancien comportement Qt ou No etait le
    bouton de repli)."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    btn_yes = box.addButton(t("btn.yes"), QMessageBox.ButtonRole.YesRole)
    btn_no = box.addButton(t("btn.no"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(btn_no)
    box.exec()
    return box.clickedButton() is btn_yes
