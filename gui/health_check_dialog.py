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
Tableau de bord "bilan de sante" du scenario -- lance en un clic les 4
verifications existantes (references, regles metier, blocs en attente,
jetons non utilises) et affiche un resume consolide, avec un bouton par
categorie pour ouvrir la VRAIE fenetre correspondante en cas de probleme
trouve. Ne reimplemente aucun affichage detaille -- reutilise entierement
les fenetres deja construites (CrossReferenceDialog, ValidationDialog,
OrphanDialog, check_pending_conflicts_dialog), pour eviter toute divergence
entre le resume et le detail.

Fenetre NON MODALE (meme motif que les autres verifications)."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QWidget,
)

from gui.busy import busy_guard
from core.i18n import t
from gui.theme import icon, icon_size


class _CategoryRow(QWidget):
    """Une ligne du tableau de bord : nom de categorie, resume, bouton de
    detail (actif seulement si des problemes ont ete trouves)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel(f"<b>{title}</b>")
        self.title_label.setMinimumWidth(220)
        layout.addWidget(self.title_label)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label, 1)

        self.btn_detail = QPushButton(t("health.btn_view_detail"))
        self.btn_detail.setObjectName("secondaryButton")
        self.btn_detail.setEnabled(False)
        layout.addWidget(self.btn_detail)

    def set_result(self, ok: bool, summary_text: str, on_click):
        if ok:
            self.status_label.setText(f"<span style='color:#2e7d32'>✓ {summary_text}</span>")
            self.btn_detail.setEnabled(False)
        else:
            self.status_label.setText(f"<span style='color:#c62828'>{summary_text}</span>")
            self.btn_detail.setEnabled(True)
        try:
            self.btn_detail.clicked.disconnect()
        except TypeError:
            pass  # rien de connecte encore (premier appel)
        self.btn_detail.clicked.connect(on_click)


class HealthCheckDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.workspace = main_window.workspace
        self.setWindowTitle(t("verification.center_title"))
        self.setMinimumSize(620, 340)

        layout = QVBoxLayout(self)
        intro = QLabel(t("health.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        box = QGroupBox()
        box_layout = QVBoxLayout(box)
        self.row_refs = _CategoryRow(t("health.category_refs"))
        box_layout.addWidget(self.row_refs)
        self.row_validation = _CategoryRow(t("health.category_validation"))
        box_layout.addWidget(self.row_validation)
        self.row_pending = _CategoryRow(t("health.category_pending"))
        box_layout.addWidget(self.row_pending)
        self.row_orphans = _CategoryRow(t("health.category_orphans"))
        box_layout.addWidget(self.row_orphans)
        layout.addWidget(box)

        layout.addStretch()

        bottom_row = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        bottom_row.addWidget(self.summary_label)
        bottom_row.addStretch()

        # "Tout verifier" : le refresh() de CE dialogue relance bien les
        # 5 familles de verification (P4 -- audit du 30/08/2026), le libelle
        # doit le dire plutot que "Actualiser".
        btn_refresh = QPushButton(icon("fa5s.sync-alt", "#4a7dfc"), t("health.check_all"))
        btn_refresh.setIconSize(icon_size())
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self.refresh)
        bottom_row.addWidget(btn_refresh)

        btn_close = QPushButton(t("validation.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

        self.refresh()

    def _ecf_files(self):
        return [f.path for f in self.workspace.working.configuration if f.extension == '.ecf']

    def refresh(self):
        # Retour utilisateur 30/08/2026 : "Tout verifier" peut prendre du
        # temps -- curseur + boite "en cours" modale a la fenetre.
        with busy_guard(self):
            self._refresh_all_checks()

    def _refresh_all_checks(self):
        total_problems = 0

        # --- References (les 4 verifications de cross_reference_check.py,
        # heritage Ref inclus -- meme regroupement que le bouton "Verifier les
        # references croisees", pour ne jamais compter deux fois la meme chose
        # separement du menu "Verifier les references" seul) ---
        from core.ecf.cross_reference_check import CrossRefContext, run_checks, CROSS_REFERENCE_CHECKS
        ctx = CrossRefContext(ecf_files=self._ecf_files(), yaml_files=[],
                               scenario_root=self.workspace.working_root)
        ref_issues = run_checks(ctx, [c.id for c in CROSS_REFERENCE_CHECKS])
        ok = len(ref_issues) == 0
        total_problems += len(ref_issues)
        self.row_refs.set_result(
            ok, t("health.all_ok") if ok else t("health.n_issues", n=len(ref_issues)),
            self.main_window.check_cross_references_dialog)

        # --- Regles metier (validation.py) ---
        from core.ecf.validation import validate_scenario
        by_file = validate_scenario(self.workspace.working_root)
        validation_count = sum(len(issues) for issues in by_file.values())
        ok = validation_count == 0
        total_problems += validation_count
        self.row_validation.set_result(
            ok, t("health.all_ok") if ok else t("health.n_issues", n=validation_count),
            self.main_window.validate_scenario_dialog)

        # --- Blocs en attente ---
        from core.ecf.pending_conflicts import find_pending_conflicts
        from core.ecf.parser import parse_ecf_file
        pending_count = 0
        for path in self._ecf_files():
            try:
                doc = parse_ecf_file(path)
            except Exception:
                continue
            pending_count += len(find_pending_conflicts(doc))
        ok = pending_count == 0
        total_problems += pending_count
        self.row_pending.set_result(
            ok, t("health.all_ok") if ok else t("health.n_issues", n=pending_count),
            self.main_window.check_pending_conflicts_dialog)

        # --- Jetons non utilises (informatif -- ne compte pas dans le total
        # de "problemes", coherent avec orphan_check.py qui n'est jamais une
        # erreur) ---
        from core.ecf.orphan_check import find_unused_tokens
        unused = find_unused_tokens(self._ecf_files())
        ok = len(unused) == 0
        self.row_orphans.set_result(
            ok, t("health.all_ok") if ok else t("health.n_issues", n=len(unused)),
            self.main_window._open_orphan_dialog)

        if total_problems == 0:
            self.summary_label.setText(t("health.overall_ok"))
        else:
            self.summary_label.setText(t("health.overall_problems", n=total_problems))
