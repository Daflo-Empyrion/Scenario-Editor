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
Exception structuree : le garde-fou de fermeture a TROIS choix
(Save/Discard/Cancel) n'est pas un Oui/Non -- voir ask_save_discard_cancel(),
meme principe (boutons application t(...)).

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


def ask_save_discard_cancel(parent, title: str, text: str) -> str:
    """Dialogue a trois choix pour quitter avec des modifications non
    enregistrees : retourne "save" (enregistrer tout), "discard" (abandonner
    les modifications) ou "cancel" (rester dans l'application). Boutons
    APPLICATION t("btn.save_files")/t("btn.discard")/t("btn.cancel") -- meme
    chaine de traduction que ask_yes_no(), jamais les boutons standards de Qt
    (l'ancien QMessageBox.question dessinait Save/Discard/Cancel via les
    fichiers qtbase_<lang>.qm, hors de portee de i18n). Bouton par defaut =
    Enregistrer tout (quitter en croyant avoir sauvegarde ne doit jamais
    perdre de donnees ; cohérent avec l'ancien comportement Qt dont le
    bouton de repli etait Save)."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    btn_save = box.addButton(t("btn.save_files"),
                             QMessageBox.ButtonRole.AcceptRole)
    btn_discard = box.addButton(t("btn.discard"),
                                QMessageBox.ButtonRole.DestructiveRole)
    btn_cancel = box.addButton(t("btn.cancel"),
                               QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(btn_save)
    box.exec()
    clicked = box.clickedButton()
    if clicked is btn_discard:
        return "discard"
    if clicked is btn_cancel:
        return "cancel"
    return "save"
