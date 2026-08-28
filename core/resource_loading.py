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
Resolution partagee de chemin vers un fichier de donnees embarque (dossier data/),
que l'application tourne depuis les sources ou depuis un executable construit par
PyInstaller. Meme logique que MainWindow._resolve_asset_path (gui/main_window.py)
pour assets/, mais utilisable depuis les modules core/ (charges avant toute
instance de MainWindow) -- voir empyrion_editor.spec, ou data/ doit etre ajoute
aux `datas` au meme titre que assets/.
"""
import json
import sys
from pathlib import Path
from typing import Any


def resolve_data_path(filename: str) -> Path:
    """Trouve un fichier dans le dossier data/ a la racine du projet. Leve
    FileNotFoundError si introuvable -- contrairement a _resolve_asset_path
    (assets/, purement decoratif), ces fichiers sont necessaires au
    fonctionnement de l'application (traductions, glossaire) donc l'absence
    doit etre visible immediatement plutot que de degrader silencieusement."""
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys._MEIPASS) / "data" / filename)
    candidates.append(Path(__file__).resolve().parent.parent / "data" / filename)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Fichier de donnees introuvable : {filename} (cherche dans {candidates})")


def load_json_data(filename: str) -> Any:
    """Charge et parse un fichier JSON du dossier data/ (voir resolve_data_path)."""
    path = resolve_data_path(filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
