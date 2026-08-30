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
Traductions STANDARD de Qt -- boutons generes par Qt lui-meme (Yes/No/OK/
Cancel des QMessageBox.question, QDialogButtonBox, QInputDialog, pages des
QWizard...) : sans ce module, ces boutons restent en ANGLAIS quelle que soit
la langue choisie dans l'application, car Qt ne les traduit qu'avec son
propre fichier de traduction 'qtbase_<lang>.qm' (fourni avec PyQt6), a
installer explicitement sur la QApplication.

C'est la cause principale des boutons anglais constates sous langue
francaise (demande d'audit du 30/08/2026) : l'application traduisait TOUT
son propre texte via core.i18n, mais jamais les boutons standards de Qt.

install_qt_language() est sans effet si aucune QApplication n'existe encore
(a appeler APRES la creation de QApplication, dans gui.main_window.main) et
doit etre REAPPELEE a chaque changement de langue a chaud (voir
MainWindow._apply_language) : elle retire le traducteur precedent avant
d'installer le nouveau. Pour 'en', aucun fichier n'est charge : l'anglais
EST la langue source de Qt, retirer le traducteur suffit.
"""
from typing import Optional

from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
from PyQt6.QtWidgets import QApplication

_translator: Optional[QTranslator] = None


def install_qt_language(lang: str) -> bool:
    """Installe (ou retire) la traduction standard de Qt pour `lang` ('fr'/'en').
    Retourne True si un traducteur est actif apres l'appel. Jamais d'exception
    si le fichier qtbase est introuvable (PyQt6 tronque, environnement exotique) :
    les boutons standards retombent alors sur l'anglais, comme avant."""
    global _translator
    app = QApplication.instance()
    if app is None:
        return False
    if _translator is not None:
        app.removeTranslator(_translator)
        _translator = None
    if lang == "en":
        return False  # anglais = langue source de Qt, rien a charger
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    translator = QTranslator(app)  # parente a l'app : vit toute la session
    if not translator.load(QLocale(lang), "qtbase", "_", translations_path):
        return False
    app.installTranslator(translator)
    _translator = translator
    return True
