"""Selecteur de catalogue REUTILISABLE (items + blocs) -- fenetre a 3 onglets
(Par categorie / A→Z / Tous) avec cases a cocher, recherche qui filtre dans
tous les onglets, icônes reelles chargees par lots (jamais de blocage UI) et
MarketPrice par ligne.

Contrat :
- SELECTION_ACCEPTED : bouton « Ajouter la selection » -> liste[CatalogEntry] ;
- ITEM_CHOSEN : double-clic sur une ligne -> ajout immediat d'UNE entree
  (la fenetre reste ouverte pour enchainer).

Branche aujourd'hui dans l'editeur d'economie ; reutilisable partout ou l'on
choisit un item/bloc (retrofits prelus apres validation).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QTabWidget, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from core.item_catalog import SOURCE_BLOCK, SOURCE_ITEM, CatalogEntry
from core.i18n import t
from gui.theme import icon

_ICON_CHUNK = 150   # icones chargees par tic de timer (UI jamais bloquee)


class ItemCatalogDialog(QDialog):
    """SELECTION_ACCEPTED(list[CatalogEntry]) : bouton « Ajouter la selection ».
    ITEM_CHOSEN(CatalogEntry) : double-clic = ajout immediat d'UNE entree
    (la fenetre reste ouverte pour enchainer)."""

    SELECTION_ACCEPTED = pyqtSignal(list)
    ITEM_CHOSEN = pyqtSignal(object)

    def __init__(self, entries: List[CatalogEntry], parent=None,
                 icon_loader: Optional[Callable[[CatalogEntry], Optional[QPixmap]]] = None,
                 display_name: Optional[Callable[[CatalogEntry], Optional[str]]] = None,
                 preselected_keys: Optional[List[str]] = None,
                 refresh_callback: Optional[Callable[[], List[CatalogEntry]]] = None):
        super().__init__(parent)
        self.setWindowTitle(t("icat.title"))
        self.resize(880, 620)
        self._entries = entries
        self._refresh_callback = refresh_callback
        self._by_key: Dict[str, CatalogEntry] = {e.key: e for e in entries}
        self._icon_loader = icon_loader
        self._display_name = display_name
        self._checked: Dict[str, CatalogEntry] = {e.key: e for e in entries
                                                  if e.key in set(preselected_keys or [])}
        self._loading = False
        self._icon_cache: Dict[str, QIcon] = {}
        self._pending_icons: List[tuple] = []

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("icat.search"))
        self.search.textChanged.connect(self._rebuild_views)
        top.addWidget(self.search, 1)
        # Rafraichir : reconstruit le catalogue + l'index d'icones en ignorant
        # les caches (cas d'un item/bloc tout juste cree).
        if self._refresh_callback is not None:
            self.btn_refresh = QPushButton(icon("fa5s.sync", "#4a7dfc"), t("icat.refresh"))
            self.btn_refresh.setObjectName("secondaryButton")
            self.btn_refresh.clicked.connect(self._refresh_catalog)
            top.addWidget(self.btn_refresh)
        self.hide_no_price = QCheckBox(t("icat.hide_no_price"))
        self.hide_no_price.stateChanged.connect(self._rebuild_views)
        top.addWidget(self.hide_no_price)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        self.cat_tree = QTreeWidget()
        self.cat_tree.setColumnCount(3)
        self.cat_tree.setHeaderLabels([t("icat.col_item"), t("icat.col_source"),
                                       t("icat.col_price")])
        self.cat_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cat_tree.itemChanged.connect(self._on_item_changed)
        self.cat_tree.itemDoubleClicked.connect(self._on_double_clicked)
        self.tabs.addTab(self.cat_tree, t("icat.tab_categories"))

        self.az_list = QListWidget()
        self.az_list.itemChanged.connect(self._on_list_item_changed)
        self.az_list.itemDoubleClicked.connect(self._on_list_double_clicked)
        self.tabs.addTab(self.az_list, t("icat.tab_az"))

        self.all_list = QListWidget()
        self.all_list.itemChanged.connect(self._on_list_item_changed)
        self.all_list.itemDoubleClicked.connect(self._on_list_double_clicked)
        self.tabs.addTab(self.all_list, t("icat.tab_all"))
        # icones DOUBLES dans le catalogue aussi (demande utilisateur 09/09/2026)
        for view in (self.cat_tree, self.az_list, self.all_list):
            view.setIconSize(QSize(48, 48))
        layout.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        self.icons_label = QLabel("")
        self.icons_label.setStyleSheet("color: gray; font-size: 11px;")
        bottom.addWidget(self.icons_label)
        self.count_label = QLabel("")
        bottom.addWidget(self.count_label, 1)
        self.btn_add = QPushButton(icon("fa5s.plus", "#ffffff"), "")
        self.btn_add.setObjectName("primaryButton")
        self.btn_add.clicked.connect(self._accept_selection)
        bottom.addWidget(self.btn_add)
        btn_close = QPushButton(t("btn.close"))
        btn_close.clicked.connect(self.reject)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        self._rebuild_views()
        self._load_icons_chunked()

    # ------------------------------------------------------------ filtrage

    def _refresh_catalog(self):
        """Bouton Rafraichir : le callback de l'appelant reconstruit les
        entrees en ignorant les caches (nouvel item/bloc tout juste cree)."""
        if self._refresh_callback is None:
            return
        try:
            entries = self._refresh_callback()
        except Exception:
            entries = None
        if not entries:
            return
        self._entries = entries
        self._by_key = {e.key: e for e in entries}
        self._checked = {k: e for k, e in self._checked.items() if k in self._by_key}
        self._icon_cache = {}
        self._rebuild_views()

    def _filtered_entries(self) -> List[CatalogEntry]:
        query = self.search.text().strip().lower()
        hide = self.hide_no_price.isChecked()
        out = []
        for e in self._entries:
            if hide and e.market_price is None:
                continue
            if query:
                label = (self._display_name(e) or "") if self._display_name else ""
                if query not in e.name.lower() and query not in label.lower():
                    continue
            out.append(e)
        return out

    def _entry_label(self, e: CatalogEntry) -> str:
        label = e.name
        if self._display_name:
            disp = self._display_name(e)
            if disp and disp != e.name:
                label = f"{disp}  ·  {e.name}"
        return label

    def _price_text(self, e: CatalogEntry) -> str:
        if e.market_price is None:
            return "-"
        p = e.market_price
        return str(int(p)) if p == int(p) else str(p)

    def _source_text(self, e: CatalogEntry) -> str:
        return t("icat.source_block") if e.source == SOURCE_BLOCK else t("icat.source_item")

    def _apply_icon(self, widget_item, e: CatalogEntry):
        """setIcon a une signature DIFFERENTE selon le type d'item :
        QTreeWidgetItem.setIcon(colonne, QIcon) mais QListWidgetItem.setIcon(QIcon)
        -- confondre les deux leve une TypeError qui, dans un slot QTimer,
        tue toute la chaine de chargement (crash silencieux constate)."""
        ic = self._icon_cache.get(e.key)
        if ic is None:
            return
        if isinstance(widget_item, QListWidgetItem):
            widget_item.setIcon(ic)
        else:
            widget_item.setIcon(0, ic)

    # ------------------------------------------------------------ vues

    def _rebuild_views(self):
        self._loading = True
        try:
            entries = self._filtered_entries()
            self._build_category_tree(entries)
            self._build_flat_list(self.az_list, sorted(
                entries, key=lambda e: self._entry_label(e).lower()))
            self._build_flat_list(self.all_list, entries)
            self._update_count()
        finally:
            self._loading = False
        self._load_icons_chunked()

    def _build_category_tree(self, entries: List[CatalogEntry]):
        self.cat_tree.clear()
        for source, label_key in ((SOURCE_ITEM, "icat.group_items"),
                                  (SOURCE_BLOCK, "icat.group_blocks")):
            group = [e for e in entries if e.source == source]
            if not group:
                continue
            root = QTreeWidgetItem([t(label_key)])
            root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.cat_tree.addTopLevelItem(root)
            by_cat: Dict[str, List[CatalogEntry]] = {}
            for e in group:
                by_cat.setdefault(e.category, []).append(e)
            for cat in sorted(by_cat, key=str.lower):
                cat_label = t("icat.no_category") if not cat else cat
                cat_item = QTreeWidgetItem([cat_label, "", ""])
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                root.addChild(cat_item)
                for e in sorted(by_cat[cat], key=lambda x: self._entry_label(x).lower()):
                    leaf = QTreeWidgetItem([self._entry_label(e),
                                            self._source_text(e),
                                            self._price_text(e)])
                    leaf.setData(0, Qt.ItemDataRole.UserRole, e.key)
                    leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    leaf.setCheckState(0, Qt.CheckState.Checked
                                       if e.key in self._checked else Qt.CheckState.Unchecked)
                    cat_item.addChild(leaf)
            root.setExpanded(True)

    def _build_flat_list(self, listw: QListWidget, entries: List[CatalogEntry]):
        listw.clear()
        for e in entries:
            it = QListWidgetItem(f"{self._entry_label(e)}   [{self._source_text(e)}]  "
                                 f"({self._price_text(e)})")
            it.setData(Qt.ItemDataRole.UserRole, e.key)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked
                             if e.key in self._checked else Qt.CheckState.Unchecked)
            listw.addItem(it)

    # ------------------------------------------------------------ icones

    def _load_icons_chunked(self):
        """Charge les icones par lots (QTimer) : des milliers de lignes ne
        doivent jamais geler l'interface (regle projet non-bloquant)."""
        self._pending_icons = []
        if self._icon_loader is None:
            return
        for i in range(self.cat_tree.topLevelItemCount()):
            root = self.cat_tree.topLevelItem(i)
            for j in range(root.childCount()):
                cat = root.child(j)
                for k in range(cat.childCount()):
                    leaf = cat.child(k)
                    self._pending_icons.append((leaf, leaf.data(0, Qt.ItemDataRole.UserRole)))
        for listw in (self.az_list, self.all_list):
            for i in range(listw.count()):
                it = listw.item(i)
                self._pending_icons.append((it, it.data(Qt.ItemDataRole.UserRole)))
        QTimer.singleShot(0, self._load_next_icon_chunk)

    def _load_next_icon_chunk(self):
        if not self._pending_icons:
            return
        # setIcon emet itemChanged -> garde _loading pour ne pas declencher
        # les handlers de checkbox pendant un simple chargement visuel.
        self._loading = True
        try:
            for widget_item, key in self._pending_icons[:_ICON_CHUNK]:
                e = self._by_key.get(key)
                if e is None:
                    continue
                if e.key not in self._icon_cache:
                    pixmap = self._icon_loader(e)
                    if pixmap is not None:
                        self._icon_cache[e.key] = QIcon(pixmap)
                self._apply_icon(widget_item, e)
        finally:
            self._loading = False
        self._pending_icons = self._pending_icons[_ICON_CHUNK:]
        if self._pending_icons:
            QTimer.singleShot(0, self._load_next_icon_chunk)
        else:
            # diagnostic visible : X icones trouvees / Y entrees (si 0, les
            # sources d'icones sont absentes de l'installation de l'utilisateur)
            self.icons_label.setText(t("icat.icons_status",
                                       ok=len(self._icon_cache),
                                       n=len(self._entries)))

    # ------------------------------------------------------------ selection

    def _entry_by_key(self, key: Optional[str]) -> Optional[CatalogEntry]:
        return self._by_key.get(key) if key else None

    def _on_item_changed(self, item: QTreeWidgetItem, _col: int):
        if self._loading:
            return
        self._set_checked(item.data(0, Qt.ItemDataRole.UserRole),
                          item.checkState(0) == Qt.CheckState.Checked)
        self._sync_other_views(item.data(0, Qt.ItemDataRole.UserRole))

    def _on_list_item_changed(self, it: QListWidgetItem):
        if self._loading:
            return
        self._set_checked(it.data(Qt.ItemDataRole.UserRole),
                          it.checkState(0) == Qt.CheckState.Checked)
        self._sync_other_views(it.data(Qt.ItemDataRole.UserRole))

    def _set_checked(self, key: Optional[str], checked: bool):
        e = self._entry_by_key(key)
        if e is None:
            return
        if checked:
            self._checked[e.key] = e
        else:
            self._checked.pop(e.key, None)
        self._update_count()

    def _sync_other_views(self, key: Optional[str]):
        """Une case cochee dans un onglet : les AUTRES vues suivent (etat
        partage par cle, pas par widget)."""
        if self._loading or not key:
            return
        state = Qt.CheckState.Checked if key in self._checked else Qt.CheckState.Unchecked
        self._loading = True
        try:
            for i in range(self.cat_tree.topLevelItemCount()):
                root = self.cat_tree.topLevelItem(i)
                for j in range(root.childCount()):
                    cat = root.child(j)
                    for k in range(cat.childCount()):
                        leaf = cat.child(k)
                        if leaf.data(0, Qt.ItemDataRole.UserRole) == key:
                            leaf.setCheckState(0, state)
            for listw in (self.az_list, self.all_list):
                for i in range(listw.count()):
                    it = listw.item(i)
                    if it.data(Qt.ItemDataRole.UserRole) == key:
                        it.setCheckState(state)
        finally:
            self._loading = False

    def _update_count(self):
        n = len(self._checked)
        self.count_label.setText(t("icat.selected_count", n=n))
        self.btn_add.setText(t("icat.add_selection", n=n))
        self.btn_add.setEnabled(n > 0)

    def _on_double_clicked(self, item: QTreeWidgetItem, _col: int):
        e = self._entry_by_key(item.data(0, Qt.ItemDataRole.UserRole))
        if e is not None:
            self.ITEM_CHOSEN.emit(e)

    def _on_list_double_clicked(self, it: QListWidgetItem):
        e = self._entry_by_key(it.data(Qt.ItemDataRole.UserRole))
        if e is not None:
            self.ITEM_CHOSEN.emit(e)

    def _accept_selection(self):
        # ordre stable : ordre du catalogue (items d'abord), pas l'ordre de coche
        chosen = [e for e in self._entries if e.key in self._checked]
        if chosen:
            self.SELECTION_ACCEPTED.emit(chosen)
        self.accept()
