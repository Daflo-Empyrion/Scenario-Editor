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

import gc
import os
import sys
from pathlib import Path

import pytest

# Ajoute la racine du projet (parent de tests/) au sys.path pour importer core
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force un affichage virtuel (offscreen) pour les tests touchant a PyQt6 -- evite
# tout echec dans un environnement sans vrai serveur graphique (CI, sandbox...).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Sur la plateforme offscreen, Qt ne charge AUCUNE police systeme par defaut
# (QFontDatabase vide) : le layout de texte d'un texte en gras sur une police
# non resolue peut alors ne jamais terminer (observe avec le delegue de
# selection neon). Pointer Qt sur les vraies polices Windows resout le
# probleme et rend les captures de tests fideles ; sur une autre
# plate-forme, le dossier absent est simplement ignore par Qt.
os.environ.setdefault(
    "QT_QPA_FONTDIR",
    str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"))


@pytest.fixture(scope="session")
def qapp():
    """Instance QApplication partagee pour toute la session de tests -- necessaire
    avant de construire le moindre widget PyQt6. Une seule instance globale (comme
    le voudrait normalement l'appli elle-meme), jamais recreee entre les tests."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _no_real_central_backups(tmp_path, monkeypatch):
    """Aucun test n'ecrit dans ~/.empyrion_editor/backups/ (vecu 04/10 :
    les fixtures de test polluaient le dossier reel de sauvegardes)."""
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda p, kind="sectors": tmp_path / "backup.yaml")


@pytest.fixture(autouse=True)
def _no_real_vanilla_config(monkeypatch):
    """Aucun test ne lit la config vanilla installee (l'arbre technologique
    reporte les patchs '+Block'/'+Item' de la config de base : un test sur
    des fixtures synthetiques deviendrait dependant de l'installation du
    poste). Les tests qui veulent la base la passent explicitement."""
    monkeypatch.setattr("core.settings.get_vanilla_content_path", lambda: "")


@pytest.fixture(autouse=True)
def _collect_qt_cycles():
    """PyQt6 + Python 3.14 : les cycles de widgets (tableaux, items YAML)
    accumules pendant toute la session faisaient crasher en access violation
    le gc.collect() d'un test ulterieur (vecu 20/10 en plein suite). Une
    collecte APRES chaque test garde le tas propre et evite le ramassage
    massif tardif ; les tests restent independants.

    Les dialogues NON detruits par leur test figeaient ce gc (vecu 22/10 :
    test_launch_check et test_epb_check_dialog passaient puis le processus
    ne rendait jamais la main) : on detruit ceux qui restent ouverts avant
    la collecte — un test ne doit de toute facon rien laisser ouvert."""
    yield
    from PyQt6 import sip
    from PyQt6.QtWidgets import QApplication, QDialog
    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            # un dialogue deja detruit par Qt reste dans la liste : son
            # wrapper Python est mort, le supprimer de nouveau leve
            if isinstance(widget, QDialog) and not sip.isdeleted(widget):
                sip.delete(widget)
    gc.collect()
