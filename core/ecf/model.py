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
import re
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

    def remove(self, key: str) -> bool:
        """Retire une propriete de la ligne d'ouverture du bloc (ex: pour dupliquer un
        bloc en abandonnant son Id, pour ne le laisser identifie que par Name)."""
        for i, (k, v) in enumerate(self.pairs):
            if k == key:
                del self.pairs[i]
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


def normalized_kind(kind: str) -> str:
    """Retire le prefixe '+'/'-' d'un genre de bloc pour les comparaisons d'identite.

    Empyrion utilise ce prefixe comme convention de PATCH/SURCHARGE : un meme Id peut
    apparaitre une fois comme '{ Block Id: 53...}' (definition de base) et une autre
    fois comme '{ +Block Id: 53...}' (patch qui le complete) -- c'est le MEME bloc
    conceptuellement, pas deux blocs differents. Sans cette normalisation, le merge et
    le diff les traitent a tort comme deux entites distinctes et en creent des doublons.
    """
    return kind.lstrip('+-').strip()


def add_property_line(block: EcfBlock, pairs: List[Tuple[Optional[str], str]]) -> EcfProperty:
    """Insere une nouvelle ligne de propriete dans un bloc (avant le premier sous-bloc
    s'il y en a un, pour rester groupee avec les autres proprietes simples, sinon a la
    fin). Retourne le noeud cree."""
    indent = "  "
    for child in block.children:
        if isinstance(child, EcfProperty):
            indent = child.indent
            break
    new_prop = EcfProperty(raw="", indent=indent, pairs=list(pairs), comment=None,
                            eol=block.eol or "\r\n", dirty=True)
    insert_at = len(block.children)
    for i, child in enumerate(block.children):
        if isinstance(child, EcfBlock):
            insert_at = i
            break
    block.children.insert(insert_at, new_prop)
    return new_prop


_ITEM_KEY_RE = re.compile(r'^([A-Za-z]+)_(\d+)$')


def add_repeating_item_row(block: EcfBlock, item_type: str, first_value: str,
                            extra_pairs: List[Tuple[str, str]]) -> EcfProperty:
    """Ajoute une NOUVELLE ligne a une structure repetitive de type 'Child Items'
    (Name_0/Name_1/..., Group_0/Group_1/...) -- utilise par le mode tableau de
    l'interface. Calcule automatiquement le PROCHAIN NUMERO libre pour le type demande
    (Name ou Group) et insere la ligne juste APRES la derniere entree du MEME type
    (ou, a defaut, apres la derniere entree du type oppose, ou en dernier recours a la
    position habituelle de add_property_line) -- jamais a l'aveugle en toute fin de
    bloc, ce qui casserait la numerotation sequentielle et l'ordre attendu par le
    moteur du jeu (constate sensible a l'ordre pour ce genre de structure).

    `item_type` doit etre 'Name' ou 'Group'. Retourne le noeud cree."""
    same_type_max = -1
    same_type_last_index = -1
    other_type_last_index = -1
    last_prop_index = -1
    indent = "  "

    for i, child in enumerate(block.children):
        if not isinstance(child, EcfProperty):
            continue
        last_prop_index = i
        indent = child.indent
        if not child.pairs:
            continue
        m = _ITEM_KEY_RE.match(child.pairs[0][0] or "")
        if not m:
            continue
        if m.group(1) == item_type:
            same_type_max = max(same_type_max, int(m.group(2)))
            same_type_last_index = i
        else:
            other_type_last_index = i

    next_number = same_type_max + 1
    new_key = f"{item_type}_{next_number}"
    pairs = [(new_key, first_value)] + list(extra_pairs)
    new_prop = EcfProperty(raw="", indent=indent, pairs=pairs, comment=None,
                            eol=block.eol or "\r\n", dirty=True)

    if same_type_last_index >= 0:
        insert_at = same_type_last_index + 1
    elif other_type_last_index >= 0:
        insert_at = other_type_last_index + 1
    elif last_prop_index >= 0:
        insert_at = last_prop_index + 1
    else:
        insert_at = len(block.children)
        for i, child in enumerate(block.children):
            if isinstance(child, EcfBlock):
                insert_at = i
                break

    block.children.insert(insert_at, new_prop)
    return new_prop


def remove_property_line(block: EcfBlock, prop_node: EcfProperty) -> bool:
    """Supprime une ligne de propriete d'un bloc. Retourne False si elle n'y etait pas."""
    if prop_node in block.children:
        block.children.remove(prop_node)
        return True
    return False


def remove_block(nodes: List["EcfNode"], target: EcfBlock) -> bool:
    """Supprime un bloc (a n'importe quelle profondeur) d'une liste de noeuds.
    Retourne False si le bloc n'a pas ete trouve."""
    if target in nodes:
        nodes.remove(target)
        return True
    for node in nodes:
        if isinstance(node, EcfBlock):
            if remove_block(node.children, target):
                return True
    return False


def create_block(kind: str, pairs: List[Tuple[Optional[str], str]], eol: str = "\r\n") -> EcfBlock:
    """Cree un nouveau bloc de toutes pieces (pas encore attache a un document)."""
    return EcfBlock(indent="", kind=kind, pairs=list(pairs), comment=None, eol=eol,
                     raw_open="", close_raw=f"}}{eol}", children=[], dirty=True)


def annotate_property(prop: EcfProperty, note_text: str) -> None:
    """Ajoute une note de tracabilite en fin de ligne (ex: '# original: 100 -- Mod par
    Daflo'), sans ecraser un commentaire deja present sur cette ligne."""
    if prop.comment:
        prop.comment = prop.comment + "  " + note_text
    else:
        prop.comment = note_text
    prop.dirty = True


def duplicate_block(block: EcfBlock, overrides: Optional[dict] = None,
                     remove_keys: Optional[List[str]] = None) -> EcfBlock:
    """Copie profonde d'un bloc, avec certaines proprietes d'en-tete optionnellement
    remplacees (overrides, ex: {'Id': '700000'}) et/ou retirees (remove_keys, ex:
    ['Id'] pour dupliquer un bloc en l'identifiant desormais seulement par Name) --
    pour l'utiliser comme modele de depart pour un NOUVEL element distinct (pas une
    fusion : le bloc obtenu est independant de l'original, aucun lien conserve).

    Le genre est TOUJOURS normalise (+Block/-Block -> Block, +Item -> Item, etc.),
    meme si l'original etait un patch (+). Un bloc duplique porte par definition un
    nouvel Id/Name qui n'existe nulle part ailleurs -- le prefixe '+' n'a de sens que
    pour completer une entree deja existante (souvent une entree du jeu de base,
    invisible dans les fichiers texte). Le conserver ferait du duplicata un patch
    orphelin, ignore silencieusement par le jeu ou source de plantage (deja rencontre
    concretement : IdMapping/NullReferenceException sur un item duplique)."""
    import copy as _copy
    new_block = _copy.deepcopy(block)
    new_block.dirty = True
    new_block.kind = normalized_kind(new_block.kind)
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                new_block.set(key, value)
    if remove_keys:
        for key in remove_keys:
            new_block.remove(key)
    return new_block


def detect_repeating_items(block: "EcfBlock") -> Optional[Tuple[List[str], List[str]]]:
    """Detecte les sous-blocs a structure repetitive : une suite de lignes de
    propriete dont la PREMIERE paire suit le motif 'Prefixe_N: valeur' (N
    croissant -- Name_0/Name_1, Group_0/Group_1, mais aussi Item_0/Item_1
    (LootGroups.ecf), DamageMultiplier_1/DamageMultiplier_2
    (DamageMultiplierConfig.ecf), et tout autre prefixe suivant la meme
    convention), suivie d'un jeu de parametres (param1, param2, display...)
    globalement coherent d'une ligne a l'autre.

    Retourne (param_columns, prefixes) si detecte -- param_columns : liste
    ordonnee des noms de colonnes parametres (peut etre vide) ; prefixes : liste
    ordonnee des prefixes distincts vus (ex: ['Name', 'Group'] ou ['Item'] ou
    ['DamageMultiplier']), utilisee pour peupler le choix 'Type' du formulaire
    d'ajout de ligne. Retourne None si la structure ne correspond pas (retombe
    alors sur l'affichage classique cle/valeur).

    EXTRAIT depuis gui/ecf_edit_widget.py (etait une methode d'instance
    utilisant self._ITEM_KEY_RE) pour garder une source unique de verite --
    voir EcfEditWidget._detect_repeating_items qui delegue desormais ici."""
    prop_children = [c for c in block.children if isinstance(c, EcfProperty)]
    if len(prop_children) < 2:
        return None
    matches = 0
    param_keys_seen = []
    prefixes_seen = []
    for prop in prop_children:
        if not prop.pairs:
            continue
        first_key = prop.pairs[0][0]
        m = _ITEM_KEY_RE.match(first_key) if first_key else None
        if m:
            matches += 1
            if m.group(1) not in prefixes_seen:
                prefixes_seen.append(m.group(1))
            for k, v in prop.pairs[1:]:
                if k and k not in param_keys_seen:
                    param_keys_seen.append(k)
    if matches < 2 or matches < len(prop_children) * 0.5:
        return None

    def _natural_key(k):
        m = re.search(r'(\d+)$', k)
        return (k[:m.start()] if m else k, int(m.group(1)) if m else 0)
    param_keys_seen.sort(key=_natural_key)
    return param_keys_seen, prefixes_seen


def find_first_inline_comment_for_key(doc: "EcfDocument", key: str) -> Optional[str]:
    """Repli pour les infobulles de colonne/propriete quand le glossaire
    manuel (core/ecf_header_glossary.py) ne couvre pas ce champ precis :
    cherche dans le VRAI fichier ouvert la premiere ligne ou cette cle
    apparait avec un commentaire de fin ('# ...'), et retourne ce
    commentaire tel quel -- jamais une explication inventee, uniquement
    ce que le fichier documente lui-meme a cet endroit precis. Utile pour
    les fichiers hors glossaire, ou pour des champs que le glossaire
    n'a pas encore couverts."""
    def _scan(nodes) -> Optional[str]:
        for node in nodes:
            if isinstance(node, EcfProperty) and node.comment:
                for k, _v in node.pairs:
                    if k == key:
                        cleaned = node.comment.lstrip('#').strip()
                        if cleaned:
                            return cleaned
            if isinstance(node, EcfBlock):
                if node.comment:
                    for k, _v in node.pairs:
                        if k == key:
                            cleaned = node.comment.lstrip('#').strip()
                            if cleaned:
                                return cleaned
                found = _scan(node.children)
                if found:
                    return found
        return None
    return _scan(doc.nodes)


# Motif 1bis de scan_section_groups_and_labels (voir sa docstring) : titre de
# section combine sur une seule ligne de commentaire, ex: '====Pistols HHW01==='
# -- le titre (groupe 2) doit commencer par un caractere non-separateur, pour
# ne jamais confondre une ligne de separateurs PURE avec un titre combine.
_COMBINED_SECTION_RE = re.compile(r'^([=\-*]{2,})\s*([^=\-*].*?)\s*([=\-*]{2,})$')


@dataclass
class EcfDocument:
    nodes: List[EcfNode]
    source_path: Optional[str] = None

    def render(self) -> str:
        parts = []
        for n in self.nodes:
            text = n.render()
            # Garde-fou : si un noeud precedent (typiquement un commentaire de fin de
            # fichier sans retour a la ligne final, cas reel rencontre sur un fichier
            # vanille Empyrion) ne se termine pas par un saut de ligne, on en ajoute un
            # avant le noeud suivant -- sinon les deux se collent sur la meme ligne et
            # le fichier redevient illisible au re-parsing (ex: '# }{ Item Id: ...').
            if parts and parts[-1] and not parts[-1].endswith(('\n', '\r')):
                parts.append('\n')
            parts.append(text)
        return "".join(parts)

    def extract_header_comment(self) -> str:
        """Texte brut de TOUTES les lignes (commentaires, vides, ou meme mal
        classees a cause d'un BOM en tout debut de fichier) qui precedent le tout
        premier bloc/item reel -- typiquement la documentation technique en tete des
        fichiers ECF officiels (BlocksConfig.ecf en particulier). Retire le '#' de
        debut de chaque ligne commentaire pour un affichage plus lisible."""
        lines = []
        for node in self.nodes:
            if isinstance(node, EcfBlock):
                break
            raw = getattr(node, 'raw', None)
            if raw is None:
                continue
            # Retire un BOM eventuel en tout debut de fichier (premiere ligne)
            raw = raw.lstrip('\ufeff')
            stripped = raw.strip('\r\n')
            if stripped.startswith('#'):
                cleaned = stripped.lstrip('#').strip()
                lines.append(cleaned)
            elif stripped == '':
                lines.append('')
        # Retire les lignes vides en trop (plus de 2 consecutives) pour un affichage
        # plus compact
        result = []
        blank_run = 0
        for l in lines:
            if l == '':
                blank_run += 1
                if blank_run > 1:
                    continue
            else:
                blank_run = 0
            result.append(l)
        return "\n".join(result).strip('\n')

    def scan_section_groups_and_labels(self):
        """Detecte TROIS motifs de documentation courants dans les vrais fichiers ECF :

        1. Groupe de section (3 lignes) : trois commentaires consecutifs a un seul '#'
           formant 'separateur / titre / separateur' (ex: lignes de '='), qui
           introduisent une categorie visuelle regroupant tous les blocs suivants
           jusqu'au prochain groupe (ou la fin du fichier). Exemple reel
           (Containers.ecf) :
               # ==================================================================
               # Gigas
               # ==================================================================

        1bis. Groupe de section (1 ligne combinee) : separateur, titre et separateur
           sur UNE SEULE ligne de commentaire (ex: ItemsConfig.ecf reel, signale par
           l'utilisateur -- regression du 29/08/2026 : ce motif n'etait PAS du tout
           reconnu, contrairement au motif 3-lignes). Exemple reel :
               #====Pistols HHW01===

        2. Etiquette de bloc : un commentaire a DOUBLE '#' ('##') place juste avant un
           bloc (lignes vides tolerees entre les deux), qui lui donne un nom lisible
           complementaire a son Id/Name technique. Exemple reel :
               ## GolemSwamp
               { +Container Id: 5

        Retourne (group_before_index: {index dans self.nodes: titre du groupe},
                  label_by_block_id: {id(bloc): etiquette}) -- utilise l'id Python du
        bloc comme cle plutot que le bloc lui-meme pour rester utilisable meme si le
        bloc n'est pas hashable de facon fiable."""
        def _clean(raw: str) -> str:
            return raw.strip('\r\n').lstrip('#').strip()

        def _is_separator(text: str) -> bool:
            s = text.strip()
            return len(s) >= 5 and len(set(s)) == 1 and s[0] in '=-*'

        def _combined_section_title(text: str) -> Optional[str]:
            """Motif 1bis (voir docstring) : 'sepTITREsep' sur une seule ligne, ex:
            '====Pistols HHW01==='. Le titre doit commencer par un caractere qui
            N'EST PAS lui-meme un caractere de separateur, pour ne jamais confondre
            une ligne de separateurs PURE (ex: '====================') avec un
            titre combine -- celle-ci reste geree par le motif 3-lignes existant."""
            m = _COMBINED_SECTION_RE.match(text.strip())
            return m.group(2).strip() if m else None

        nodes = self.nodes
        group_before = {}
        label_by_block_id = {}
        i, n = 0, len(nodes)
        while i < n:
            node = nodes[i]
            is_plain_comment = isinstance(node, EcfComment) and not node.raw.lstrip().startswith('##')
            if (is_plain_comment and _is_separator(_clean(node.raw)) and i + 2 < n
                    and isinstance(nodes[i + 1], EcfComment)
                    and not nodes[i + 1].raw.lstrip().startswith('##')
                    and not _is_separator(_clean(nodes[i + 1].raw))
                    and isinstance(nodes[i + 2], EcfComment)
                    and not nodes[i + 2].raw.lstrip().startswith('##')
                    and _is_separator(_clean(nodes[i + 2].raw))):
                group_before[i] = _clean(nodes[i + 1].raw)
                i += 3
                continue
            if is_plain_comment:
                combined_title = _combined_section_title(_clean(node.raw))
                if combined_title:
                    group_before[i] = combined_title
                    i += 1
                    continue
            if (isinstance(node, EcfComment) and node.raw.lstrip().startswith('##')
                    and not _is_separator(_clean(node.raw))):
                j = i + 1
                while j < n and isinstance(nodes[j], EcfBlank):
                    j += 1
                if j < n and isinstance(nodes[j], EcfBlock):
                    label_by_block_id[id(nodes[j])] = _clean(node.raw)
            i += 1
        return group_before, label_by_block_id

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


def property_lines(block: EcfBlock) -> "dict[str, List[Tuple[Optional[str], str]]]":
    """
    Regroupe les propriétés directes d'un bloc par IDENTITE DE LIGNE (sa première clé,
    ex: 'Count', 'Name_0', 'Group_1'), et non par clé simple -- voir la docstring de
    EcfProperty pour la raison (une clé comme 'param1' se répète sur plusieurs lignes
    sœurs Name_0/Name_1/..., il faut comparer/fusionner ligne entière par ligne entière).

    Inclut aussi les paires déclarées sur la ligne d'ouverture du bloc (Id, etc.).
    Partagée entre le diff et le merge.
    """
    lines: "dict[str, List[Tuple[Optional[str], str]]]" = {}
    for k, v in block.pairs:
        if k is not None:
            lines[k] = [(k, v)]
    for child in block.children:
        if isinstance(child, EcfProperty) and child.pairs:
            first_key = child.pairs[0][0]
            ident = first_key if first_key is not None else f"_ligne_{id(child)}"
            lines[ident] = child.pairs
    return lines
