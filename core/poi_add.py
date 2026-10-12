# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""Ajout de POIs dans un playfield_static.yaml (demande 09/10).

Le bloc est GENERE EN TEXTE par l'assistant, puis passe par le moteur de
fusion generique (analyze + apply sur un playfield temporaire) : creation
de POIs:/Random:/Fixed: absentes, insertion en fin de liste, idempotent
(GroupName/Name deja present ignore), commentaires et mise en forme
preserves -- aucun code d'insertion propre, tout vient de yaml_merge.
L'indentation et l'EOL du temporaire sont calques sur le fichier de
destination : yamllite ressert le raw du bloc clone tel quel."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import List, Set, Tuple

from core.fsutil import atomic_write_text
from core.yamllite.parser import parse_yaml_file
from core.yaml_merge import (YamlUnit, analyze_yaml_merge, apply_yaml_units,
                             _child_entries, _detail, _identity,
                             _identity_prune, _seq_items, _top_entries)


def detect_indent(text: str) -> str:
    """Indentation des items de liste du playfield (Barren reel : 8 esp) ;
    sans aucune liste : 8 esp aussi, la convention des fichiers du jeu
    (sous-cles a 4, items a 8)."""
    m = re.search(r"(?m)^([ \t]+)- ", text)
    return m.group(1) if m else "        "


def _poi_indents(text: str) -> Tuple[str, str]:
    """(indent de la sous-cle POIs/Random, indent des items) LUS DANS LA
    SECTION POIs du playfield : une liste a 2 esp ailleurs dans le fichier
    (vecu : Barren) ne doit pas decider la mise en forme du bloc insere.
    La section est coupee a la 1re ligne col 0 qui n'est PAS un commentaire
    (les POIs listes ont leurs commentaires col 0 DEDANS, vecu Barren).
    Sans item dans la section (Random vide, vecu Starter_Akua_V2) : items
    a sous-cle + 4. Garantie structurelle : les items sont TOUJOURS plus
    indentes que la sous-cle, sinon yamllite les attache au parent
    POIs (vecu : POI affiche hors de Random)."""
    m = re.search(r"(?m)^[ \t]*POIs:.*$", text)
    if m:
        rest = text[m.end():]
        m_next = re.search(r"(?m)^(?!\s)(?!#)", rest)
        sec = rest[:m_next.start()] if m_next else rest
        m_item = re.search(r"(?m)^([ \t]+)- ", sec)
        m_sub = re.search(r"(?m)^([ \t]+)\w+:", sec)
        if m_sub:
            sub = m_sub.group(1)
            item = (m_item.group(1) if m_item
                    else " " * (len(sub) + 4))
            if len(item) <= len(sub):
                item = sub + "    "
            return sub, item
    m_any = re.search(r"(?m)^([ \t]+)- ", text)
    item = m_any.group(1) if m_any else "        "
    if len(item) >= 6:
        return " " * (len(item) - 4), item
    return "  ", item


def detect_eol(data: bytes) -> str:
    return "\r\n" if b"\r\n" in data else "\n"


def add_poi_block(dest_yaml: Path, block_text: str, section: str) -> int:
    """Insere un bloc POI (texte YAML d'un item complet, premiere ligne
    '- Cle: valeur') sous POIs/<section> ('Random'/'Fixed') du playfield
    dest. Retourne le nombre d'unites appliquees (0 = deja present)."""
    dest_yaml = Path(dest_yaml)
    data = dest_yaml.read_bytes()
    text = data.decode("utf-8", errors="replace")
    sub_indent, indent = _poi_indents(text)
    eol = detect_eol(data)
    lines = ["POIs:", f"{sub_indent}{section}:"]
    lines.extend(indent + ln if ln.strip() else "" for ln in
                 block_text.rstrip().splitlines())
    fd, tmp_name = tempfile.mkstemp(suffix=".yaml")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(eol.join(lines) + eol)
        units = [u for u in analyze_yaml_merge(dest_yaml, tmp)
                 if u.kind in ("key", "subkey", "item")
                 and (u.root.startswith("POIs")
                      or (u.root == "" and u.name == "POIs"))]
        return apply_yaml_units(dest_yaml, tmp, units)
    finally:
        tmp.unlink(missing_ok=True)


def poi_units(dest_yaml: Path, source_yaml: Path) -> List[YamlUnit]:
    """Unites POIs d'un autre playfield absentes du dest (Random/Fixed/
    sections entieres), pretes pour apply_yaml_units."""
    units = [u for u in analyze_yaml_merge(dest_yaml, source_yaml)
             if u.kind in ("key", "subkey", "item")
             and (u.root.startswith("POIs")
                  or (u.root == "" and u.name == "POIs"))]
    return units


def scan_playfield_statics(working_root: os.PathLike) -> List[Path]:
    """Les playfield_static.yaml de la copie de travail (Playfields/<N>/)."""
    root = Path(working_root) / "Playfields"
    if not root.is_dir():
        return []
    return sorted(root.glob("*/playfield_static.yaml"))


def field_pool(dest_yaml: Path, key: str) -> List[str]:
    """Valeurs deja utilisees pour une cle (Faction, Type...) dans le
    playfield dest : pool de la combo, l'existant d'abord."""
    text = Path(dest_yaml).read_text(encoding="utf-8", errors="replace")
    seen: List[str] = []
    for m in re.finditer(rf"(?m)^[ \t]*{key}:[ \t]*([^\s#][^#]*?)[ \t]*$", text):
        v = m.group(1).strip().strip("'\"")
        if v and v not in seen:
            seen.append(v)
    return seen


def scan_prefab_names(*roots: os.PathLike) -> List[str]:
    """Noms de prefabs (.epb sans extension) des dossiers donnes, tries
    (scenarIo d'abord : l'ordre des roots est respecte)."""
    names: List[str] = []
    for root in roots:
        p = Path(root) if root else None
        if p is None or not p.is_dir():
            continue
        for f in p.glob("*.epb"):
            if f.stem not in names:
                names.append(f.stem)
    return sorted(names)


def _pois_entry(doc) -> object:
    return next((e for e in _top_entries(doc) if e.key == "POIs"), None)


def list_pois(dest_yaml: Path) -> List[Tuple[str, Tuple[str, str], str]]:
    """Les POIs existants du playfield : (section, (idkey, valeur), detail)
    -- detail = premiere sous-ligne informative (Faction, Type...)."""
    doc = parse_yaml_file(Path(dest_yaml))
    pois = _pois_entry(doc)
    out: List[Tuple[str, Tuple[str, str], str]] = []
    if pois is None:
        return out
    for sub in _child_entries(pois):
        if sub.is_sequence_item or sub.key is None:
            continue
        for item in _seq_items(sub):
            ident = _identity(item)
            if ident:
                out.append((sub.key, ident, _detail(item)))
    return out


def remove_pois(dest_yaml: Path, targets: Set[Tuple[str, Tuple[str, str]]]) -> int:
    """Retire les POIs identifies par (section, (idkey, valeur)) -- ex
    ('Random', ('GroupName', 'X')). Suppression par IDENTITE (F9 : jamais
    le premier doublon par valeur), commentaires du reste preserves,
    ecriture atomique. Retourne le nombre d'items retires."""
    dest_yaml = Path(dest_yaml)
    doc = parse_yaml_file(dest_yaml)
    pois = _pois_entry(doc)
    if pois is None:
        return 0
    removed = 0
    for sub in _child_entries(pois):
        if sub.is_sequence_item or sub.key is None:
            continue
        wanted = {ident for sec, ident in targets if sec == sub.key}
        if not wanted:
            continue
        doomed = [i for i in _seq_items(sub) if _identity(i) in wanted]
        if doomed:
            # children DIRECTEMENT (pas _child_entries : copie jetable) --
            # les YamlBlank voisins restent, cosmétique sans effet jeu
            _identity_prune(sub.children, doomed)
            removed += len(doomed)
    if removed:
        atomic_write_text(dest_yaml, doc.render())
    return removed
