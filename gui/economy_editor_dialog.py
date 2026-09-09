"""Editeur d'economie (marchands PNJ) -- dialogue module au-dessus du VRAI onglet
TraderNPCConfig.ecf de la copie de travail (meme contrat que l'editeur PDA :
mutations in-place du document partage, undo/modified gerés par l'onglet,
round-trip byte-perfect pour toute ligne non touchee).

Le dialogue reste testable hors MainWindow : les crochets on_before_mutate /
on_mutate (snapshot undo + marquage modifie) sont passes par l'appelant.
"""
from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap
from PyQt6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QGroupBox,
                             QHeaderView, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPlainTextEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QMessageBox)

from core.economy.market_price import lookup_case_insensitive
from core.economy.model import RangeSpec, TradeItem
from core.economy.trader_config import TraderConfigDoc, TraderItemRow, TraderView
from core.economy.validation import validate_trader_doc
from core.i18n import t
from gui.theme import icon

CATALOG_MIME = "application/x-empyrion-economy-item"
_GOODS_POOL_SEED = ("trwFood", "trwSpecial", "trwEquipment", "trwWeapons",
                    "trwArmor", "trwMedicine", "trwResources", "trwCommodities")
_MAX_CATALOG_RESULTS = 300


class _CatalogList(QListWidget):
    """Liste du catalogue : source du drag & drop (mime texte = nom d'item)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, actions):
        item = self.currentItem()
        if item is None:
            return
        from PyQt6.QtCore import QMimeData
        mime = QMimeData()
        mime.setData(CATALOG_MIME, item.data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        mime.setText(item.data(Qt.ItemDataRole.UserRole))
        from PyQt6.QtGui import QDrag
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(actions)


class EconomyEditorDialog(QDialog):
    def __init__(self, config: TraderConfigDoc, market_index: Dict[str, Optional[float]],
                 parent=None, on_before_mutate: Optional[Callable[[], None]] = None,
                 on_mutated: Optional[Callable[[], None]] = None,
                 undo_target: Optional[object] = None,
                 catalog_entries: Optional[list] = None,
                 working_root=None,
                 catalog_paths: Optional[list] = None):
        super().__init__(parent)
        self.config = config
        self.market_index = market_index
        self.catalog_entries = catalog_entries
        self.working_root = working_root
        self.catalog_paths = catalog_paths
        self._on_before_mutate = on_before_mutate or (lambda: None)
        self._on_mutated = on_mutated or (lambda: None)
        self._undo_target = undo_target
        self._current: Optional[TraderView] = None
        self._loading = False

        self.setWindowTitle(t("eco.title"))
        self.resize(1150, 640)

        root = QVBoxLayout(self)
        cols = QHBoxLayout()
        root.addLayout(cols, 1)

        # -- gauche : profils + fiche -------------------------------------
        left = QVBoxLayout()
        cols.addLayout(left, 2)
        left.addWidget(QLabel(t("eco.profiles.title")))
        self.trader_list = QListWidget()
        self.trader_list.currentItemChanged.connect(self._on_trader_selected)
        left.addWidget(self.trader_list, 1)
        btns = QHBoxLayout()
        for icon_name, cb, tip in (("fa5s.plus", self._add_trader, "eco.btn.add"),
                                   ("fa5s.copy", self._duplicate_trader, "eco.btn.duplicate"),
                                   ("fa5s.trash", self._remove_trader, "eco.btn.delete")):
            b = QPushButton(icon(icon_name, "#ffffff"), t(tip))
            b.clicked.connect(lambda _, f=cb: f())
            btns.addWidget(b)
        left.addLayout(btns)

        card = QGroupBox(t("eco.card.title"))
        card_l = QVBoxLayout(card)
        card_l.addWidget(QLabel(t("eco.card.text")))
        self.card_text = QPlainTextEdit()
        self.card_text.setFixedHeight(72)
        card_l.addWidget(self.card_text)
        row_g = QHBoxLayout()
        row_g.addWidget(QLabel(t("eco.card.goods")))
        self.card_goods = QComboBox()
        self.card_goods.setEditable(True)
        for g in self._goods_pool():
            self.card_goods.addItem(g)
        row_g.addWidget(self.card_goods, 1)
        row_g.addWidget(QLabel(t("eco.card.discount")))
        self.card_discount = QLineEdit()
        self.card_discount.setMaximumWidth(80)
        row_g.addWidget(self.card_discount)
        card_l.addLayout(row_g)
        b_apply = QPushButton(icon("fa5s.check", "#ffffff"), t("eco.btn.apply_card"))
        b_apply.clicked.connect(self._apply_card)
        card_l.addWidget(b_apply, 0, Qt.AlignmentFlag.AlignRight)
        left.addWidget(card)

        # -- presets (application) + variantes regionales -------------------
        presets_box = QGroupBox(t("eco.preset.title"))
        pl = QVBoxLayout(presets_box)
        from PyQt6.QtWidgets import QCheckBox
        self.preset_only_selected = QCheckBox(t("eco.preset.only_selected"))
        pl.addWidget(self.preset_only_selected)
        row_p = QHBoxLayout()
        b_infl = QPushButton(icon("fa5s.arrow-up", "#ffffff"), t("eco.preset.inflation"))
        b_infl.clicked.connect(self._apply_inflation)
        row_p.addWidget(b_infl)
        b_scar = QPushButton(icon("fa5s.box-open", "#ffffff"), t("eco.preset.scarcity"))
        b_scar.clicked.connect(self._apply_scarcity)
        row_p.addWidget(b_scar)
        pl.addLayout(row_p)
        b_variant = QPushButton(icon("fa5s.clone", "#4a7dfc"), t("eco.preset.variant"))
        b_variant.setObjectName("secondaryButton")
        b_variant.clicked.connect(self._create_variant)
        pl.addWidget(b_variant)
        row_t = QHBoxLayout()
        self.type_profile_combo = QComboBox()
        self._reload_type_profiles()
        row_t.addWidget(self.type_profile_combo, 1)
        b_apply_type = QPushButton(icon("fa5s.paper-plane", "#ffffff"), t("eco.preset.apply_type"))
        b_apply_type.clicked.connect(self._apply_type_profile)
        row_t.addWidget(b_apply_type)
        pl.addLayout(row_t)
        row_t2 = QHBoxLayout()
        b_save_type = QPushButton(icon("fa5s.save", "#4a7dfc"), t("eco.preset.save_type"))
        b_save_type.setObjectName("secondaryButton")
        b_save_type.clicked.connect(self._save_type_profile)
        row_t2.addWidget(b_save_type)
        b_del_type = QPushButton(icon("fa5s.trash", "#4a7dfc"), t("eco.preset.delete_type"))
        b_del_type.setObjectName("secondaryButton")
        b_del_type.clicked.connect(self._delete_type_profile)
        row_t2.addWidget(b_del_type)
        pl.addLayout(row_t2)
        left.addWidget(presets_box)

        # -- centre : tableau des items ------------------------------------
        center = QVBoxLayout()
        cols.addLayout(center, 5)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([t("eco.col.icon"), t("eco.col.item"),
                                              t("eco.col.action"),
                                              t("eco.col.sell_price"), t("eco.col.sell_stock"),
                                              t("eco.col.buy_price"), t("eco.col.buy_max")])
        self.table.horizontalHeader().setStretchLastSection(True)
        # icônes DOUBLES (demande utilisateur 09/09/2026) : 48px, lignes 56px
        self.table.setIconSize(QSize(48, 48))
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setColumnWidth(0, 64)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.dragEnterEvent = self._table_drag_enter
        self.table.dragMoveEvent = lambda e: e.acceptProposedAction()
        self.table.dropEvent = self._table_drop
        center.addWidget(self.table, 1)
        tbl_btns = QHBoxLayout()
        b_del_item = QPushButton(icon("fa5s.trash", "#ffffff"), t("eco.btn.delete_item"))
        b_del_item.clicked.connect(self._remove_item_row)
        tbl_btns.addWidget(b_del_item)
        b_to_mf = QPushButton(icon("fa5s.exchange-alt", "#4a7dfc"), t("eco.btn.to_factor"))
        b_to_mf.setObjectName("secondaryButton")
        b_to_mf.clicked.connect(lambda: self._convert_selected(True))
        tbl_btns.addWidget(b_to_mf)
        b_to_abs = QPushButton(icon("fa5s.exchange-alt", "#4a7dfc"), t("eco.btn.to_absolute"))
        b_to_abs.setObjectName("secondaryButton")
        b_to_abs.clicked.connect(lambda: self._convert_selected(False))
        tbl_btns.addWidget(b_to_abs)
        tbl_btns.addStretch()
        center.addLayout(tbl_btns)

        # -- droite : catalogue ---------------------------------------------
        right = QVBoxLayout()
        cols.addLayout(right, 2)
        right.addWidget(QLabel(t("eco.catalog.title")))
        b_catalog = QPushButton(icon("fa5s.book-open", "#ffffff"), t("eco.btn.catalog"))
        b_catalog.clicked.connect(self._open_catalog_dialog)
        right.addWidget(b_catalog)
        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText(t("eco.catalog.search"))
        self.catalog_search.textChanged.connect(self._refresh_catalog)
        right.addWidget(self.catalog_search)
        self.catalog_list = _CatalogList()
        self.catalog_list.itemDoubleClicked.connect(
            lambda it: self._add_catalog_item(it.data(Qt.ItemDataRole.UserRole)))
        right.addWidget(self.catalog_list, 1)
        right.addWidget(QLabel(t("eco.catalog.drop_hint")))

        # -- bas -------------------------------------------------------------
        bottom = QHBoxLayout()
        self.status = QLabel("")
        # DEFENSE : un texte tres long (ex: liste de 65 marchands) ne doit
        # JAMAIS elargir la fenetre hors ecran -- retour a la ligne oblige.
        self.status.setWordWrap(True)
        bottom.addWidget(self.status, 1)
        b_check = QPushButton(icon("fa5s.clipboard-check", "#4a7dfc"), t("eco.btn.check"))
        b_check.setObjectName("secondaryButton")
        b_check.clicked.connect(self._run_validation)
        bottom.addWidget(b_check)
        b_close = QPushButton(t("btn.close"))
        b_close.clicked.connect(self.accept)
        bottom.addWidget(b_close)
        root.addLayout(bottom)

        # Ctrl+Z dans le dialogue : meme routage que la fenetre principale
        # (champ focus -> undo du champ, sinon undo de l'onglet ECF + refresh).
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self._dialog_undo)

        self._refresh_traders()

    # ------------------------------------------------------------ helpers

    def _status(self, key: str, **params) -> None:
        self.status.setText(t(key, **params))

    def _goods_pool(self) -> List[str]:
        pool = list(_GOODS_POOL_SEED)
        for v in self.config.views():
            if v.selling_goods and v.selling_goods not in pool:
                pool.append(v.selling_goods)
        return pool

    def _mutate(self, fn: Callable[[], None]) -> None:
        self._on_before_mutate()
        fn()
        self._on_mutated()

    def _dialog_undo(self):
        from PyQt6.QtWidgets import QApplication, QLineEdit, QComboBox, QPlainTextEdit
        w = QApplication.focusWidget()
        if isinstance(w, (QLineEdit, QPlainTextEdit)) and w.isEnabled():
            w.undo()
            return
        if isinstance(w, QComboBox) and w.isEditable() and w.lineEdit() is not None:
            w.lineEdit().undo()
            return
        if self._undo_target is not None and hasattr(self._undo_target, "undo"):
            self._undo_target.undo()
            self._refresh_all()
        else:
            # secours : dernier snapshot du doc seulement (hors onglet, tests)
            self._refresh_all()

    # ------------------------------------------------------------ refresh

    def _reload_current(self):
        """Re-derive la vue du marchand courant : les lignes d'items ont pu etre
        ajoutees/retirees, la vue cachee est perimee (regle : jamais de reference
        figee, toujours re-deriver)."""
        if self._current is None:
            return
        block = self.config.find(self._current.name)
        if block is None:
            self._current = None
            return
        self._current = next((v for v in self.config.views() if v.block is block), None)

    def _reload_and_refresh(self):
        self._reload_current()
        self._refresh_table()

    def _refresh_all(self):
        name = self._current.name if self._current else None
        self._refresh_traders()
        if name:
            self._select_trader_by_name(name)

    def _refresh_traders(self):
        self._loading = True
        try:
            self.trader_list.blockSignals(True)
            self.trader_list.clear()
            for v in self.config.views():
                it = QListWidgetItem(v.name)
                it.setData(Qt.ItemDataRole.UserRole, v.name)
                self.trader_list.addItem(it)
        finally:
            self.trader_list.blockSignals(False)
            self._loading = False

    def _select_trader_by_name(self, name: str):
        for i in range(self.trader_list.count()):
            if self.trader_list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.trader_list.setCurrentRow(i)
                return
        self._on_trader_selected(self.trader_list.currentItem(), None)

    def _on_trader_selected(self, current, _previous):
        if self._loading:
            return
        self._current = None
        name = current.data(Qt.ItemDataRole.UserRole) if current else None
        if name:
            block = self.config.find(name)
            if block is not None:
                self._current = next((v for v in self.config.views() if v.block is block), None)
        self._refresh_card()
        self._refresh_table()

    def _refresh_card(self):
        self._loading = True
        try:
            v = self._current
            self.card_text.setPlainText(v.selling_text if v else "")
            goods = v.selling_goods if v else ""
            self.card_goods.clear()
            for g in self._goods_pool():
                self.card_goods.addItem(g)
            self.card_goods.setCurrentText(goods)
            self.card_discount.setText(v.discount if v else "")
        finally:
            self._loading = False

    def _refresh_table(self):
        self._loading = True
        try:
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            v = self._current
            if v is None:
                return
            for row_def in v.rows:
                r = self.table.rowCount()
                self.table.insertRow(r)
                icon_it = QTableWidgetItem()
                icon_it.setFlags(icon_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if row_def.item is not None:
                    pixmap = self._icon_pixmap_for(row_def.item.name)
                    if pixmap is not None:
                        icon_it.setIcon(QIcon(pixmap))
                self.table.setItem(r, 0, icon_it)
                name_it = QTableWidgetItem(row_def.key + " · " +
                                           (row_def.item.name if row_def.item else "??"))
                name_it.setData(Qt.ItemDataRole.UserRole, row_def.key)
                name_it.setFlags(name_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, 1, name_it)
                combo = QComboBox()
                combo.addItem(t("eco.action.sell"))
                combo.addItem(t("eco.action.buy_sell"))
                combo.setCurrentIndex(1 if (row_def.item and row_def.item.has_buy) else 0)
                combo.currentIndexChanged.connect(
                    lambda idx, key=row_def.key: self._on_action_changed(key, idx))
                self.table.setCellWidget(r, 2, combo)
                specs = [(3, "sell_price"), (4, "sell_stock"), (5, "buy_price"), (6, "buy_max_stock")]
                for col, attr in specs:
                    spec = getattr(row_def.item, attr) if row_def.item else None
                    it = QTableWidgetItem(spec.render() if spec else "")
                    if row_def.item is None:
                        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(r, col, it)
        finally:
            self.table.blockSignals(False)
            self._loading = False

    def _refresh_catalog(self):
        query = self.catalog_search.text().strip().lower()
        self.catalog_list.clear()
        count = 0
        for name in sorted(self.market_index.keys(), key=str.lower):
            if query and query not in name.lower():
                continue
            price = self.market_index.get(name)
            label = f"{name}   ({price:g})" if price is not None else name
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.catalog_list.addItem(it)
            count += 1
            if count >= _MAX_CATALOG_RESULTS:
                break

    # ------------------------------------------------------------ actions

    def _add_trader(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, t("eco.btn.add"), t("eco.dialog.new_name"))
        if not ok:
            return
        name = name.strip().strip('"')
        if not name:
            return
        if self.config.find(name) is not None:
            self._status("eco.status.name_exists", name=name)
            return
        self._mutate(lambda: self.config.create_trader(name))
        self._refresh_traders()
        self._select_trader_by_name(name)
        self._status("eco.status.trader_added", name=name)

    def _duplicate_trader(self):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        from PyQt6.QtWidgets import QInputDialog
        base = self._current.name
        name, ok = QInputDialog.getText(self, t("eco.btn.duplicate"),
                                        t("eco.dialog.new_name"), text=base)
        if not ok:
            return
        name = name.strip().strip('"')
        if not name or name == base:
            return
        if self.config.find(name) is not None:
            self._status("eco.status.name_exists", name=name)
            return
        self._mutate(lambda: self.config.duplicate_trader(self._current.block, name))
        self._refresh_traders()
        self._select_trader_by_name(name)
        self._status("eco.status.trader_duplicated", name=name)

    def _remove_trader(self):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        name = self._current.name
        ret = QMessageBox.question(self, t("eco.btn.delete"),
                                   t("eco.dialog.confirm_delete", name=name))
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._mutate(lambda: self.config.remove_trader(self._current.block))
        self._current = None
        self._refresh_traders()
        self._refresh_table()
        self._refresh_card()
        self._status("eco.status.trader_deleted", name=name)

    def _apply_card(self):
        if self._current is None or self._loading:
            return
        block = self._current.block

        def _apply():
            TraderConfigDoc.set_selling_text(block, self.card_text.toPlainText())
            TraderConfigDoc.set_selling_goods(block, self.card_goods.currentText().strip())
            TraderConfigDoc.set_discount(block, self.card_discount.text().strip())
        self._mutate(_apply)
        self._status("eco.status.card_applied", name=self._current.name)

    def _row_key(self, r: int) -> Optional[str]:
        # colonne 0 = icone (sans UserRole) ; la cle vit en colonne 1
        it = self.table.item(r, 1)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_cell_double_clicked(self, row: int, column: int):
        """Double-clic sur la colonne icone -> ZOOM x4 (image source agrandie,
        demande utilisateur 09/09/2026). Les autres colonnes gardent leur
        comportement normal (edition inline, liste deroulante...)."""
        if column != 0 or self._current is None:
            return
        key = self._row_key(row)
        row_def = self._current.row_by_key(key) if key else None
        if row_def is None or row_def.item is None:
            return
        pixmap = self._icon_pixmap_for(row_def.item.name)
        if pixmap is None or pixmap.isNull():
            return
        self._show_icon_zoom(pixmap)

    def _show_icon_zoom(self, pixmap: QPixmap):
        """Popup sans bordure : l'image source a x3 (demande utilisateur),
        bouton de fermeture en croix ; le type Popup ferme aussi nativement au
        clic exterieur. JAMAIS d'override d'evenement par lambda sur l'instance
        (PyQt6 : sipBadCatcherResult, constate 09/09/2026)."""
        # x3 en transformation RAPIDE (nearest-neighbor) : agrandir une icone
        # 128px avec le lissage produit un flou visible (retour utilisateur
        # 09/09/2026) ; au pixel pres, le rendu reste net.
        zoom = pixmap.scaled(pixmap.width() * 3, pixmap.height() * 3,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        popup = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        lay = QVBoxLayout(popup)
        lay.setContentsMargins(6, 6, 6, 6)
        bar = QHBoxLayout()
        bar.addStretch(1)
        btn_close = QPushButton(icon("fa5s.times", "#ffffff"), "")
        btn_close.setFixedSize(26, 26)
        btn_close.clicked.connect(popup.close)
        bar.addWidget(btn_close)
        lay.addLayout(bar)
        label = QLabel()
        label.setPixmap(zoom)
        lay.addWidget(label)
        self._zoom_popup = popup
        from PyQt6.QtGui import QCursor
        popup.move(QCursor.pos())
        popup.show()

    def _icon_pixmap_for(self, name: str):
        """Icône d'un item pour le tableau (cache par nom, resolution paresseuse
        via le meme index que la fiche info et la fenetre catalogue). La cle
        respecte la regle fiche : 'CustomIcon' de la definition si connue
        (via le catalogue), sinon le nom."""
        if not hasattr(self, "_table_icon_cache"):
            self._table_icon_cache: Dict[str, Optional[QPixmap]] = {}
        if name in self._table_icon_cache:
            return self._table_icon_cache[name]
        icon_key = name
        if not hasattr(self, "_icon_key_by_name"):
            self._icon_key_by_name: Dict[str, str] = {}
            for e in (self.catalog_entries or []):
                self._icon_key_by_name.setdefault(e.name, e.icon_key)
        icon_key = self._icon_key_by_name.get(name, name)
        pixmap = None
        try:
            from core.tech_tree_icons import (build_icon_index, resolve_icon_path,
                                              load_icon_bytes)
            if not hasattr(self, "_icon_index_cache"):
                self._icon_index_cache = build_icon_index(self.working_root) \
                    if self.working_root else {}
            ref = resolve_icon_path(self._icon_index_cache, icon_key)
            if ref is not None:
                data = load_icon_bytes(ref)
                if data:
                    pixmap = QPixmap()
                    if not (pixmap.loadFromData(data) and not pixmap.isNull()):
                        pixmap = None
        except Exception:
            pixmap = None
        self._table_icon_cache[name] = pixmap
        return pixmap

    def _current_row(self) -> Optional[Tuple[int, TraderItemRow]]:
        r = self.table.currentRow()
        key = self._row_key(r)
        if self._current is None or key is None:
            self._status("eco.status.no_selection")
            return None
        row = self._current.row_by_key(key)
        if row is None:
            return None
        return r, row

    def _default_item_specs(self, name: str):
        """Prix/stock par defaut d'un item ajoute : REPRISE DU MARKETPRICE en
        prix absolu (regle utilisateur), repli mf=1.1-1.2 si prix inconnu."""
        from core.economy.market_price import lookup_case_insensitive
        mp = lookup_case_insensitive(self.market_index, name)
        if mp is not None and mp > 0:
            price_text = str(int(mp)) if mp == int(mp) else str(mp)
            price = RangeSpec.parse(price_text)
        else:
            price = RangeSpec.parse("mf=1.1-1.2")
        return price, RangeSpec.parse("10-50")

    def _add_catalog_item(self, name: str):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        name = (name or "").strip()
        if not name:
            return
        price, stock = self._default_item_specs(name)

        def _add():
            self.config.add_item(self._current.block, TradeItem(
                name=name, sell_price=price, sell_stock=stock))
        self._mutate(_add)
        self._reload_current()
        self._refresh_table()
        self._status("eco.status.item_added", name=name)

    def _add_catalog_entry_from_catalog(self, entry):
        """Double-clic dans la fenetre catalogue : ajout immediat de l'item."""
        self._add_catalog_item(entry.name)

    def _add_catalog_entries(self, entries: list):
        """Ajout MULTIPLE depuis la fenetre catalogue : UN SEUL snapshot undo
        pour toute la selection."""
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        if not entries:
            return
        block = self._current.block

        def _add():
            for e in entries:
                price, stock = self._default_item_specs(e.name)
                self.config.add_item(block, TradeItem(
                    name=e.name, sell_price=price, sell_stock=stock))
        self._mutate(_add)
        self._reload_current()
        self._refresh_table()
        self._status("eco.status.items_added", n=len(entries))

    def _open_catalog_dialog(self):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        if not self.catalog_entries:
            self._status("eco.status.catalog_unavailable")
            return
        from gui.item_catalog_dialog import ItemCatalogDialog
        catalog = ItemCatalogDialog(
            self.catalog_entries, parent=self,
            icon_loader=self._catalog_icon_loader,
            display_name=self._catalog_display_name,
            refresh_callback=self._refresh_catalog_entries)
        catalog.ITEM_CHOSEN.connect(self._add_catalog_entry_from_catalog)
        catalog.SELECTION_ACCEPTED.connect(self._add_catalog_entries)
        catalog.exec()

    def _refresh_catalog_entries(self):
        """Bouton Rafraichir du catalogue : reconstruit entrees + index d'icones
        en ignorant les caches disque (nouvel item/bloc tout juste cree)."""
        if not self.catalog_paths:
            return None
        from core.item_catalog import load_catalog, price_index
        from core.tech_tree_icons import build_icon_index_cached
        entries = load_catalog(self.catalog_paths, refresh=True)
        if not entries:
            return None
        self.catalog_entries = entries
        self.market_index = price_index(entries)
        if self.working_root:
            self._icon_index_cache = build_icon_index_cached(self.working_root,
                                                             refresh=True)
        self._table_icon_cache = {}
        if hasattr(self, "_icon_key_by_name"):
            del self._icon_key_by_name
        return entries

    def _catalog_icon_loader(self, entry):
        """Icône reelle (meme resolution que la fiche info), chargee paresseusement.
        Les erreurs ATTENDUES (icone absente, fichier illisible) retournent None ;
        une erreur de PROGRAMMATION (import, TypeError...) est imprimee une fois
        sur stderr -- la bouler silencieusement ferait un '0 icone' indiagnosticable
        (retour utilisateur du 09/09/2026 : NameError QPixmap avale -> 0/7616)."""
        if not self.working_root:
            return None
        from core.tech_tree_icons import (build_icon_index, resolve_icon_path,
                                          load_icon_bytes)
        try:
            if not hasattr(self, "_icon_index_cache"):
                self._icon_index_cache = build_icon_index(self.working_root)
            ref = resolve_icon_path(self._icon_index_cache, entry.icon_key)
            if ref is None:
                return None
            data = load_icon_bytes(ref)
            if not data:
                return None
            pixmap = QPixmap()
            return pixmap if pixmap.loadFromData(data) and not pixmap.isNull() else None
        except Exception:
            if not getattr(self, "_icon_error_shown", False):
                self._icon_error_shown = True
                import traceback
                import sys as _sys
                print("chargement d'icones du catalogue en echec :",
                      file=_sys.stderr)
                traceback.print_exc()
            return None

    def _catalog_display_name(self, entry):
        """Nom lisible (Localization.csv scenario + vanilla), langue courante."""
        if not self.working_root:
            return None
        try:
            from core.localization_lookup import build_localization_index
            from core.i18n import get_language
            if not hasattr(self, "_loc_index_cache"):
                self._loc_index_cache = build_localization_index(self.working_root)
            return self._loc_index_cache.get(entry.name, get_language())
        except Exception:
            return None

    def _remove_item_row(self):
        cur = self._current_row()
        if cur is None:
            return
        r, row = cur
        self._mutate(lambda: TraderConfigDoc.remove_item(self._current.block, row))
        self._reload_current()
        self._refresh_table()
        self._status("eco.status.item_deleted")

    def _on_action_changed(self, key: str, idx: int):
        if self._loading or self._current is None:
            return
        row = self._current.row_by_key(key)
        if row is None or row.item is None or row.item.has_buy == (idx == 1):
            return
        item = row.item
        if idx == 1:
            item.buy_price = RangeSpec.parse("mf=0.4-0.5")
            item.buy_max_stock = RangeSpec.parse("55-150")
        else:
            item.buy_price = None
            item.buy_max_stock = None
        self._mutate(lambda: TraderConfigDoc.set_item(row, item))
        self._reload_current()
        self._refresh_table()

    def _on_cell_changed(self, item: QTableWidgetItem):
        if self._loading or self._current is None:
            return
        key = self._row_key(item.row())
        row = self._current.row_by_key(key) if key else None
        if row is None or row.item is None:
            return
        attr = {3: "sell_price", 4: "sell_stock",
                5: "buy_price", 6: "buy_max_stock"}.get(item.column())
        if attr is None:
            return
        spec = RangeSpec.parse(item.text())
        # REGLE MODULE : prix/stocks absolus = entiers (les facteurs mf=
        # restent decimaux). Saisie refusee sinon, cellule re-affichee.
        if spec is None or not spec.is_integral():
            self._status("eco.status.invalid_value", value=item.text())
            QTimer.singleShot(0, self._refresh_table)   # retour affichage, hors reentrance
            return
        new_item = row.item
        setattr(new_item, attr, spec)
        self._mutate(lambda: TraderConfigDoc.set_item(row, new_item))
        self._status("eco.status.item_saved")
        # la colonne Action peut changer (saisie d'un prix d'achat) : refresh differe
        QTimer.singleShot(0, self._reload_and_refresh)

    def _convert_selected(self, to_factor: bool):
        cur = self._current_row()
        if cur is None:
            return
        _r, row = cur
        if row.item is None:
            return
        price = lookup_case_insensitive(self.market_index, row.item.name)
        if price is None or price == 0:
            self._status("eco.err.no_market_price", name=row.item.name)
            return
        item = row.item
        item.sell_price = item.sell_price.converted(price, to_factor)
        if item.buy_price is not None:
            item.buy_price = item.buy_price.converted(price, to_factor)
        self._mutate(lambda: TraderConfigDoc.set_item(row, item))
        self._refresh_table()
        self._status("eco.status.converted", name=row.item.name)

    def _run_validation(self):
        issues = validate_trader_doc(self.config, self.market_index)
        if not issues:
            QMessageBox.information(self, t("eco.issues.title"), t("eco.issues.none"))
            return
        lines = []
        for i in issues:
            loc = f"[{i.trader} / {i.item_key}] " if i.item_key else f"[{i.trader}] " if i.trader else ""
            lines.append(("ERREUR: " if i.level == "error" else "") + loc + t(i.code, **i.params))
        QMessageBox.warning(self, t("eco.issues.title"), "\n".join(lines))

    # ------------------------------------------------------------ presets

    def _preset_targets(self) -> List[str]:
        if self.preset_only_selected.isChecked():
            if self._current is None:
                self._status("eco.status.no_selection")
                return []
            return [self._current.name]
        return self.config.names()

    def _apply_inflation(self):
        from PyQt6.QtWidgets import QInputDialog
        targets = self._preset_targets()
        if not targets:
            return
        percent, ok = QInputDialog.getDouble(
            self, t("eco.preset.inflation"), t("eco.preset.dialog_inflation"),
            10.0, -90.0, 1000.0, 1)
        if not ok:
            return
        multiplier = 1.0 + percent / 100.0
        from core.economy.presets import scale_profile_prices

        def _run():
            for name in targets:
                scale_profile_prices(self.config, name, multiplier)
        self._mutate(_run)
        self._reload_current()
        self._refresh_table()
        self._preset_status(targets)

    def _apply_scarcity(self):
        from PyQt6.QtWidgets import QInputDialog
        targets = self._preset_targets()
        if not targets:
            return
        divisor, ok = QInputDialog.getDouble(
            self, t("eco.preset.scarcity"), t("eco.preset.dialog_scarcity"),
            2.0, 1.1, 1000.0, 1)
        if not ok:
            return
        from core.economy.presets import scale_profile_stocks

        def _run():
            for name in targets:
                scale_profile_stocks(self.config, name, divisor)
        self._mutate(_run)
        self._reload_current()
        self._refresh_table()
        self._preset_status(targets)

    def _preset_status(self, targets: List[str]) -> None:
        """Message de fin de preset : jamais la liste complete des noms — sur un
        fichier vanilla (65 marchands) le QLabel tirait la fenetre hors ecran."""
        if len(targets) <= 3:
            self._status("eco.status.preset_applied", targets=", ".join(targets))
        else:
            self._status("eco.status.preset_applied_many", n=len(targets))

    def _create_variant(self):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        from PyQt6.QtWidgets import QInputDialog
        multiplier, ok = QInputDialog.getDouble(
            self, t("eco.preset.variant"), t("eco.preset.dialog_multiplier"),
            1.5, 0.1, 100.0, 2)
        if not ok:
            return
        from core.economy.presets import create_scaled_variant
        source = self._current.name
        result = {}

        def _run():
            result["name"] = create_scaled_variant(self.config, source, multiplier)
        self._mutate(_run)
        if not result.get("name"):
            self._status("eco.status.no_selection")
            return
        self._refresh_traders()
        self._select_trader_by_name(result["name"])
        self._status("eco.status.variant_created", name=result["name"])

    def _reload_type_profiles(self):
        from core.economy.presets import list_user_presets
        self.type_profile_combo.clear()
        self.type_profile_combo.addItem(t("eco.preset.builtin_military"),
                                        userData="builtin:military")
        self.type_profile_combo.addItem(t("eco.preset.builtin_agricultural"),
                                        userData="builtin:agricultural")
        for snap in list_user_presets():
            self.type_profile_combo.addItem(snap.get("name", "?"), userData="user:" + snap.get("name", "?"))

    def _apply_type_profile(self):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        tag = self.type_profile_combo.currentData()
        if not tag:
            self._status("eco.status.no_type_selected")
            return
        name = self._current.name
        from core.economy.presets import (BUILTIN_TYPE_PROFILES, apply_snapshot,
                                          replace_profile_items)

        def _run():
            if tag.startswith("builtin:"):
                p = BUILTIN_TYPE_PROFILES[tag.split(":", 1)[1]]
                replace_profile_items(self.config, name, p.items,
                                      goods=p.selling_goods, discount=p.discount)
            else:
                snap = next((s for s in self._user_snapshots()
                             if s.get("name") == tag.split(":", 1)[1]), None)
                if snap is not None:
                    apply_snapshot(self.config, name, snap)
        self._mutate(_run)
        self._reload_current()
        self._refresh_table()
        self._refresh_card()
        self._status("eco.status.preset_applied", targets=name)

    @staticmethod
    def _user_snapshots():
        from core.economy.presets import list_user_presets
        return list_user_presets()

    def _save_type_profile(self):
        if self._current is None:
            self._status("eco.status.no_selection")
            return
        from PyQt6.QtWidgets import QInputDialog
        from core.economy.presets import save_user_preset, snapshot_profile
        name, ok = QInputDialog.getText(self, t("eco.preset.save_type"),
                                        t("eco.preset.name_prompt"),
                                        text=self._current.name)
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        save_user_preset(name, snapshot_profile(self._current))
        self._reload_type_profiles()
        self._status("eco.status.preset_saved", name=name)

    def _delete_type_profile(self):
        tag = self.type_profile_combo.currentData()
        if not tag or not tag.startswith("user:"):
            self._status("eco.status.no_type_selected")
            return
        from core.economy.presets import delete_user_preset
        name = tag.split(":", 1)[1]
        delete_user_preset(name)
        self._reload_type_profiles()
        self._status("eco.status.preset_deleted", name=name)

    # ------------------------------------------------------------ drag & drop

    def _table_drag_enter(self, event):
        if event.mimeData().hasFormat(CATALOG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _table_drop(self, event):
        name = bytes(event.mimeData().data(CATALOG_MIME)).decode("utf-8")
        self._add_catalog_item(name)
        event.acceptProposedAction()
