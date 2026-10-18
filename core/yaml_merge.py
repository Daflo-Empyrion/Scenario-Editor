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

"""Fusion STRUCTURELLE GENERIQUE des YAML (demande 26/09/2026 : un
PDA.yaml existant etait ecrase ou copie en aveugle, seule la fusion
dediee de Sectors.yaml (core/sectors_merge.py) insérait sans ecraser).

Principe identique a sectors_merge, generalise a tout fichier YAML :
on propose UNITE PAR UNITE ce que la source apporte et qui manque a la
copie de travail --
  - une CLE RACINE absente (branche entiere inseree) ;
  - un ELEMENT d'une liste de blocs sous une cle commune aux deux
    fichiers (chapitre PDA identifie par son Id, bloc identifie par son
    Name...) -- identite = premiere cle renseignee parmi
    Id/Name/IndexName/Index/Key chez les ENFANTS de l'element ;
  - une SOUS-CLE (liste) absente d'un bloc present (YAML-009 : visible
    et cochenable, plus de skip silencieux) ;
  - les elements des SOUS-LISTES d'un bloc present des deux cotes
    (complement recursif : taches, actions, POIs... ajoutes chez la
    source dans un bloc deja connu).
Les blocs presents ne sont jamais REECRITS : seuls des ajouts y sont
inseres, et seulement si coches ; le rendu yamllite preserve commentaires
et mise en forme."""
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from core.yamllite.model import YamlBlank, YamlEntry
from core.yamllite.parser import parse_yaml_file

_IDENTITY_KEYS = ("Id", "Name", "GroupName", "ChapterTitle", "IndexName",
                  "Index", "Key")
_DETAIL_KEYS = ("Title", "Category", "Description", "Name")
_MAX_DEPTH = 12        # garde-fou anti-boucle sur des imbrications pathologiques


@dataclass
class YamlUnit:
    """Une unite fusionnable : cle racine entiere, element d'une liste de
    blocs, ou sous-cle absente d'un bloc present (YAML-009)."""
    kind: str            # 'key' | 'item' | 'subkey' | 'modified'
    root: str            # '' pour une cle top-level, sinon le chemin lisible
                         # qui porte la liste ('POIs/Random',
                         # 'Chapters/MaMission/Tasks')
    name: str            # cle (kind='key'/'subkey') ou identite de
                         # l'element (kind='item')
    detail: str = ""     # info complementaire (titre, categorie...)
    idkey: str = ""      # cle d'identite de l'element ('Id', 'ChapterTitle'...)
                         # pour un appariement exact a l'application
    path: tuple = None   # segments de navigation exacts a l'application :
                         # ('key', cle) | ('item', cle_identite, valeur) —
                         # None = derive de root (compat anciens appels)
    rows: tuple = ()     # kind='modified' : YamlLineRow (diff ligne a ligne
                         # du bloc present des deux cotes -- 07/10)


@dataclass
class YamlLineRow:
    """Une ligne du diff fin d'un bloc present des deux cotes (demande
    07/10 : « tout montrer et je choisis ») -- path designe l'ENFANT
    concerne depuis le bloc porte par l'unite (meme grammaire que
    YamlUnit.path, plus ('index', i) pour les scalaires de sequence)."""
    state: str           # 'same' | 'changed' | 'add' | 'remove'
    path: tuple          # segments de navigation vers l'enfant concerne
    before: str = ""     # texte working (ligne brute, sans fin de ligne)
    after: str = ""      # texte source
    checked: bool = False    # changed/remove : False (copie de travail
                             # prioritaire, suppression jamais implicite) ;
                             # add : True (rien ne se perd)
    replace_subtree: bool = False   # changed ou feuille vs branche : ne
                                    # passe pas par set(valeur) mais par
                                    # remplacement du sous-arbre entier



def _top_entries(doc) -> List[YamlEntry]:
    return [n for n in doc.nodes if isinstance(n, YamlEntry)]


def _child_entries(entry: YamlEntry) -> List[YamlEntry]:
    return [c for c in entry.children if isinstance(c, YamlEntry)]


def _seq_items(entry: YamlEntry) -> List[YamlEntry]:
    return [c for c in _child_entries(entry) if c.is_sequence_item]


def _scalar(entry: YamlEntry, key: str) -> str:
    for c in _child_entries(entry):
        if c.key == key and c.value:
            return c.value.strip().strip("'\"")
    return ""


def _identity(entry: YamlEntry) -> Optional[Tuple[str, str]]:
    """(cle, valeur) d'identite d'un element de liste, ou None. Convention
    yamllite : '- ChapterTitle: tok' porte la cle sur l'item LUI-MEME
    (key/value), ses suites sont des enfants. Genericite (vecu 26/09 : les
    chapitres RE2 du PDA.yaml commencent par ChapterTitle, sans Id) :
    TOUTE item '- Cle: valeur' est identifiable par sa propre premiere
    cle ; la boucle _IDENTITY_KEYS ne sert qu'aux rares listes dont
    l'identite est une SOUS-cle de l'item."""
    if entry.is_sequence_item and entry.key and entry.value:
        return entry.key, entry.value.strip().strip("'\"")
    for k in _IDENTITY_KEYS:
        v = _scalar(entry, k)
        if v:
            return k, v
    return None


def _detail(entry: YamlEntry) -> str:
    for k in _DETAIL_KEYS:
        v = entry.value.strip().strip("'\"") \
            if (entry.is_sequence_item and entry.key == k and entry.value) \
            else _scalar(entry, k)
        if v:
            return v
    for c in _child_entries(entry):
        if c.key and c.value:
            return f"{c.key}: {_strip_quotes(c.value)}"
    return entry.value.strip() if entry.value else ""


_LIST_SUMMARY_LIMIT = 5


def _list_summary(entry: YamlEntry) -> str:
    """Tous les noms des elements d'une liste de blocs (ex : presets d'un
    playfield : 'Empty, GrsDnse_04 …'), plafonnee -- permet de voir d'un
    coup d'oeil si la cle n'apporte que le preset 'off' ou de la vraie
    configuration, sans ouvrir le fichier."""
    names = [_strip_quotes(ident[1]) for ident in
             (_identity(item) for item in _seq_items(entry))
             if ident is not None]
    if not names:
        return ""
    shown = ", ".join(names[:_LIST_SUMMARY_LIMIT])
    if len(names) > _LIST_SUMMARY_LIMIT:
        shown += f" … (+{len(names) - _LIST_SUMMARY_LIMIT})"
    return shown


def _strip_quotes(v: str) -> str:
    return v.strip().strip("'\"")


def _line_text(entry: YamlEntry) -> str:
    """Texte brut de la ligne d'une entree (affichage du diff fin) ; les
    chaines multilignes entre guillemets sont resumees premiere ligne +
    nombre de lignes de suite."""
    text = (entry.raw or "").rstrip("\r\n")
    if entry.quoted_continuation_raw:
        extra = entry.quoted_continuation_raw.count("\n") + 1
        text = f"{text}  … (+{extra} lignes)"
    return text


def _key_with_attached(children: List[YamlEntry], key: str):
    """(entree, items attaches) pour une cle enfant. PIEGE du format
    vertical Empyrion : une liste a indentation EGALE ('Coordinates:'
    suivi de '- 0.5' au meme niveau) donne des items FRERES de l'entree
    chez leur parent commun, pas des enfants de la cle (le parseur
    n'attache que ce qui est strictement plus indenté) ; ils suivent
    l'entree jusqu'au prochain non-seq."""
    for index, child in enumerate(children):
        if not child.is_sequence_item and child.key == key:
            attached = []
            for sibling in children[index + 1:]:
                if sibling.is_sequence_item:
                    attached.append(sibling)
                else:
                    break
            return child, attached
    return None, []


def _seq_items_attached(owner: YamlEntry, key: str) -> List[YamlEntry]:
    """Tous les items de sequence d'une sous-liste, qu'elle soit INDENTEE
    (enfants de la cle) ou VERTICALE (freres attaches chez le parent)."""
    child, attached = _key_with_attached(_child_entries(owner), key)
    if child is None:
        return []
    return _seq_items(child) or attached


def _scalar_items(items: List[YamlEntry]) -> bool:
    return bool(items) and all(i.key is None for i in items)


def _identity_index(children: list, target) -> int:
    """Position par IDENTITE : YamlEntry.__eq__ compare par VALEUR, deux
    lignes identiques sont donc value-egales — index()/remove_entry()
    prendraient le PREMIER doublon au lieu de l'objet vise."""
    for index, child in enumerate(children):
        if child is target:
            return index
    return -1


def _identity_prune(children: list, targets) -> None:
    drop = {id(target) for target in targets}
    children[:] = [child for child in children if id(child) not in drop]


def _diff_scalar_seq(w_items: List[YamlEntry], s_items: List[YamlEntry],
                     path: tuple, seg_at) -> List[YamlLineRow]:
    """Liste de SCALAIRES ('- valeur') : TOUTES les lignes affichees,
    AUCUN appariement (demande 07/10 : l'appariement — par index puis
    par valeur — donnait des « identique » TROMPEURS quand les
    commentaires differaient — « # 6 - Trading Stations » n'est pas un
    « # 6 - Alien » — et empechait de choisir ligne par ligne).

    Chaque ligne working = un candidat SUPPRESSION (colonne Avant,
    DECOCHÉ) ; chaque ligne source = un candidat AJOUT (colonne Apres,
    cochee SAUF si sa valeur existe deja telle quelle dans la liste
    working — l'ajouter la dupliquerait). Remplacer une valeur = cocher
    l'ajout ET la suppression ; tout reste cochable librement.
    seg_at(i) fabrique le segment de navigation de l'item i ('index'
    pour une liste indente, 'sib' pour une liste verticale)."""
    rows: List[YamlLineRow] = []
    w_values = {w.value for w in w_items}
    for i, w in enumerate(w_items):
        rows.append(YamlLineRow("remove", path + (seg_at(i),),
                                _line_text(w), ""))
    for i, s in enumerate(s_items):
        rows.append(YamlLineRow("add", path + (seg_at(i),), "",
                                _line_text(s),
                                checked=s.value not in w_values))
    return rows


def _diff_rows(w_entry: YamlEntry, s_entry: YamlEntry,
               path: tuple = (), depth: int = 0) -> List[YamlLineRow]:
    """Diff fin ENTRE DEUX BLOCS APPARIES (meme cle / meme identite) --
    demande 07/10 : « tout montrer et je choisis » sur SolarSystemConfig.

    - 'same'    : ligne identique (info, jamais appliquee) ;
    - 'changed' : valeur differente -- cochee = la SOURCE remplace le
                  working (copie de travail prioritaire par defaut) ;
    - 'add'     : presente source seul -- cochee (rien ne se perd) ;
    - 'remove'  : presente working seul (miroir) -- DECOCHEE (une
                  suppression n'est jamais implicite).

    Perimetre : les enfants MAPPING (par cle, recursif dans les
    sous-mappings) et les listes de SCALAIRES, indentees OU verticales
    (items freres de la cle, format Empyrion). Les listes de blocs a
    identite ('- Cle: valeur') ne sont PAS traitees ici : leur
    appariement element par element appartient a _scan_list (unites
    'item' et 'modified' par element) -- evite le double emploi."""
    rows: List[YamlLineRow] = []
    if depth > _MAX_DEPTH:
        return rows
    w_children = _child_entries(w_entry)
    s_children = _child_entries(s_entry)
    for s_child in [c for c in s_children
                    if not c.is_sequence_item and c.key is not None]:
        key = s_child.key
        seg_path = path + (("key", key),)
        w_child, w_attached = _key_with_attached(w_children, key)
        _ign, s_attached = _key_with_attached(s_children, key)
        if w_child is None:
            if s_attached:
                # sous-liste VERTICALE entiere : invisible des unites
                # 'subkey' (elles ne voient que l'indente) -> une ligne
                # d'ajout couvrant l'entree ET ses items
                after = _line_text(s_child) + \
                    f"  … (+{len(s_attached)} lignes)"
                rows.append(YamlLineRow("add", seg_path, "", after,
                                        checked=True))
            elif _seq_items(s_child):
                continue        # sous-liste indente entiere : unite 'subkey'
            else:
                rows.append(YamlLineRow("add", seg_path, "",
                                        _line_text(s_child), checked=True))
            continue
        if s_attached and w_attached:
            # deux listes verticales : scalaires apparies par index (les
            # listes de blocs a identite restent a _scan_list, comme avant)
            # -- segment 'sib' SEUL : l'item se resout depuis le PARENT
            # (frere de la cle), pas depuis l'entree de la cle
            if _scalar_items(w_attached) and _scalar_items(s_attached):
                rows.extend(_diff_scalar_seq(
                    w_attached, s_attached, path,
                    lambda i, k=key: ("sib", k, i)))
            continue
        w_seq, s_seq = _seq_items(w_child), _seq_items(s_child)
        if w_seq and s_seq:
            if _scalar_items(w_seq) and _scalar_items(s_seq):
                rows.extend(_diff_scalar_seq(
                    w_seq, s_seq, seg_path, lambda i: ("index", i)))
            # liste de blocs : appariement element par element dans
            # _scan_list (niveau suivant) -- rien a emettre ici
            continue
        if not w_seq and not s_seq and not s_attached and not w_attached:
            if w_child.children and s_child.children:
                rows.extend(_diff_rows(w_child, s_child, seg_path,
                                       depth + 1))
                continue
            # comparaison SEMANTIQUE (valeur + commentaire de fin de
            # ligne) : le rendu apres application (deux espaces devant
            # le commentaire) ne doit pas re-proposer la meme ligne
            same = (w_child.value == s_child.value
                    and w_child.comment == s_child.comment)
            if same:
                rows.append(YamlLineRow("same", seg_path,
                                        _line_text(w_child),
                                        _line_text(s_child)))
                continue
            rows.append(YamlLineRow(
                "changed", seg_path, _line_text(w_child),
                _line_text(s_child),
                replace_subtree=bool(w_child.children or s_child.children)))
            continue
        # feuille vs branche, vertical vs indente : remplacement du
        # sous-arbre working (l'entree + ses items attaches) par le clone
        # source -- set(valeur) ecraserait la structure
        before = _line_text(w_child)
        after = _line_text(s_child)
        if w_attached:
            before += f"  … (+{len(w_attached)} lignes)"
        if s_attached:
            after += f"  … (+{len(s_attached)} lignes)"
        rows.append(YamlLineRow("changed", seg_path, before, after,
                                replace_subtree=True))
    s_keys = {c.key for c in s_children if not c.is_sequence_item}
    for w_child in [c for c in w_children
                    if not c.is_sequence_item and c.key is not None]:
        key = w_child.key
        if key in s_keys:
            continue
        w_found, w_attached = _key_with_attached(w_children, key)
        before = _line_text(w_found)
        if w_attached:
            before += f"  … (+{len(w_attached)} lignes)"
        rows.append(YamlLineRow("remove", path + (("key", key),),
                                before, ""))
    return rows


def _modified_summary(rows: List[YamlLineRow]) -> str:
    """Detail compact et NEUTRE (affiche dans les deux langues) :
    « 3↔ 1+ 2− » = 3 modifiees, 1 ajoutee, 2 supprimables."""
    chg = sum(1 for r in rows if r.state == "changed")
    add = sum(1 for r in rows if r.state == "add")
    rem = sum(1 for r in rows if r.state == "remove")
    return f"{chg}↔ {add}+ {rem}−"


def _child_by_seg(owner: YamlEntry, seg: tuple) -> Optional[YamlEntry]:
    """Enfant designe par un segment de navigation depuis owner. 'sib' =
    i-eme item d'une liste VERTICALE (freres suivant la cle k chez le
    meme parent) -- jamais segment intermediaire (un scalaire n'a pas
    d'enfants)."""
    children = _child_entries(owner)
    if seg[0] == "key":
        return next((c for c in children
                     if not c.is_sequence_item and c.key == seg[1]), None)
    if seg[0] == "item":
        return next((c for c in children
                     if c.is_sequence_item
                     and _same_identity(_identity(c), seg[1], seg[2])), None)
    if seg[0] == "sib":
        _child, attached = _key_with_attached(children, seg[1])
        return attached[seg[2]] if 0 <= seg[2] < len(attached) else None
    seq = [c for c in children if c.is_sequence_item]
    return seq[seg[1]] if 0 <= seg[1] < len(seq) else None


def _source_chain(owner: YamlEntry, seg: tuple) -> List[YamlEntry]:
    """Chaine source a cloner pour un segment : l'entree + ses items
    attaches si le segment est une cle porteuse de liste verticale,
    sinon l'entree seule."""
    child = _child_by_seg(owner, seg)
    if child is None:
        return []
    if seg[0] == "key":
        _found, attached = _key_with_attached(_child_entries(owner), seg[1])
        return [child] + attached
    return [child]


def _attached_of(owner: YamlEntry, seg: tuple) -> List[YamlEntry]:
    if seg[0] != "key":
        return []
    _found, attached = _key_with_attached(_child_entries(owner), seg[1])
    return attached


def _remove_sort_key(row: YamlLineRow) -> int:
    seg = row.path[-1]
    if seg[0] == "index":
        return -seg[1]
    if seg[0] == "sib":
        return -seg[2]
    return 0


def _apply_line_row(w_target: YamlEntry, s_target: YamlEntry,
                    row: YamlLineRow, eol: str) -> bool:
    """Applique UNE ligne cochee d'une unite 'modified' ; False = rien
    fait (idempotence, absent, ambiguous)."""
    w_owner, s_owner = w_target, s_target
    for seg in row.path[:-1]:
        w_owner = _child_by_seg(w_owner, seg)
        s_owner = _child_by_seg(s_owner, seg)
        if w_owner is None or s_owner is None:
            return False
    seg = row.path[-1]
    if row.state == "changed":
        w_child = _child_by_seg(w_owner, seg)
        s_child = _child_by_seg(s_owner, seg)
        if w_child is None or s_child is None:
            return False
        if row.replace_subtree:
            chain = _source_chain(s_owner, seg)
            # retire aussi les items attaches du working (liste
            # verticale remplacee par une autre structure)
            _identity_prune(w_owner.children, _attached_of(w_owner, seg))
            position = _identity_index(w_owner.children, w_child)
            if position < 0:
                return False
            w_owner.children[position] = _copy_entry(chain[0])
            for extra in reversed([_copy_entry(c) for c in chain[1:]]):
                w_owner.children.insert(position + 1, extra)
            return True
        if w_child.is_sequence_item:
            w_child.set_own_value(s_child.value)
        else:
            w_child.value = s_child.value
            w_child.comment = s_child.comment     # sinon jamais idempotent
        w_child.dirty = True
        return True
    if row.state == "add":
        s_item = _child_by_seg(s_owner, seg)
        if s_item is None:
            return False
        if seg[0] == "sib":
            # liste verticale : insertion APRES le dernier item attache
            # (appendir en fin de bloc la ferait atterrir sous une autre
            # cle). Choix explicite de l'utilisateur : pas de garde par
            # valeur — s'il coche une ligne deja presente, il la veut.
            anchor, _att = _key_with_attached(
                _child_entries(w_owner), seg[1])
            attached = _seq_items_attached(w_owner, seg[1])
            last = attached[-1] if attached else anchor
            last_index = _identity_index(w_owner.children, last)
            if last_index < 0:
                return False
            w_owner.children.insert(last_index + 1, _copy_entry(s_item))
            return True
        if seg[0] == "index":
            w_owner.children.append(_copy_entry(s_item))  # fin de liste
            return True
        # sous-cle / enfant mapping : l'entree + ses items attaches
        # (sous-liste VERTICALE entiere — les indente suivent les
        # unites 'subkey', ce bloc ne les voit jamais)
        chain = _source_chain(s_owner, seg)
        _ensure_blank_before(w_owner.children, eol)
        for entry in chain:
            w_owner.children.append(_copy_entry(entry))
        return True
    if row.state == "remove":
        if seg[0] == "key":
            dupes = [c for c in _child_entries(w_owner)
                     if not c.is_sequence_item and c.key == seg[1]]
            if len(dupes) > 1:
                return False        # cle dupliquee : suppression ambiguë
        targets = [c for c in _source_chain(w_owner, seg)
                   if any(c is node for node in w_owner.children)]
        if not targets:
            return False
        _identity_prune(w_owner.children, targets)
        return True
    return False


def yaml_files_identical(working_yaml: Path, source_yaml: Path) -> bool:
    try:
        a = Path(working_yaml).read_bytes()
        b = Path(source_yaml).read_bytes()
    except OSError:
        return False
    return a == b


def analyze_yaml_merge(working_yaml: Path,
                       source_yaml: Path) -> List[YamlUnit]:
    """Unites du YAML SOURCE absentes du YAML de la copie de travail :
    cles racines entieres + elements absents des listes de blocs sous une
    cle commune. Fichiers identiques ou illisibles -> []."""
    working_yaml, source_yaml = Path(working_yaml), Path(source_yaml)
    if yaml_files_identical(working_yaml, source_yaml):
        return []
    try:
        working_doc = parse_yaml_file(working_yaml)
        source_doc = parse_yaml_file(source_yaml)
    except Exception:                        # noqa: BLE001 - yaml illisible
        return []
    working_top = _top_entries(working_doc)
    source_top = _top_entries(source_doc)

    def _usable(entries: List[YamlEntry]) -> bool:
        # une ligne binaire/illisible donne une pseudo-entree key=None
        # (fallback du parseur) : pas de fusion structurelle fiable,
        # l'appelant proposera le remplacement explicite
        return any(e.key is not None or e.is_sequence_item for e in entries)

    if not _usable(working_top) or not _usable(source_top):
        return []
    units: List[YamlUnit] = []
    working_keys = {e.key: e for e in working_top if not e.is_sequence_item}
    source_keys = {e.key: e for e in source_top if not e.is_sequence_item}

    def _modified_unit(root_label: str, name: str, idkey: str,
                       w_e: YamlEntry, s_e: YamlEntry, path: tuple) -> None:
        """Bloc present des deux cotes avec des LIGNES differentes ->
        unite 'modified' (demande 07/10 : voir et choisir ligne a ligne ;
        avant : differences invisibles, seule l'absence etait proposee)."""
        rows = _diff_rows(w_e, s_e)
        if not any(r.state != "same" for r in rows):
            return
        units.append(YamlUnit(kind="modified", root=root_label, name=name,
                              idkey=idkey,
                              detail=_modified_summary(rows),
                              path=path, rows=tuple(rows)))

    def _scan_list(root_label: str, wlist: Optional[YamlEntry],
                   slist: YamlEntry, path: tuple, depth: int) -> None:
        """Elements absents d'une liste de blocs -> unites 'item' ; un
        element PRESENT des deux cotes est explore recursivement (taches,
        actions... ajoutees chez la source, vecu 06/10 : mission PDA
        completee invisible) et son DIFF FIN devient une unite
        'modified' si des lignes different."""
        if wlist is None or depth > _MAX_DEPTH:
            return
        working_ids = {_identity(c) for c in _seq_items(wlist)}
        # listes a identites NON uniques dans la source (ex : plusieurs
        # items commencant par la meme '- Cle: valeur') : rien a proposer
        # pour ces items, l'appariement a l'application ne serait pas fiable
        source_counts = {}
        for c in _seq_items(slist):
            ident = _identity(c)
            if ident is not None:
                source_counts[ident] = source_counts.get(ident, 0) + 1
        for item in _seq_items(slist):
            ident = _identity(item)
            if ident is None or source_counts[ident] > 1:
                continue
            if ident not in working_ids:
                units.append(YamlUnit(kind="item", root=root_label,
                                      name=ident[1], detail=_detail(item),
                                      idkey=ident[0], path=path))
                continue
            w_item = next((c for c in _seq_items(wlist)
                           if _identity(c) == ident), None)
            if w_item is None:
                continue
            item_path = path + (("item", ident[0], ident[1]),)
            _modified_unit(f"{root_label}/{ident[1]}", ident[1], ident[0],
                           w_item, item, item_path)
            _scan_children(f"{root_label}/{ident[1]}", w_item, item,
                           item_path, depth + 1)

    def _scan_children(root_label: str, w_entry: YamlEntry,
                       s_entry: YamlEntry, path: tuple, depth: int) -> None:
        """Sous-listes d'un bloc : absentes de la working -> unite
        'subkey' VISIBLE et cochenable (YAML-009 — avant : skip
        silencieux « convention de l'hote ») ; presentes -> _scan_list."""
        if depth > _MAX_DEPTH:
            return
        for sub in _child_entries(s_entry):
            if sub.is_sequence_item or sub.key is None:
                continue
            if not _seq_items(sub):
                continue
            w_sub = next((c for c in _child_entries(w_entry)
                          if not c.is_sequence_item and c.key == sub.key),
                         None)
            if w_sub is None:
                units.append(YamlUnit(kind="subkey", root=root_label,
                                      name=sub.key,
                                      detail=_list_summary(sub),
                                      path=path))
                continue
            sub_path = path + (("key", sub.key),)
            _modified_unit(f"{root_label}/{sub.key}", sub.key, "",
                           w_sub, sub, sub_path)
            _scan_list(f"{root_label}/{sub.key}", w_sub, sub,
                       sub_path, depth + 1)

    for key, s_entry in source_keys.items():
        w_entry = working_keys.get(key)
        if w_entry is None:
            units.append(YamlUnit(kind="key", root="", name=key,
                                  detail=_list_summary(s_entry)
                                  or _detail(s_entry)))
            continue
        _modified_unit(key, key, "", w_entry, s_entry, (("key", key),))
        _scan_list(key, w_entry, s_entry, (("key", key),), 0)
        _scan_children(key, w_entry, s_entry, (("key", key),), 0)
    # document racine = liste de blocs (pas de mappings top-level) : meme
    # comparaison au niveau du document
    source_items = [e for e in source_top if e.is_sequence_item]
    working_items = [e for e in working_top if e.is_sequence_item]
    if source_items and (working_items or not source_keys):
        working_ids = {_identity(c) for c in working_items}
        for item in source_items:
            ident = _identity(item)
            if ident is None:
                continue
            if ident in working_ids:
                w_item = next((c for c in working_items
                               if _identity(c) == ident), None)
                item_path = (("item", ident[0], ident[1]),)
                _modified_unit(ident[1], ident[1], ident[0],
                               w_item, item, item_path)
                _scan_children(ident[1], w_item, item, item_path, 0)
                continue
            if working_items:
                units.append(YamlUnit(kind="item", root="", name=ident[1],
                                      detail=_detail(item)))
    return units


def _same_identity(ident: Optional[Tuple[str, str]], idkey: str,
                   name: str) -> bool:
    if ident is None:
        return False
    if idkey and ident[0] != idkey:
        return False
    return _strip_quotes(ident[1]).casefold() == name.casefold()


def _eol_of(entries: List[YamlEntry]) -> str:
    for e in entries:
        if e.eol:
            return e.eol
    return "\r\n"


def _ensure_blank_before(children: List, eol: str) -> None:
    if children and not isinstance(children[-1], YamlBlank):
        children.append(YamlBlank(raw=eol))


def _copy_entry(entry: YamlEntry) -> YamlEntry:
    return copy.deepcopy(entry)


def _segments(unit: YamlUnit) -> tuple:
    """Segments de navigation d'une unite : son path exact, ou derive de
    root (cles uniquement) pour les unites sans path (compat)."""
    if unit.path is not None:
        return unit.path
    return tuple(("key", s) for s in unit.root.split("/") if s)


def _walk(entries: List[YamlEntry], segments: tuple) -> Optional[YamlEntry]:
    """Descend des segments ('key', cle) / ('item', cle_identite, valeur)
    depuis des entrees top-level ; retourne l'entree atteinte ou None."""
    cur_list = entries
    cur = None
    for seg in segments:
        if seg[0] == "key":
            cur = next((e for e in cur_list
                        if not e.is_sequence_item and e.key == seg[1]), None)
        else:
            cur = next((e for e in cur_list
                        if e.is_sequence_item
                        and _same_identity(_identity(e), seg[1], seg[2])),
                       None)
        if cur is None:
            return None
        cur_list = _child_entries(cur)
    return cur


def apply_yaml_units(working_yaml: Path, source_yaml: Path,
                     units: List[YamlUnit]) -> int:
    """Insere les unites cochees dans le YAML de la copie de travail
    (rendu yamllite : commentaires preserves) et ecrit en atomique ;
    retourne le nombre d'unites reellement inserees. Idempotent : une
    identite deja presente est ignoree. L'appelant gere backup et undo
    (capture_file AVANT l'appel)."""
    if not units:
        return 0
    working_doc = parse_yaml_file(working_yaml)
    source_doc = parse_yaml_file(source_yaml)
    working_top = _top_entries(working_doc)
    source_top = _top_entries(source_doc)
    eol = _eol_of(working_top)
    applied = 0
    for unit in units:
        if unit.kind == "modified":
            w_target = _walk(working_top, _segments(unit))
            s_target = _walk(source_top, _segments(unit))
            if w_target is None or s_target is None:
                continue
            # ajouts + modifications d'abord (positions d'origine), puis
            # suppressions en index DECROISSANT (les indexes des scalaires
            # de sequence ne doivent pas glisser pendant le retrait)
            actionable = [r for r in unit.rows
                          if getattr(r, "checked", False) and r.state != "same"]
            ordered = ([r for r in actionable if r.state != "remove"]
                       + sorted((r for r in actionable
                                 if r.state == "remove"),
                                key=_remove_sort_key))
            for row in ordered:
                if _apply_line_row(w_target, s_target, row, eol):
                    applied += 1
            continue
        if unit.kind == "key":
            src = next((e for e in source_top
                        if not e.is_sequence_item and e.key == unit.name),
                       None)
            already = any(not e.is_sequence_item and e.key == unit.name
                          for e in working_top)
            if src is None or already:
                continue
            clone = _copy_entry(src)
            _ensure_blank_before(working_doc.nodes, eol)
            working_doc.nodes.append(clone)
            working_top.append(clone)
            applied += 1
            continue
        if unit.kind == "subkey":
            # sous-liste absente d'un bloc present (YAML-009) : le path
            # designe le bloc PARENT, on y clone la sous-cle entiere
            w_parent = _walk(working_top, _segments(unit))
            s_parent = _walk(source_top, _segments(unit))
            if w_parent is None or s_parent is None:
                continue
            already = any(not c.is_sequence_item and c.key == unit.name
                          for c in _child_entries(w_parent))
            if already:
                continue
            src = next((c for c in _child_entries(s_parent)
                        if not c.is_sequence_item and c.key == unit.name),
                       None)
            if src is None:
                continue
            clone = _copy_entry(src)
            _ensure_blank_before(w_parent.children, eol)
            w_parent.children.append(clone)
            applied += 1
            continue
        if unit.root == "" and unit.path is None:
            w_items = [e for e in working_top if e.is_sequence_item]
            s_items = [e for e in source_top if e.is_sequence_item]
            attach = working_doc.nodes
        else:
            w_list = _walk(working_top, _segments(unit))
            s_list = _walk(source_top, _segments(unit))
            w_items = _seq_items(w_list) if w_list is not None else []
            s_items = _seq_items(s_list) if s_list is not None else []
            attach = w_list.children if w_list is not None else None
        if not s_items or attach is None:
            continue
        src = next((c for c in s_items
                    if _same_identity(_identity(c), unit.idkey, unit.name)),
                   None)
        if src is None:
            continue
        already = any(_same_identity(_identity(c), unit.idkey, unit.name)
                      for c in w_items)
        if already:
            continue
        clone = _copy_entry(src)
        _ensure_blank_before(attach, eol)
        attach.append(clone)
        applied += 1
    if applied:
        from core.fsutil import atomic_write_text
        atomic_write_text(working_yaml, working_doc.render())
    return applied
