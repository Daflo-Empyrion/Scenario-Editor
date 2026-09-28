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
    Id/Name/IndexName/Index/Key chez les ENFANTS de l'element.
Les elements presents des deux cotes ne sont JAMAIS modifies (copie de
travail prioritaire, comme la fusion ECF en mode 'properties') ; le
rendu yamllite preserve commentaires et mise en forme."""
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from core.yamllite.model import YamlBlank, YamlEntry
from core.yamllite.parser import parse_yaml_file

_IDENTITY_KEYS = ("Id", "Name", "GroupName", "ChapterTitle", "IndexName",
                  "Index", "Key")
_DETAIL_KEYS = ("Title", "Category", "Description", "Name")


@dataclass
class YamlUnit:
    """Une unite fusionnable : cle racine entiere ou element d'une liste
    de blocs."""
    kind: str            # 'key' | 'item'
    root: str            # '' pour une cle top-level, sinon la cle qui porte la liste
    name: str            # cle (kind='key') ou identite de l'element (kind='item')
    detail: str = ""     # info complementaire (titre, categorie...)
    idkey: str = ""      # cle d'identite de l'element ('Id', 'ChapterTitle'...)
                         # pour un appariement exact a l'application


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

    def _scan_list(root: str, wlist: Optional[YamlEntry],
                   slist: YamlEntry) -> None:
        if wlist is None:
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
                units.append(YamlUnit(kind="item", root=root,
                                      name=ident[1], detail=_detail(item),
                                      idkey=ident[0]))

    for key, s_entry in source_keys.items():
        w_entry = working_keys.get(key)
        if w_entry is None:
            units.append(YamlUnit(kind="key", root="", name=key,
                                  detail=_list_summary(s_entry)
                                  or _detail(s_entry)))
            continue
        _scan_list(key, w_entry, s_entry)
    # document racine = liste de blocs (pas de mappings top-level) : meme
    # comparaison au niveau du document
    source_items = [e for e in source_top if e.is_sequence_item]
    working_items = [e for e in working_top if e.is_sequence_item]
    if source_items and (working_items or not source_keys):
        working_ids = {_identity(c) for c in working_items}
        for item in source_items:
            ident = _identity(item)
            if ident is not None and ident not in working_ids \
                    and working_items:
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
        if unit.root:
            w_list = next((e for e in working_top
                           if not e.is_sequence_item and e.key == unit.root),
                          None)
            s_list = next((e for e in source_top
                           if not e.is_sequence_item and e.key == unit.root),
                          None)
            w_items = _seq_items(w_list) if w_list is not None else []
            s_items = _seq_items(s_list) if s_list is not None else []
            attach = w_list.children if w_list is not None else None
        else:
            w_items = [e for e in working_top if e.is_sequence_item]
            s_items = [e for e in source_top if e.is_sequence_item]
            attach = working_doc.nodes
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
