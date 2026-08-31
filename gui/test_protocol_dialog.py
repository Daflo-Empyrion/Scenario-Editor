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
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSplitter,
)

from core.i18n import t
from core.test_protocol import CATEGORIES, cases_by_category, protocol_to_markdown


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

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        splitter.addWidget(self.details)
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
        for code, label in CATEGORIES:
            cases = grouped[code]
            if not cases:
                continue
            matching = [c for c in cases
                        if not query
                        or query in c["id"].lower()
                        or query in c["titre"].lower()
                        or any(query in step.lower() for step in c.get("etapes", []))
                        or query in c["attendu"].lower()]
            if not matching:
                continue
            cat_item = QTreeWidgetItem([label])
            for case in matching:
                rev = f" (rev {case['rev']})" if case.get("rev") else ""
                item = QTreeWidgetItem([case["id"], case["titre"] + rev])
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
        lines = [f"<b>{case['id']} - {case['titre']}</b><br>"]
        if case.get("pre"):
            lines.append(f"<i>{t('protocol.pre')} : {case['pre']}</i><br>")
        lines.append("<ol>")
        for step in case.get("etapes", []):
            lines.append(f"<li>{step}</li>")
        lines.append("</ol>")
        lines.append(f"<b>{t('protocol.expected')} :</b> {case['attendu']}")
        self.details.setHtml("".join(lines))

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
