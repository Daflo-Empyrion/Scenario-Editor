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
Extraction structuree d'un fichier Dialogues.ecf pour navigation --
vocabulaire de champs confirme sur un vrai fichier (5417 blocs, 48601
lignes) : Output, Option_N/OptionNext_N/OptionIf_N/OptionExecute_N (choix
proposes au joueur), Next_N/NextIf_N (transitions automatiques, sans choix
du joueur), Variable_N (avec param1: type), Execute_N (scripts), NPCName.

'End'/'GotoAndReset'/'Return' sont des sentinelles reservees (jamais des
noms de dialogue reels) -- confirme lors de la construction de la
verification croisee (core/ecf/cross_reference_check.py:_check_dialogue_refs).

Sur OptionNext_N, un param1 present correspond systematiquement au Name du
dialogue CONTENANT lui-meme (confirme sur 5 echantillons reels, 473 cas sur
8769) -- un "point de retour" apres un sous-dialogue plutot qu'une reference
croisee vers un autre fichier."""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ecf.model import EcfProperty
from .ecf.cross_reference_check import _DIALOGUE_REF_SENTINELS


@dataclass
class DialogueOption:
    index: int
    text: str
    next_target: Optional[str] = None
    next_return_to: Optional[str] = None
    condition: Optional[str] = None
    execute: Optional[str] = None


@dataclass
class DialogueTransition:
    index: int
    target: str
    condition: Optional[str] = None


@dataclass
class DialogueVariable:
    name: str
    var_type: str


@dataclass
class DialogueInfo:
    name: str
    npc_name: Optional[str] = None
    output: Optional[str] = None
    options: List[DialogueOption] = field(default_factory=list)
    transitions: List[DialogueTransition] = field(default_factory=list)
    variables: List[DialogueVariable] = field(default_factory=list)
    executes: List[str] = field(default_factory=list)
    source_block = None  # EcfBlock -- pas type-hinte pour eviter l'import circulaire


def _indexed_children(block, prefix: str) -> Dict[int, EcfProperty]:
    """Toutes les proprietes enfants dont la cle correspond a 'prefix_N',
    indexees par N."""
    result = {}
    for child in block.children:
        if not isinstance(child, EcfProperty) or not child.pairs:
            continue
        key = child.pairs[0][0]
        if not key:
            continue
        m = re.match(rf'^{re.escape(prefix)}_(\d+)$', key)
        if m:
            result[int(m.group(1))] = child
    return result


def parse_dialogue_block(block) -> DialogueInfo:
    info = DialogueInfo(name=block.get_property("Name") or "?")
    info.source_block = block

    npc_prop = next((c for c in block.children if isinstance(c, EcfProperty) and c.pairs
                      and c.pairs[0][0] == "NPCName"), None)
    if npc_prop:
        info.npc_name = npc_prop.pairs[0][1]

    output_prop = next((c for c in block.children if isinstance(c, EcfProperty) and c.pairs
                         and c.pairs[0][0] == "Output"), None)
    if output_prop:
        info.output = output_prop.pairs[0][1]

    option_texts = _indexed_children(block, "Option")
    option_nexts = _indexed_children(block, "OptionNext")
    option_ifs = _indexed_children(block, "OptionIf")
    option_execs = _indexed_children(block, "OptionExecute")
    for idx in sorted(option_texts.keys()):
        next_prop = option_nexts.get(idx)
        next_target = next_prop.pairs[0][1] if next_prop else None
        return_to = None
        if next_prop and len(next_prop.pairs) > 1:
            for k, v in next_prop.pairs[1:]:
                if k == "param1":
                    return_to = v
        cond_prop = option_ifs.get(idx)
        exec_prop = option_execs.get(idx)
        info.options.append(DialogueOption(
            index=idx, text=option_texts[idx].pairs[0][1],
            next_target=next_target, next_return_to=return_to,
            condition=cond_prop.pairs[0][1] if cond_prop else None,
            execute=exec_prop.pairs[0][1] if exec_prop else None,
        ))

    next_targets = _indexed_children(block, "Next")
    next_ifs = _indexed_children(block, "NextIf")
    for idx in sorted(next_targets.keys()):
        cond_prop = next_ifs.get(idx)
        info.transitions.append(DialogueTransition(
            index=idx, target=next_targets[idx].pairs[0][1],
            condition=cond_prop.pairs[0][1] if cond_prop else None,
        ))

    variables = _indexed_children(block, "Variable")
    for idx in sorted(variables.keys()):
        var_prop = variables[idx]
        var_name = var_prop.pairs[0][1]
        var_type = ""
        for k, v in var_prop.pairs[1:]:
            if k == "param1":
                var_type = v
        info.variables.append(DialogueVariable(name=var_name, var_type=var_type))

    executes = _indexed_children(block, "Execute")
    for idx in sorted(executes.keys()):
        info.executes.append(executes[idx].pairs[0][1])

    return info


def build_dialogue_index(doc) -> Dict[str, DialogueInfo]:
    """Name -> DialogueInfo, pour toutes les entrees +Dialogue du document."""
    index = {}
    for block in doc.iter_blocks():
        if block.kind.lstrip("+-") != "Dialogue":
            continue
        info = parse_dialogue_block(block)
        index[info.name] = info
    return index


def build_incoming_links_index(dialogue_index: Dict[str, DialogueInfo]) -> Dict[str, List[str]]:
    """target_name -> [noms des dialogues qui y menent] -- construit une seule
    fois pour tout le fichier plutot que de re-parcourir a chaque clic de
    navigation. Ignore les sentinelles (End, GotoAndReset, Return) et les
    references dynamiques (@Variable), coherent avec
    cross_reference_check.py:_check_dialogue_refs."""
    incoming: Dict[str, List[str]] = {}
    for name, info in dialogue_index.items():
        targets = [t.target for t in info.transitions] + [o.next_target for o in info.options if o.next_target]
        for target in targets:
            if not target or target in _DIALOGUE_REF_SENTINELS or target.startswith("@"):
                continue
            incoming.setdefault(target, []).append(name)
    return incoming
