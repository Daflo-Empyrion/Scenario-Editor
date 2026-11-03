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
Dialogue "Verifier les references croisees" -- complement a la verification
Ref classique (menu Verification > Verifier les references), qui ne regarde
qu'un seul type de lien au sein des fichiers ECF. Ici, plusieurs verifications
independantes et activables/desactivables (voir
core/ecf/cross_reference_check.py, CROSS_REFERENCE_CHECKS) : items/blocs
references, jetons, POI de playfield.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox,
)
from PyQt6.QtCore import Qt

from core.i18n import t
from gui.module_info import add_info_button
from core.ecf.cross_reference_check import (
    CROSS_REFERENCE_CHECKS, CrossRefContext, CrossRefIssue, run_checks,
    apply_dialogue_ref_fix, apply_pda_poi_fix, collect_pda_poi_pool,
)
from gui.results_window_helpers import export_text_to_file
from gui.theme import icon, icon_size


class CrossReferenceDialog(QDialog):
    def __init__(self, workspace, main_window, parent=None, only_check_ids=None):
        """only_check_ids : si fourni, seules ces verifications demarrent
        cochees (les autres restent decochees par defaut) -- utilise par
        l'ancien menu "Verifier les references" (check_references_dialog dans
        main_window.py) pour reutiliser cette meme fenetre (export,
        actualisation, navigation) en ne montrant que la verification
        d'heritage Ref, plutot que de dupliquer toute cette logique."""
        super().__init__(parent)
        self.workspace = workspace
        self.main_window = main_window
        self._last_issues = []

        self.setWindowTitle(t("crossref.title"))
        self.setMinimumSize(680, 520)
        from gui.window_geometry import track
        track(self, "cross_reference")
        layout = QVBoxLayout(self)

        intro = QLabel(t("crossref.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel(t("crossref.checks_label")))
        self.checkboxes = {}
        for check in CROSS_REFERENCE_CHECKS:
            box = QCheckBox(check.label_fr if _current_lang() == "fr" else check.label_en)
            checked = check.id in only_check_ids if only_check_ids is not None else check.enabled_by_default
            box.setChecked(checked)
            box.setToolTip(check.description_fr if _current_lang() == "fr" else check.description_en)
            layout.addWidget(box)
            self.checkboxes[check.id] = box

        btn_run = QPushButton(t("crossref.btn_run"))
        btn_run.setObjectName("primaryButton")
        btn_run.clicked.connect(self._do_run)
        layout.addWidget(btn_run)

        layout.addWidget(QLabel(t("crossref.results_label")))
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._navigate_to_issue)
        layout.addWidget(self.results_list, 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        bottom_row = QHBoxLayout()
        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("results_window.btn_refresh"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self._do_run)
        bottom_row.addWidget(btn_refresh)

        btn_export = QPushButton(icon("fa5s.file-export", "#4a7dfc"), t("results_window.btn_export"))
        btn_export.setIconSize(icon_size())
        btn_export.setObjectName("secondaryButton")
        btn_export.clicked.connect(self._export_results)
        bottom_row.addWidget(btn_export)

        add_info_button(bottom_row, "xref.info_html")
        bottom_row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _do_run(self):
        selected_ids = [cid for cid, box in self.checkboxes.items() if box.isChecked()]
        if not selected_ids:
            QMessageBox.information(self, t("crossref.title"), t("crossref.no_check_selected"))
            return

        # VERIF-001 : l'analyse lit le disque -- proposer d'abord d'enregistrer
        # les onglets modifies, sinon des modifications en memoire sont
        # invisibles pour les verifications.
        self.main_window.ensure_analysis_fresh_tabs()

        ecf_files = [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']

        ctx = CrossRefContext(
            ecf_files=ecf_files, yaml_files=[],
            scenario_root=self.workspace.working_root,
        )

        self.results_list.clear()
        # Retour utilisateur 30/08/2026 : l'analyse peut etre longue sur un
        # gros scenario (voir gui/busy.py) ; 23/09/2026 : calcul en worker +
        # gerbe plasma au-dela d'une seconde.
        try:
            from gui.busy import run_long
            issues = run_long(self, lambda: run_checks(ctx, selected_ids))
        except Exception as e:
            QMessageBox.critical(self, t("err.title"), f"{t('check.verification_error')} :\n{e}")
            return

        self._last_issues = issues
        if not issues:
            self.summary_label.setText(t("crossref.all_ok"))
            return

        for issue in issues[:500]:
            item = QListWidgetItem(issue.label())
            item.setData(Qt.ItemDataRole.UserRole, issue)
            self.results_list.addItem(item)
        more = ""
        if len(issues) > 500:
            more = t("crossref.more_issues", n=len(issues) - 500)
        self.summary_label.setText(t("crossref.issues_found", n=len(issues)) + more)

    def _export_results(self):
        """Exporte la liste complete des resultats (pas seulement les 500
        premiers affiches) vers un fichier texte -- utile pour garder une trace
        ou travailler hors de l'application. Relance la verification d'abord si
        elle n'a jamais ete lancee, pour ne jamais exporter un fichier vide par
        erreur d'usage."""
        if not self._last_issues and self.results_list.count() == 0 and not self.summary_label.text():
            self._do_run()
        lines = [t("crossref.title"), "=" * len(t("crossref.title")), ""]
        if not self._last_issues:
            lines.append(t("crossref.all_ok"))
        else:
            for issue in self._last_issues:
                lines.append(issue.label())
        export_text_to_file(self, "references_croisees.txt", "\n".join(lines))

    def _propose_dialogue_fix(self, issue: CrossRefIssue):
        """VERIF-006 : fenetre explicative + propositions de correction pour
        une reference Next/OptionNext vers un dialogue inexistant.
        Retourne True (correction appliquee), False (voir sans corriger) ou
        None (ferme sans rien faire)."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
            QRadioButton, QPushButton,
        )
        from core.ecf.cross_reference_check import (
            collect_dialogue_names, collect_dialogue_stats,
            closest_dialogue_name,
        )
        from core.workspace_undo import FileStateUndo, capture_file
        import re as _re

        ecf_files = [f.path for f in self.workspace.working.configuration
                     if f.extension == '.ecf']
        names = collect_dialogue_names(ecf_files)
        stats = collect_dialogue_stats(ecf_files)
        # la suggestion ne propose jamais le bloc source lui-meme (vecu
        # 03/11 : ExpeditionGeneral_Quit -> suggerait ExpeditionGeneral_Greet,
        # une auto-boucle)
        suggestion = closest_dialogue_name(
            issue.ref_value, [n for n in names if n != issue.source_identity])

        if self._is_path_modified(issue.source_file):
            QMessageBox.warning(self, t("crossref.fix_title"),
                                t("crossref.fix_locked", name=issue.source_file.name))
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle(t("crossref.fix_title"))
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)

        explanation = QLabel(t("crossref.fix_explain",
                               key=issue.ref_key, value=issue.ref_value,
                               block=issue.source_identity, file=issue.source_file.name))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        replace_radio = QRadioButton(t("crossref.fix_replace"))
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(names)
        if suggestion:
            combo.setCurrentText(suggestion)
        combo.setEnabled(False)
        replace_radio.toggled.connect(combo.setEnabled)
        layout.addWidget(replace_radio)
        layout.addWidget(combo)

        # coherence : a quoi ressemble le dialogue choisi (pointe par qui ?
        # terminal ?) -- le remplacement reste un choix de fond, l'indicateur
        # evite juste de poser une cible au hasard
        stats_label = QLabel("")
        stats_label.setWordWrap(True)
        stats_label.setStyleSheet("color: gray;")
        layout.addWidget(stats_label)

        def _update_stats():
            name = combo.currentText().strip()
            info = stats.get(name)
            if info is None:
                stats_label.setText(t("crossref.fix_stats_unknown"))
            else:
                kind = (t("crossref.fix_terminal") if info["terminal"]
                        else t("crossref.fix_branching"))
                stats_label.setText(t("crossref.fix_stats", name=name,
                                      refs=info["refs"], kind=kind))
        combo.currentTextChanged.connect(_update_stats)
        _update_stats()

        remove_radio = QRadioButton(t("crossref.fix_remove", key=issue.ref_key))
        remove_radio.setChecked(suggestion is None)
        replace_radio.setChecked(suggestion is not None)
        layout.addWidget(remove_radio)

        # consequences concretes de la suppression, selon la forme de la ref
        m_opt = _re.match(r"OptionNext_(\d+)", issue.ref_key)
        implication = QLabel(
            t("crossref.fix_implication_option", n=m_opt.group(1)) if m_opt
            else t("crossref.fix_implication_next"))
        implication.setWordWrap(True)
        implication.setStyleSheet("color: gray;")
        layout.addWidget(implication)

        note = QLabel(t("crossref.fix_note", suggest=suggestion) if suggestion
                      else t("crossref.fix_note_none"))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        btn_apply = QPushButton(t("crossref.fix_apply"))
        btn_apply.setObjectName("primaryButton")
        btn_apply.clicked.connect(dialog.accept)
        buttons.addWidget(btn_apply)
        btn_view = QPushButton(t("crossref.fix_view"))
        btn_view.setObjectName("secondaryButton")

        outcome = {"applied": False}
        def _accept():
            outcome["applied"] = True
            dialog.accept()
        btn_apply.clicked.disconnect()
        btn_apply.clicked.connect(_accept)

        def _view():
            outcome["applied"] = False
            dialog.accept()
        btn_view.clicked.connect(_view)
        buttons.addWidget(btn_view)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        def _reject():
            outcome["applied"] = None
            dialog.reject()
        btn_cancel.clicked.connect(_reject)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        dialog.exec()
        if outcome["applied"] is None:
            return None
        if not outcome["applied"]:
            return False

        new_value = combo.currentText().strip() if replace_radio.isChecked() else None
        if replace_radio.isChecked() and not new_value:
            QMessageBox.warning(self, t("crossref.fix_title"), t("crossref.fix_empty"))
            return False
        try:
            prior = capture_file(issue.source_file)
            applied = apply_dialogue_ref_fix(
                issue.source_file, issue.source_identity,
                issue.ref_key, issue.ref_value, new_value)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"),
                                 t("check.verification_error") + " : " + str(e))
            return False
        if not applied:
            QMessageBox.warning(self, t("crossref.fix_title"), t("crossref.fix_notfound"))
            return False
        self.main_window._push_workspace_undo(FileStateUndo(
            issue.source_file, prior,
            t("crossref.fix_undo", key=issue.ref_key, value=issue.ref_value)))
        self.main_window.workspace.rescan_working()
        self.main_window._reload_tab_if_open_and_unmodified(issue.source_file)
        self.statusBarMessage(t("crossref.fix_done", key=issue.ref_key,
                                value=issue.ref_value))
        return True

    def statusBarMessage(self, text: str):
        self.main_window.statusBar().showMessage(text)

    def _is_path_modified(self, path):
        return self.main_window._is_path_modified(path)

    def _propose_pda_poi_fix(self, issue: CrossRefIssue):
        """Fenetre de correction d'une cible POI de mission PDA inexistante
        (vecu 03/11/2026) : remplacer par un POI/GroupName existant du
        scenario (nom le plus proche preselectionne) ou retirer la cible de
        la liste Names. Retourne True (appliquee), False (voir sans
        corriger) ou None (ferme sans rien faire)."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
            QRadioButton, QPushButton,
        )
        from core.ecf.cross_reference_check import closest_dialogue_name
        from core.workspace_undo import FileStateUndo, capture_file

        pool_exact, _display = collect_pda_poi_pool(self.workspace.working_root)
        names = sorted(pool_exact)
        # la suggestion ne propose jamais la valeur cassee elle-meme
        suggestion = closest_dialogue_name(
            issue.ref_value, [n for n in names if n != issue.ref_value])

        if self._is_path_modified(issue.source_file):
            QMessageBox.warning(self, t("crossref.fix_title"),
                                t("crossref.fix_locked", name=issue.source_file.name))
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle(t("crossref.fix_title"))
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)

        explanation = QLabel(t("crossref.pda_fix_explain",
                               key=issue.ref_key, value=issue.ref_value,
                               block=issue.source_identity,
                               file=issue.source_file.name))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        replace_radio = QRadioButton(t("crossref.fix_replace"))
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(names)
        if suggestion:
            combo.setCurrentText(suggestion)
        combo.setEnabled(False)
        replace_radio.toggled.connect(combo.setEnabled)
        layout.addWidget(replace_radio)
        layout.addWidget(combo)

        remove_radio = QRadioButton(t("crossref.fix_remove", key=issue.ref_key))
        remove_radio.setChecked(suggestion is None)
        replace_radio.setChecked(suggestion is not None)
        layout.addWidget(remove_radio)

        implication = QLabel(t("crossref.pda_fix_implication_remove",
                               value=issue.ref_value, block=issue.source_identity))
        implication.setWordWrap(True)
        implication.setStyleSheet("color: gray;")
        layout.addWidget(implication)

        note = QLabel(t("crossref.fix_note", suggest=suggestion) if suggestion
                      else t("crossref.fix_note_none"))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)

        buttons = QHBoxLayout()
        btn_apply = QPushButton(t("crossref.fix_apply"))
        btn_apply.setObjectName("primaryButton")
        buttons.addWidget(btn_apply)
        btn_view = QPushButton(t("crossref.fix_view"))
        btn_view.setObjectName("secondaryButton")
        buttons.addWidget(btn_view)
        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

        outcome = {"applied": None}
        btn_apply.clicked.connect(lambda: outcome.__setitem__("applied", True)
                                  or dialog.accept())
        btn_view.clicked.connect(lambda: outcome.__setitem__("applied", False)
                                 or dialog.accept())
        btn_cancel.clicked.connect(lambda: outcome.__setitem__("applied", None)
                                   or dialog.reject())

        dialog.exec()
        if outcome["applied"] is None:
            return None
        if not outcome["applied"]:
            return False

        new_value = combo.currentText().strip() if replace_radio.isChecked() else None
        if replace_radio.isChecked() and not new_value:
            QMessageBox.warning(self, t("crossref.fix_title"), t("crossref.fix_empty"))
            return False
        try:
            prior = capture_file(issue.source_file)
            applied = apply_pda_poi_fix(
                issue.source_file, issue.source_identity,
                issue.ref_key, issue.ref_value, new_value)
        except Exception as e:
            QMessageBox.critical(self, t("err.title"),
                                 t("check.verification_error") + " : " + str(e))
            return False
        if not applied:
            QMessageBox.warning(self, t("crossref.fix_title"), t("crossref.fix_notfound"))
            return False
        self.main_window._push_workspace_undo(FileStateUndo(
            issue.source_file, prior,
            t("crossref.fix_undo", key=issue.ref_key, value=issue.ref_value)))
        self.main_window.workspace.rescan_working()
        self.main_window._reload_tab_if_open_and_unmodified(issue.source_file)
        if new_value is None:
            self.statusBarMessage(t("crossref.fix_done", key=issue.ref_key,
                                    value=issue.ref_value))
        else:
            self.statusBarMessage(t("crossref.pda_fix_done", key=issue.ref_key,
                                    new=new_value))
        return True

    def _navigate_to_issue(self, item: QListWidgetItem):
        """Ouvre (ou active) l'onglet du fichier concerne par ce resultat, puis
        navigue directement jusqu'au bloc/sous-bloc et, si possible, jusqu'a la
        cellule exacte -- evite d'avoir a chercher soi-meme ou se trouve le
        probleme signale, notamment pour les playfields ou plusieurs fichiers
        portent le meme nom (voir CrossRefIssue.display_path).

        VERIF-006 : pour une reference de dialogue cassee (Next/OptionNext),
        une fenetre de correction est proposee AVANT la navigation : nom le
        plus proche (typo probable), choix parmi les dialogues existants, ou
        suppression de la reference."""
        issue: CrossRefIssue = item.data(Qt.ItemDataRole.UserRole)
        if issue is None:
            return

        if issue.check_id == "dialogue_refs":
            applied = self._propose_dialogue_fix(issue)
            if applied is None:
                return  # ferme : ne rien faire
            if applied:
                self._do_run()  # la correction a ete ecrite : resultats frais
        elif issue.check_id == "pda_poi_refs":
            applied = self._propose_pda_poi_fix(issue)
            if applied is None:
                return  # ferme : ne rien faire
            if applied:
                self._do_run()  # la correction a ete ecrite : resultats frais

        widget = self.main_window.open_working_file_tab(issue.source_file)
        if widget is None:
            return

        # CompareWidget (fichiers .ecf) expose le vrai widget editable via
        # .edit_widget -- les autres types de fichiers sont directement le bon
        # widget (voir open_working_file_tab() dans main_window.py).
        edit_widget = getattr(widget, "edit_widget", widget)

        ext = issue.source_file.suffix.lower()
        if ext == ".ecf" and hasattr(edit_widget, "select_block_by_identity"):
            edit_widget.select_block_by_identity(
                issue.source_identity, prop_key=issue.ref_key, prop_value=issue.ref_value)
        elif ext in (".yaml", ".yml") and hasattr(edit_widget, "select_entry_by_key_value"):
            edit_widget.select_entry_by_key_value(issue.ref_key, issue.ref_value)


def _current_lang() -> str:
    from core import i18n
    return i18n.get_language()
