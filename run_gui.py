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
Lance l'interface graphique de l'editeur de scenario Empyrion.

UTILISATION :
    python run_gui.py
"""
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Executable construit par PyInstaller (voir empyrion_editor.spec) : 'core' et
    # 'gui' sont deja compiles dans l'archive et directement importables, aucune
    # recherche de dossier necessaire -- la detection ci-dessous ne s'applique
    # qu'a une execution depuis les sources.
    pass
else:
    _ici = Path(__file__).resolve().parent
    _candidats = [_ici, _ici / "empyrion_editor", _ici.parent, _ici.parent / "empyrion_editor"]
    for _c in _candidats:
        if (_c / "core" / "scanner.py").exists():
            sys.path.insert(0, str(_c))
            break
    else:
        print("ERREUR : impossible de trouver le dossier 'core'.")
        sys.exit(1)

from gui.main_window import main

if __name__ == "__main__":
    main()
