"""
Fenetre de comparaison de deux scenarios complets. Independante d'un projet ouvert --
accessible depuis Fichier > Comparer deux scenarios...

Affiche a la fois :
  - un arbre interactif (fichiers organises par dossier, colores par statut, clic pour
    voir le detail)
  - un bouton d'export vers un rapport texte complet (tout en un fichier)
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter, QProgressDialog, QApplication, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

from core.i18n import t
from core.scenario_diff import compare_scenarios, ScenarioDiffResult, FileDiffEntry
from gui.theme import icon, icon_size, GREEN, RED, ORANGE, TEXT_GRAY, PRIMARY_DARK


STATUS_COLORS = {
    'added': GREEN,
    'removed': RED,
    'modified': ORANGE,
    'unchanged': TEXT_GRAY,
}


class ScenarioCompareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("compare.title"))
        self.resize(1100, 700)
        self.result: Optional[ScenarioDiffResult] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.edit_a = QLineEdit()
        btn_a = QPushButton(t("newproj.browse"))
        btn_a.clicked.connect(lambda: self._browse(self.edit_a))
        row_a = QHBoxLayout()
        row_a.addWidget(self.edit_a)
        row_a.addWidget(btn_a)
        form.addRow(t("compare.scenario_a"), row_a)

        self.edit_b = QLineEdit()
        btn_b = QPushButton(t("newproj.browse"))
        btn_b.clicked.connect(lambda: self._browse(self.edit_b))
        row_b = QHBoxLayout()
        row_b.addWidget(self.edit_b)
        row_b.addWidget(btn_b)
        form.addRow(t("compare.scenario_b"), row_b)
        layout.addLayout(form)

        top_row = QHBoxLayout()
        btn_run = QPushButton(icon("fa5s.balance-scale", "#ffffff"), t("compare.run"))
        btn_run.setIconSize(icon_size())
        btn_run.clicked.connect(self._run_compare)
        top_row.addWidget(btn_run)
        self.checkbox_show_unchanged = QCheckBox(t("compare.show_unchanged"))
        self.checkbox_show_unchanged.toggled.connect(self._populate_tree)
        top_row.addWidget(self.checkbox_show_unchanged)
        top_row.addStretch()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        top_row.addWidget(self.summary_label)
        layout.addLayout(top_row)

        self.direction_label = QLabel("")
        self.direction_label.setStyleSheet(f"font-weight: 700; color: {PRIMARY_DARK}; padding: 4px 0;")
        layout.addWidget(self.direction_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Fichier"])
        self.tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self.tree)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setPlainText(t("compare.select_file_hint"))
        splitter.addWidget(self.detail_view)
        splitter.setSizes([450, 650])
        layout.addWidget(splitter, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("compare.export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_report)
        bottom_row.addWidget(btn_export)
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.reject)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _browse(self, target_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, t("compare.choose_folder"))
        if folder:
            target_edit.setText(folder)

    def _run_compare(self):
        path_a_text = self.edit_a.text().strip()
        path_b_text = self.edit_b.text().strip()
        if not path_a_text or not path_b_text:
            QMessageBox.warning(self, t("err.missing_field"), t("compare.both_required"))
            return
        path_a, path_b = Path(path_a_text), Path(path_b_text)
        if not path_a.exists() or not path_b.exists():
            QMessageBox.warning(self, t("err.invalid_path"), t("compare.both_required"))
            return

        progress = QProgressDialog(t("compare.progress"), None, 0, 0, self)
        progress.setWindowTitle(t("progress.please_wait"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def on_progress(current, total, rel_path):
            if total:
                progress.setRange(0, total)
                progress.setValue(current)
            QApplication.processEvents()

        try:
            self.result = compare_scenarios(path_a, path_b, progress_callback=on_progress)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, t("compare.error_title"), str(e))
            return
        progress.close()

        c = self.result.counts()
        self.summary_label.setText(t("compare.summary", added=c['added'], removed=c['removed'],
                                      modified=c['modified'], unchanged=c['unchanged']))
        self.direction_label.setText(
            t("compare.direction_label", name_a=self.result.root_a.name, name_b=self.result.root_b.name)
        )
        self._populate_tree()

    def _populate_tree(self):
        self.tree.clear()
        if not self.result:
            return
        include_unchanged = self.checkbox_show_unchanged.isChecked()
        entries = self.result.entries if include_unchanged else self.result.changed_entries()

        # Regroupe par dossier pour un arbre lisible plutot qu'une liste plate.
        folder_items = {}

        def get_folder_item(parts):
            if not parts:
                return self.tree.invisibleRootItem()
            key = tuple(parts)
            if key in folder_items:
                return folder_items[key]
            parent = get_folder_item(parts[:-1])
            item = QTreeWidgetItem(parent, [parts[-1]])
            item.setExpanded(True)
            folder_items[key] = item
            return item

        for entry in entries:
            path_parts = entry.rel_path.split('/')
            folder_parts, filename = path_parts[:-1], path_parts[-1]
            parent_item = get_folder_item(folder_parts)
            symbol = {'added': '+', 'removed': '-', 'modified': '~', 'unchanged': ' '}[entry.status]
            file_item = QTreeWidgetItem(parent_item, [f"{symbol} {filename}"])
            file_item.setData(0, Qt.ItemDataRole.UserRole, entry)
            color = QColor(STATUS_COLORS[entry.status])
            file_item.setForeground(0, QBrush(color))

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        entry: Optional[FileDiffEntry] = item.data(0, Qt.ItemDataRole.UserRole)
        if entry is None:
            return  # clic sur un dossier, pas un fichier
        if entry.status == 'unchanged':
            self.detail_view.setPlainText(entry.rel_path)
        elif entry.detail:
            self.detail_view.setPlainText(f"{entry.rel_path}\n{'=' * len(entry.rel_path)}\n\n{entry.detail}")
        else:
            self.detail_view.setPlainText(f"{entry.rel_path}\n\n{t('compare.no_detail')}")

    def _export_report(self):
        if not self.result:
            QMessageBox.warning(self, t("err.missing_field"), t("compare.both_required"))
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self, t("compare.export_title"), "rapport_comparaison.txt", "Texte (*.txt)")
        if not path_str:
            return
        report = self.result.render_report(include_unchanged=self.checkbox_show_unchanged.isChecked())
        Path(path_str).write_text(report, encoding='utf-8')
        QMessageBox.information(self, t("compare.export_done_title"),
                                 t("compare.export_done_msg", path=path_str))
