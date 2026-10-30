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

"""Jetons de quete (TokenConfig.ecf) : lecture, edition, creation et
comptage des usages reels.

Grammaire confirmee sur de vrais fichiers (RE2, 470 blocs) :
    { Token Id: 4001, Name: UCH Keycard
      CustomIcon: UCHKeycard
      Description: ...
      RemoveOnUse: true
    }
'Id' et 'Name' sont des paires de la LIGNE D'OUVERTURE du bloc (kind
'Token'), le reste sont des proprietes enfants. Le META du jeton est cet Id :
le jeu n'accepte que 4 chiffres (1..9999) et seul l'item 'Token'
(ItemsConfig id 1305) les porte.

Les usages 'Token:<id>' se trouvent dans Extras/PDA, TraderNPCConfig.ecf et
TokenConfig.ecf lui-meme (aucun playfield en RE2) : le scan reste borne a ces
emplacements, pas aux 550 playfields."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.ecf.model import (EcfBlock, EcfDocument, EcfProperty,
                            add_property_line, create_block)
from core.ecf.parser import parse_ecf_file
from core.ecf.validation import ValidationIssue

TOKEN_FILE = "TokenConfig.ecf"
TOKEN_REF_RE = re.compile(r"Token:\s*(\d+)")
MAX_TOKEN_ID = 9999

FLAG_KEYS = ("RemoveOnUse", "DropOnDeath")
FIELD_KEYS = ("Name", "Description", "CustomIcon")


@dataclass
class TokenEntry:
    token_id: int
    block: EcfBlock
    doc: EcfDocument
    path: Path
    name: str = ""
    description: str = ""
    custom_icon: str = ""
    remove_on_use: bool = False
    drop_on_death: bool = False
    usages: int = 0

    @property
    def label(self) -> str:
        return self.name or f"Token {self.token_id}"


@dataclass
class TokenScan:
    path: Optional[Path] = None
    doc: Optional[EcfDocument] = None
    entries: List[TokenEntry] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def editable(self) -> bool:
        return self.path is not None and self.doc is not None


def find_token_file(root: Path) -> Optional[Path]:
    for candidate in (Path(root) / "Content" / "Configuration" / TOKEN_FILE,
                      Path(root) / "Configuration" / TOKEN_FILE):
        if candidate.is_file():
            return candidate
    return None


def _child_prop(block: EcfBlock, key: str) -> Optional[EcfProperty]:
    for child in block.children:
        if isinstance(child, EcfProperty) and child.get(key) is not None:
            return child
    return None


def _child_value(block: EcfBlock, key: str) -> str:
    prop = _child_prop(block, key)
    return (prop.get(key) or "").strip() if prop else ""


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _entries_from(doc: EcfDocument, path: Path) -> List[TokenEntry]:
    entries = []
    for node in doc.nodes:
        if not isinstance(node, EcfBlock) or node.kind != "Token":
            continue
        raw_id = (node.get("Id") or "").strip()
        try:
            token_id = int(raw_id)
        except ValueError:
            token_id = -1          # Id absent/illisible : signale par un check
        entries.append(TokenEntry(
            token_id=token_id, block=node, doc=doc, path=path,
            name=(node.get("Name") or "").strip(),
            description=_child_value(node, "Description"),
            custom_icon=_child_value(node, "CustomIcon"),
            remove_on_use=_parse_bool(_child_value(node, "RemoveOnUse")),
            drop_on_death=_parse_bool(_child_value(node, "DropOnDeath"))))
    return entries


def count_usages(root: Path) -> Dict[int, int]:
    """Occurrences 'Token:<id>' dans les fichiers ou elles apparaissent
    reellement (PDA, marchands, TokenConfig) — pas les 550 playfields."""
    counts: Dict[int, int] = {}
    root = Path(root)
    targets: List[Path] = []
    for pattern in ("Content/Configuration/*.ecf", "Configuration/*.ecf",
                    "Extras/**/*.yaml", "Extras/**/*.csv"):
        targets.extend(sorted(root.glob(pattern)))
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in TOKEN_REF_RE.finditer(text):
            token_id = int(match.group(1))
            counts[token_id] = counts.get(token_id, 0) + 1
    return counts


def next_free_id(entries: List[TokenEntry]) -> int:
    """Plus petit Id libre >= max(4000, max existant + 1), plafonne a 9999 —
    4 chiffres obligatoires (seul l'item 'Token' porte un META)."""
    used = {e.token_id for e in entries if 0 < e.token_id <= MAX_TOKEN_ID}
    start = max(4000, (max(used) + 1) if used else 4000)
    for candidate in range(start, MAX_TOKEN_ID + 1):
        if candidate not in used:
            return candidate
    for candidate in range(1, MAX_TOKEN_ID + 1):
        if candidate not in used:
            return candidate
    raise ValueError("tous les Id de jeton 1..9999 sont utilises")


def scan(root: Path) -> TokenScan:
    path = find_token_file(root)
    result = TokenScan(path=path)
    if path is None:
        return result
    try:
        doc = parse_ecf_file(path)
    except Exception as exc:                      # noqa: BLE001 - fichier illisible
        result.issues.append(ValidationIssue(
            code="E320", level="error",
            message=f"TokenConfig.ecf illisible : {exc}", file_path=path))
        return result
    result.entries = _entries_from(doc, path)
    result.doc = doc
    usages = count_usages(root)
    seen: Dict[int, str] = {}
    for entry in result.entries:
        entry.usages = usages.get(entry.token_id, 0)
        if entry.token_id <= 0 or entry.token_id > MAX_TOKEN_ID:
            result.issues.append(ValidationIssue(
                code="E321", level="error",
                message=f"jeton '{entry.label}' : Id '{entry.token_id}' hors "
                        f"1..{MAX_TOKEN_ID} (le META doit tenir sur 4 chiffres)",
                file_path=path))
        elif entry.token_id in seen:
            result.issues.append(ValidationIssue(
                code="W320", level="warning",
                message=f"Id de jeton {entry.token_id} declare deux fois "
                        f"('{seen[entry.token_id]}' et '{entry.label}')",
                file_path=path))
        else:
            seen[entry.token_id] = entry.label
        if not entry.name:
            result.issues.append(ValidationIssue(
                code="W322", level="warning",
                message=f"jeton {entry.token_id} sans 'Name' (inventaire "
                        f"affichera le nom brut de l'item)",
                file_path=path))
    return result


# ============================================================================
# Edition
# ============================================================================

def set_field(entry: TokenEntry, key: str, value: str) -> bool:
    """Ecrit un champ — 'Name' sur la ligne d'ouverture, le reste en enfant
    (cree la propriete si elle n'existe pas encore)."""
    if key == "Name":
        if entry.block.set("Name", value):
            entry.name = value
            return True
        return False
    prop = _child_prop(entry.block, key)
    if prop is not None:
        prop.set(key, value)
    else:
        if not value:
            return True                  # rien a creer pour une valeur vide
        add_property_line(entry.block, [(key, value)])
    if key == "Description":
        entry.description = value
    elif key == "CustomIcon":
        entry.custom_icon = value
    return True


def set_flag(entry: TokenEntry, key: str, enabled: bool) -> bool:
    """RemoveOnUse / DropOnDeath : poses en propriete quand actives, retires
    quand desactives (le defaut du jeu est False — une ligne 'false'
    explicite est equivalente mais plus bruyante)."""
    if key not in FLAG_KEYS:
        return False
    prop = _child_prop(entry.block, key)
    if enabled:
        if prop is not None:
            prop.set(key, "true")
        else:
            add_property_line(entry.block, [(key, "true")])
    elif prop is not None:
        entry.block.children.remove(prop)
    if key == "RemoveOnUse":
        entry.remove_on_use = enabled
    else:
        entry.drop_on_death = enabled
    return True


def create_token(doc: EcfDocument, path: Path, token_id: int, name: str,
                 description: str = "", custom_icon: str = "") -> TokenEntry:
    """Ajoute un bloc Token en FIN de fichier (creation de toutes pieces)."""
    eol = _detect_eol(doc)
    block = create_block("Token", [("Id", str(token_id)), ("Name", name)], eol=eol)
    if custom_icon:
        add_property_line(block, [("CustomIcon", custom_icon)])
    if description:
        add_property_line(block, [("Description", description)])
    doc.nodes.append(block)
    return TokenEntry(token_id=token_id, block=block, doc=doc, path=path,
                      name=name, description=description,
                      custom_icon=custom_icon)


def _detect_eol(doc: EcfDocument) -> str:
    for node in doc.nodes:
        eol = getattr(node, "eol", None)
        if eol:
            return eol
    return "\r\n"


def save(scan_result: TokenScan) -> Path:
    """Backup central puis ecriture atomique du fichier rendu."""
    from core.fsutil import atomic_write_text, central_backup  # local : monkeypatch conftest
    if scan_result.path is None or scan_result.doc is None:
        raise ValueError("TokenConfig.ecf absent")
    central_backup(scan_result.path, "tokens")
    atomic_write_text(scan_result.path, scan_result.doc.render())
    return scan_result.path


def check_tokens(root: Path) -> List[ValidationIssue]:
    """Controle bilan des jetons :
    - structure de TokenConfig.ecf (Id hors 1..9999, Id en double, sans Name) ;
    - references 'Token:<id>' introuvables la ou le jeu les lit (marchands,
      PDA, dialogues, loot) — le cas 'jeton utilise mais jamais defini' ;
    Les jetons DEFINIS MAIS JAMAIS REFERENCES ne sont pas signales au bilan
    (RE2 en compte 280, dont des separateurs decoratifs volontaires) : le
    dialogue des jetons les affiche deja par son compteur d'usages."""
    issues = list(scan(root).issues)
    config_dir = Path(root) / "Content" / "Configuration"
    ecf_files = sorted(config_dir.glob("*.ecf")) if config_dir.is_dir() else []
    if not ecf_files:
        return issues
    from core.ecf.cross_reference_check import CrossRefContext, run_checks
    context = CrossRefContext(ecf_files=ecf_files, yaml_files=[],
                              scenario_root=Path(root))
    for ref in run_checks(context, ["token_refs"]):
        issues.append(ValidationIssue(
            code="E322", level="error",
            message=f"{ref.source_kind} [{ref.source_identity}] : "
                    f"{ref.ref_value} introuvable dans TokenConfig.ecf",
            file_path=ref.source_file))
    return issues
