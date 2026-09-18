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
Assistant du moteur de traduction GROQ (LLM en ligne compatible OpenAI,
tier gratuit permanent) : creation de compte et de cle AVEC LIENS
CLIQUABLES (demande 18/09/2026), champ cle API, choix du modele, test reel.

SUIVRE LE MODELE de nllb_setup_dialog.py : simple (retour utilisateur :
Azure etait trop complique). La cle est stockee dans settings.json LOCAL
(jamais dans le depot) ; le texte a traduire part EN LIGNE chez Groq Inc.
(la case Options > Traduction en ligne autorise/bloque ce moteur).
"""
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from core import groq_provider, settings
from core.i18n import t
from gui.busy import busy_guard
from gui.theme import icon, icon_size


class GroqSetupDialog(QDialog):
    """Compte/cle Groq (liens cliquables), cle API, modele, activation et
    test reel du moteur."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("groq.title"))
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        intro = QLabel(t("groq.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Etapes avec LIENS CLIQUABLES (demande 18/09/2026)
        steps = QLabel(t("groq.step_account") + "<br>" + t("groq.step_key")
                       + "<br>" + t("groq.step_paste"))
        steps.setWordWrap(True)
        steps.setOpenExternalLinks(True)
        layout.addWidget(steps)

        key_row = QHBoxLayout()
        key_label = QLabel(t("groq.key_label"))
        key_row.addWidget(key_label)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setText(settings.get_groq_api_key())
        key_row.addWidget(self.key_edit, 1)
        btn_verify = QPushButton(icon("fa5s.check", "#ffffff"),
                                 t("groq.verify_btn"))
        btn_verify.setObjectName("secondaryButton")
        btn_verify.clicked.connect(self._verify)
        key_row.addWidget(btn_verify)
        layout.addLayout(key_row)

        self.verify_status = QLabel("")
        self.verify_status.setWordWrap(True)
        layout.addWidget(self.verify_status)

        model_row = QHBoxLayout()
        model_label = QLabel(t("groq.model_label"))
        model_row.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(groq_provider.KNOWN_MODELS)
        self.model_combo.setToolTip(t("groq.model_tip"))
        current = settings.get_groq_model()
        if self.model_combo.findText(current) < 0:
            self.model_combo.addItem(current)
        self.model_combo.setCurrentText(current)
        self.model_combo.currentTextChanged.connect(self._set_model)
        model_row.addWidget(self.model_combo, 1)
        layout.addLayout(model_row)

        # Style / ton (demande du backlog 18/09/2026) : consigne libre
        # injectee dans la consigne systeme de CHAQUE requete (fragments,
        # cellule entiere et lots). Vide = consigne par defaut.
        style_label = QLabel(t("groq.style_label"))
        layout.addWidget(style_label)
        self.style_edit = QPlainTextEdit()
        self.style_edit.setPlaceholderText(t("groq.style_placeholder"))
        self.style_edit.setToolTip(t("groq.style_tip"))
        self.style_edit.setPlainText(settings.get_groq_style())
        self.style_edit.setFixedHeight(56)
        self.style_edit.textChanged.connect(self._set_style)
        layout.addWidget(self.style_edit)

        self.use_check = QCheckBox(t("groq.use_as_engine"))
        self.use_check.toggled.connect(self._toggle_engine)
        layout.addWidget(self.use_check)

        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        layout.addWidget(self.test_result)

        row = QHBoxLayout()
        btn_test = QPushButton(icon("fa5s.check", "#ffffff"),
                               t("groq.test_btn"))
        btn_test.clicked.connect(self._test)
        row.addWidget(btn_test)
        row.addStretch()
        btn_close = QPushButton(t("btn.close"))
        btn_close.setObjectName("secondaryButton")
        btn_close.clicked.connect(self.close)
        row.addWidget(btn_close)
        layout.addLayout(row)

        self._refresh()

    def _refresh(self) -> None:
        configured = groq_provider.is_configured()
        self.use_check.blockSignals(True)
        self.use_check.setChecked(
            configured and settings.get_translation_engine() == "groq")
        self.use_check.blockSignals(False)
        if not configured:
            self.use_check.setEnabled(False)
            self.use_check.setToolTip(t("groq.need_key"))
        else:
            self.use_check.setEnabled(True)
            self.use_check.setToolTip("")

    def _notify_main(self) -> None:
        """Repercute la disponibilite/le modele sur la radio du menu
        principal (fenetre parente si presente)."""
        mw = self.parent()
        if mw is not None and hasattr(mw, "_refresh_engine_menu"):
            mw._refresh_engine_menu()

    def _verify(self) -> None:
        """Sauvegarde la cle saisie puis l'eprouve sur /models (appel reel
        legere) : remplit le combo avec les modeles texte du compte."""
        key = self.key_edit.text().strip()
        if not key:
            self.verify_status.setText(t("groq.need_key"))
            return
        settings.set_groq_api_key(key)
        try:
            with busy_guard(self, "groq.verifying"):
                models = groq_provider.list_models()
        except Exception as e:
            self.verify_status.setStyleSheet("color: #b02a2a;")
            self.verify_status.setText(t("groq.verify_fail", error=e))
            return
        self.verify_status.setStyleSheet("")
        self.verify_status.setText(t("groq.verify_ok", count=len(models)))
        self.model_combo.blockSignals(True)
        current = self.model_combo.currentText().strip()
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if current:
            if self.model_combo.findText(current) < 0:
                self.model_combo.addItem(current)
            self.model_combo.setCurrentText(current)
            self.model_combo.blockSignals(False)
        self._refresh()
        self._notify_main()

    def _set_model(self, model: str) -> None:
        model = (model or "").strip()
        if model:
            settings.set_groq_model(model)

    def _set_style(self) -> None:
        settings.set_groq_style(self.style_edit.toPlainText())

    def _toggle_engine(self, checked: bool) -> None:
        if checked and not groq_provider.is_configured():
            return
        from core import settings as s
        s.set_translation_engine("groq" if checked else "google")
        self._notify_main()

    def _test(self) -> None:
        """Test reel : persiste la cle saisie, traduit une phrase fixe."""
        settings.set_groq_api_key(self.key_edit.text().strip())
        self._refresh()
        self.test_result.setStyleSheet("color: gray;")
        self.test_result.setText(t("groq.testing"))
        try:
            with busy_guard(self, "groq.testing"):
                result = groq_provider.quick_check()
        except Exception as e:
            self.test_result.setStyleSheet("color: #b02a2a;")
            self.test_result.setText(t("groq.test_fail", error=e))
            return
        self.test_result.setStyleSheet("")
        self.test_result.setText(t("groq.test_ok", result=result))
