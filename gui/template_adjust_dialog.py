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
Dialogue d'ajustement des Template(s) auto-cree(s) pendant une duplication
(voir gui/ecf_edit_widget.py::_create_templates_for_variants) -- demande
explicite de l'utilisateur (session du 29/08/2026, PRECISEE apres un premier
essai trop simplifie) :
  - Chaque Template cree doit etre editable INDIVIDUELLEMENT -- un onglet par
    Template (voir gui/template_recipe_editor.py), PAS une seule valeur
    appliquee uniformement a tous (contrairement au tableau de proprietes du
    bloc lui-meme dans DuplicateVariantsDialog, qui reste uniforme).
  - Chaque onglet permet aussi d'AJOUTER un nouvel ingredient a la recette
    via une liste deroulante des blocs/items valides (voir
    core.ecf.block_creation.list_craftable_names), pas seulement d'ajuster
    la quantite d'un ingredient deja present."""
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget

from core.i18n import t
from gui.template_recipe_editor import TemplateRecipeEditor


class TemplateAdjustDialog(QDialog):
    """`template_names` : noms des Templates a creer (un onglet chacun).
    `scalar_fields`/`ingredients` : etat de depart du Template SOURCE,
    duplique comme point de depart identique pour CHAQUE onglet (l'edition
    ulterieure de chaque onglet est independante). `craftable_names` : pool
    pour la liste deroulante d'ajout d'ingredient (voir
    core.ecf.block_creation.list_craftable_names). `property_pool` : noms de
    proprietes observes sur les autres Templates du fichier (liste
    deroulante d'AJOUT de propriete scalaire) ; `values_by_key` : valeurs
    observees par propriete (liste deroulante de valeurs) ;
    `common_quantities` : quantites d'ingredients observees (liste
    deroulante des quantites) ; `ingredient_values_by_key` : quantites
    observees PER-INGREDIENT (prioritaires sur common_quantities dans la
    colonne quantite) -- demandes du 30/08/2026 : liste deroulante
    PARTOUT ou c'est possible."""

    def __init__(self, template_names: List[str], scalar_fields: List[Tuple[str, str]],
                 ingredients: List[Tuple[str, str]], craftable_names: List[str],
                 property_pool: Optional[List[str]] = None,
                 values_by_key: Optional[Dict[str, List[str]]] = None,
                 common_quantities: Optional[List[str]] = None,
                 ingredient_values_by_key: Optional[Dict[str, List[str]]] = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dup.adjust_template_toggle"))
        self.setMinimumSize(520, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("dup.adjust_template_hint")))

        self.tabs = QTabWidget()
        self._editors: Dict[str, TemplateRecipeEditor] = {}
        for name in template_names:
            editor = TemplateRecipeEditor(
                list(scalar_fields), list(ingredients), craftable_names,
                property_pool=property_pool, values_by_key=values_by_key,
                common_quantities=common_quantities,
                ingredient_values_by_key=ingredient_values_by_key)
            self._editors[name] = editor
            self.tabs.addTab(editor, name)
        layout.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        btn_ok = QPushButton(t("transform.btn_apply"))
        btn_ok.clicked.connect(self.accept)
        buttons.addWidget(btn_ok)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def get_entries(self) -> Dict[str, Dict[str, object]]:
        """Retourne {nom_template: {'scalar': {...}, 'ingredients': {...},
        'removed': [...], 'removed_scalars': [...]}} -- UNIQUEMENT pour les
        Templates ayant au moins un changement (scalaire modifie/ajoute,
        ingredient ajoute/modifie ou retire, PROPRIETE SCALAIRE retiree),
        chacun avec SES PROPRES modifications (jamais uniformes entre
        Templates -- voir docstring du module)."""
        entries: Dict[str, Dict[str, object]] = {}
        for name, editor in self._editors.items():
            scalar = editor.get_scalar_overrides()
            ingredients = editor.get_changed_or_added_ingredients()
            removed = editor.get_removed_ingredients()
            removed_scalars = editor.get_removed_scalars()
            if scalar or ingredients or removed or removed_scalars:
                entries[name] = {'scalar': scalar, 'ingredients': ingredients,
                                 'removed': removed, 'removed_scalars': removed_scalars}
        return entries
