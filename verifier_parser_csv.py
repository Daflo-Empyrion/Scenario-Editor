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

Point d'entree racine (c'est la forme documentee dans le wiki :
`python verifier_parser_csv.py ...`) -- simple renvoi vers l'implementation reelle dans
cli/verifier_parser_csv.py, qui reste l'UNIQUE SOURCE DE VERITE. Avant cette refactorisation,
les deux copies etaient dupliquees a ~99% et divergeaient silencieusement.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli.verifier_parser_csv import main

if __name__ == "__main__":
    main()
