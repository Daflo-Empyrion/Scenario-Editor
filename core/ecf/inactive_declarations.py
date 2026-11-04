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

"""Declarations ECF desactivees (commentees) -- module issu de la
manipulation manuelle du 04/11/2026 sur ItemsConfig/BlocksConfig :

- une declaration commentee dont le NOM n'existe plus parmi les declarations
  actives est REACTIVEE : son bloc est decommente et ajoute en fin de
  fichier ; si son Id est deja pris, l'Id est abandonne (le nom suffit) ;
- les declarations commentees qui ont deja un homonyme actif sont
  SUPPRIMEES avec leur en-tete de fusion (CONFLIT D'ID / DOUBLON DE NOM),
  afin qu'une fusion ulterieure ne les reintroduise pas.

Le module ne touche qu'aux lignes commentees : les declarations actives sont
lues (noms/Ids) mais jamais modifiees. `apply_plan` verifie le resultat en
reparant le texte AVANT ecriture et refuse la moindre perte de nom actif.
"""
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from core import fsutil

from .parser import parse_ecf_file, parse_ecf_text

# Bloc de premier niveau commente : '# { +Item ...', '# { Block ...'
_DECL_RE = re.compile(r'^#\s*\{\s*(\+?)(Item|Block)\b', re.IGNORECASE)
# En-tete de fusion place juste avant le bloc desactive
_HEADER_RE = re.compile(r"^#\s*(DOUBLON DE NOM|CONFLIT D'ID)\b")
_ID_RE = re.compile(r'\s*\bId:\s*(\d+)\s*,?')


@dataclass
class InactiveDeclaration:
    """Une declaration de premier niveau entierement commentee."""
    kind: str                  # '+Item', 'Item', '+Block', 'Block'
    name: str
    id: Optional[str]
    text: str                  # lignes decommenteES, fins de ligne comprises
    first_line: int            # 1-based, ligne '#' d'ouverture
    last_line: int
    header: Optional[str] = None


@dataclass
class InactivePlan:
    """Etat d'un fichier avant application (lecture seule)."""
    path: Path
    active_names: Set[str]
    active_ids: Set[str]
    inactive: List[InactiveDeclaration] = field(default_factory=list)
    to_restore: List[InactiveDeclaration] = field(default_factory=list)
    to_drop: List[InactiveDeclaration] = field(default_factory=list)
    id_dropped: List[str] = field(default_factory=list)

    @property
    def nothing_to_do(self) -> bool:
        return not self.inactive


@dataclass
class ApplyResult:
    restored: int
    dropped: int
    headers_removed: int
    id_dropped: int
    backup: Optional[Path]


def _uncomment(line: str) -> str:
    """Retire le '#' de commentaire de bloc (un seul niveau) en gardant les
    '#' de proprietes commentees a l'interieur."""
    body = line.rstrip('\r\n')
    eol = line[len(body):]
    return re.sub(r'^# ?', '', body) + eol


def _field(lines: List[str], key: str) -> Optional[str]:
    m = re.search(rf'\b{key}:\s*([^,}}\r\n]+)', '\n'.join(lines))
    return m.group(1).strip() if m else None


def _active_declarations(path: Path):
    """(noms, ids) des declarations Item/Block de premier niveau actives."""
    doc = parse_ecf_file(path)
    names: Set[str] = set()
    ids: Set[str] = set()
    for node in doc.nodes:
        kind = getattr(node, 'kind', '').lstrip('+-').strip().lower()
        if kind not in ('item', 'block'):
            continue
        name = (node.get_property('Name') or '').strip()
        if name:
            names.add(name)
        id_val = node.get('Id')
        if id_val:
            ids.add(id_val.strip())
    return doc, names, ids


def _extract_blocks(lines: List[str]) -> List[InactiveDeclaration]:
    """Blocs Item/Block de premier niveau entierement commentes. Les lignes
    vides internes sont tolerees ; toute autre ligne non commentee interrompt
    la lecture (bloc malforme = ignore, jamais devine)."""
    out: List[InactiveDeclaration] = []
    i = 0
    while i < len(lines):
        if not _DECL_RE.match(lines[i]):
            i += 1
            continue
        depth = 0
        j = i
        end = None
        while j < len(lines):
            body = lines[j].strip()
            if not body:
                j += 1
                continue
            if not body.startswith('#'):
                break
            depth += body[1:].count('{') - body[1:].count('}')
            if depth == 0:
                end = j
                break
            j += 1
        if end is None:
            i = j + 1                   # bloc malforme : ne pas rescanner dedans
            continue
        raw = lines[i:end + 1]
        body_lines = [_uncomment(l) for l in raw]
        name = _field([body_lines[0]], 'Name') or ''
        id_val = _ID_RE.search(body_lines[0])
        header = lines[i - 1] if i > 0 and _HEADER_RE.match(lines[i - 1]) else None
        if name:
            match = _DECL_RE.match(lines[i])
            out.append(InactiveDeclaration(
                kind=('+' if match.group(1) else '') + match.group(2),
                name=name, id=id_val.group(1) if id_val else None,
                text=''.join(body_lines), first_line=i + 1,
                last_line=end + 1, header=header))
        i = end + 1
    return out


def scan_file(path) -> InactivePlan:
    """Analyse (sans ecrire) les declarations inactives d'un fichier ECF."""
    path = Path(path)
    lines = path.read_bytes().decode('utf-8', errors='surrogateescape').splitlines(keepends=True)
    _doc, active_names, active_ids = _active_declarations(path)
    plan = InactivePlan(path=path, active_names=active_names, active_ids=active_ids)
    plan.inactive = _extract_blocks(lines)
    seen: Set[str] = set()
    restore_ids: Set[str] = set(active_ids)
    for decl in plan.inactive:
        if decl.name in active_names or decl.name in seen:
            plan.to_drop.append(decl)
            continue
        seen.add(decl.name)
        plan.to_restore.append(decl)
        if decl.id and decl.id in restore_ids:
            plan.id_dropped.append(decl.name)
        if decl.id:
            restore_ids.add(decl.id)
    return plan


def apply_plan(plan: InactivePlan, remove_dropped: bool = True) -> ApplyResult:
    """Applique le plan : reactive les declarations manquantes (Id abandonne
    s'il est deja pris) et, si `remove_dropped`, supprime TOUTES les
    declarations inactives avec leur en-tete de fusion.

    Le texte final est re-parse et compare AVANT ecriture : toute perte de
    nom actif ou toute reactivation manquante leve RuntimeError, le fichier
    reste intact."""
    path = Path(plan.path)
    if plan.nothing_to_do:
        return ApplyResult(0, 0, 0, 0, None)

    raw = path.read_bytes().decode('utf-8', errors='surrogateescape')
    lines = raw.splitlines(keepends=True)
    eol = '\r\n' if lines and lines[0].endswith('\r\n') else '\n'

    # 1) suppression des blocs inactifs (et de leur en-tete) -- du bas vers
    #    le haut. Les blocs reactives sont toujours retires de leur place
    #    d'origine (ils sont recopies decommentes en fin de fichier).
    removed = plan.inactive if remove_dropped else plan.to_restore
    ranges = []
    for decl in removed:
        start = decl.first_line - 1
        if decl.header is not None:
            start -= 1
        ranges.append((start, decl.last_line - 1))
    removed_headers = sum(1 for d in removed if d.header is not None)
    for start, end in sorted(ranges, reverse=True):
        del lines[start:end + 1]

    # 2) en-tetes orphelins restes au-dessus d'une declaration ACTIVE
    i = 0
    while i < len(lines):
        if not _HEADER_RE.match(lines[i]):
            i += 1
            continue
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or _HEADER_RE.match(lines[j])):
            j += 1
        if j < len(lines) and re.match(r'\{\s*\+?(Item|Block)\b', lines[j].lstrip(), re.IGNORECASE):
            del lines[i]
            removed_headers += 1
        else:
            i += 1

    # 3) ajout des declarations a reactiver
    added_lines: List[str] = []
    if plan.to_restore:
        stamp = time.strftime('%Y-%m-%d')
        added_lines.append(
            f"# Declarations reactivees le {stamp} : blocs commentes sans "
            f"equivalent actif (meme nom).{eol}")
        for decl in plan.to_restore:
            text = decl.text
            if decl.name in plan.id_dropped:
                text = _ID_RE.sub('', text, count=1)
            if not text.endswith(('\n', '\r')):
                text += eol
            added_lines.append(text)

    base = ''.join(lines)
    if added_lines and base and not base.endswith(('\n', '\r')):
        base += eol
    new_text = base + ''.join(added_lines)

    # 4) verification AVANT ecriture : aucun nom actif perdu, reactivations
    #    toutes presentes, aucun Id duplique cree par les reactivations
    try:
        check_doc = parse_ecf_text(new_text)
    except Exception as e:                      # parseur : refus total
        raise RuntimeError(f"Le resultat ne se reparse pas : {e}") from e
    names: Set[str] = set()
    ids: List[str] = []
    for node in check_doc.nodes:
        kind = getattr(node, 'kind', '').lstrip('+-').strip().lower()
        if kind not in ('item', 'block'):
            continue
        name = (node.get_property('Name') or '').strip()
        if name:
            names.add(name)
        if node.get('Id'):
            ids.append(node.get('Id').strip())
    lost = plan.active_names - names
    if lost:
        raise RuntimeError(f"Noms actifs perdus : {sorted(lost)[:5]}")
    missing = {d.name for d in plan.to_restore} - names
    if missing:
        raise RuntimeError(f"Reactivations absentes du resultat : {sorted(missing)[:5]}")
    kept_ids = [d.id for d in plan.to_restore if d.id and d.name not in plan.id_dropped]
    dup_ids = {i for i in kept_ids if ids.count(i) > 1}
    if dup_ids:
        raise RuntimeError(f"Ids dupliques apres operation : {sorted(dup_ids)[:5]}")

    backup = fsutil.central_backup(path, 'inactive_declarations')
    # octets fidelement preserves : un fichier de mod peut contenir des
    # sequences non UTF-8 valides (decodees en surrogateescape plus haut)
    fsutil.atomic_write_bytes(path, new_text.encode('utf-8', 'surrogateescape'))
    return ApplyResult(restored=len(plan.to_restore),
                       dropped=len(plan.to_drop) if remove_dropped else 0,
                       headers_removed=removed_headers,
                       id_dropped=len(plan.id_dropped), backup=backup)
