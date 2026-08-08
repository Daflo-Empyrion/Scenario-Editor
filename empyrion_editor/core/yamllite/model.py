"""
Modèle AST pour un parser YAML "léger" (yamllite), conçu sur le même principe que le
parser ECF : chaque ligne garde son texte brut d'origine, donc tant qu'on ne modifie
rien, la sérialisation reproduit le fichier à l'identique, byte pour byte -- quelle que
soit la complexité de la structure YAML sous-jacente.

Contrairement à un parser YAML générique (type ruamel.yaml), on ne cherche PAS à
comprendre finement chaque construction YAML (ancres, tags, styles de pliage...). On se
limite au sous-ensemble réellement utilisé par les fichiers Empyrion (playfields) :
mappings imbriqués par indentation, séquences ('- item'), scalaires simples, listes/
mappings "flow" sur une seule ligne ([a, b], {k: v}) traités comme du texte opaque, et
commentaires. C'est le même choix de conception que pour l'ECF : mieux vaut un
sous-ensemble fidèle à 100% qu'un parser généraliste qui trahit la moindre subtilité.

Types de nœuds :
  - YamlBlank    : ligne vide
  - YamlComment  : ligne de commentaire (#...), jamais réinterprétée
  - YamlEntry    : une ligne "clé: valeur" (mapping) ou "- valeur" (séquence), avec
                   ses enfants imbriqués (indentation supérieure)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class YamlBlank:
    raw: str

    def render(self) -> str:
        return self.raw


@dataclass
class YamlComment:
    raw: str

    def render(self) -> str:
        return self.raw


@dataclass
class YamlEntry:
    """
    Une ligne de contenu structurel : soit une entrée de mapping ('Cle: valeur'), soit
    un item de sequence ('- valeur' ou '- Cle: valeur' pour une sequence de mappings).
    """
    raw: str                          # texte d'origine complet (utilise si non modifie)
    indent: str                       # espaces en debut de ligne
    is_sequence_item: bool            # True si la ligne commence par '- '
    key: Optional[str]                # cle du mapping, ou None si scalaire de sequence pur
    value: str                        # valeur brute apres ':' ou apres '- ' (peut etre vide
                                       # si le contenu continue sur les lignes suivantes,
                                       # plus indentees)
    comment: Optional[str]            # commentaire de fin de ligne, ou None
    eol: str
    children: List["YamlNode"] = field(default_factory=list)
    dirty: bool = False

    def get(self, key: str) -> Optional[str]:
        """Cherche une valeur parmi les enfants directs (mapping imbrique)."""
        for child in self.children:
            if isinstance(child, YamlEntry) and child.key == key:
                return child.value
        return None

    def set(self, key: str, new_value: str) -> bool:
        """Modifie la valeur d'une cle enfant existante. Retourne False si absente."""
        for child in self.children:
            if isinstance(child, YamlEntry) and child.key == key:
                child.value = new_value
                child.dirty = True
                return True
        return False

    def set_own_value(self, new_value: str) -> None:
        """Modifie la valeur de CETTE entree elle-meme (pas d'un enfant)."""
        self.value = new_value
        self.dirty = True

    def render(self) -> str:
        parts = [self._render_self_line()]
        for child in self.children:
            parts.append(child.render())
        return "".join(parts)

    def _render_self_line(self) -> str:
        if not self.dirty:
            return self.raw
        prefix = "- " if self.is_sequence_item else ""
        if self.key is not None:
            body = f"{self.key}: {self.value}" if self.value else f"{self.key}:"
        else:
            body = self.value
        line = f"{self.indent}{prefix}{body}"
        if self.comment:
            line += "  " + self.comment
        return line + self.eol


YamlNode = Union[YamlBlank, YamlComment, YamlEntry]


@dataclass
class YamlDocument:
    nodes: List[YamlNode]
    source_path: Optional[str] = None

    def render(self) -> str:
        return "".join(n.render() for n in self.nodes)

    def iter_entries(self):
        """Parcourt recursivement toutes les entrees (mapping/sequence) du document."""
        def _walk(nodes):
            for n in nodes:
                if isinstance(n, YamlEntry):
                    yield n
                    yield from _walk(n.children)
        yield from _walk(self.nodes)

    def find(self, key: str) -> Optional[YamlEntry]:
        """Trouve la premiere entree de mapping portant cette cle, a n'importe quel niveau."""
        for entry in self.iter_entries():
            if entry.key == key:
                return entry
        return None

    def get_path(self, *keys: str) -> Optional[str]:
        """Navigue par une suite de cles imbriquees, ex: get_path('Playfield','Name')."""
        current_nodes = self.nodes
        entry = None
        for key in keys:
            entry = None
            for n in current_nodes:
                if isinstance(n, YamlEntry) and n.key == key:
                    entry = n
                    break
            if entry is None:
                return None
            current_nodes = entry.children
        return entry.value if entry else None
