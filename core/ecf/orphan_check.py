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
Detection de definitions potentiellement inutilisees -- suggestion directe
d'un membre de la communaute Empyrion (Begebum, commentaire Steam) : jamais
une erreur, toujours informatif, car certaines definitions sont utilisees
implicitement par le jeu (voir DOCSTRING de chaque fonction pour le detail).

IMPORTANT -- portee : ces fonctions doivent TOUJOURS etre appelees avec
l'ensemble complet des fichiers .ecf d'UN scenario reellement coherent (ex:
workspace.working.configuration dans l'application), jamais un sous-ensemble
de fichiers epars -- une verification sur un ensemble incomplet produirait
des faux positifs massifs (confirme lors du developpement : 60% de "jetons
inutilises" sur une collection de fichiers non garantie complete/coherente,
chiffre non fiable tant que la source n'est pas un vrai scenario entier).

Seul le cas des JETONS (TokenConfig.ecf) est couvert pour l'instant --
volontairement restreint. Une verification similaire sur les blocs/items
generiques produirait un flot de faux positifs : un bloc de construction basique
n'est jamais "reference" dans les fichiers de configuration, il est simplement
place en jeu par le joueur -- l'absence de reference n'y signifie rien.
Les jetons, eux, n'existent que pour etre references (Token:XXXX) : leur
absence de reference est un signal nettement plus fiable.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .parser import parse_ecf_file
from .model import EcfBlock, EcfProperty, EcfComment

_TOKEN_REF_PATTERN = re.compile(r'Token:\s*(\d+)')


@dataclass
class OrphanedDefinition:
    kind: str            # 'token' pour l'instant, extensible plus tard
    identifier: str       # Id ou Name selon le type
    label: str             # texte lisible (ex: Name du jeton)
    source_file: Optional[Path] = None

    def display(self) -> str:
        loc = f" ({self.source_file.name})" if self.source_file else ""
        return f"Token:{self.identifier} -- {self.label}{loc}"


def _iter_token_refs(nodes) -> "set":
    """Parcourt l'arbre du document (blocs/proprietes/commentaires) a la
    recherche de references 'Token:XXXX', en appelant render()/render_open()
    sur chaque noeud INDIVIDUEL plutot que de re-serialiser tout le document
    d'un coup (doc.render()) -- evite de reconstruire une chaine de texte
    complete juste pour y faire une recherche regex, plus couteux et plus
    fragile en cas de changement du format de rendu global."""
    found: set = set()
    for node in nodes:
        if isinstance(node, EcfBlock):
            for match in _TOKEN_REF_PATTERN.finditer(node.render_open()):
                found.add(match.group(1))
            found |= _iter_token_refs(node.children)
        elif isinstance(node, (EcfProperty, EcfComment)):
            for match in _TOKEN_REF_PATTERN.finditer(node.render()):
                found.add(match.group(1))
    return found


def find_unused_tokens(ecf_files: List[Path]) -> List[OrphanedDefinition]:
    """Jetons definis dans TokenConfig.ecf mais jamais references
    (Token:XXXX) nulle part dans l'ensemble COMPLET des fichiers .ecf fournis
    -- voir la portee obligatoire en tete de module. Retourne une liste
    vide si TokenConfig.ecf n'est pas present dans ecf_files."""
    token_path = next((f for f in ecf_files if f.name == "TokenConfig.ecf"), None)
    if token_path is None:
        return []

    try:
        token_doc = parse_ecf_file(token_path)
    except Exception:
        return []

    defined: dict = {}
    for block in token_doc.iter_blocks():
        if block.kind != "Token":
            continue
        token_id = block.get("Id")
        if token_id:
            defined[token_id] = block.get_property("Name") or ""

    referenced: set = set()
    for path in ecf_files:
        try:
            doc = parse_ecf_file(path)
        except Exception:
            continue
        referenced |= _iter_token_refs(doc.nodes)

    unused = []
    for token_id, name in sorted(defined.items(), key=lambda kv: int(kv[0])):
        if token_id not in referenced:
            unused.append(OrphanedDefinition(
                kind="token", identifier=token_id, label=name, source_file=token_path))
    return unused
