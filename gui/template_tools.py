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
Outils partages de creation de Templates (recettes de craft) -- utilises par
TOUS les modes qui peuvent aboutir a un bloc/item sans recette : creation
guidee, duplication simple, duplication multi-variantes, fusion depuis
Scenario A/B (demande explicite de l'utilisateur du 30/08/2026).

Deux sources de pre-remplissage :
- un Template SOURCE existant (duplication d'un bloc qui en avait un) :
  copie exacte de sa structure, seul le Name change ;
- AUCUN Template source : le Template de base part des VALEURS LES PLUS
  COURANTES du fichier (scan_template_defaults) et contient TOUTES les
  proprietes observees sur les autres Templates du fichier (pas seulement
  CraftTime/Target -- demande explicite du 30/08/2026 : on pre-remplit
  large et l'utilisateur supprime ce qui ne convient pas, une propriete
  absente du depart etant une propriete oubliee).

Dans tous les cas, un apercu editable individuel par Template est propose
avant l'ecriture (gui/template_adjust_dialog.py), avec AJOUT et SUPPRESSION
de proprietes scalaires (listes deroulantes : noms observes sur les autres
Templates, valeurs courantes par propriete) et AJOUT et SUPPRESSION
d'ingredients (listes deroulantes : blocs/items valides, quantites
courantes -- gui/template_recipe_editor.py).
"""
import copy as _copy
from pathlib import Path
from typing import List, Optional

from core.ecf.block_creation import (
    create_new_block, add_child_inputs, scan_template_defaults,
)
from core.ecf.variants import (
    list_template_scalar_fields, list_template_ingredients,
    set_block_field, set_template_ingredient, remove_template_ingredient,
    remove_template_scalar,
)
from gui.template_adjust_dialog import TemplateAdjustDialog


def create_templates(parent, main_window, templates_path: Path,
                     variant_names: List[str],
                     source_template_name: str = "", author: str = "",
                     craftable_names: Optional[List[str]] = None) -> int:
    """Cree un Template par nom de `variant_names` dans Templates.ecf, ouvert
    comme un VRAI onglet de la copie de travail (jamais d'ecriture directe
    disque, cf. _create_associated_template).

    - `source_template_name` fourni ET trouve dans le fichier : chaque
      Template est une copie de sa structure (Target, CraftTime, Child
      Inputs...), seul le Name change.
    - sinon (nom absent, vide, ou Template introuvable) : chaque Template
      part des VALEURS LES PLUS COURANTES du fichier (scan_template_defaults)
      avec TOUTES les proprietes observees sur les autres Templates -- demande
      explicite de l'utilisateur du 30/08/2026 : pouvoir creer une recette
      meme quand le bloc duplique/cree n'en avait pas d'origine.

    Un apercu editable individuel (ajustement/ajout/SUPPRESSION de scalaires,
    ajout/suppression d'ingredients, listes deroulantes de valeurs et de
    quantites courantes) est propose avant l'ecriture ; l'annuler signifie
    'sans ajustement', pas 'annuler la creation'. Retourne le nombre cree.
    Aucune question de confirmation ici : l'appelant l'a deja posee."""
    widget = main_window.open_working_file_tab(templates_path)
    if widget is None:
        return 0
    templates_edit = getattr(widget, "edit_widget", widget)
    if not hasattr(templates_edit, "doc"):
        return 0
    templates_doc = templates_edit.doc

    source_template = None
    if source_template_name:
        for block in templates_doc.iter_blocks():
            if block.get_property('Name') == source_template_name:
                source_template = block
                break

    # Pool global du fichier : noms de proprietes observes sur les autres
    # Templates (liste deroulante d'ajout), valeurs courantes par propriete
    # (liste deroulante de valeurs), quantites courantes (liste deroulante
    # des quantites) -- alimente l'apercu editable dans TOUS les modes, meme
    # quand un Template source existe (on veut pouvoir lui AJOUTER une
    # propriete existant ailleurs dans le fichier).
    pool = scan_template_defaults(templates_doc)
    values_by_key = (pool or {}).get("values_by_key", {})
    common_quantities = (pool or {}).get("quantities", [])
    ingredient_values_by_key = (pool or {}).get("ingredient_values_by_key", {})
    property_pool = list(values_by_key) if values_by_key else None

    if source_template is not None:
        scalar_fields = list_template_scalar_fields(source_template)
        ingredients = list_template_ingredients(source_template)
    else:
        if pool is None:
            # Aucun Template dans le fichier : aucune valeur courante dont
            # partir -- l'appelant aura deja prevenue avant d'appeler.
            return 0
        scalar_fields = pool["scalars"]
        ingredients = pool["ingredients"]

    from PyQt6.QtWidgets import QDialog
    adjust_dialog = TemplateAdjustDialog(
        variant_names, list(scalar_fields), list(ingredients),
        list(craftable_names or []), property_pool=property_pool,
        values_by_key=values_by_key, common_quantities=common_quantities,
        ingredient_values_by_key=ingredient_values_by_key, parent=parent)
    entries: dict = {}
    if adjust_dialog.exec() == QDialog.DialogCode.Accepted:
        entries = adjust_dialog.get_entries()
    # Annuler l'ajustement ne bloque PAS la creation (deja confirmee en amont).

    if hasattr(templates_edit, "_snapshot_undo"):
        templates_edit._snapshot_undo()

    existing_names = {b.get_property('Name') for b in templates_doc.iter_blocks()
                      if b.get_property('Name')}
    created = 0
    for variant_name in variant_names:
        if variant_name in existing_names:
            continue
        if source_template is not None:
            new_template = _copy.deepcopy(source_template)
            new_template.dirty = True
            if not new_template.set('Name', variant_name):
                new_template.set_property('Name', variant_name)
            new_template.remove('Id')
            if author:
                new_template.comment = (f"# Ajouté par {author} "
                                        f"(variante de {source_template_name})")
        else:
            new_template = create_new_block(pool["kind"], None, variant_name,
                                             list(scalar_fields))
            if ingredients:
                add_child_inputs(new_template, list(ingredients))
            if author:
                new_template.comment = f"# Ajouté par {author}"
        variant_entries = entries.get(variant_name, {})
        for field_key, field_value in variant_entries.get('scalar', {}).items():
            set_block_field(new_template, field_key, field_value)
        for scalar_key in variant_entries.get('removed_scalars', []):
            remove_template_scalar(new_template, scalar_key)
        for ingredient_name, quantity in variant_entries.get('ingredients', {}).items():
            set_template_ingredient(new_template, ingredient_name, quantity)
        for ingredient_name in variant_entries.get('removed', []):
            remove_template_ingredient(new_template, ingredient_name)
        templates_doc.nodes.append(new_template)
        created += 1

    if created > 0:
        if hasattr(templates_edit, "_set_modified"):
            templates_edit._set_modified(True)
        if hasattr(templates_edit, "_populate_tree"):
            templates_edit._populate_tree()
    return created


def templates_path_in(sibling_ecf_files: Optional[List[Path]]) -> Optional[Path]:
    """Templates.ecf parmi les fichiers voisins du scenario, ou None."""
    from core.ecf.block_creation import find_file_by_name
    return find_file_by_name(sibling_ecf_files or [], 'Templates.ecf')
