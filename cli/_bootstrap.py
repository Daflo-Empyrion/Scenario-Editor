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
Bootstrap partage par les 9 scripts CLI (cli/verifier_parser_ecf.py etc.) --
rend le paquet `core` importable, que le script tourne depuis les sources ou
depuis l'executable construit par PyInstaller (EmpyrionEditorCLI, voir
empyrion_editor.spec). Factorise le bloc identique auparavant duplique dans
chaque script (voir audit de code v1.3.3).

USAGE (en tete de chaque script, AVANT tout `from core...` ) :
    from cli._bootstrap import ensure_core_importable
    ensure_core_importable("core/ecf/diff.py")   # marqueur propre au script
"""
import sys
from pathlib import Path


def ensure_core_importable(marker_relpath: str) -> None:
    """Ajoute la racine du projet a sys.path si necessaire pour que `core`
    soit importable. `marker_relpath` est un chemin relatif (ex:
    "core/ecf/diff.py") propre au module que le script appelant va importer
    juste apres -- sert a distinguer la vraie racine du projet parmi les
    candidats plutot que de supposer une structure fixe. Ne fait rien si
    l'executable tourne en mode "frozen" (PyInstaller) : `core` y est deja
    compile et importable directement."""
    if getattr(sys, 'frozen', False):
        return

    # Le script appelant vit dans cli/ (racine_projet/cli/xxx.py) -- la racine
    # du projet est donc son grand-parent. On garde aussi quelques candidats
    # de repli (structure historique racine/empyrion_editor/) pour rester
    # robuste si le script est copie/lance depuis un autre contexte.
    ici = Path(__file__).resolve().parent  # cli/
    candidats = [
        ici.parent,                          # racine du projet
        ici.parent / "empyrion_editor",
        ici.parent.parent,
        ici.parent.parent / "empyrion_editor",
    ]
    for c in candidats:
        if (c / marker_relpath).exists():
            sys.path.insert(0, str(c))
            return

    print(f"ERREUR : impossible de trouver {marker_relpath}")
    sys.exit(1)
