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
Edition structuree d'un playfield.yaml -- Ressources (aleatoires + asteroides),
POI, Creatures -- en plus de l'edition YAML brute classique (onglet "YAML
complet", toujours disponible pour tout ce que ces vues structurees ne
couvrent pas : atmosphere, ciel, drones...).

Portee volontaire (voir core/playfield_editor.py pour le detail complet) :
- Ressources : ajout/suppression/modification, avec liste deroulante de blocs
  "*Resource" reellement trouves dans BlocksConfig.ecf.
- POI et Creatures : MODIFICATION SEULEMENT des entrees deja presentes
  (delais, difficulte, distances, quantites...) -- jamais d'ajout d'un nouveau
  POI/creature par selection de type, faute de source fiable pour peupler une
  telle liste (voir le commentaire de tete de core/playfield_editor.py).

Les tables structurees et l'onglet "YAML complet" partagent le MEME document
en memoire (self.doc) -- une modification faite d'un cote est immediatement
visible de l'autre des le changement d'onglet.
"""
from pathlib import Path
from typing import List, Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QDialog, QComboBox, QDialogButtonBox, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.i18n import t
from core.yamllite.model import YamlEntry
from core.playfield_editor import (
    find_top_level_key, list_items, find_poi_items, find_creature_items,
    get_item_params, set_item_param, list_resource_block_names,
    add_resource_item, remove_resource_item,
    get_creature_biome, get_properties_value, set_properties_value,
    find_space_resource_items, get_space_resource_display_name,
    list_space_material_names, add_space_resource_item, remove_space_resource_item,
    find_drone_stock_items, find_free_drones_items, find_space_vessels_items,
    find_drone_spawning_items, find_spawn_rate_zones_items, find_spawn_zones_items,
    find_special_effects_local_items, find_special_effects_global_items,
)
from gui.playfield_canvas_widget import PlayfieldCanvasWidget
from gui.yaml_edit_widget import YamlEditWidget
from gui.theme import icon, icon_size


class SyntheticColumn:
    """Colonne calculee (pas directement issue de get_item_params) -- ex: le
    biome d'une creature (contexte englobant, pas un parametre de l'item
    lui-meme), ou RegenAfter d'un POI (imbrique dans Properties, pas une
    valeur scalaire directe). getter(item) -> texte affiche ; setter(item,
    texte) -> bool (None si colonne en lecture seule, ex: le biome)."""

    def __init__(self, label: str, getter: Callable[[YamlEntry], Optional[str]],
                 setter: Optional[Callable[[YamlEntry, str], bool]] = None):
        self.label = label
        self.getter = getter
        self.setter = setter

    @property
    def editable(self) -> bool:
        return self.setter is not None


def _is_complex_param(item: YamlEntry, key: str) -> bool:
    """True si ce parametre est lui-meme une structure imbriquee (ex: 'Properties'
    avec ses propres sous-entrees Key/Value) plutot qu'une simple valeur scalaire
    -- non editable directement dans une cellule de tableau."""
    for child in item.children:
        if isinstance(child, YamlEntry) and child.key == key:
            return any(isinstance(c, YamlEntry) for c in child.children)
    return False


class AddResourceDialog(QDialog):
    """Petit dialogue de choix du bloc a ajouter comme nouvelle ressource --
    liste deroulante peuplee depuis BlocksConfig.ecf (voir
    list_resource_block_names), jamais de saisie libre pour eviter un nom
    inventé qui ne correspondrait a aucun bloc reel."""

    def __init__(self, resource_names: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("playfield.add_resource_title"))
        layout = QFormLayout(self)
        self.combo = QComboBox()
        self.combo.addItems(resource_names)
        self.combo.setEditable(False)
        layout.addRow(t("playfield.resource_name_label"), self.combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_name(self) -> Optional[str]:
        return self.combo.currentText() if self.combo.currentText() else None


class PlayfieldSectionTable(QWidget):
    """Tableau generique pour une section de playfield (Ressources, POI,
    Creatures) -- colonnes calculees dynamiquement depuis l'union des
    parametres reellement presents sur les items (chaque item n'a pas
    forcement les memes champs que ses voisins, ex: certains POI n'ont pas de
    DroneProb). Les colonnes les plus frequentes apparaissent en premier."""

    changed = pyqtSignal()  # emis apres toute modification reussie (edition/ajout/suppression)

    def __init__(self, get_items_fn: Callable[[], List[YamlEntry]], name_column_label: str,
                 allow_add_remove: bool = False, add_callback: Optional[Callable] = None,
                 remove_callback: Optional[Callable[[YamlEntry], None]] = None,
                 before_edit_callback: Optional[Callable[[], None]] = None,
                 synthetic_columns: Optional[List[SyntheticColumn]] = None,
                 name_display_fn: Optional[Callable[[YamlEntry], str]] = None,
                 parent=None):
        super().__init__(parent)
        self.get_items_fn = get_items_fn
        self.add_callback = add_callback
        self.remove_callback = remove_callback
        self.before_edit_callback = before_edit_callback
        self.synthetic_columns = synthetic_columns or []
        self.name_display_fn = name_display_fn or (lambda item: item.value)
        self._items_by_row: List[YamlEntry] = []
        self._columns: List[str] = []

        layout = QVBoxLayout(self)

        if allow_add_remove:
            toolbar = QHBoxLayout()
            self.btn_add = QPushButton(t("playfield.btn_add"))
            self.btn_add.clicked.connect(self._on_add_clicked)
            toolbar.addWidget(self.btn_add)
            self.btn_remove = QPushButton(t("playfield.btn_remove"))
            self.btn_remove.clicked.connect(self._on_remove_clicked)
            toolbar.addWidget(self.btn_remove)
            toolbar.addStretch()
            layout.addLayout(toolbar)

        self.count_label = QLabel("")
        layout.addWidget(self.count_label)

        self.table = QTableWidget()
        self.table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, 1)

        self._name_column_label = name_column_label
        self._allow_add_remove = allow_add_remove
        self.refresh()

    def refresh(self):
        """Reconstruit entierement le tableau depuis le document actuel -- a
        appeler apres toute modification externe (undo, sauvegarde...)."""
        self.table.blockSignals(True)
        self._items_by_row = list(self.get_items_fn())

        # Union des cles de parametres, triees par frequence d'usage decroissante
        # (les plus communes d'abord, plus lisible qu'un ordre alphabetique brut
        # quand une section a beaucoup de parametres differents comme les POI).
        key_counts = {}
        for item in self._items_by_row:
            for key, _ in get_item_params(item):
                key_counts[key] = key_counts.get(key, 0) + 1
        self._columns = sorted(key_counts.keys(), key=lambda k: -key_counts[k])

        # Colonnes synthetiques (biome, RegenAfter...) juste apres le Nom, avant
        # les parametres directs -- ce sont generalement les infos les plus
        # importantes a voir en premier (voir SyntheticColumn).
        n_synth = len(self.synthetic_columns)
        headers = [self._name_column_label] + [c.label for c in self.synthetic_columns] + self._columns
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self._items_by_row))

        for row, item in enumerate(self._items_by_row):
            name_item = QTableWidgetItem(self.name_display_fn(item))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)

            for col_offset, synth in enumerate(self.synthetic_columns):
                value = synth.getter(item)
                cell = QTableWidgetItem(value if value is not None else "")
                if not synth.editable or value is None:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 1 + col_offset, cell)

            params = dict(get_item_params(item))
            for col, key in enumerate(self._columns, start=1 + n_synth):
                if key not in params:
                    cell = QTableWidgetItem("")
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                elif _is_complex_param(item, key):
                    cell = QTableWidgetItem(t("playfield.complex_value_placeholder"))
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                else:
                    cell = QTableWidgetItem(params[key])
                self.table.setItem(row, col, cell)

        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        self.count_label.setText(t("playfield.count_label", n=len(self._items_by_row)))
        if self._allow_add_remove:
            self.btn_remove.setEnabled(len(self._items_by_row) > 0)

    def _on_cell_changed(self, cell: QTableWidgetItem):
        row, col = cell.row(), cell.column()
        if col == 0 or row >= len(self._items_by_row):
            return  # colonne Nom non editable ; ligne perimee (rare, entre deux refresh)
        item = self._items_by_row[row]
        n_synth = len(self.synthetic_columns)

        if self.before_edit_callback:
            self.before_edit_callback()

        if col <= n_synth:
            synth = self.synthetic_columns[col - 1]
            if synth.setter:
                synth.setter(item, cell.text())
        else:
            key = self._columns[col - 1 - n_synth]
            set_item_param(item, key, cell.text())
        self.changed.emit()

    def _on_add_clicked(self):
        if self.add_callback:
            self.add_callback()

    def _on_remove_clicked(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._items_by_row):
            QMessageBox.information(self, t("playfield.btn_remove"), t("playfield.no_row_selected"))
            return
        item = self._items_by_row[row]
        confirm = QMessageBox.question(
            self, t("playfield.btn_remove"),
            t("playfield.confirm_remove", name=item.value),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self.remove_callback:
            self.remove_callback(item)


class PlayfieldEditWidget(QWidget):
    """Widget principal ouvert pour tout fichier playfield*.yaml -- combine les
    vues structurees (Ressources/POI/Creatures) et l'edition YAML brute
    classique, toutes operant sur le MEME document en memoire."""

    modified_changed = pyqtSignal(bool)
    saved = pyqtSignal()

    def __init__(self, path: Path, blocks_ecf_files: Optional[List[Path]] = None, parent=None):
        super().__init__(parent)
        self.path = path
        self.blocks_ecf_files = blocks_ecf_files or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Barre persistante -- visible quel que soit l'onglet actif (Ressources,
        # POI, Creatures, YAML complet), pour que "Enregistrer" ne soit jamais a
        # chercher dans un onglet precis. Signale directement par retour
        # utilisateur : avant cette barre, il fallait passer par l'onglet "YAML
        # complet" pour trouver le bouton, facilement oublie apres une
        # modification faite depuis un autre onglet.
        toolbar = QHBoxLayout()
        self.modified_label = QLabel("")
        toolbar.addWidget(self.modified_label)
        toolbar.addStretch()
        self.btn_save = QPushButton(t("playfield.btn_save"))
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self.save)
        toolbar.addWidget(self.btn_save)
        layout.addLayout(toolbar)

        # Raccourci Ctrl+S au niveau du widget entier (pas seulement l'onglet
        # YAML brut) -- fonctionne quel que soit l'onglet actif au moment de
        # l'appui, contrairement au raccourci propre a YamlEditWidget qui ne
        # s'applique que quand CET onglet precis a le focus clavier.
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # L'onglet "YAML complet" EST le vrai YamlEditWidget -- gere deja
        # save/undo/etat modifie proprement. Les tables structurees ci-dessous
        # partagent SON document (self.doc = self.raw_widget.doc), jamais une
        # copie -- une modification d'un cote est visible immediatement de
        # l'autre.
        self.raw_widget = YamlEditWidget(path)
        self.doc = self.raw_widget.doc
        self.raw_widget.modified_changed.connect(self.modified_changed.emit)
        self.raw_widget.modified_changed.connect(self._update_modified_label)
        self.raw_widget.saved.connect(self.saved.emit)
        self.raw_widget.saved.connect(lambda: self._update_modified_label(False))

        resources_tab = self._build_resources_tab()
        canvas_tab = self._build_canvas_tab()
        poi_regen_column = SyntheticColumn(
            label=t("playfield.col_regen_after"),
            getter=lambda item: get_properties_value(item, "RegenAfter"),
            setter=lambda item, value: set_properties_value(item, "RegenAfter", value),
        )
        poi_tab_inner = self._build_readonly_params_tab(
            lambda: find_poi_items(self.doc), t("playfield.col_groupname"),
            synthetic_columns=[poi_regen_column])
        poi_tab = self._wrap_with_poi_inspector_button(poi_tab_inner)

        creature_biome_column = SyntheticColumn(
            label=t("playfield.col_biome"),
            getter=get_creature_biome,
        )
        creatures_tab = self._build_readonly_params_tab(
            lambda: find_creature_items(self.doc), t("playfield.col_name"),
            synthetic_columns=[creature_biome_column])

        drones_tab = self._build_drones_tab()
        spawn_zones_tab = self._build_spawn_zones_tab()
        special_effects_tab = self._build_special_effects_tab()

        self.tab_widget.addTab(canvas_tab, t("playfield.tab_canvas"))
        self.tab_widget.addTab(resources_tab, t("playfield.tab_resources"))
        self.tab_widget.addTab(poi_tab, t("playfield.tab_poi"))
        self.tab_widget.addTab(creatures_tab, t("playfield.tab_creatures"))
        self.tab_widget.addTab(drones_tab, t("playfield.tab_drones"))
        self.tab_widget.addTab(spawn_zones_tab, t("playfield.tab_spawn_zones"))
        self.tab_widget.addTab(special_effects_tab, t("playfield.tab_special_effects"))
        self.tab_widget.addTab(self.raw_widget, t("playfield.tab_raw_yaml"))

        # Rafraichit les vues structurees quand on revient dessus, au cas ou
        # l'onglet YAML brut aurait modifie quelque chose entre-temps (edition
        # directe, undo...).
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        widget = self.tab_widget.widget(index)
        if isinstance(widget, QWidget) and hasattr(widget, "_playfield_tables"):
            for table in widget._playfield_tables:
                table.refresh()

    def _wrap_with_poi_inspector_button(self, poi_tab_inner: QWidget) -> QWidget:
        """Ajoute un bouton 'Inspecteur de POI...' au-dessus du tableau POI en
        lecture seule -- specifique a l'onglet POI (pas Creatures, qui
        reutilise la meme methode generique _build_readonly_params_tab sans
        ces statistiques, non pertinentes pour les creatures)."""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.addStretch()
        btn_inspector = QPushButton(icon("fa5s.chart-bar", "#ffffff"), t("menu.tools.poi_inspector"))
        btn_inspector.setIconSize(icon_size())
        btn_inspector.clicked.connect(self._open_poi_inspector)
        top_row.addWidget(btn_inspector)
        layout.addLayout(top_row)
        layout.addWidget(poi_tab_inner, 1)
        # Reporte _playfield_tables sur l'enveloppe -- code externe (et les
        # tests) accedent a cet attribut directement sur le widget retourne
        # par le tab, sans savoir qu'il est enveloppe pour le bouton
        # inspecteur.
        wrapper._playfield_tables = poi_tab_inner._playfield_tables
        return wrapper

    def _open_poi_inspector(self):
        from gui.poi_inspector_dialog import PoiInspectorDialog
        self._poi_inspector_dialog = PoiInspectorDialog(self.doc, parent=self)
        self._poi_inspector_dialog.show()

    def _build_canvas_tab(self) -> QWidget:
        """Vue 2D top-down des entites positionnables du playfield -- voir
        gui/playfield_canvas_widget.py. La modification d'une position par
        glisser-deposer doit se refleter dans l'indicateur "modifications non
        enregistrees" de l'onglet YAML complet, comme toute autre edition
        structuree (meme mecanisme que _on_structured_change)."""
        self.canvas_widget = PlayfieldCanvasWidget(self.doc)
        self.canvas_widget.modified.connect(lambda: self._on_structured_change([]))
        return self.canvas_widget

    def _build_resources_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel(f"<b>{t('playfield.random_resources_label')}</b>"))
        random_table = PlayfieldSectionTable(
            get_items_fn=lambda: list_items(self.doc, "RandomResources", "Name"),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=True,
            add_callback=lambda: self._add_resource("RandomResources"),
            remove_callback=lambda item: self._remove_resource("RandomResources", item),
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(random_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.asteroid_resources_label')}</b>"))
        asteroid_table = PlayfieldSectionTable(
            get_items_fn=lambda: list_items(self.doc, "AsteroidResources", "Name"),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=True,
            add_callback=lambda: self._add_resource("AsteroidResources"),
            remove_callback=lambda item: self._remove_resource("AsteroidResources", item),
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(asteroid_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.space_resources_label')}</b>"))
        space_regen_column = SyntheticColumn(
            label=t("playfield.col_regen_after"),
            getter=lambda item: get_properties_value(item, "RegenAfter"),
            setter=lambda item, value: set_properties_value(item, "RegenAfter", value),
        )
        space_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_space_resource_items(self.doc),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=True,
            add_callback=self._add_space_resource,
            remove_callback=self._remove_space_resource,
            before_edit_callback=self.raw_widget._snapshot_undo,
            synthetic_columns=[space_regen_column],
            name_display_fn=get_space_resource_display_name,
        )
        layout.addWidget(space_table, 1)

        random_table.changed.connect(lambda: self._on_structured_change([random_table]))
        asteroid_table.changed.connect(lambda: self._on_structured_change([asteroid_table]))
        space_table.changed.connect(lambda: self._on_structured_change([space_table]))
        tab._playfield_tables = [random_table, asteroid_table, space_table]
        return tab

    def _build_readonly_params_tab(self, get_items_fn, name_column_label: str,
                                    synthetic_columns: Optional[List[SyntheticColumn]] = None) -> QWidget:
        """POI et Creatures : modification des entrees existantes uniquement, pas
        d'ajout (voir le commentaire de portee en tete de fichier)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(t("playfield.existing_only_note"))
        info.setWordWrap(True)
        layout.addWidget(info)

        table = PlayfieldSectionTable(
            get_items_fn=get_items_fn,
            name_column_label=name_column_label,
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
            synthetic_columns=synthetic_columns,
        )
        layout.addWidget(table, 1)
        table.changed.connect(lambda: self._on_structured_change([table]))
        tab._playfield_tables = [table]
        return tab

    def _build_drones_tab(self) -> QWidget:
        """Garnison de base de drones (planete) et drones/vaisseaux de patrouille
        (espace) -- trois tableaux, chacun vide si non pertinent pour le type de
        playfield ouvert (meme principe que l'onglet Ressources). Modification
        des entrees existantes uniquement, meme raisonnement que POI/Creatures :
        les noms (ex: 'DroneAeroZiraxMinigun', 'RE2_OPVRogueT1') ne correspondent
        a aucun bloc/item trouve dans BlocksConfig.ecf/ItemsConfig.ecf, donc pas
        de source fiable pour une liste deroulante d'ajout de nouveau type."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(t("playfield.existing_only_note"))
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel(f"<b>{t('playfield.drone_stock_label')}</b>"))
        stock_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_drone_stock_items(self.doc),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(stock_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.free_drones_label')}</b>"))
        free_drones_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_free_drones_items(self.doc),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(free_drones_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.space_vessels_label')}</b>"))
        vessels_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_space_vessels_items(self.doc),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(vessels_table, 1)

        for table in (stock_table, free_drones_table, vessels_table):
            table.changed.connect(lambda t=table: self._on_structured_change([t]))
        tab._playfield_tables = [stock_table, free_drones_table, vessels_table]
        return tab

    def _build_spawn_zones_tab(self) -> QWidget:
        """DroneSpawning (patrouilles planete), SpawnRateZones (modulation du
        taux d'apparition autour des POI) et SpawnZones (creatures liees a un
        POI, different de l'onglet Creatures qui est par biome) -- trois
        tableaux, chacun vide si non pertinent pour le type de playfield
        ouvert. Modification des entrees existantes uniquement."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(t("playfield.existing_only_note"))
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel(f"<b>{t('playfield.drone_spawning_label')}</b>"))
        drone_spawning_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_drone_spawning_items(self.doc),
            name_column_label=t("playfield.col_dronesminmax"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(drone_spawning_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.spawn_rate_zones_label')}</b>"))
        spawn_rate_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_spawn_rate_zones_items(self.doc),
            name_column_label=t("playfield.col_spawnat"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(spawn_rate_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.spawn_zones_label')}</b>"))
        spawn_zones_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_spawn_zones_items(self.doc),
            name_column_label=t("playfield.col_spawnat"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(spawn_zones_table, 1)

        for table in (drone_spawning_table, spawn_rate_table, spawn_zones_table):
            table.changed.connect(lambda t=table: self._on_structured_change([t]))
        tab._playfield_tables = [drone_spawning_table, spawn_rate_table, spawn_zones_table]
        return tab

    def _build_special_effects_tab(self) -> QWidget:
        """Effets visuels locaux (pollen, papillons... par biome) et globaux
        (meteo, effets a plus grande echelle) -- purement cosmetique, sans
        impact sur le gameplay, mais couvert pour une coherence complete."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(t("playfield.existing_only_note"))
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel(f"<b>{t('playfield.special_effects_local_label')}</b>"))
        local_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_special_effects_local_items(self.doc),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(local_table, 1)

        layout.addWidget(QLabel(f"<b>{t('playfield.special_effects_global_label')}</b>"))
        global_table = PlayfieldSectionTable(
            get_items_fn=lambda: find_special_effects_global_items(self.doc),
            name_column_label=t("playfield.col_name"),
            allow_add_remove=False,
            before_edit_callback=self.raw_widget._snapshot_undo,
        )
        layout.addWidget(global_table, 1)

        for table in (local_table, global_table):
            table.changed.connect(lambda t=table: self._on_structured_change([t]))
        tab._playfield_tables = [local_table, global_table]
        return tab

    def _on_structured_change(self, tables_to_refresh: List[PlayfieldSectionTable]):
        """Appele apres toute edition de cellule reussie -- l'edition elle-meme a
        deja mute le document (voir PlayfieldSectionTable._on_cell_changed), il
        reste a synchroniser l'etat modifie/undo de l'onglet YAML brut."""
        self.raw_widget._set_modified(True)
        self.modified_changed.emit(True)

    def _add_resource(self, section_key: str):
        blocks_files = self.blocks_ecf_files or []
        resource_names = list_resource_block_names(blocks_files)
        if not resource_names:
            QMessageBox.information(self, t("playfield.add_resource_title"),
                                     t("playfield.no_resources_found"))
            return
        dialog = AddResourceDialog(resource_names, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.selected_name()
        if not name:
            return

        section = find_top_level_key(self.doc, section_key)
        if section is None:
            QMessageBox.warning(self, t("playfield.add_resource_title"),
                                 t("playfield.section_not_found", section=section_key))
            return

        # Reprend les CLES de parametres (pas forcement les valeurs) du premier
        # item existant comme modele -- garantit une structure coherente avec le
        # reste de la section plutot que d'inventer une liste de parametres.
        existing_items = list_items(self.doc, section_key, "Name")
        if existing_items:
            template_params = get_item_params(existing_items[0])
        else:
            template_params = []

        self.raw_widget._snapshot_undo()
        add_resource_item(self.doc, section_key, name, template_params)
        self.raw_widget._set_modified(True)
        self.modified_changed.emit(True)
        self._refresh_resources_tab()

    def _remove_resource(self, section_key: str, item: YamlEntry):
        self.raw_widget._snapshot_undo()
        remove_resource_item(self.doc, section_key, item)
        self.raw_widget._set_modified(True)
        self.modified_changed.emit(True)
        self._refresh_resources_tab()

    def _add_space_resource(self):
        materials = list_space_material_names(self.blocks_ecf_files or [])
        if not materials:
            QMessageBox.information(self, t("playfield.add_resource_title"),
                                     t("playfield.no_resources_found"))
            return
        dialog = AddResourceDialog(materials, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        material = dialog.selected_name()
        if not material:
            return

        section = find_top_level_key(self.doc, "Resources")
        if section is None:
            QMessageBox.warning(self, t("playfield.add_resource_title"),
                                 t("playfield.section_not_found", section="Resources"))
            return

        existing_items = find_space_resource_items(self.doc)
        template = existing_items[0] if existing_items else None

        self.raw_widget._snapshot_undo()
        add_space_resource_item(self.doc, material, template_item=template)
        self.raw_widget._set_modified(True)
        self.modified_changed.emit(True)
        self._refresh_resources_tab()

    def _remove_space_resource(self, item: YamlEntry):
        self.raw_widget._snapshot_undo()
        remove_space_resource_item(self.doc, item)
        self.raw_widget._set_modified(True)
        self.modified_changed.emit(True)
        self._refresh_resources_tab()

    def _refresh_resources_tab(self):
        resources_tab = self.tab_widget.widget(1)
        for table in getattr(resources_tab, "_playfield_tables", []):
            table.refresh()

    # ------------------------------------------------------------------
    # Delegation vers l'onglet YAML brut, qui gere reellement save/undo --
    # signature identique aux autres widgets d'edition (YamlEditWidget,
    # EcfEditWidget...) pour rester utilisable de facon interchangeable par
    # main_window.py (save, is_modified, undo).
    # ------------------------------------------------------------------

    def save(self):
        self.raw_widget.save()

    def is_modified(self) -> bool:
        return self.raw_widget.is_modified()

    def undo(self):
        self.raw_widget.undo()
        self.doc = self.raw_widget.doc  # undo() reconstruit doc via reparse -- resynchronise la reference
        self._refresh_all_tables()

    def _refresh_all_tables(self):
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            for table in getattr(widget, "_playfield_tables", []):
                table.refresh()

    def _update_modified_label(self, modified: bool):
        self.modified_label.setText(t("playfield.unsaved_changes") if modified else "")
