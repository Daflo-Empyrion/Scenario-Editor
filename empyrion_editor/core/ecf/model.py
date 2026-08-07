"""
Modèle AST (arbre syntaxique) pour les fichiers ECF d'Empyrion.

Principe de conception : chaque nœud garde son texte brut d'origine (raw), donc tant
qu'on ne modifie rien, la sérialisation reproduit le fichier à l'identique, byte pour
byte (commentaires, indentation, fins de ligne CRLF/LF, espacement -- tout est préservé).
Quand une valeur est modifiée, seule la ligne concernée est régénérée ; le reste du
fichier reste intact.

Un fichier ECF est une séquence de "nœuds" au niveau racine, où un nœud est :
  - EcfBlank    : une ligne vide
  - EcfComment  : une ligne de commentaire (# ou ##...), jamais interprétée comme structure,
                  même si elle contient des accolades (utile pour les blocs désactivés)
  - EcfProperty : une ligne "Cle: valeur[, Cle2: valeur2, ...]" avec commentaire de fin optionnel
  - EcfBlock    : un bloc "{ ... }" avec un "genre" (ex: "+Container", "Child Items"),
                  des propriétés déclarées sur la ligne d'ouverture, et des enfants
                  (récursivement les mêmes types de nœuds) jusqu'à la accolade fermante.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

# Cles utilisees pour identifier un bloc de maniere unique (dans cet ordre de priorite).
# Partagees entre le diff et l'editeur pour qu'un bloc soit toujours repere de la meme facon.
IDENTITY_KEYS = ('Id', 'Name', 'Ref')


@dataclass
class EcfBlank:
    raw: str  # ligne brute complète, avec sa fin de ligne d'origine

    def render(self) -> str:
        return self.raw


@dataclass
class EcfComment:
    raw: str  # ligne brute complète -- jamais réinterprétée, même si elle contient '{' ou '}'

    def render(self) -> str:
        return self.raw


@dataclass
class EcfProperty:
    """Une ligne du type 'Cle: valeur, Cle2: valeur2  # commentaire'."""
    raw: str                                  # texte d'origine complet (utilisé si non modifié)
    indent: str                               # espaces/tabs en début de ligne
    pairs: List[Tuple[Optional[str], str]]    # liste ordonnée de (cle, valeur_brute)
    comment: Optional[str]                    # commentaire de fin de ligne (avec son '#'), ou None
    eol: str                                  # fin de ligne d'origine ('\r\n' ou '\n')
    dirty: bool = False                       # True si modifié depuis le parsing -> à régénérer

    def get(self, key: str) -> Optional[str]:
        for k, v in self.pairs:
            if k == key:
                return v
        return None

    def set(self, key: str, new_value: str) -> bool:
        """Modifie la valeur d'une clé existante sur cette ligne. Retourne False si la clé n'existe pas."""
        for i, (k, v) in enumerate(self.pairs):
            if k == key:
                self.pairs[i] = (k, new_value)
                self.dirty = True
                return True
        return False

    def render(self) -> str:
        if not self.dirty:
            return self.raw
        body = ", ".join(f"{k}: {v}" if k is not None else v for k, v in self.pairs)
        line = self.indent + body
        if self.comment:
            line += "  " + self.comment
        return line + self.eol


@dataclass
class EcfBlock:
    """Un bloc '{ genre Cle: valeur, ... }' avec des enfants imbriqués."""
    indent: str
    kind: str                                 # ex: '+Container', 'Child Items', 'Container'
    pairs: List[Tuple[Optional[str], str]]    # propriétés déclarées sur la ligne d'ouverture
    comment: Optional[str]                    # commentaire de fin sur la ligne d'ouverture
    eol: str
    raw_open: str                             # ligne d'ouverture brute d'origine
    close_raw: str                            # ligne de fermeture '}' brute d'origine
    children: List["EcfNode"] = field(default_factory=list)
    dirty: bool = False

    def get(self, key: str) -> Optional[str]:
        """Cherche une propriété déclarée sur la ligne d'ouverture du bloc (ex: Id)."""
        for k, v in self.pairs:
            if k == key:
                return v
        return None

    def set(self, key: str, new_value: str) -> bool:
        for i, (k, v) in enumerate(self.pairs):
            if k == key:
                self.pairs[i] = (k, new_value)
                self.dirty = True
                return True
        return False

    def get_property(self, key: str) -> Optional[str]:
        """Cherche une propriété parmi les enfants directs (lignes EcfProperty) du bloc,
        et si absente, dans les propriétés déclarées sur la ligne d'ouverture."""
        for child in self.children:
            if isinstance(child, EcfProperty):
                val = child.get(key)
                if val is not None:
                    return val
        return self.get(key)

    def set_property(self, key: str, new_value: str) -> bool:
        """Modifie une propriété existante, qu'elle soit sur la ligne d'ouverture ou une ligne enfant."""
        for child in self.children:
            if isinstance(child, EcfProperty) and child.set(key, new_value):
                return True
        return self.set(key, new_value)

    def child_blocks(self, kind: Optional[str] = None) -> List["EcfBlock"]:
        """Sous-blocs directs, filtrés par genre si précisé (ex: 'Child Items')."""
        return [c for c in self.children if isinstance(c, EcfBlock) and (kind is None or c.kind == kind)]

    def summary_line(self, max_items: int = 3) -> str:
        """Résumé court et lisible du bloc (utilisé par l'éditeur en ligne de commande),
        ex: 'Count: "3,4", Size: "8,1", SfxOpen: UseActions/body_open'."""
        items = []
        for k, v in self.pairs:
            if k is not None and k not in IDENTITY_KEYS:
                items.append(f"{k}: {v}")
        for child in self.children:
            if len(items) >= max_items:
                break
            if isinstance(child, EcfProperty) and child.pairs:
                k, v = child.pairs[0]
                if k is not None:
                    items.append(f"{k}: {v}")
        return ", ".join(items[:max_items])

    def render_open(self) -> str:
        if not self.dirty:
            return self.raw_open
        body = ", ".join(f"{k}: {v}" if k is not None else v for k, v in self.pairs)
        line = f"{self.indent}{{ {self.kind}"
        if body:
            line += f" {body}"
        if self.comment:
            line += "  " + self.comment
        return line + self.eol

    def render(self) -> str:
        parts = [self.render_open()]
        for child in self.children:
            parts.append(child.render())
        parts.append(self.close_raw)
        return "".join(parts)


EcfNode = Union[EcfBlank, EcfComment, EcfProperty, EcfBlock]


def block_identity(block: EcfBlock) -> Optional[str]:
    """Identite d'un bloc, dans l'ordre de priorite IDENTITY_KEYS (Id, puis Name, puis Ref).
    Utilisee par le diff et l'editeur pour reperer un bloc de maniere stable."""
    for key in IDENTITY_KEYS:
        val = block.get(key)
        if val is not None:
            return val
    return None


@dataclass
class EcfDocument:
    nodes: List[EcfNode]
    source_path: Optional[str] = None

    def render(self) -> str:
        return "".join(n.render() for n in self.nodes)

    def iter_blocks(self, kind: Optional[str] = None):
        """Parcourt récursivement tous les blocs du document, filtrés par genre si précisé."""
        def _walk(nodes):
            for n in nodes:
                if isinstance(n, EcfBlock):
                    if kind is None or n.kind == kind:
                        yield n
                    yield from _walk(n.children)
        yield from _walk(self.nodes)

    def find_block(self, kind: str, key: str, value: str) -> Optional[EcfBlock]:
        """Trouve le premier bloc d'un genre donné dont la propriété `key` vaut `value`.
        Ex: find_block('+Container', 'Id', '5')."""
        for block in self.iter_blocks(kind):
            if block.get(key) == value:
                return block
        return None

    def find_block_by_identity(self, kind: str, identity: str) -> Optional[EcfBlock]:
        """Trouve le premier bloc d'un genre donné par son identite (Id, ou a defaut Name/Ref).
        Ex: find_block_by_identity('+Container', '5')."""
        for block in self.iter_blocks(kind):
            if block_identity(block) == identity:
                return block
        return None

    def top_level_kinds(self) -> List[Tuple[str, int]]:
        """Liste les genres de blocs presents au niveau racine, avec leur nombre
        d'occurrences -- utile pour explorer un fichier ECF inconnu."""
        counts: dict = {}
        for n in self.nodes:
            if isinstance(n, EcfBlock):
                counts[n.kind] = counts.get(n.kind, 0) + 1
        return list(counts.items())
