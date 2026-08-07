"""
Interface commune que chaque type de fichier (ECF, YAML, CSV...) devra implémenter.

Étape 0 : on pose le contrat et un registre d'extensions -> handler.
L'implémentation réelle du parsing ECF arrive à l'Étape 1 ; pour l'instant les handlers
enregistrés sont des placeholders qui savent juste dire "je gère cette extension".
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional


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
    """Registre par défaut. Les handlers réels remplaceront ces placeholders au fil des étapes."""
    reg = HandlerRegistry()
    reg.register(UnimplementedHandler(('.ecf',)))
    reg.register(UnimplementedHandler(('.yaml', '.yml')))
    reg.register(UnimplementedHandler(('.csv',)))
    return reg
