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

"""Import cible d'un scenario source (A ou B) vers la copie de travail.

Demande 22/10 : l'assistant ne voyait que la copie de travail et ne pouvait
donc pas lister les dependances d'un bloc avant de le fusionner. Ce module
fournit la partie PURE (aucun Qt) :

  - `parse_target` : "<scope>:<chemin relatif>[#<Id ou Name>]" ;
  - `block_plan`   : statut d'un bloc vu de la copie de travail, SANS ecrire
                     (added / merged / conflict) ;
  - `import_block` : ecrit UN bloc, via `merge_single_block` (le moteur de
                     fusion existant), jamais un ecrasement a l'aveugle.

Le fichier entier et le dossier restent aux moteurs existants
(`merge_file_into_working` / `merge_folder_into_working`) : ils savent deja
fusionner un ECF existant, completer un CSV et copier le reste.
"""
import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .ecf.merge import merge_single_block
from .ecf.model import EcfBlock, EcfDocument, block_identity
from .ecf.parser import parse_ecf_file
from .fsutil import atomic_write_text, clear_readonly

_TARGET_RE = re.compile(
    r"^(?P<scope>[A-Za-z]+)\s*:\s*(?P<rel>[^#]+?)\s*(?:#\s*(?P<ident>.+))?$")


@dataclass(frozen=True)
class ImportTarget:
    scope: str                  # 'a' ou 'b'
    rel: str                    # chemin relatif, separateurs '/'
    ident: str = ""             # bloc ECF cible (vide = fichier/dossier entier)
    with_deps: bool = False     # '#Bloc+deps' : graphe complet resolu a l'apply


def parse_target(target: str) -> Optional[ImportTarget]:
    """Decode "<scope>:<rel>[#ident][+deps]". None si illisible ou chemin
    absolu / remontant (l'import ne sort jamais des scenarios du projet).
    '+deps' demande la resolution recursive au moment de l'application (le
    modele ne recopie alors qu'UNE ligne, pas 60)."""
    match = _TARGET_RE.match((target or "").strip())
    if not match:
        return None
    rel = match.group("rel").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        return None
    ident = (match.group("ident") or "").strip()
    with_deps = ident.endswith("+deps")
    if with_deps:
        ident = ident[:-len("+deps")].strip()
    return ImportTarget(scope=match.group("scope").lower(), rel=rel,
                        ident=ident, with_deps=with_deps)


def _find_block(doc: EcfDocument, ident: str) -> Tuple[Optional[EcfBlock], str]:
    """Un seul bloc portant cette identite : Name d'abord, puis Id, puis
    l'identite de repli. `Ref` n'est PAS une cle de recherche : des dizaines
    de blocs heritent du meme template et rendaient toute recherche ambigue
    (vecu 22/10 sur ComponentsTemplate)."""
    wanted = (ident or "").strip()
    for getter in (lambda b: b.get("Name"), lambda b: b.get("Id"),
                   block_identity):
        matches = [b for b in doc.iter_blocks() if getter(b) == wanted]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            return None, "ecf_block_ambiguous"
    return None, "ecf_block_not_found"


def block_plan(source_file: Path, dest_file: Path, ident: str) -> dict:
    """Statut du bloc `ident` s'il etait importe dans `dest_file`, SANS rien
    ecrire : on rejoue la fusion sur une COPIE du document de destination."""
    source_file, dest_file = Path(source_file), Path(dest_file)
    try:
        source_doc = parse_ecf_file(source_file)
    except Exception as e:  # noqa: BLE001 -- fichier illisible = reponse
        return {"error": f"cannot parse {source_file.name}: {e}"}
    block, code = _find_block(source_doc, ident)
    if block is None:
        return {"error": code}
    if dest_file.exists():
        try:
            dest_doc = parse_ecf_file(dest_file)
        except Exception as e:  # noqa: BLE001
            return {"error": f"cannot parse {dest_file.name}: {e}"}
    else:
        dest_doc = EcfDocument(nodes=[])
    probe = copy.deepcopy(dest_doc)
    status, info = merge_single_block(probe, block, "source")
    result = {"block": {"ident": ident,
                        "kind": block.kind,
                        "name": block.get("Name")},
              "status": status,
              "dest_exists": dest_file.exists()}
    if status == "merged":
        result["added_keys"] = sorted(info[1])
    elif status == "conflict":
        result["conflict"] = {"working_name": info.base_name,
                              "source_name": info.conflicting_name}
        result["note"] = ("the working copy has the same identity with "
                          "another Name: the incoming block is appended "
                          "disabled (commented) for manual review")
    return result


def import_blocks(blocks, dest_file: Path) -> Tuple[bool, List[str], str]:
    """Ecrit PLUSIEURS blocs dans un meme fichier de la copie de travail.
    `blocks` = [(fichier source, ident)]. La destination n'est chargee et
    reecrite qu'UNE fois : importer 20 blocs ne relit pas 20 fois 2 Mo.
    Tout est parse et fusionne en memoire avant la moindre ecriture."""
    dest_file = Path(dest_file)
    if dest_file.exists():
        try:
            dest_doc = parse_ecf_file(dest_file)
        except Exception:  # noqa: BLE001
            return False, [], "scenario_import_failed"
    else:
        dest_doc = EcfDocument(nodes=[])
    statuses: List[str] = []
    source_docs = {}
    for source_file, ident in blocks:
        key = str(source_file)
        source_doc = source_docs.get(key)
        if source_doc is None:
            try:
                source_doc = parse_ecf_file(Path(source_file))
            except Exception:  # noqa: BLE001
                return False, [], "scenario_import_failed"
            source_docs[key] = source_doc
        block, _code = _find_block(source_doc, ident)
        if block is None:
            return False, [], "scenario_import_failed"
        status, _info = merge_single_block(dest_doc, block, "source")
        statuses.append(status)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    if dest_file.exists():
        clear_readonly(dest_file)
    atomic_write_text(dest_file, dest_doc.render())
    return True, statuses, ""


def import_block(source_file: Path, dest_file: Path, ident: str
                 ) -> Tuple[bool, str, str]:
    """Ecrit UN bloc. Retourne (ok, statut, code)."""
    ok, statuses, code = import_blocks([(source_file, ident)], dest_file)
    return ok, (statuses[0] if statuses else ""), code
