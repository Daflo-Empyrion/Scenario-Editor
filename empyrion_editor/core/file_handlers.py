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
Interface commune que chaque type de fichier (ECF, YAML, CSV...) devra implémenter.

Étape 0 : on pose le contrat et un registre d'extensions -> handler.
Étape 1 : le handler ECF réel est branché ici (voir EcfHandler plus bas).
Les autres extensions (.yaml, .csv) restent en placeholder pour les étapes suivantes.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional

from .ecf.parser import parse_ecf_file, parse_ecf_text
from .ecf.model import EcfDocument


class FileHandler(ABC):
    """Contrat commun à tous les parsers de fichiers de scénario."""

    extensions: tuple = ()

    @abstractmethod
    def load(self, path: Path) -> Any:
        """Lit le fichier depuis le disque et retourne son contenu brut (texte, bytes...)."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: Any) -> Any:
        """Transforme le contenu brut en structure interne éditable (AST)."""
        raise NotImplementedError

    @abstractmethod
    def serialize(self, ast: Any) -> str:
        """Reconstruit le texte du fichier à partir de l'AST (doit préserver commentaires/ordre)."""
        raise NotImplementedError

    def diff(self, ast_a: Any, ast_b: Any) -> Any:
        """Compare deux AST du même type. Implémenté à l'Étape 3."""
        raise NotImplementedError(f"{type(self).__name__}: diff pas encore implémenté")

    def merge(self, sources: List[Any], rules: Optional[Any] = None) -> Any:
        """Fusionne plusieurs AST du même type selon des règles. Implémenté à l'Étape 4."""
        raise NotImplementedError(f"{type(self).__name__}: merge pas encore implémenté")


class EcfHandler(FileHandler):
    """Handler réel pour les fichiers .ecf, basé sur le parser de l'Étape 1.
    Garantit un round-trip fidèle (byte pour byte) tant qu'aucune valeur n'est modifiée."""

    extensions = ('.ecf',)

    def load(self, path: Path) -> str:
        # Voir la note dans core/ecf/parser.py : 'utf-8' (pas 'utf-8-sig') pour préserver
        # un éventuel BOM comme partie du texte, et garantir le round-trip byte-pour-byte.
        with open(path, 'r', encoding='utf-8', newline='') as f:
            return f.read()

    def parse(self, raw: str) -> EcfDocument:
        return parse_ecf_text(raw)

    def serialize(self, ast: EcfDocument) -> str:
        return ast.render()


class UnimplementedHandler(FileHandler):
    """
    Placeholder utilisé tant qu'un vrai parser n'existe pas pour une extension donnée.
    Permet de savoir dès l'Étape 0 quelles extensions seront un jour éditables, sans
    encore fournir de vraie logique de parsing.
    """

    def __init__(self, extensions: tuple):
        self.extensions = extensions

    def load(self, path: Path) -> Any:
        return path.read_text(encoding='utf-8', errors='replace')

    def parse(self, raw: Any) -> Any:
        raise NotImplementedError("Parser non encore implémenté (arrive à l'Étape 1)")

    def serialize(self, ast: Any) -> str:
        raise NotImplementedError("Serializer non encore implémenté (arrive à l'Étape 1)")


class HandlerRegistry:
    """Associe une extension de fichier à son FileHandler."""

    def __init__(self):
        self._handlers = {}

    def register(self, handler: FileHandler) -> None:
        for ext in handler.extensions:
            self._handlers[ext.lower()] = handler

    def get_handler(self, path: Path) -> Optional[FileHandler]:
        return self._handlers.get(path.suffix.lower())

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self._handlers

    def supported_extensions(self) -> List[str]:
        return sorted(self._handlers.keys())


def default_registry() -> HandlerRegistry:
    """Registre par défaut. Les handlers ECF et YAML sont réels (Étapes 1 et 6, tous
    deux avec parser maison, sans dépendance externe) ; CSV reste un placeholder."""
    reg = HandlerRegistry()
    reg.register(EcfHandler())
    from .yaml_handler import YamlHandler
    reg.register(YamlHandler())
    from .csv_handler import CsvHandler
    reg.register(CsvHandler())
    return reg
