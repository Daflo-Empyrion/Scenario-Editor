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

"""Contrat d'une surface d'edition pour l'assistant.

Une surface fournit trois choses, et rien d'autre :
  - son CONTEXTE (ce qui est joint a la question, plafonne) ;
  - ses OUTILS de lecture (le modele peut aller chercher plus loin) ;
  - son APPLIQUER : un callback qui valide puis ecrit dans l'editeur, avec
    snapshot undo -- jamais l'assistant lui-meme.

C'est ce contrat qui rend l'assistant « partout » sans un ecran par onglet :
un editeur l'implemente en quinze lignes et herite de la fenetre, du flux,
de la revue et de l'annulation.
"""
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ..actions import Action
from ..context import TabContext
from ..tools import ToolRegistry

DEFAULT_INSTRUCTION = (
    "Answer the user's question about the active editor. Use the attached "
    "context and the read-only tools instead of guessing. If a change is "
    "needed, propose it as a change set and let the user review it; never "
    "claim it was applied.")

# Onglet sans ecrivain : les valeurs vont en prose. Avec un espace de travail,
# seul l'import A/B (scenario_import) reste ecrivable.
READ_ONLY_INSTRUCTION = (
    "No editor is active for this tab and no working copy is open: you cannot "
    "apply any change. Do NOT return a JSON change set. Instead give the "
    "exact file, key and value to change, one per line, so the user can "
    "apply them.")

READ_ONLY_IMPORT_INSTRUCTION = (
    "No editor is active for this tab. You may propose ONLY 'scenario_import' "
    "changes (copy from A/B into the working copy). Never propose ecf_set, "
    "yaml_set, csv_set, pda_field or playfield_place here: nothing would "
    "apply them. For any other change, give the exact file, key and value "
    "to change in prose.")


@dataclass
class SurfaceBinding:
    name: str
    context: Callable[[], TabContext]
    registry: Callable[[], ToolRegistry]
    apply: Callable[[List], Tuple[bool, str]]
    instruction: str = ""
    # Developpe le ChangeSet juste AVANT la revue (ex. une ligne
    # 'scenario_import ... +deps' -> une ligne par dependance). L'ecriture
    # reste interdite ici : on ne fait que proposer plus finement.
    expand: Optional[Callable] = None
    # False = surface sans ecrivain (onglet non editeur) : ne jamais proposer
    # un ChangeSet que l'apply refusera (vecu 23/10 : « Cet onglet n'applique
    # aucune modification » devant une proposition gameoptions.yaml).
    produces_changeset: bool = True
    # Kinds que cet applier sait ecrire ; None = tous. Les autres lignes sont
    # retirees AVANT la revue : jamais de bouton Appliquer qui refuse.
    kinds: Optional[Tuple[str, ...]] = None

    def action(self) -> Action:
        return Action(id="chat", surface=self.name, min_class="normal",
                      needs_tools=bool(self.registry().names(self.name)),
                      produces_changeset=self.produces_changeset,
                      instruction=self.instruction or DEFAULT_INSTRUCTION)


def with_scenario_tools(binding: SurfaceBinding, root, extra_roots=None
                        ) -> SurfaceBinding:
    """Ajoute les outils de lecture du scenario (lister, chercher, lire,
    bloc ECF d'un autre fichier) a une surface existante.

    Vecu 21/10 : le modele ne pouvait lire que le fichier actif et repondait
    « donne-moi le fichier » a « ou est reference X ». Vecu 22/10 : il ne
    pouvait lister que la COPIE DE TRAVAIL, donc etait incapable de preparer
    la fusion d'un bloc de B avec ses dependances. `extra_roots` (ex.
    {'a': ..., 'b': ...}) ouvre les scenarios sources en lecture seule."""
    from . import scenario

    def registry():
        tools = binding.registry()
        scenario.add_tools(tools, root, binding.name, extra_roots)
        return tools

    parts = [binding.instruction, scenario.INSTRUCTION]
    if extra_roots and any(extra_roots.values()):
        parts.append(scenario.IMPORT_INSTRUCTION)
    instruction = "\n".join(part for part in parts if part).strip()
    return SurfaceBinding(name=binding.name, context=binding.context,
                          registry=registry, apply=binding.apply,
                          instruction=instruction, expand=binding.expand,
                          produces_changeset=binding.produces_changeset,
                          kinds=binding.kinds)


def arg(args: dict, *names) -> str:
    """Tolerance aux noms de parametres devines par le modele (id/name/block
    au lieu de ident...) : un modele qui se trompe ne doit pas boucler sur
    une erreur cryptique."""
    for name in names:
        value = (args or {}).get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def problem_text(code: str) -> str:
    """Cle i18n d'un code de validation ; le code brut reste affiche si la
    traduction manque (jamais de message vide devant l'utilisateur)."""
    from core.i18n import has, t
    key = _PROBLEM_KEYS.get(code)
    return t(key) if key and has(key) else code


_PROBLEM_KEYS = {
    "changeset_vide": "assistant.cs_empty",
    "changeset_trop_long": "assistant.cs_too_long",
    "changeset_absent": "assistant.cs_absent",
    "kind_inconnu": "assistant.cs_unknown_kind",
    "cible_vide": "assistant.cs_empty_target",
    "changement_sans_effet": "assistant.cs_no_effect",
    "outils_indisponibles": "assistant.cs_no_tools",
    "aucune_question": "assistant.cs_no_question",
    "boucle_outils_interrompue": "assistant.cs_tool_loop",
    "scenario_import_invalid": "assistant.import_invalid",
    "scenario_import_missing": "assistant.import_missing",
    "scenario_import_failed": "assistant.import_failed",
    "scenario_import_unavailable": "assistant.import_unavailable",
    "ecf_target_invalid": "assistant.ecf_target_invalid",
    "ecf_block_not_found": "assistant.ecf_block_not_found",
    "ecf_block_ambiguous": "assistant.ecf_block_ambiguous",
    "ecf_key_missing": "assistant.ecf_key_missing",
    "ecf_key_ambiguous": "assistant.ecf_key_ambiguous",
    "ecf_value_changed": "assistant.ecf_value_changed",
    "ecf_block_invalid": "assistant.ecf_block_invalid",
    "ecf_identity_missing": "assistant.ecf_identity_missing",
    "ecf_duplicate_identity": "assistant.ecf_duplicate_identity",
    "ecf_kind_unsupported": "assistant.ecf_kind_unsupported",
    "ecf_nothing_written": "assistant.ecf_nothing_written",
    "csv_target_invalid": "assistant.csv_target_invalid",
    "csv_row_out": "assistant.csv_row_out",
    "csv_column_unknown": "assistant.csv_column_unknown",
    "csv_value_changed": "assistant.csv_value_changed",
    "csv_kind_unsupported": "assistant.csv_kind_unsupported",
    "csv_nothing_written": "assistant.csv_nothing_written",
    "yaml_target_invalid": "assistant.yaml_target_invalid",
    "yaml_key_not_found": "assistant.yaml_key_not_found",
    "yaml_value_changed": "assistant.yaml_value_changed",
    "yaml_kind_unsupported": "assistant.yaml_kind_unsupported",
    "yaml_nothing_written": "assistant.yaml_nothing_written",
    "pda_field_unknown": "assistant.pda_field_unknown",
    "pda_kind_unsupported": "assistant.pda_kind_unsupported",
    "unsupported": "assistant.unsupported",
}


def first_problem(problems: List[str]) -> Optional[str]:
    return problem_text(problems[0]) if problems else None
