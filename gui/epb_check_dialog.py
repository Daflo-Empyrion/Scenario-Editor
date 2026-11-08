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

"""Dialogue de controle des blueprints .epb : liste TOUS les blocs (inconnus
surlignes), vue 3D voxel, remplacement d'un bloc par un bloc du catalogue,
suppression, export CSV -- core/epb_blueprint.py."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMenu, QStyledItemDelegate, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from core.epb_blueprint import (EpbBlueprint, extract_block_definition,
                                block_id_from_definition, load_block_catalog,
                                load_workshop_block_names, read_meta_info,
                                scan_epb_files)
from core.fsutil import central_backup
from core.i18n import t
from core.propriete_glossary import find_explanation as find_glossary_explanation
from core.settings import get_vanilla_content_path
from gui.module_info import add_info_button
from gui.epb_view_3d import EpbView3D, block_color
from gui.msgboxes import ask_yes_no
from gui.window_geometry import track

# RETOUR UTILISATEUR 23/09 (v3) : les fonds « sombres » (72,26,26) etaient
# quasi noirs sur le theme sombre — invisibles a l'oeil malgre des tests
# pixel verts. Couleurs SATUREES, lisibles sur theme clair comme sombre.
_UNKNOWN_FG = QBrush(QColor(255, 200, 200))
_UNKNOWN_BG = QBrush(QColor(150, 25, 25))
_FORBIDDEN_FG = QBrush(QColor(255, 235, 180))
_FORBIDDEN_BG = QBrush(QColor(180, 105, 0))


def _tag_row(child, fg: QBrush, bg: QBrush) -> None:
    """Surlignage impossible a rater : fond colore + texte colore + gras
    sur toutes les colonnes de la ligne. NOTE : les roles du modele sont
    IGNORES par QStyleSheetStyle des qu'une regle QSS touche
    QTreeWidget::item (padding/border-radius du theme) -- c'est le
    delegate qui les peint reellement."""
    font = child.font(0)
    font.setBold(True)
    for col in range(child.columnCount()):
        child.setForeground(col, fg)
        child.setBackground(col, bg)
        child.setFont(col, font)


class _TagDelegate(QStyledItemDelegate):
    """Peint LUI-MEME fond + texte des lignes tagguees : sous une feuille
    de style globale (theme fluent), les roles Background/Foreground du
    modele ne rendent RIEN (vecu 23/09 : lignes inconnu/interdit blanches
    dans l'appli alors que les tests hors ecran voyaient le rouge).
    `show_forbidden = False` desactive le surlignage des seuls blocs
    interdits (retour utilisateur 07/11)."""

    show_forbidden = True

    def paint(self, painter, option, index):
        # retour utilisateur 07/11 : le surlignage des blocs interdits doit
        # pouvoir se desactiver — « interdit » ne veut pas dire corrompu
        # (un prefab de POI embarque des blocs refuses au joueur, et c'est
        # voulu). Le statut est porte en UserRole par _fill_block_children.
        if (index.data(Qt.ItemDataRole.UserRole) == "forbidden"
                and not self.show_forbidden):
            super().paint(painter, option, index)
            return
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg is None:
            super().paint(painter, option, index)
            return
        painter.save()
        painter.fillRect(option.rect, bg)
        font = index.data(Qt.ItemDataRole.FontRole)
        if font is not None:
            painter.setFont(font)
        fg = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(fg.color() if fg is not None else QColor(0, 0, 0))
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight,
                                    max(12, option.rect.width() - 10))
        painter.drawText(option.rect.adjusted(5, 0, -5, 0),
                         Qt.AlignmentFlag.AlignLeft
                         | Qt.AlignmentFlag.AlignVCenter, elided)
        painter.restore()


class EpbCheckDialog(QDialog):
    """Controle d'un .epb ou de tous les .epb d'un dossier : liste complete
    des blocs (inconnus surlignes), vue 3D, remplacement, suppression."""

    def __init__(self, parent, catalog_paths=None):
        super().__init__(parent)
        self.setWindowTitle(t("epb.title"))
        self.catalog_paths = list(catalog_paths or [])
        self.catalog = None                # BlockCatalog (ids + names)
        self._extra_names = {}             # {id: nom} des autres scenarios
        self._targets = []               # [{"path", "bp", "unknown", "item", "dirty"}]
        self._current_target = None
        self._extra_names = {}
        self._source_cache = None        # textes des BlocksConfig sources
        self._suppress_tree_select = False

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("epb.path_label")))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(t("epb.path_hint"))
        row.addWidget(self.path_edit, 1)
        self.btn_file = QPushButton(t("epb.browse_file"))
        self.btn_file.clicked.connect(self._pick_file)
        row.addWidget(self.btn_file)
        self.btn_dir = QPushButton(t("epb.browse_folder"))
        self.btn_dir.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_dir)
        lay.addLayout(row)

        row_filter = QHBoxLayout()
        self.chk_problems = QCheckBox(t("epb.filter_problems"))
        self.chk_problems.setChecked(True)
        self.chk_problems.toggled.connect(self._apply_filter)
        row_filter.addWidget(self.chk_problems)
        self.chk_forbidden = QCheckBox(t("epb.highlight_forbidden"))
        self.chk_forbidden.setChecked(True)
        self.chk_forbidden.setToolTip(t("epb.forbidden_hint"))
        self.chk_forbidden.toggled.connect(self._toggle_forbidden)
        row_filter.addWidget(self.chk_forbidden)
        add_info_button(row_filter, "epbcheck.info_html")
        row_filter.addStretch(1)
        lay.addLayout(row_filter)
        self.btn_analyze = QPushButton(t("epb.analyze"))
        self.btn_analyze.clicked.connect(self._analyze)
        lay.addWidget(self.btn_analyze)

        # infos d'entete du blueprint affiche (retour utilisateur 07/11 :
        # le GroupName indexe les POI dans le moteur, il doit etre visible)
        self.lbl_info = QLabel(t("epb.info_none"))
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        # Infobulle : definitions EPB des champs du bandeau (GroupName, Tags,
        # DisplayName) depuis le glossaire general
        header_exp = [f"<b>{k}</b> : {find_glossary_explanation(k, scope='epb')}"
                      for k in ("GroupName", "Tags", "DisplayName")
                      if find_glossary_explanation(k, scope="epb")]
        if header_exp:
            self.lbl_info.setToolTip("<br>".join(header_exp))
        lay.addWidget(self.lbl_info)

        # metas du prefab affiche : pivot (le remblai du terrain suit le
        # pivot — vecu 07/11 : pivot corrompu = POI enseveli dans un prisme
        # de terre) et AddDigoutBox (creuse une boite autour du POI)
        meta_row = QHBoxLayout()
        self.lbl_pivot = QLabel(t("epb.pivot_none"))
        # Infobulles : glossaire general (section EPB -- PivotPoint,
        # AddDigoutBox) en complement des textes i18n existants
        pivot_exp = find_glossary_explanation("PivotPoint", scope="epb")
        if pivot_exp:
            self.lbl_pivot.setToolTip(f"<b>PivotPoint</b><br>{pivot_exp}")
        meta_row.addWidget(self.lbl_pivot, 1)
        self.btn_pivot = QPushButton(t("epb.pivot_reset"))
        self.btn_pivot.setEnabled(False)
        self.btn_pivot.clicked.connect(self._reset_pivot)
        if pivot_exp:
            self.btn_pivot.setToolTip(f"<b>PivotPoint</b><br>{pivot_exp}")
        meta_row.addWidget(self.btn_pivot)
        self.chk_digout = QCheckBox(t("epb.digout_label"))
        self.chk_digout.setEnabled(False)
        digout_exp = find_glossary_explanation("AddDigoutBox", scope="epb")
        self.chk_digout.setToolTip(
            t("epb.digout_hint")
            + (f"<br><b>AddDigoutBox</b><br>{digout_exp}" if digout_exp else ""))
        self.chk_digout.toggled.connect(self._toggle_digout)
        meta_row.addWidget(self.chk_digout)
        lay.addLayout(meta_row)

        middle = QHBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("epb.col_file"), t("epb.col_blocks"),
                                   t("epb.col_unknown"), t("epb.col_id"),
                                   t("epb.col_name"), t("epb.col_count"),
                                   t("epb.col_group")])
        self.tree.setColumnWidth(0, 340)
        self.tree.setColumnWidth(1, 70)
        self.tree.setColumnWidth(2, 110)
        self.tree.setColumnWidth(3, 90)
        self.tree.setColumnWidth(4, 230)
        self.tree.setColumnWidth(6, 160)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        self.tree.currentItemChanged.connect(self._on_tree_select)
        self._tag_delegate = _TagDelegate(self.tree)
        self.tree.setItemDelegate(self._tag_delegate)
        middle.addWidget(self.tree, 5)

        right = QVBoxLayout()
        self.view3d = EpbView3D()
        self.view3d.blockClicked.connect(self._on_block_clicked)
        right.addWidget(self.view3d, 1)
        nav = QHBoxLayout()
        self.btn_rot = QPushButton(t("epb.rotate"))
        self.btn_rot.clicked.connect(
            lambda: self.view3d.set_quarter(self.view3d.get_quarter() + 1))
        nav.addWidget(self.btn_rot)
        self.btn_recenter = QPushButton(t("epb.recenter"))
        self.btn_recenter.clicked.connect(self.view3d.recenter)
        nav.addWidget(self.btn_recenter)
        self.btn_color_index = QPushButton(t("epb.color_index"))
        self.btn_color_index.setEnabled(False)
        self.btn_color_index.clicked.connect(self._open_color_index)
        nav.addWidget(self.btn_color_index)
        self.btn_view3d = QPushButton(t("epb.view3d"))
        self.btn_view3d.setEnabled(False)
        self.btn_view3d.clicked.connect(self._open_view3d)
        nav.addWidget(self.btn_view3d)
        self._view3d_window = None
        nav.addStretch(1)
        self.lbl_block = QLabel(t("epb.no_selection"))
        nav.addWidget(self.lbl_block, 1)
        right.addLayout(nav)

        replace_box = QHBoxLayout()
        self.lbl_replace = QLabel(t("epb.replace_with"))
        replace_box.addWidget(self.lbl_replace)
        self.combo_replace = QComboBox()
        self.combo_replace.setEnabled(False)
        replace_box.addWidget(self.combo_replace, 1)
        self.btn_replace = QPushButton(t("epb.replace_btn"))
        self.btn_replace.setEnabled(False)
        self.btn_replace.clicked.connect(self._replace_current)
        replace_box.addWidget(self.btn_replace)
        right.addLayout(replace_box)
        middle.addLayout(right, 4)
        lay.addLayout(middle, 1)

        bottom = QHBoxLayout()
        self.btn_export = QPushButton(t("epb.export_csv"))
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_csv)
        bottom.addWidget(self.btn_export)
        self.btn_save = QPushButton(t("epb.save"))
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_modified)
        bottom.addWidget(self.btn_save)
        self.btn_remove = QPushButton(t("epb.remove"))
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self._remove_unknown)
        bottom.addWidget(self.btn_remove)
        self.btn_import = QPushButton(t("epb.import_blocks"))
        self.btn_import.setEnabled(False)
        self.btn_import.setToolTip(t("epb.import_hint"))
        self.btn_import.clicked.connect(self._import_missing)
        bottom.addWidget(self.btn_import)
        bottom.addStretch(1)
        self.btn_close = QPushButton(t("btn.close"))
        self.btn_close.clicked.connect(self.accept)
        bottom.addWidget(self.btn_close)
        lay.addLayout(bottom)

        self.status_label = QLabel("")
        lay.addWidget(self.status_label)

        track(self, "epb_check", (980, 620))

    # ------------------------------------------------------------- navigation

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("epb.browse_file"), self.path_edit.text() or ".",
            "Empyrion (*.epb)")
        if path:
            self.path_edit.setText(path)

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("epb.browse_folder"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    # ------------------------------------------------------------- analyse

    def _analyze(self):
        path = self.path_edit.text().strip()
        if not path:
            self.status_label.setText(t("epb.need_path"))
            return
        self.tree.clear()
        self._targets = []
        self._current_target = None
        self._refresh_replace_panel()
        self.btn_remove.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_pivot.setEnabled(False)
        self.chk_digout.setEnabled(False)
        self.lbl_pivot.setText(t("epb.pivot_none"))
        self.view3d.set_data((0, 0, 0), [])
        self.lbl_block.setText(t("epb.no_selection"))

        paths = scan_epb_files(path)
        if not paths:
            self.status_label.setText(t("epb.no_epb"))
            return
        self.catalog = load_block_catalog(self.catalog_paths)
        _ws_root, self._extra_names, ws_scen = self._load_extra_names()

        unknown_total = 0
        forbidden_total = 0
        files_with_unknown = 0
        for p in paths:
            try:
                bp = EpbBlueprint(p, ecf_paths=self.catalog_paths).parse()
            except Exception as e:  # noqa: BLE001 - rapport d'erreur par fichier
                item = QTreeWidgetItem([str(p), "?", t("err.title"), "", "",
                                        "", ""])
                item.setToolTip(0, str(e))
                self.tree.addTopLevelItem(item)
                continue
            meta = read_meta_info(p)
            unknown = bp.unknown_counts(set(self.catalog.ids),
                                        self.catalog.names)
            forb = bp.forbidden_counts(self.catalog.forbidden,
                                       self.catalog.forbidden_names)
            unknown_total += sum(unknown.values())
            forbidden_total += sum(forb.values())
            if unknown:
                files_with_unknown += 1
            unknown_txt = (t("epb.unknown_count", n=sum(unknown.values()))
                           if unknown else t("epb.file_ok"))
            item = QTreeWidgetItem([str(p), str(len(bp.blocks)), unknown_txt,
                                    "", "", "", meta["group"]])
            item.setToolTip(0, t("epb.info_line", group=meta["group"] or "—",
                                 tags=meta["tags"] or "—",
                                 display=meta["display"] or "—",
                                 ver=bp.version,
                                 size="x".join(map(str, bp.size))))
            self._fill_block_children(item, bp, unknown, forb)
            self.tree.addTopLevelItem(item)
            self._targets.append({"path": p, "bp": bp, "unknown": unknown,
                                  "forb": forb, "item": item, "dirty": False,
                                  "meta": meta})

        self.tree.expandAll()
        self.btn_export.setEnabled(bool(self._targets))
        self.btn_color_index.setEnabled(bool(self._targets))
        if self.catalog is None or not self.catalog.ids:
            self.status_label.setText(t("epb.catalog_empty"))
        elif self._targets:
            self.status_label.setText(
                t("epb.unknown_total", n=unknown_total,
                  f=files_with_unknown) if unknown_total else t("epb.all_ok"))
            self.btn_remove.setEnabled(bool(unknown_total))
            self.btn_import.setEnabled(bool(self._missing_names()))
        else:
            self.status_label.setText(t("epb.all_ok"))
        if forbidden_total:
            # corrige : la chaine attend n ET f (les {f} bruts s'affichaient
            # depuis v1.11.0 -- l'appel ne passait que n)
            files_with_forbidden = sum(1 for tg in self._targets
                                       if tg["forb"])
            self.status_label.setText(
                self.status_label.text() + " " +
                t("epb.forbidden_total", n=forbidden_total,
                  f=files_with_forbidden))
            # retour utilisateur 07/11 : distinguer bloquant / non bloquant
            self.status_label.setText(
                self.status_label.text() + " " + t("epb.forbidden_hint"))
        # Preuve textuelle de la detection (vecu : l'utilisateur ne savait
        # pas si l'analyse trouvait quelque chose) : detail des problemes.
        details = self._problems_detail_text()
        if details:
            self.status_label.setText(self.status_label.text() + "  " + details)
        # Transparence du catalogue (vecu 23/09 : analyse faite avec la
        # vanille SEULE — le scenario n'etait pas ouvert — et CPUExtenderCVT4
        # est le nom VANILLE de l'id 2031 : aucun probleme affiche, fausse
        # impression de bug). Le dialogue dit toujours ce qu'il a compare.
        n_sources = len([p for p in self.catalog_paths if str(p).strip()])
        head = t("epb.catalog_sources", n=len(self.catalog.ids))
        if n_sources < 2:
            head += " " + t("epb.catalog_vanilla_only")
        if ws_scen:
            head += "  " + t("epb.workshop_names", n=ws_scen)
        self.status_label.setText(head + "  " + self.status_label.text())
        # RETOUR UTILISATEUR 23/09 (v2) : les lignes colorees etaient
        # RENDERED mais INVISIBLES — enterrees en bas de centaines de
        # lignes triees par quantite (4 cellules d'inconnu contre des
        # milliers de coques). Le filtre « problemes uniquement » coche
        # par defaut n'etait JAMAIS applique apres l'analyse.
        self._apply_filter()
        if self.chk_problems.isChecked() and not self._any_row_visible():
            # aucun probleme dans tout l'arbre : le filtre ne laisserait
            # qu'un arbre vide — decoche pour montrer le resultat complet
            self.chk_problems.setChecked(False)
        first = self._first_problem_item()
        if first is not None:
            self.tree.setCurrentItem(first)

    def _display_name(self, bid: int, bp: EpbBlueprint) -> str:
        """Nom affiche d'un id : mapping embarque du blueprint, catalogue
        (vanille + scenario), puis annuaire des AUTRES scenarios du
        workshop (retour utilisateur 07/11 : un id absent d'ici existe
        souvent ailleurs — le nom permet de choisir un equivalent)."""
        return (bp.id_mapping.get(bid) or self.catalog.ids.get(bid)
                or self._extra_names.get(bid) or f"ID_Bloc_{bid}")

    def _missing_names(self) -> set:
        """Noms references par les blueprints analyses mais absents du
        catalogue (vanille + scenario) — les blocs que le jeu supprime
        au chargement."""
        missing = set()
        for tg in self._targets:
            bp = tg["bp"]
            for bid in tg["unknown"]:
                name = bp.id_mapping.get(bid)
                if name:
                    missing.add(name)
        return {n for n in missing if n not in self.catalog.names}

    def _source_texts(self) -> list:
        """Textes des BlocksConfig sources pour l'import : vanille puis
        scenarios du workshop."""
        if self._source_cache is None:
            texts = []
            vanilla = get_vanilla_content_path() or ""
            if vanilla:
                vf = Path(vanilla) / "BlocksConfig.ecf"
                if vf.is_file():
                    texts.append(vf.read_text(encoding="utf-8",
                                              errors="replace"))
            root, _names, _n = load_workshop_block_names(
                get_vanilla_content_path() or "")
            if root:
                for sc in sorted(Path(root).iterdir()):
                    vf = sc / "Content" / "Configuration" / "BlocksConfig.ecf"
                    if vf.is_file():
                        texts.append(vf.read_text(encoding="utf-8",
                                                  errors="replace"))
            self._source_cache = texts
        return self._source_cache

    def _scenario_blocks_ecf(self) -> Path:
        """BlocksConfig.ecf du scenario (dernier chemin de catalogue)."""
        last = Path(self.catalog_paths[-1])
        return last / "BlocksConfig.ecf" if last.is_dir() else last

    def _import_missing(self):
        """Importe les definitions de blocs manquants depuis la vanille et
        les autres scenarios du workshop : le POI se recharge complet
        (retour utilisateur 07/11 — Citadel of Zirax incompleta)."""
        if not self._targets:
            return
        missing = self._missing_names()
        if not missing:
            self.status_label.setText(t("epb.import_none"))
            return
        texts = self._source_texts()
        scen_ecf = self._scenario_blocks_ecf()
        scen_text = scen_ecf.read_text(encoding="utf-8", errors="replace")
        imported, not_found = [], list(missing)
        # deux passes : les Ref des blocs importes peuvent referencer
        # d'autres manquants
        for _round in range(3):
            round_imported = []
            rest = []
            for name in not_found:
                text = None
                for src in texts:
                    text = extract_block_definition(src, name)
                    if text:
                        break
                if not text:
                    rest.append(name)
                    continue
                # collision d'Id dans le scenario : on importe SANS Id
                # (le jeu attribue un id runtime et le mapping resout
                # par nom)
                bid = block_id_from_definition(text)
                if bid is not None and bid in self.catalog.ids:
                    text = re.sub(r'^\s*Id:\s*\d+,?\s*$', '', text,
                                  flags=re.MULTILINE)
                scen_text += text + "\r\n"
                imported.append(name)
                round_imported.append(name)
            not_found = rest
            if not round_imported:
                break
            # les blocs importes peuvent referencer d'autres manquants :
            # les resolution de Ref se fait sur le texte du scenario
            for name in round_imported:
                pass
        if imported:
            central_backup(scen_ecf, "epb_import")
            scen_ecf.write_text(scen_text, encoding="utf-8")
            self._source_cache = None
            self.catalog = load_block_catalog(self.catalog_paths)
            self._analyze()
            self.status_label.setText(
                t("epb.import_done", n=len(imported),
                  names=", ".join(sorted(imported)[:6]))
                + ("" if not not_found else "  "
                   + t("epb.import_not_found", n=len(not_found))))
        else:
            self.status_label.setText(
                t("epb.import_not_found", n=len(not_found)))

    def _load_extra_names(self):
        """Annuaire {id: nom} des autres scenarios du workshop (cache) ;
        ne change JAMAIS le statut connu/inconnu, uniquement le nom."""
        root, names, scenarios = load_workshop_block_names(
            get_vanilla_content_path() or "")
        self._extra_names = names
        return root, names, scenarios

    def _problems_detail_text(self) -> str:
        """Liste texte des problemes detectes (max 4) : « Nom x4 (inconnu) »
        — preuve en clair de ce que l'analyse a trouve."""
        entries = []
        for tg in self._targets:
            bp = tg["bp"]
            for bid, cnt in list(tg["unknown"].items())[:2]:
                name = self._display_name(bid, bp)
                entries.append(f"{name} x{cnt} ({t('epb.unknown_tag')})")
            for bid, cnt in list(tg["forb"].items())[:2]:
                name = self._display_name(bid, bp)
                entries.append(f"{name} x{cnt} ({t('epb.forbidden_tag')})")
        if not entries:
            return ""
        shown = " ; ".join(entries[:4])
        if len(entries) > 4:
            shown += " ..."
        return "(" + shown + ")"

    def _fill_block_children(self, item, bp, unknown, forbidden=None):
        """Enfants du fichier : TOUS les ids distincts (tries par quantite).
        Statuts : inconnu (rouge) = absent du catalogue ; interdit (orange) =
        AllowedInBlueprint: false dans les ECF — refuse au spawn d'un
        blueprint JOUEUR, sans effet sur un POI/playfield (retour 07/11 :
        le surlignage orange se desactive, il ne signale pas une
        corruption). Le UserRole porte le statut pour le delegate et le
        filtre."""
        forbidden = forbidden or {}
        counts: dict = {}
        for b in bp.blocks:
            counts[b.block_id] = counts.get(b.block_id, 0) + 1
        for bid, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            name = self._display_name(bid, bp)
            child = QTreeWidgetItem(["", "", "", str(bid), name,
                                     t("epb.unknown_count", n=cnt), ""])
            if bid in forbidden:
                child.setText(2, t("epb.forbidden_tag"))
                child.setData(0, Qt.ItemDataRole.UserRole, "forbidden")
                _tag_row(child, _FORBIDDEN_FG, _FORBIDDEN_BG)
            elif bid in unknown:
                child.setText(2, t("epb.unknown_tag"))
                child.setData(0, Qt.ItemDataRole.UserRole, "unknown")
                _tag_row(child, _UNKNOWN_FG, _UNKNOWN_BG)
                child.setToolTip(4, t("epb.unknown_tooltip"))
            item.addChild(child)

    def _refresh_item(self, target):
        """Rafraichit l'item d'arbre d'un blueprint modifie en memoire."""
        unknown = target["bp"].unknown_counts(set(self.catalog.ids),
                                              self.catalog.names)
        forb = target["bp"].forbidden_counts(self.catalog.forbidden,
                                             self.catalog.forbidden_names)
        target["unknown"] = unknown
        target["forb"] = forb
        item = target["item"]
        item.setText(2, (t("epb.unknown_count", n=sum(unknown.values()))
                         if unknown else t("epb.file_ok")))
        item.takeChildren()
        self._fill_block_children(item, target["bp"], unknown, forb)
        self._apply_filter()

    def _toggle_forbidden(self, checked: bool):
        """Surlignage des blocs interdits on/off (retour utilisateur 07/11) :
        le delegate saute la peinture orange, le filtre les compte comme
        des lignes normales."""
        self._tag_delegate.show_forbidden = checked
        self.tree.viewport().update()
        self._apply_filter()

    # ------------------------------------------------------------- metas

    def _refresh_meta_panel(self, target):
        """Pivot et AddDigoutBox du blueprint affiche (metas de l'entete)."""
        bp = target["bp"]
        try:
            values = bp.meta_values()
        except Exception:  # noqa: BLE001 - prefab exotique : panneau inerte
            values = {}
        pivot = values.get(18)
        digout = values.get(1)
        has = bool(bp._props_span)
        self.lbl_pivot.setText(t("epb.pivot_label",
                                 value=str(pivot) if pivot is not None
                                 else "—"))
        self.btn_pivot.setEnabled(has and pivot not in (None, 0))
        self.chk_digout.setEnabled(has and digout is not None)
        self.chk_digout.blockSignals(True)
        self.chk_digout.setChecked(bool(digout))
        self.chk_digout.blockSignals(False)

    def _reset_pivot(self):
        """Remet le pivot a 0 : le remblai du terrain suit le pivot — un
        pivot corrompu ensevelit le POI (vecu : ATL_Citadel, pivot
        140640852475882, 2/3 du POI sous un prisme de terre)."""
        target = self._current_target
        if target is None:
            return
        if not ask_yes_no(self, t("epb.confirm_title"),
                          t("epb.pivot_confirm")):
            return
        target["bp"].set_meta_values({18: 0})
        target["dirty"] = True
        self.btn_save.setEnabled(any(tg["dirty"] for tg in self._targets))
        self._refresh_meta_panel(target)
        self.status_label.setText(t("epb.pivot_done"))

    def _toggle_digout(self, checked: bool):
        target = self._current_target
        if target is None:
            return
        target["bp"].set_meta_values({1: bool(checked)})
        target["dirty"] = True
        self.btn_save.setEnabled(any(tg["dirty"] for tg in self._targets))
        self.status_label.setText(t("epb.digout_done",
                                   state=t("epb.digout_on" if checked
                                           else "epb.digout_off")))

    def _apply_filter(self):
        """Filtre 'problemes uniquement' : masque les lignes de blocs connus
        (et les fichiers sans aucun probleme) quand la case est cochee.
        Les blocs interdits ne comptent comme problemes que si leur
        surlignage est actif (retour 07/11 : interdit n'est pas bloquant
        pour un POI)."""
        only = self.chk_problems.isChecked()
        show_forb = self.chk_forbidden.isChecked()
        for tg in self._targets:
            item = tg["item"]
            forb = tg.get("forb") or {}
            for i in range(item.childCount()):
                child = item.child(i)
                bid = self._id_of_item(child)
                has_issue = (bid in tg["unknown"]) or (
                    bid in forb and show_forb)
                child.setHidden(only and not has_issue)
            visible = any(not item.child(i).isHidden()
                          for i in range(item.childCount()))
            item.setHidden(only and not visible)

    def _any_row_visible(self) -> bool:
        """Au moins une ligne (fichier ou bloc) visible dans l'arbre ?"""
        for tg in self._targets:
            item = tg["item"]
            if not item.isHidden():
                return True
            for i in range(item.childCount()):
                if not item.child(i).isHidden():
                    return True
        return False

    def _first_problem_item(self):
        """Premiere ligne de bloc probleme (inconnu ou interdit) de l'arbre,
        visible de preference — pour l'amenner a l'ecran a l'analyse."""
        for want_visible in (True, False):
            for tg in self._targets:
                item = tg["item"]
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.text(2) and (not want_visible
                                          or not child.isHidden()):
                        return child
        return None

    # ------------------------------------------------------------- selection

    def _on_tree_select(self, current, _previous):
        """Selection d'un fichier ou d'un bloc : vue 3D + panneau
        de remplacement si une ligne de bloc est selectionnee."""
        if self._suppress_tree_select:
            return
        self._refresh_replace_panel()
        target = self._target_for_item(current) if current is not None else None
        if target is None:
            return
        self._show_target(target)

    def _show_target(self, target):
        if self._current_target is not target:
            self.view3d.set_data(target["bp"].size, target["bp"].blocks,
                                 self._effective_known_ids(target))
            self._current_target = target
        meta = target.get("meta") or {}
        bp = target["bp"]
        self.lbl_info.setText(t(
            "epb.info_line", group=meta.get("group") or "—",
            tags=meta.get("tags") or "—",
            display=meta.get("display") or "—", ver=bp.version,
            size="x".join(map(str, bp.size))))
        self._refresh_meta_panel(target)
        self.btn_export.setEnabled(True)
        self.btn_view3d.setEnabled(True)

    def _effective_known_ids(self, target):
        """Ids connus effectifs pour un blueprint : ceux du catalogue plus
        les ids du blueprint dont le nom (mapping embarque) existe dans les
        ECF (blocs Ref: sans Id, id attribue par le jeu au chargement)."""
        bp = target["bp"]
        known = set(self.catalog.ids)
        if self.catalog.names:
            for b in bp.blocks:
                name = bp.id_mapping.get(b.block_id)
                if name and name in self.catalog.names:
                    known.add(b.block_id)
        return known

    def _target_for_item(self, item):
        target_item = item
        while target_item is not None and target_item.parent() is not None:
            target_item = target_item.parent()
        for tgt in self._targets:
            if tgt["item"] is target_item:
                return tgt
        return None

    def _id_of_item(self, item):
        parent = item.parent() if item is not None else None
        if parent is None:
            return None
        try:
            return int(item.text(3))
        except ValueError:
            return None

    def _open_view3d(self):
        """Fenetre externe EPD-like : cubes colores, camera orbitale
        (gui/epb_3d_window.py) ; une seule instance, re-alimentee."""
        target = self._current_target
        if target is None:
            return
        if self._view3d_window is None:
            from gui.epb_3d_window import Epb3dWindow
            self._view3d_window = Epb3dWindow(target["bp"], parent=self)
        else:
            self._view3d_window.set_blueprint(target["bp"])
        self._view3d_window.show()
        self._view3d_window.raise_()

    def _on_block_clicked(self, info):
        """Clic sur un voxel de la vue 3D : affiche id + nom et selectionne
        la ligne correspondante dans l'arbre (si presente)."""
        if not info or info.get("id") is None:
            self.lbl_block.setText(t("epb.no_selection"))
            return
        bid = info["id"]
        name = self._display_name(bid, self._current_target["bp"])
        self.lbl_block.setText(t("epb.block_info", id=bid, name=name))
        self._select_block_in_tree(bid)

    def _mapping_name(self, bid: int):
        """Nom d'un id via le mapping embarque du blueprint affiche."""
        target = self._current_target
        if target is not None:
            name = target["bp"].id_mapping.get(bid)
            if name:
                return name
        return None

    def _select_block_in_tree(self, bid: int):
        target = self._current_target
        if target is None:
            return
        item = target["item"]
        for i in range(item.childCount()):
            child = item.child(i)
            if child.text(3) == str(bid):
                # evite une re-projection complete de la vue 3D
                self._suppress_tree_select = True
                self.tree.setCurrentItem(child)
                self._suppress_tree_select = False
                self._refresh_replace_panel()
                return

    # ---------------------------------------------------------- remplacement

    def _refresh_replace_panel(self):
        """Combo de remplacement (editable, saisie libre) : actif des qu'un
        fichier est selectionne avec un catalogue non vide ; le bouton
        Remplacer s'active sur une ligne de bloc precise."""
        item = self.tree.currentItem()
        target = self._target_for_item(item) if item is not None else None
        usable = target is not None and bool(self.catalog.ids)
        self.combo_replace.setEnabled(usable)
        self.btn_replace.setEnabled(False)
        if not usable:
            return
        if self.combo_replace.count() == 0:
            self._populate_replace_combo()
        bid = self._id_of_item(item)
        if bid is not None:
            idx = self.combo_replace.findData(bid)
            self.combo_replace.setCurrentIndex(max(0, idx))
            self.btn_replace.setEnabled(True)

    def _populate_replace_combo(self):
        """Remplit le combo (editable + completion contient, insensible a la
        casse) avec tous les blocs du catalogue tries PAR NOM ALPHABETIQUE
        (demande 24/09/2026 : en tapant « core », tous les blocs contenant
        core apparaissent groupes dans la liste). NB : on regle le completer
        INTERNE du combo (cree par setEditable) -- installer un QCompleter
        manuel sur le model du combo crashe nativement (PyQt 6.11)."""
        self.combo_replace.clear()
        for bid in sorted(self.catalog.ids,
                          key=lambda b: self.catalog.ids[b].lower()):
            self.combo_replace.addItem(
                t("epb.combo_entry", name=self.catalog.ids[bid], id=bid), bid)
        self.combo_replace.setEditable(True)
        self.combo_replace.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self.combo_replace.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def _resolve_replacement(self, text: str) -> Optional[int]:
        """Resout la saisie libre du combo : id numerique, texte d'item
        'Nom (id)', nom exact (insensible casse) ou contient unique."""
        text = (text or "").strip()
        if not text:
            return None
        m = re.match(r"^(.*)\((\d+)\)\s*$", text)
        if m and int(m.group(2)) in self.catalog.ids:
            return int(m.group(2))
        if text.isdigit():
            return int(text)
        lowered = text.lower()
        exact = [bid for bid, name in self.catalog.ids.items()
                 if name.lower() == lowered]
        if exact:
            return exact[0]
        contains = [bid for bid, name in self.catalog.ids.items()
                    if lowered in name.lower()]
        if len(contains) == 1:
            return contains[0]
        return None

    def _replace_current(self):
        item = self.tree.currentItem()
        if item is None or item.parent() is None:
            return
        old_id = self._id_of_item(item)
        new_id = self._resolve_replacement(self.combo_replace.currentText())
        if old_id is None or new_id is None or new_id == old_id:
            if new_id is None:
                self.status_label.setText(
                    t("epb.replace_not_found",
                      text=self.combo_replace.currentText()))
            return
        target = self._target_for_item(item)
        count = target["bp"].replace_ids({old_id: new_id},
                                         id_names=self.catalog.ids)
        target["dirty"] = True
        self._refresh_item(target)
        self._show_target(target)
        self.btn_save.setEnabled(any(tg["dirty"] for tg in self._targets))
        self.btn_remove.setEnabled(any(tg["unknown"] for tg in self._targets))
        self.status_label.setText(
            t("epb.replaced_done", n=count, old=old_id,
              name=self.catalog.ids.get(new_id, str(new_id))))

    # ---------------------------------------------------------- sauvegardes

    def _save_modified(self):
        saved = 0
        for tg in self._targets:
            if tg["dirty"]:
                tg["bp"].save(backup=True)
                tg["dirty"] = False
                saved += 1
        self.btn_save.setEnabled(False)
        self.status_label.setText(t("epb.saved_done", f=saved))

    def _export_csv(self):
        item = self.tree.currentItem()
        target = self._target_for_item(item) if item else (
            self._targets[0] if self._targets else None)
        if target is None:
            return
        bp = target["bp"]
        out_path = target["path"].with_suffix("")
        suggested = str(out_path) + "_blocs.csv"
        out, _ = QFileDialog.getSaveFileName(self, t("epb.export_csv"),
                                             suggested, "CSV (*.csv)")
        if not out:
            return
        bp.export_csv(out, headers=t("epb.csv_headers").split(";"),
                      name_of=lambda bid: self._display_name(bid, bp))
        self.status_label.setText(t("epb.csv_done", path=out))

    # ---------------------------------------------------------- index couleurs

    def _open_color_index(self):
        dlg = self._build_color_index_dialog()
        if dlg is not None:
            dlg.exec()

    def _build_color_index_dialog(self):
        """Index des couleurs de la vue 3D : un item par id de bloc
        (pastille de couleur, nom, quantite), tries par quantite."""
        target = self._current_target or (self._targets[0] if self._targets
                                          else None)
        if target is None:
            return None
        bp = target["bp"]
        counts: dict = {}
        for b in bp.blocks:
            counts[b.block_id] = counts.get(b.block_id, 0) + 1
        dlg = QDialog(self)
        dlg.setWindowTitle(t("epb.color_index"))
        lay = QVBoxLayout(dlg)
        lst = QListWidget(dlg)
        for bid, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            name = self._display_name(bid, bp)
            item = QListWidgetItem(
                t("epb.color_entry", n=cnt, name=name, id=bid), lst)
            pm = QPixmap(12, 12)
            pm.fill(block_color(bid,
                                unknown=bid not in self.catalog.ids))
            item.setIcon(QIcon(pm))
            lst.addItem(item)
        lay.addWidget(lst)
        btn_close = QPushButton(t("btn.close"))
        btn_close.clicked.connect(dlg.accept)
        lay.addWidget(btn_close)
        dlg.resize(380, 460)
        return dlg

    # ---------------------------------------------------------- menu contextuel

    def _tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None or item.parent() is None:
            return
        bid = self._id_of_item(item)
        if bid is None:
            return
        menu = QMenu(self)
        act_replace = menu.addAction(t("epb.ctx_replace"))
        act_delete = menu.addAction(t("epb.ctx_delete"))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == act_replace:
            self.tree.setCurrentItem(item)          # active le panneau
            self.combo_replace.setFocus()
        elif chosen == act_delete:
            self._delete_block(item, bid)

    def _delete_block(self, item, bid):
        target = self._target_for_item(item)
        if target is None:
            return
        if not ask_yes_no(self, t("epb.confirm_title"),
                          t("epb.confirm_delete_block", id=bid)):
            return
        removed = target["bp"].remove_ids({bid})
        target["dirty"] = True
        self._refresh_item(target)
        self._show_target(target)
        self.btn_save.setEnabled(any(tg["dirty"] for tg in self._targets))
        self.btn_remove.setEnabled(any(tg["unknown"] for tg in self._targets))
        self.status_label.setText(t("epb.deleted_done", n=removed))

    # ---------------------------------------------------------- suppression

    def _remove_unknown(self):
        if not self._targets or self.catalog is None or not self.catalog.ids:
            return
        files = [tg for tg in self._targets if tg["unknown"]]
        if not files:
            return
        if not ask_yes_no(self, t("epb.confirm_title"),
                          t("epb.confirm_body", f=len(files))):
            return
        removed_total = 0
        for tg in files:
            removed_total += tg["bp"].remove_ids(tg["unknown"].keys())
            tg["bp"].save(backup=True)
            tg["dirty"] = False
            self._refresh_item(tg)
        self.view3d.set_data((0, 0, 0), [])
        self._current_target = None
        self.btn_remove.setEnabled(False)
        self.status_label.setText(t("epb.removed_done", n=removed_total))
