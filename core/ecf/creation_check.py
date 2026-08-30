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
Controle AVANT validation d'une creation/duplication de bloc ou d'item --
verifie les obligations qui, si elles sont ignorees, cassent le jeu ou rendent
l'entree invisible/impossible a fabriquer (contraintes confirmees sur de vrais
fichiers du jeu, synthese utilisateur du 30/08/2026) :

1. ENREGISTREMENT (fichier cible : BlocksConfig.ecf / ItemsConfig.ecf) :
   - Id unique, numerique, sous la limite du jeu (8192) ;
   - Name unique -- et surtout unique A LA CASSE PRES : le moteur d'Empyrion
     est sensible a la casse, 'MonBloc' et 'monbloc' dans deux fichiers
     plantent ou s'ignorent silencieusement (piege mortel no 2).
2. RECETTE (Templates.ecf) : un Template portant le MEME Name (strictement,
   casse comprise) doit pouvoir exister sans collision -- un Template deja
   present au meme nom, ou a la casse pres, rendra la creation incoherente.
   Sans Template, le bloc existe mais personne ne peut le fabriquer.
3. LOCALISATION (Extras/Localization.csv du scenario) : sans entree a la cle
   Name, le jeu affiche la cle technique brute ou 'Key not found'.
4. ARBRE TECHNOLOGIQUE (UnlockLevel/UnlockCost) : optionnel en creation,
   requis pour que l'item soit debloquable en Survie -- signale en info.

Chaque probleme est retourne en CreationIssue{severite, obligation, message} :
- 'erreur'        : bloque la validation (plantage/incoherence assuree) ;
- 'avertissement' : n'empeche pas d'avancer, mais l'entree sera defaillante
                    (nom brut en jeu, materiau inconnu...) ;
- 'info'          : recommandation (arbre technologique).

Les messages passent par core/i18n (cles 'createcheck.*') : l'application est
bilingue, les controles de creation doivent l'etre aussi.

Les documents de reference (Templates.ecf, MaterialConfig.ecf) sont passes par
la classe CreationContext, qui MET EN CACHE leur parsing -- le panneau GUI se
rafraichit a chaque frappe, il ne faut donc pas relire les fichiers a chaque
appel (les fichiers de reference ne changent pas pendant le dialogue).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.i18n import t

from .model import EcfDocument
from .block_creation import find_file_by_name
from .validation import MAX_BLOCK_ID

SEVERITE_ERREUR = "erreur"
SEVERITE_AVERTISSEMENT = "avertissement"
SEVERITE_INFO = "info"

_TEMPLATES_FILENAME = "Templates.ecf"
_MATERIAL_CONFIG_FILENAME = "MaterialConfig.ecf"

_OBL_REGISTRY = "createcheck.obl_registry"
_OBL_RECIPE = "createcheck.obl_recipe"
_OBL_LOCALIZATION = "createcheck.obl_localization"
_OBL_TECHTREE = "createcheck.obl_techtree"


@dataclass
class CreationIssue:
    """Un probleme detecte : severite + obligation + message traduit via i18n
    (cle 'createcheck.*' + placeholders)."""
    severite: str
    obligation_key: str
    message_key: str
    message_kwargs: Dict[str, str] = field(default_factory=dict)

    @property
    def obligation(self) -> str:
        return t(self.obligation_key)

    @property
    def message(self) -> str:
        return t(self.message_key, **self.message_kwargs)


class CreationContext:
    """Documents de reference parses UNE FOIS et mis en cache pour toute la
    duree du dialogue (Templates.ecf, MaterialConfig.ecf) + index de
    localisation. A construire une fois par dialogue, en passant la liste des
    fichiers voisins du scenario."""

    def __init__(self, sibling_ecf_files: Optional[List[Path]],
                 working_root: Optional[Path]):
        self.templates_path = find_file_by_name(sibling_ecf_files or [], _TEMPLATES_FILENAME)
        self.material_path = find_file_by_name(sibling_ecf_files or [], _MATERIAL_CONFIG_FILENAME)
        self.working_root = working_root
        self._templates_names: Optional[Set[str]] = None
        self._templates_loaded = False
        self._material_names: Optional[Set[str]] = None
        self._localization_keys: Optional[Set[str]] = None

    def templates_names(self) -> Optional[Set[str]]:
        """Noms des Templates existants, ou None si Templates.ecf est
        introuvable/illisible."""
        if not self._templates_loaded:
            self._templates_loaded = True
            if self.templates_path is not None:
                try:
                    from .parser import parse_ecf_file
                    doc = parse_ecf_file(self.templates_path)
                    self._templates_names = {
                        b.get_property('Name') for b in doc.iter_blocks()
                        if b.get_property('Name')}
                except Exception:
                    self._templates_names = None
        return self._templates_names

    def material_names(self) -> Optional[Set[str]]:
        """Noms des materiaux definis par MaterialConfig.ecf, ou None si le
        fichier est introuvable/illisible (controle alors silencieusement
        ignore -- on ne signale pas une erreur sans etre sure)."""
        if self._material_names is None:
            names: Set[str] = set()
            if self.material_path is not None:
                try:
                    from .parser import parse_ecf_file
                    doc = parse_ecf_file(self.material_path)
                    for block in doc.iter_blocks():
                        name = block.get_property('Name')
                        if name:
                            names.add(name)
                except Exception:
                    names = set()
            self._material_names = names
        return self._material_names

    def localization_keys(self) -> Optional[Set[str]]:
        """Cles de localisation connues (scenario + pack vanilla), ou None si
        aucun contexte de scenario (working_root absent)."""
        if self._localization_keys is None:
            if self.working_root is None:
                return None
            from core.localization_lookup import build_localization_index
            try:
                index = build_localization_index(self.working_root)
            except Exception:
                return set()
            self._localization_keys = index.all_keys()
        return self._localization_keys


def _iter_names(doc: EcfDocument) -> List[str]:
    """Tous les Name declares dans le document cible (en-tetes ET corps)."""
    names = []
    for block in doc.iter_blocks():
        name = block.get_property('Name')
        if name:
            names.append(name)
    return names


def check_creation(target_doc: EcfDocument, context: CreationContext,
                   kind: str, id_value: Optional[str], name_value: Optional[str],
                   properties: Optional[List[tuple]] = None,
                   check_template_collision: bool = True,
                   check_techtree_hint: bool = False) -> List[CreationIssue]:
    """Tous les controles pre-validation pour l'entree en cours de saisie.
    `target_doc` est le document DANS lequel l'entree sera inseree (le nouveau
    bloc ne doit PAS encore y figurer). `check_template_collision` desactive la
    verification Templates quand le fichier cible EST Templates.ecf (le
    controle Name suffit deja). `check_techtree_hint` active le rappel
    UnlockLevel/UnlockCost (seulement pour un bloc/item, jamais un Template)."""
    issues: List[CreationIssue] = []
    properties = properties or []
    name = (name_value or "").strip()
    id_text = (id_value or "").strip()

    # ---- 1. ENREGISTREMENT -------------------------------------------------
    if not name:
        issues.append(CreationIssue(SEVERITE_ERREUR, _OBL_REGISTRY,
                                    "createcheck.err_name_missing"))
    if id_text:
        try:
            id_num = int(id_text)
        except ValueError:
            issues.append(CreationIssue(SEVERITE_ERREUR, _OBL_REGISTRY,
                                        "createcheck.err_id_not_numeric", {"id": id_text}))
        else:
            if id_num >= MAX_BLOCK_ID:
                issues.append(CreationIssue(SEVERITE_ERREUR, _OBL_REGISTRY,
                                            "createcheck.err_id_too_high",
                                            {"id": id_text, "max": str(MAX_BLOCK_ID)}))
            if id_text in {b.get('Id') for b in target_doc.iter_blocks() if b.get('Id')}:
                issues.append(CreationIssue(SEVERITE_ERREUR, _OBL_REGISTRY,
                                            "createcheck.err_id_used", {"id": id_text}))

    if name:
        existing_names = _iter_names(target_doc)
        if name in existing_names:
            issues.append(CreationIssue(SEVERITE_ERREUR, _OBL_REGISTRY,
                                        "createcheck.err_name_used", {"name": name}))
        else:
            # Piege mortel no 2 : meme Name a la casse pres -- le moteur est
            # sensible a la casse, deux entrees ne differant que par la casse
            # coexistent dans les fichiers mais s'ecrasent/s'ignorent en jeu.
            clashes = sorted(n for n in existing_names
                             if n != name and n.lower() == name.lower())
            if clashes:
                issues.append(CreationIssue(
                    SEVERITE_ERREUR, _OBL_REGISTRY, "createcheck.err_name_case",
                    {"name": name, "others": ", ".join(clashes)}))

        material = next((v for k, v in properties if k == 'Material' and v.strip()), None)
        if material:
            known = context.material_names()
            if known is not None and material.strip() not in known:
                issues.append(CreationIssue(
                    SEVERITE_AVERTISSEMENT, _OBL_REGISTRY,
                    "createcheck.warn_material_unknown",
                    {"material": material.strip()}))

    # ---- 2. RECETTE (Templates.ecf) ----------------------------------------
    if name and check_template_collision:
        template_names = context.templates_names()
        if template_names is None:
            issues.append(CreationIssue(SEVERITE_AVERTISSEMENT, _OBL_RECIPE,
                                        "createcheck.warn_templates_missing"))
        elif name in template_names:
            issues.append(CreationIssue(SEVERITE_ERREUR, _OBL_RECIPE,
                                        "createcheck.err_template_used", {"name": name}))
        else:
            case_clashes = sorted(n for n in template_names
                                  if n != name and n.lower() == name.lower())
            if case_clashes:
                issues.append(CreationIssue(
                    SEVERITE_ERREUR, _OBL_RECIPE, "createcheck.err_template_case",
                    {"name": name, "others": ", ".join(case_clashes)}))

    # ---- 3. LOCALISATION ----------------------------------------------------
    if name:
        loc_keys = context.localization_keys()
        if loc_keys is not None and name not in loc_keys:
            issues.append(CreationIssue(SEVERITE_AVERTISSEMENT, _OBL_LOCALIZATION,
                                        "createcheck.warn_localization_missing",
                                        {"name": name}))

    # ---- 4. ARBRE TECHNOLOGIQUE ---------------------------------------------
    if name and check_techtree_hint:
        prop_keys = {k for k, _v in properties}
        if 'UnlockLevel' not in prop_keys and 'UnlockCost' not in prop_keys:
            issues.append(CreationIssue(SEVERITE_INFO, _OBL_TECHTREE,
                                        "createcheck.info_techtree_missing"))

    return issues


def has_blocking(issues: List[CreationIssue]) -> bool:
    """True si au moins une erreur BLOQUANTE (la validation doit etre refusee)."""
    return any(i.severite == SEVERITE_ERREUR for i in issues)


def format_blocking(issues: List[CreationIssue]) -> str:
    """Liste lisible des erreurs bloquantes, pour un message de refus."""
    return "\n".join(f"- {i.obligation} : {i.message}"
                     for i in issues if i.severite == SEVERITE_ERREUR)


def names_needing_localization(working_root: Optional[Path],
                               names: List[Optional[str]]) -> List[str]:
    """Parmi `names`, ceux sans entree de localisation (scenario + vanilla) --
    utilise pour ne proposer le dialogue de nom affiche que pour les entrees
    qui en ont reellement besoin."""
    if working_root is None:
        return []
    from core.localization_lookup import build_localization_index
    try:
        index = build_localization_index(working_root)
    except Exception:
        return [n for n in names if n]
    return [n for n in names if n and not index.has(n)]
