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
Handler YAML pour les fichiers de playfield (playfield_static.yaml, playfield_dynamic.yaml).

Utilise le parser maison "yamllite" (core/yamllite/), qui garantit un round-trip fidele
par construction -- meme principe que le parser ECF : chaque ligne garde son texte brut,
donc rien n'est modifie tant qu'on ne touche pas explicitement une valeur.

Historique : une premiere version utilisait ruamel.yaml (bibliotheque tierce, mode
round-trip), mais des tests sur de vrais fichiers Empyrion ont revele plusieurs pertes
de fidelite non corrigibles simplement (lignes vides "orphelines" perdues selon le
contexte). D'ou le passage a un parser maison, comme pour l'ECF a l'Etape 1.
"""
from pathlib import Path
from typing import Any

from .file_handlers import FileHandler
from .yamllite.parser import parse_yaml_text
from .yamllite.model import YamlDocument


class YamlHandler(FileHandler):
    """Handler round-trip pour les fichiers .yaml/.yml (playfields Empyrion notamment)."""

    extensions = ('.yaml', '.yml')

    def load(self, path: Path) -> str:
        with open(path, 'rb') as f:
            return f.read().decode('utf-8')

    def parse(self, raw: str) -> YamlDocument:
        return parse_yaml_text(raw)

    def serialize(self, ast: YamlDocument) -> str:
        return ast.render()


