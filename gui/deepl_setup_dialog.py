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
Assistant du moteur de traduction DEEPL (plan "DeepL API FREE" : 500 000
caracteres/mois, sans carte bancaire) -- SUIVRE LE MODELE de
groq_setup_dialog.py : liens cliquables, cle masquee, verification REELLE
via /v2/usage (retourne aussi le quota consomme), test de traduction,
case moteur principal. La cle est stockee dans settings.json LOCAL
(jamais dans le depot) ; le texte part chez DeepL SE (soumis a la case
"Traduction en ligne").
"""
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

from core import deepl_provider, settings
from core.i18n import t
from gui.busy import busy_guard
from gui.theme import icon


class DeepLSetupDialog(QDialog):
    """Compte/cle DeepL (liens cliquables), verification reelle + quota
    consomme, test de traduction, activation comme moteur."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("deepl.title"))
        self.setMinimumWidth(600)
        self.resize(640, 580)
        from gui.window_geometry import track
        track(self, "deepl_setup")

        layout = QVBoxLayout(self)
        intro = QLabel(t("deepl.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Etapes avec LIENS CLIQUABLES (meme motif que l'assistant Groq)
        steps = QLabel(t("deepl.step_account") + "<br>" + t("deepl.step_key")
                       + "<br>" + t("deepl.step_paste"))
        steps.setWordWrap(True)
        steps.setOpenExternalLinks(True)
        layout.addWidget(steps)

        key_row = QHBoxLayout()
        key_label = QLabel(t("deepl.key_label"))
        key_row.addWidget(key_label)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setText(settings.get_deepl_api_key())
        key_row.addWidget(self.key_edit, 1)
        btn_verify = QPushButton(icon("fa5s.check", "#ffffff"),
                                 t("deepl.verify_btn"))
        btn_verify.setObjectName("secondaryButton")
        btn_verify.clicked.connect(self._verify)
        key_row.addWidget(btn_verify)
        layout.addLayout(key_row)

        self.verify_status = QLabel("")
        self.verify_status.setWordWrap(True)
        layout.addWidget(self.verify_status)

        self.use_check = QCheckBox(t("deepl.use_as_engine"))
        self.use_check.toggled.connect(self._toggle_engine)
        layout.addWidget(self.use_check)

        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        layout.addWidget(self.test_result)

        row = QHBoxLayout()
        btn_test = QPushButton(icon("fa5s.check", "#ffffff"),
                               t("deepl.test_btn"))
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
        configured = deepl_provider.is_configured()
        self.use_check.blockSignals(True)
        self.use_check.setChecked(
            configured and settings.get_translation_engine() == "deepl")
        self.use_check.blockSignals(False)
        if not configured:
            self.use_check.setEnabled(False)
            self.use_check.setToolTip(t("deepl.need_key"))
        else:
            self.use_check.setEnabled(True)
            self.use_check.setToolTip("")

    def _notify_main(self) -> None:
        mw = self.parent()
        if mw is not None and hasattr(mw, "_refresh_engine_menu"):
            mw._refresh_engine_menu()

    def _verify(self) -> None:
        """Sauvegarde la cle puis l'eprouve sur /v2/usage (appel reel
        legere) : affiche aussi le quota du mois consomme."""
        key = self.key_edit.text().strip()
        if not key:
            self.verify_status.setText(t("deepl.need_key"))
            return
        settings.set_deepl_api_key(key)
        try:
            with busy_guard(self, "deepl.verifying"):
                usage = _fetch_usage()
        except Exception as e:
            self.verify_status.setStyleSheet("color: #b02a2a;")
            self.verify_status.setText(t("deepl.verify_fail", error=e))
            return
        self.verify_status.setStyleSheet("")
        self.verify_status.setText(t(
            "deepl.verify_ok",
            used=usage.get("character_count", "?"),
            limit=usage.get("character_limit", "?")))
        self._refresh()
        self._notify_main()

    def _toggle_engine(self, checked: bool) -> None:
        if checked and not deepl_provider.is_configured():
            return
        from core import settings as s
        s.set_translation_engine("deepl" if checked else "google")
        self._notify_main()

    def _test(self) -> None:
        """Test reel : persiste la cle saisie, traduit une phrase fixe."""
        settings.set_deepl_api_key(self.key_edit.text().strip())
        self._refresh()
        self.test_result.setStyleSheet("color: gray;")
        self.test_result.setText(t("deepl.testing"))
        try:
            with busy_guard(self, "deepl.testing"):
                result = deepl_provider.quick_check()
        except Exception as e:
            self.test_result.setStyleSheet("color: #b02a2a;")
            self.test_result.setText(t("deepl.test_fail", error=e))
            return
        self.test_result.setStyleSheet("")
        self.test_result.setText(t("deepl.test_ok", result=result))


def _fetch_usage() -> dict:
    """GET /v2/usage (API officielle DeepL) : character_count /
    character_limit du mois -- leve une Exception (typee) si la cle est
    mauvaise : AuthError, meme semantique que le provider."""
    import json
    import urllib.error
    import urllib.request
    from core.engine_errors import AuthError, EngineUnavailableError
    req = urllib.request.Request(
        deepl_provider.BASE_FREE + "/usage",
        headers={"Authorization": f"DeepL-Auth-Key {settings.get_deepl_api_key()}",
                 "User-Agent": "EmpyrionScenarioEditor"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise AuthError(t("deepl.bad_key"))
        raise EngineUnavailableError(f"Erreur DeepL {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise EngineUnavailableError(f"Reseau indisponible pour DeepL : {e}")
