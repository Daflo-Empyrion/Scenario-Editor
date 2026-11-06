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

"""Starters : creer, alimenter et desactiver les planetes de depart.

Un depart jouable tient a DEUX choses, dans deux fichiers :

- `Sectors.yaml` : le 4e champ de la ligne de playfield porte le marqueur de
  faction (`['0, 0, 0', Akua, Starter_Akua_V2,'Human:1', '', '', '']`). C'est
  LUI que le client lit pour proposer le playfield au menu Nouvelle partie —
  pas le `PlanetType` : `Shadows of Starlight` marque un `PlanetType: Snow`
  (`Bro1_Brexxis_Planet`, `'Agent:1'`). Vider le champ = depart desactive
  (methode documentee par RE2 lui-meme sur la ligne `Random`).
- `Playfields/<Type>/playfield_static.yaml` : un bloc `POIs > FixedPlayerStart`
  en `Mode: Survival` avec `Spawn: EscapePodLandAtPos`, `Pos`, `Status` et
  `Items` (4 niveaux EASY / MEDIUM / HARD / FRESH START, le 4e prefixe
  `#FreshStart:`). Sans lui le joueur apparait sans kit.

La `Description` du playfield est la carte affichee dans le menu : la fiche de
depart y est INSEREE devant le texte existant (jamais remplacee).

VALIDATION EN JEU : aucun critere de forme ne predit si le client acceptera
la donnee d'un depart au menu (vecu 05/11 : `Lava` ET `StarterRandom_Arid_V2`,
donnees du mod intactes, crashaient des qu'elles devenaient des departs —
alors que les 16 departs marques par l'auteur passent). Le module suit donc
les departs VALIDES EN JEU dans un cache local
(`~/.empyrion_editor/starts_valides.json`, par scénario) ; tout depart non
valide est signale « a tester » par le module et le bilan.

Ecriture via yamllite (commentaires et mise en forme preserves). L'appelant
gere sauvegardes et undo.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from core.fsutil import atomic_write_bytes, atomic_write_text
from core.playfield_editor import (find_fixed_player_start_items,
                                   find_top_level_key, get_item_params)
from core.playfield_reintegrate import sectors_yaml
from core.sectors_merge import (_coords_key, _coords_text, _find_child,
                                _find_solar_systems, _seq_items, _split_flow,
                                _start_marker_span, _strip_quotes, _systems)
from core.yamllite.model import (YamlBlank, YamlComment, YamlEntry,
                                 create_entry)
from core.yamllite.parser import parse_yaml_file

MARKER = "Human:1"
# cles du bloc FixedPlayerStart que ce module possede (le reste est conserve)
_KIT_KEYS = ("Spawn", "Pos", "RotY", "Status", "Items")
_KIT_INDENT = "          "       # 10 espaces : sous '- Mode:' (8) du corpus
_ITEM_INDENT = "        "        # 8 espaces : sous '    FixedPlayerStart:'
# kit d'Akua, copie du corpus (Starter_Akua_V2/playfield_static.yaml)
AKUA_ITEMS = (
    "Token:1:6999, Token:1:6998, Token:1:6996, CombatKnife, SurvivalTool, "
    "RadarSuitT1, Flashlight",
) * 3 + (
    "#FreshStart: Token:1:6999, Token:1:6996, Token:1:6998, SurvivalTool, "
    "RadarSuitT1, Flashlight",
)
AKUA_STATUS = ("Food: 500, Health: 500",) * 3 + (
    "#FreshStart:Food: 250, Health: 250",
)
# une Description qui contient deja un emplacement = deja une fiche de depart
_CARD_MARK = "Location:"
_DESC_QUOTE = 'Description: "'


@dataclass(frozen=True)
class PlanetRow:
    """Une planete posee dans la galaxie (ligne de playfield a 7 champs)."""
    system: str
    sector: Tuple[int, int, int]
    name: str
    type_name: str
    marker: str              # 4e champ : 'Human:1' si depart, '' sinon
    has_kit: bool            # FixedPlayerStart Survival + Items dans le playfield
    has_card: bool           # Description deja redigee comme une fiche de depart

    @property
    def is_start(self) -> bool:
        return bool(self.marker)

    @property
    def key(self) -> str:
        """Identite stable pour retrouver la ligne dans le document."""
        return f"{self.system}|{self.sector}|{self.name}"


@dataclass(frozen=True)
class StartKit:
    """Kit de depart, 4 niveaux dans l'ordre du corpus."""
    spawn: str = "EscapePodLandAtPos"
    pos: str = "[0, 70, 0]"
    rot_y: str = "160"
    status: Tuple[str, ...] = AKUA_STATUS
    items: Tuple[str, ...] = AKUA_ITEMS


# ------------------------------------------------------------------ lecture

def static_path(root, type_name: str) -> Optional[Path]:
    path = Path(root) / "Playfields" / type_name / "playfield_static.yaml"
    return path if path.is_file() else None


def _survival_start(doc) -> Optional[YamlEntry]:
    """Entree `- Mode: Survival` de FixedPlayerStart. Le Mode est la CLE de
    l'item de sequence lui-meme (pas un enfant) : `item.get("Mode")` seul ne
    trouve donc jamais rien."""
    for item in find_fixed_player_start_items(doc):
        mode = item.value if item.key == "Mode" else (item.get("Mode") or "")
        if _strip_quotes(mode or "") == "Survival":
            return item
    return None


def _levels(item: YamlEntry, key: str) -> List[str]:
    """Niveaux d'une liste flow, y compris ecrite sur PLUSIEURS lignes (forme
    du corpus : `Items: [` puis une entree `"..."` par ligne, qui restent des
    freres de la cle dans l'arbre)."""
    entry = next((child for child in item.children
                  if isinstance(child, YamlEntry) and child.key == key), None)
    if entry is None:
        return []
    raw = entry.value.strip()
    if raw.startswith("[") and not raw.endswith("]"):
        parts: List[str] = []
        index = item.children.index(entry) + 1
        while index < len(item.children):
            nxt = item.children[index]
            index += 1
            if not (isinstance(nxt, YamlEntry) and nxt.key is None):
                break
            parts.append(nxt.value)
            if nxt.value.strip().endswith("]"):
                break
        raw = f"{entry.value} {' '.join(parts)}"
    return _split_flow(raw)


def _profile(root, type_name: str) -> Tuple[bool, bool]:
    """(kit present, fiche presente) pour un type de playfield."""
    path = static_path(root, type_name)
    if path is None:
        return False, False
    try:
        doc = parse_yaml_file(path)
    except OSError:
        return False, False
    item = _survival_start(doc)
    has_kit = bool(item is not None and _levels(item, "Items"))
    desc = find_top_level_key(doc, "Description")
    has_card = bool(desc is not None and _CARD_MARK in (desc.value or "")[:200])
    return has_kit, has_card


def read_kit(root, type_name: str) -> StartKit:
    """Kit de depart du playfield ; kit d'Akua quand il n'y en a pas."""
    path = static_path(root, type_name)
    if path is None:
        return StartKit()
    try:
        doc = parse_yaml_file(path)
    except OSError:
        return StartKit()
    item = _survival_start(doc)
    if item is None:
        return StartKit()
    params = dict(get_item_params(item))
    items = _levels(item, "Items") or list(AKUA_ITEMS)
    status = _levels(item, "Status") or list(AKUA_STATUS)
    return StartKit(
        spawn=_strip_quotes(params.get("Spawn") or "") or StartKit.spawn,
        pos=params.get("Pos") or StartKit.pos,
        rot_y=_strip_quotes(params.get("RotY") or "") or StartKit.rot_y,
        status=_pad(status, AKUA_STATUS),
        items=_pad(items, AKUA_ITEMS))


def _pad(values: Sequence[str], default: Sequence[str]) -> Tuple[str, ...]:
    """Exactement 4 niveaux (le jeu lit une liste de 4)."""
    out = [str(v) for v in values][:4]
    out += [default[i] for i in range(len(out), 4)]
    return tuple(out)


def find_planets(root) -> List[PlanetRow]:
    """Toutes les planetes posees dans la galaxie.

    Une planete = ligne a 7 champs dont les deux derniers (texture et taille
    d'une GEANTE) sont vides : un depart sur une geante n'aurait pas de sol."""
    root = Path(root)
    path = sectors_yaml(root)
    if path is None:
        return []
    solar = _find_solar_systems(parse_yaml_file(path))
    if solar is None:
        return []
    profiles: Dict[str, Tuple[bool, bool]] = {}
    out: List[PlanetRow] = []
    for system in _systems(solar):
        name = _strip_quotes(system.value)
        sectors_entry = _find_child(system, "Sectors")
        for sector in (_seq_items(sectors_entry) if sectors_entry is not None
                       else []):
            playfields = _find_child(sector, "Playfields")
            for row in (_seq_items(playfields) if playfields is not None
                        else []):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) != 7 or fields[5] or fields[6]:
                    continue
                type_name = fields[2]
                if type_name not in profiles:
                    profiles[type_name] = _profile(root, type_name)
                has_kit, has_card = profiles[type_name]
                key = _coords_key(_coords_text(sector))
                coords = (int(key[0]), int(key[1]), int(key[2])) \
                    if len(key) == 3 else (0, 0, 0)
                out.append(PlanetRow(name, coords, fields[1], type_name,
                                     fields[3], has_kit, has_card))
    return out


# ---------------------------------------------------- validation en jeu

def validated_cache_path() -> Path:
    return Path.home() / ".empyrion_editor" / "starts_valides.json"


def load_validated(root) -> Tuple[set, bool]:
    """(departs valides en jeu, le cache existe-t-il deja ?). Cle = chemin du
    scenario. Cache absent -> ensemble vide (le dialogue propose
    l'initialisation ; le bilan, lui, ne dit rien sans cache)."""
    path = validated_cache_path()
    if not path.is_file():
        return set(), False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set(), True
    return set(data.get(str(Path(root)), [])), True


def mark_validated(root, type_names: Iterable[str]) -> None:
    """Enregistre des departs confirmes en jeu (cache local, jamais dans le
    scenario : la donnee du jeu ne porte pas cette information)."""
    path = validated_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) \
            if path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    key = str(Path(root))
    known = set(data.get(key, []))
    known.update(type_names)
    data[key] = sorted(known)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError:
        pass


def find_untested_starts(root) -> List[Tuple[str, str]]:
    """Departs marques non valides en jeu, [(nom, type)]. Rien sans cache :
    le bilan ne juge pas un scénario dont le module de departs n'a jamais ete
    ouvert (16 avertissements identiques = bruit)."""
    validated, exists = load_validated(root)
    if not exists:
        return []
    return [(row.name, row.type_name) for row in find_planets(root)
            if row.is_start and row.type_name not in validated]


# ----------------------------------------------------------------- ecriture

def _marker_text(value: str, marker: str) -> Optional[str]:
    """Ligne de playfield dont le 4e champ est `marker` (forme du corpus :
    pas d'espace avant le marqueur). None si la ligne a moins de 4 champs."""
    span = _start_marker_span(value)
    if span is None:
        return None
    start, end = span
    while start < end and value[start] == " ":
        start += 1                    # garde l'espacement du corpus
    body = f"'{marker}'" if marker else "''"
    return value[:start] + body + value[end:]


def _locate(solar: YamlEntry, pick: PlanetRow) -> Optional[YamlEntry]:
    """Retrouve la ligne de playfield d'une planete dans le document."""
    for system in _systems(solar):
        if _strip_quotes(system.value) != pick.system:
            continue
        sectors_entry = _find_child(system, "Sectors")
        for sector in (_seq_items(sectors_entry) if sectors_entry is not None
                       else []):
            if _coords_key(_coords_text(sector)) != tuple(
                    str(v) for v in pick.sector):
                continue
            playfields = _find_child(sector, "Playfields")
            for row in (_seq_items(playfields) if playfields is not None
                        else []):
                fields = _split_flow(row.value) if row.value else []
                if len(fields) >= 3 and fields[1] == pick.name:
                    return row
    return None


def preview_markers(root, picks: Iterable[PlanetRow],
                    marker: str) -> List[Tuple[str, str, str]]:
    """(nom, ancienne ligne, nouvelle ligne) sans rien ecrire."""
    path = sectors_yaml(root)
    if path is None:
        return []
    solar = _find_solar_systems(parse_yaml_file(path))
    if solar is None:
        return []
    out: List[Tuple[str, str, str]] = []
    for pick in picks:
        row = _locate(solar, pick)
        if row is None:
            continue
        new = _marker_text(row.value, marker)
        if new is not None and new != row.value:
            out.append((pick.name, row.value, new))
    return out


def set_starts(root, picks: Iterable[PlanetRow],
               marker: str = MARKER) -> Tuple[int, List[str]]:
    """Ecrit le marqueur de depart. Retourne (lignes ecrites, details)."""
    return _apply_markers(root, picks, marker)


def clear_starts(root, picks: Iterable[PlanetRow]) -> Tuple[int, List[str]]:
    """Vide le 4e champ : le playfield n'est plus propose au menu Nouvelle
    partie (methode documentee par le corpus)."""
    return _apply_markers(root, picks, "")


def _apply_markers(root, picks, marker: str) -> Tuple[int, List[str]]:
    picks = list(picks)
    if not picks:
        return 0, []
    path = sectors_yaml(root)
    if path is None:
        return 0, ["Sectors.yaml introuvable"]
    doc = parse_yaml_file(path)
    solar = _find_solar_systems(doc)
    if solar is None:
        return 0, ["SolarSystems introuvable"]
    written = 0
    details: List[str] = []
    for pick in picks:
        row = _locate(solar, pick)
        if row is None:
            details.append(f"{pick.name} : ligne introuvable — ignoree")
            continue
        new = _marker_text(row.value, marker)
        if new is None:
            details.append(f"{pick.name} : ligne sans 4e champ — ignoree")
            continue
        if new == row.value:
            continue                  # deja dans l'etat demande
        row.set_own_value(new)
        written += 1
    if written:
        atomic_write_text(path, doc.render())
    return written, details


def render_kit(kit: StartKit, indent: str = _KIT_INDENT) -> str:
    """Bloc `FixedPlayerStart` tel qu'ecrit (apercu du dialogue) : forme du
    corpus, `Status: [` puis un niveau cite par ligne."""
    rows = [f"{indent}{key}: {value}" for key, value in
            (("Spawn", kit.spawn), ("Pos", kit.pos), ("RotY", kit.rot_y))]
    for key, levels in (("Status", kit.status), ("Items", kit.items)):
        rows.append(f"{indent}{key}: [ ")
        rows.extend(_flow_lines(levels))
    return "\n".join(rows)


def _flow_lines(values: Sequence[str]) -> List[str]:
    """Niveaux d'une liste, un par ligne, forme du corpus (`]` sur le
    dernier)."""
    lines = [f'"{level}",' for level in values[:-1]]
    lines.append(f'"{values[-1]}" ]' if values else " ]")
    return lines


def _write_doc(doc, path: Path, eol: str) -> None:
    """Ecrit le document en garantissant un saut de ligne final.

    Le jeu lit `playfield_static.yaml` PUIS `playfield_dynamic.yaml` dans un
    MEME flux : sans saut final, la derniere ligne du static colle au `---` du
    dynamic et le playfield ne se charge plus (« While parsing a block
    mapping, did not find expected key », puis plus aucun depart dans le menu
    Nouvelle partie, NRE au lancement — vecu 05/11 sur `Lava`, dont le static
    etait l'un des 49 playfields RE2-FR sans saut final)."""
    text = doc.render()
    if not text.endswith(("\n", "\r")):
        text += eol
    atomic_write_text(path, text)


def ensure_final_eol(root, type_name: str) -> bool:
    """Repare un `playfield_static.yaml` sans saut final (voir `_write_doc`).
    A appeler pour TOUT playfield qu'on declare comme depart : sans reecriture
    du fichier, le defaut reste et le client plante. True si modifie."""
    path = static_path(root, type_name)
    if path is None:
        return False
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if data.endswith((b"\n", b"\r")):
        return False
    atomic_write_bytes(path, data + (b"\r\n" if b"\r\n" in data else b"\n"))
    return True


def write_kit(root, type_name: str, kit: StartKit) -> str:
    """Ecrit le kit dans le playfield. Retourne 'updated', 'created' ou un
    message d'echec (jamais d'exception metier)."""
    path = static_path(root, type_name)
    if path is None:
        return f"{type_name} : playfield_static.yaml introuvable"
    doc = parse_yaml_file(path)
    eol = "\r\n" if doc.render().count("\r\n") else "\n"
    pois = find_top_level_key(doc, "POIs")
    section = _find_child(pois, "FixedPlayerStart") if pois is not None else None
    item = _survival_start(doc)
    if item is not None:
        _strip_kit_keys(item)
        tail = _detach_tail(item)
        _append_kit(item, kit, item.indent + "  ", eol)
        if section is not None:
            index = section.children.index(item)
            section.children[index + 1:index + 1] = tail
        _write_doc(doc, path, eol)
        return "updated"
    if pois is None:
        return f"{type_name} : section POIs introuvable"
    if section is None:
        section = create_entry("FixedPlayerStart", "",
                               indent=pois.indent + "    ", eol=eol)
        pois.children.append(section)
    indent = _item_indent(section)
    item = create_entry("Mode", "Survival", indent=indent,
                        is_sequence_item=True, eol=eol)
    _append_kit(item, kit, indent + "  ", eol)
    last = next((child for child in reversed(section.children)
                 if isinstance(child, YamlEntry)), None)
    tail = _detach_tail(last) if last is not None else []
    section.children.extend(tail)
    _put_item(section, item, len(tail), eol)
    _write_doc(doc, path, eol)
    return "created"


def _item_indent(section: YamlEntry) -> str:
    for child in section.children:
        if isinstance(child, YamlEntry) and child.is_sequence_item:
            return child.indent
    return section.indent + "    "


def _is_loose(node) -> bool:
    return (isinstance(node, (YamlBlank, YamlComment))
            or (isinstance(node, YamlEntry) and node.key is None
                and not node.value))


def _detach_tail(item: Optional[YamlEntry]) -> List:
    """Retire les blancs et commentaires de FIN de bloc : le parseur les
    imbrique sous la DERNIERE cle du dernier item (`RotY`, derniere ligne de
    `Items`...), alors qu'ils decrivent la suite du fichier. Remontes au
    niveau de la section pour que l'item ajoute se pose devant eux."""
    tail: List = []
    node = item
    while isinstance(node, YamlEntry):
        while node.children and _is_loose(node.children[-1]):
            tail.insert(0, node.children.pop())
        last = node.children[-1] if node.children else None
        if not isinstance(last, YamlEntry):
            break
        node = last
    return tail


def _put_item(section: YamlEntry, item: YamlEntry, tail_count: int,
              eol: str) -> None:
    """Insere `item` en fin de contenu utile, DEVANT les `tail_count`
    commentaires de fin deja remis dans la section."""
    position = len(section.children) - tail_count
    if position and not isinstance(section.children[position - 1], YamlBlank):
        section.children.insert(position, YamlBlank(eol))
        position += 1
    section.children.insert(position, item)


def _strip_kit_keys(item: YamlEntry) -> None:
    """Retire les cles du kit et les lignes de continuation des listes
    multi-lignes. Les commentaires eventuellement imbriques remontent (le
    corpus y documente des variantes : on ne les perd pas)."""
    kept: List = []
    for node in item.children:
        if isinstance(node, YamlEntry) and node.key in _KIT_KEYS:
            kept.extend(node.children)
            continue
        if isinstance(node, YamlEntry) and node.key is None and node.value:
            kept.extend(node.children)
            continue
        kept.append(node)
    item.children = kept


def _append_kit(item: YamlEntry, kit: StartKit, indent: str, eol: str) -> None:
    """Ecrit le kit a l'identique du corpus (`Starter_Akua_V2`) : `Status: [`
    ouvre la liste, chaque niveau cite sur SA ligne, `]` sur le dernier.

    Vecu 05/11 : la forme une-ligne (`Status: [ "...", ... ]`) ecrite ici
    faisait planter le client au menu Nouvelle partie alors que le fichier
    passe YamlDotNet — c'est la re-serialisation du client qui ne la supporte
    pas ; les 16 départs du corpus, tous en multi-lignes, passent."""
    for key, value in (("Spawn", kit.spawn), ("Pos", kit.pos),
                       ("RotY", kit.rot_y)):
        item.children.append(create_entry(key, value, indent=indent, eol=eol))
    for key, levels in (("Status", kit.status), ("Items", kit.items)):
        item.children.append(create_entry(key, "[ ", indent=indent, eol=eol))
        for line in _flow_lines(levels):
            item.children.append(create_entry(None, line, indent=indent,
                                              eol=eol))


# ------------------------------------------------------- controle du kit

_TOKEN_RE = re.compile(r"^([A-Za-z0-9_.]+)(?::[ \t]*(\d+))?(#Drop)?$")
_ECF_ITEM_RE = re.compile(
    r"\{[ \t]*\+?Item\b[^{}]*?Name:[ \t]*([A-Za-z0-9_.]+)", re.S)
_FRESH = "#FreshStart:"


def item_names(root, vanilla: str = "") -> set:
    """Noms d'items declares par `ItemsConfig.ecf` (scenario + vanille)."""
    paths = [Path(root) / "Content" / "Configuration" / "ItemsConfig.ecf"]
    if vanilla:
        paths.append(Path(vanilla) / "Configuration" / "ItemsConfig.ecf")
    names: set = set()
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names.update(_ECF_ITEM_RE.findall(text))
    return names


def check_kit(root, kit: StartKit, vanilla: str = "") -> List[str]:
    """Items du kit que le jeu n'accordera PAS : nom absent de `ItemsConfig`
    (le jeu ignore un item inconnu en silence) ou quantite non numerique.
    `Token:...` est accepte (entrees de guide, sans ItemsConfig). Liste vide
    quand `ItemsConfig.ecf` est illisible : on ne signale pas au hasard."""
    known = {name.casefold() for name in item_names(root, vanilla)}
    if not known:
        return []
    problems: List[str] = []
    for level, line in enumerate(kit.items, 1):
        for token in line.split(","):
            token = token.strip()
            if token.startswith(_FRESH):
                token = token[len(_FRESH):].strip()
            if not token or token.startswith("Token:"):
                continue
            match = _TOKEN_RE.match(token)
            if match is None:
                problems.append(f"niveau {level} : « {token} » forme invalide "
                                f"(attendu Nom ou Nom:quantite)")
            elif match.group(1).casefold() not in known:
                problems.append(f"niveau {level} : « {match.group(1)} » inconnu "
                                f"dans ItemsConfig — le jeu l'ignorera")
    return problems


def _root_declarations(path: Path) -> List[Tuple[str, bool]]:
    """(cle, porte une valeur) des declarations de NIVEAU RACINE.

    Les items de sequence sont exclus : le parseur les remonte a la racine
    quand un commentaire en colonne 0 les precede (`- Name:` d'une liste)."""
    try:
        doc = parse_yaml_file(path)
    except OSError:
        return []
    return [(node.key, bool((node.value or "").strip()))
            for node in doc.nodes
            if isinstance(node, YamlEntry) and node.indent == "" and node.key
            and not node.is_sequence_item]


def check_playfield(root, type_name: str) -> List[str]:
    """Defauts qui empechent le CLIENT de charger le playfield une fois qu'il
    devient un depart (le menu lit `playfield_static.yaml` PUIS
    `playfield_dynamic.yaml` dans un MEME flux).

    Seule forme constatee fatale : une cle racine declaree DEUX fois dont une
    SANS VALEUR — `GroundShapes:` vide suivi de `GroundShapes:` portant sa
    sequence. Le parseur du jeu reste en « block mapping » et rejette l'item
    de sequence (« did not find expected key », col 2 = son indentation) : le
    playfield ne se charge plus, la liste des departs disparait et le client
    plante au lancement (vecu 05/11 sur `Lava`). Deux cles dupliquees TOUTES
    DEUX valorisees passent : `Starter_Pandora_V2` declare
    `PlayfieldLevelOverride` en `[3,3]` et `[4,4]` et fonctionne."""
    declarations: Dict[str, List[Tuple[str, bool]]] = {}
    for name in ("playfield_static.yaml", "playfield_dynamic.yaml"):
        path = Path(root) / "Playfields" / type_name / name
        if not path.is_file():
            continue
        for key, has_value in _root_declarations(path):
            declarations.setdefault(key, []).append((name, has_value))
    problems: List[str] = []
    for key, occurrences in declarations.items():
        if len(occurrences) < 2:
            continue
        if any(not has_value for _, has_value in occurrences):
            where = ", ".join(
                name if has_value else f"{name} (sans valeur)"
                for name, has_value in occurrences)
            problems.append(f"{key} : declare deux fois — {where}")
    return problems


# ------------------------------------------------------------- fiche du menu

def _unquote(value: str) -> str:
    """Texte d'un scalaire entre guillemets (`Description:` du corpus) : la
    carte doit montrer le texte, pas la syntaxe YAML."""
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].replace('\\"', '"')
    return text


def description(root, type_name: str) -> str:
    """`Description` du playfield = la carte du menu Nouvelle partie (balisage
    BBCode compris) ; '' si elle est absente."""
    path = static_path(root, type_name)
    if path is None:
        return ""
    try:
        doc = parse_yaml_file(path)
    except OSError:
        return ""
    entry = find_top_level_key(doc, "Description")
    return _unquote(entry.value) if entry is not None else ""


def card_preview(root, row: PlanetRow, with_card: bool) -> str:
    """Carte telle que le jeu la lira : fiche devant la description existante
    quand elle va etre ajoutee (aucun doublon si elle y est deja)."""
    text = description(root, row.type_name)
    if with_card and not row.has_card:
        return f"{start_card(row)}\\n\\n{text}" if text else start_card(row)
    return text


def start_card(row: PlanetRow) -> str:
    """Fiche affichee par le menu Nouvelle partie (BBCode du corpus)."""
    system = (f"[c][[c][00ff00][b]{row.system}[/b][-][/c][c]][-][/c]")
    sep = ("[c][A9A9A9]" + "- " * 49 + "[-][/c]")
    return ("[sup][c][A9A9A9]Start Location:[-][/c] "
            f"[c][00ffff][b]{row.name}[/b][-][/c]\n"
            f"System: {system}\n"
            "Start: [c][FFFFFF]Escape Pod[-][/c]\n\n"
            f"{sep}[/sup]")


def _escape(text: str) -> str:
    """Texte pour un scalaire YAML entre guillemets, sauts de ligne compris."""
    return (text.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n"))


def prepend_start_card(root, row: PlanetRow) -> str:
    """Insere la fiche devant la `Description` du playfield (le texte
    d'origine reste intact, y compris ses retours a la ligne reels : on ecrit
    APRES le guillemet ouvrant du scalaire). Retourne 'added', 'already' ou un
    message d'echec.

    REFUS des que la Description est un scalaire MULTI-LIGNES
    (`quoted_continuation_raw`) : le client re-serialise la donnee du
    playfield (static+dynamic fusionnes) avant de la relire et deux crashs
    non expliques au menu Nouvelle partie ont suivi l'insertion d'une fiche
    dans une Description de ce type (vecu 05/11 sur `Lava`). Non prouve -> on
    ne le fait plus : la fiche reste manuelle pour ces playfields."""
    path = static_path(root, row.type_name)
    if path is None:
        return f"{row.type_name} : playfield_static.yaml introuvable"
    doc = parse_yaml_file(path)
    desc = find_top_level_key(doc, "Description")
    if desc is None:
        return f"{row.type_name} : Description absente"
    if _CARD_MARK in (desc.value or "")[:200]:
        return "already"
    if desc.quoted_continuation_raw:
        return (f"{row.type_name} : Description sur plusieurs lignes — "
                f"fiche non ajoutee (a ecrire a la main)")
    at = desc.raw.find(_DESC_QUOTE)
    if at == -1:
        # bloc `>-`/`|` (vanilla) : on ne reecrit pas la forme du fichier
        return f"{row.type_name} : Description non guillemetee — fiche non ajoutee"
    cut = at + len(_DESC_QUOTE)
    desc.raw = (desc.raw[:cut] + _escape(start_card(row)) + "\\n\\n"
                + desc.raw[cut:])
    eol = "\r\n" if doc.render().count("\r\n") else "\n"
    _write_doc(doc, path, eol)
    return "added"
