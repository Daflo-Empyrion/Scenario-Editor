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
Consultation du PROTOCOLE DE TEST MANUEL depuis l'application -- demande
explicite de l'utilisateur : sert a la fois de TUTORIEL (parcourir ce que
l'application sait faire, etape par etape) et d'AIDE AU DEBOGAGE (reproduire
un comportement signale en suivant le cas correspondant, puis l'exporter en
Markdown pour un rapport de bug).

Les donnees sont EMBARQUEES (core/test_protocol.py) : le protocole ET le
lancement de sessions (bouton "Commencer une session de tests...", vers
gui/test_protocol_runner.py) fonctionnent aussi dans la version INSTALLEE.
Fenetre NON MODALE (meme motif que les autres fenetres de resultats).
"""
import html

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSplitter, QWidget,
)

from core.i18n import t
from core.test_protocol import (
    CATEGORIES, cases_by_category, category_label,
    localized_case, protocol_to_markdown,
)


def _theme_icon(name: str):
    """Icone qtawesome avec repli propre (QIcon vide si absente)."""
    try:
        from gui.theme import icon as _icon
        return _icon(name)
    except Exception:
        from PyQt6.QtGui import QIcon
        return QIcon()


# References fortes : une fenetre runner sans reference Python serait
# detruite par le ramasse-miettes (fenetre top-level sans parent).
_RUNNER_REFS = []


def open_runner_window():
    """Ouvre (ou ramene au premier plan) le RUNNER de test pas-a-pas. Retourne
    la fenetre, ou None si les outils de developpement sont absents."""
    from gui import test_protocol_runner as runner_module
    for runner in _RUNNER_REFS:
        if runner.isVisible():
            runner.raise_()
            runner.activateWindow()
            return runner
    runner = runner_module.MainWindow()
    _RUNNER_REFS.append(runner)
    runner.show()
    return runner


class TestProtocolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("protocol.window_title"))
        self.setMinimumSize(860, 600)
        self.setModal(False)

        self._cases_by_id = {}

        layout = QVBoxLayout(self)

        start_row = QHBoxLayout()
        self.btn_start_session = QPushButton(t("protocol.start_session"))
        self.btn_start_session.setObjectName("primaryButton")
        self.btn_start_session.clicked.connect(self._start_session)
        start_row.addWidget(self.btn_start_session)
        start_row.addStretch()
        layout.addLayout(start_row)

        top_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(t("protocol.search"))
        self.search_edit.textChanged.connect(self._populate_tree)
        top_row.addWidget(self.search_edit, 1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("mutedLabel")
        top_row.addWidget(self.count_label)
        layout.addLayout(top_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("protocol.col_case"), t("protocol.col_title")])
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self._show_details)
        splitter.addWidget(self.tree)

        details_holder = QWidget()
        details_lay = QVBoxLayout(details_holder)
        details_lay.setContentsMargins(0, 0, 0, 0)
        details_lay.setSpacing(4)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        details_lay.addWidget(self.details, 1)
        # Barre de copie des commandes du cas selectionne (commandes console
        # et chemins : un bouton par commande + copie globale).
        cmds_row = QHBoxLayout()
        self.btn_copy_all_cmds = QPushButton(t("runner.copy_all_cmds"))
        self.btn_copy_all_cmds.setObjectName("secondaryButton")
        self.btn_copy_all_cmds.setIcon(_theme_icon("fa5s.copy"))
        self.btn_copy_all_cmds.clicked.connect(self._copy_all_cmds)
        self.btn_copy_all_cmds.setVisible(False)
        cmds_row.addWidget(self.btn_copy_all_cmds)
        cmds_row.addStretch()
        details_lay.addLayout(cmds_row)
        self._current_cmds = []
        splitter.addWidget(details_holder)
        splitter.setSizes([320, 260])
        layout.addWidget(splitter, 1)

        bottom_row = QHBoxLayout()
        btn_export = QPushButton(t("results_window.btn_export"))
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_markdown)
        bottom_row.addWidget(btn_export)
        bottom_row.addStretch()
        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self._populate_tree()

    # ------------------------------------------------------------------

    def _start_session(self):
        """Lance le runner pas-a-pas (fenetre dediee) : choix session
        vierge/reprise, puis chaque cas un par un avec verdicts."""
        return open_runner_window()

    def _populate_tree(self) -> None:
        query = self.search_edit.text().strip().lower()
        self.tree.clear()
        self._cases_by_id = {}
        grouped = cases_by_category()
        shown = 0
        for code, _label in CATEGORIES:
            cases = grouped[code]
            if not cases:
                continue
            matching = []
            for c in cases:
                if not query:
                    matching.append(c)
                    continue
                loc = localized_case(c)
                if (query in c["id"].lower()
                        or query in loc["titre"].lower()
                        or any(query in row["txt"].lower() for row in loc["etapes"])
                        or any(query in cmd.lower() for row in loc["etapes"] for cmd in row["cmds"])
                        or query in loc["attendu"].lower()):
                    matching.append(c)
            if not matching:
                continue
            cat_item = QTreeWidgetItem([category_label(code)])
            for case in matching:
                loc = localized_case(case)
                rev = f" (rev {case['rev']})" if case.get("rev") else ""
                item = QTreeWidgetItem([case["id"], loc["titre"] + rev])
                item.setData(0, Qt.ItemDataRole.UserRole, case)
                self._cases_by_id[id(item)] = case
                cat_item.addChild(item)
                shown += 1
            self.tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)
        self.count_label.setText(t("protocol.n_cases", n=shown))
        self.details.setPlainText(t("protocol.select_case"))

    def _show_details(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        case = items[0].data(0, Qt.ItemDataRole.UserRole)
        if case is None:
            return
        loc = localized_case(case)
        lines = [f"<b>{html.escape(loc['id'])} - {html.escape(loc['titre'])}</b><br>"]
        if loc.get("pre"):
            lines.append(f"<i>{html.escape(t('protocol.pre'))} : "
                         f"{html.escape(loc['pre'])}</i><br>")
        lines.append("<ol>")
        self._current_cmds = []
        for row in loc["etapes"]:
            lines.append(f"<li>{html.escape(row['txt'])}</li>")
            for cmd in row["cmds"]:
                self._current_cmds.append(cmd)
                lines.append(f"<dd><code>{html.escape(cmd)}</code></dd>")
        lines.append("</ol>")
        lines.append(f"<b>{html.escape(t('protocol.expected'))} :</b> "
                     f"{html.escape(loc['attendu'])}")
        self.details.setHtml("".join(lines))
        self.btn_copy_all_cmds.setVisible(bool(self._current_cmds))

    def _copy_all_cmds(self) -> None:
        if self._current_cmds:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText("\r\n".join(self._current_cmds))

    def _export_markdown(self) -> None:
        from gui.results_window_helpers import export_text_to_file
        export_text_to_file(
            self, "protocole_de_test.md", protocol_to_markdown(),
            title_key="protocol.export_title", file_filter="Markdown (*.md)")


def open_protocol_dialog(main_window):
    """Point d'entree du menu Aide : ouvre (non modal) une SEULE instance,
    garde une reference sur la fenetre principale pour eviter la destruction
    par le ramasse-miettes (meme motif que les autres fenetres de resultats)."""
    existing = getattr(main_window, "_test_protocol_dialog", None)
    if existing is not None and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return existing
    dlg = TestProtocolDialog(main_window)
    main_window._test_protocol_dialog = dlg
    dlg.show()
    return dlg
