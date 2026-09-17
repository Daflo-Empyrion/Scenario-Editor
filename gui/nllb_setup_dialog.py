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
Assistant du moteur de traduction local NLLB (Meta, via CTranslate2) --
qualite nettement superieure aux modeles Argos sur l'anglais familier,
100 % local (aucun texte ne quitte le poste).

Concu SIMPLE (retour utilisateur : Azure etait trop complique) : deux
boutons de telechargement (600M rapide ~630 Mo / 1.3B qualite ~1,4 Go),
case « utiliser comme moteur », bouton Tester. Le telechargement se fait
depuis les depots publics HuggingFace vers ~/.empyrion_editor/nllb-<v>
(personnalisable/remplacable par l'utilisateur a la main).

INFERENCE CPU uniquement (CTranslate2 n'acceleere pas les GPU AMD ; une
voie ONNX/DirectML pour GPU AMD est envisagee en v2). LICENCE : les poids
NLLB sont CC-BY-NC 4.0 -- usage NON commercial (ok pour des scenarios
gratuits).
"""
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from core import nllb_provider, settings, translation
from core.i18n import t
from gui.busy import busy_guard
from gui.theme import icon, icon_size

_VARIANT_LABELS = {
    "600M": ("nllb.v600m.label", "nllb.v600m.tip"),
    "1.3B": ("nllb.v13b.label", "nllb.v13b.tip"),
}


class NllbSetupDialog(QDialog):
    """Installation des variantes NLLB + activation du moteur + test."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("nllb.title"))
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        intro = QLabel(t("nllb.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.variant_labels = {}
        for variant, (label_key, tip_key) in _VARIANT_LABELS.items():
            row = QHBoxLayout()
            label = QLabel()
            label.setToolTip(t(tip_key))
            label.setWordWrap(True)
            row.addWidget(label, 1)
            btn = QPushButton()
            btn.setObjectName("secondaryButton")
            btn.clicked.connect(
                lambda _checked=False, v=variant, b=btn: self._download(v, b))
            row.addWidget(btn)
            self.variant_labels[variant] = (label, btn)
            layout.addLayout(row)

        self.use_check = QCheckBox(t("nllb.use_as_engine"))
        self.use_check.toggled.connect(self._toggle_engine)
        layout.addWidget(self.use_check)

        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        layout.addWidget(self.test_result)

        row = QHBoxLayout()
        btn_test = QPushButton(icon("fa5s.check", "#ffffff"), t("nllb.test_btn"))
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
        """Repeint l'etat installe de chaque variante + la case moteur."""
        for variant, (label, _btn) in self.variant_labels.items():
            installed = nllb_provider.is_installed(variant)
            mark = "✔ " if installed else ""
            label.setText(mark + t(_VARIANT_LABELS[variant][0]))
            _btn.setText(t("nllb.reinstall") if installed
                         else t("nllb.download_btn"))
        any_installed = any(nllb_provider.is_installed(v) for v in _VARIANT_LABELS)
        self.use_check.setEnabled(any_installed)
        self.use_check.blockSignals(True)
        self.use_check.setChecked(
            any_installed and settings.get_translation_engine() == "nllb")
        self.use_check.blockSignals(False)
        if not any_installed:
            self.use_check.setToolTip(t("nllb.need_model"))
        else:
            self.use_check.setToolTip("")

    def _download(self, variant: str, button: QPushButton) -> None:
        button.setEnabled(False)
        try:
            with busy_guard(self, "nllb.downloading"):
                nllb_provider.download_and_install(variant)
            settings.set_nllb_variant(variant)
        finally:
            button.setEnabled(True)
        self._refresh()

    def _toggle_engine(self, checked: bool) -> None:
        # activer NLLB impose une variante installee : prendre la plus lourde
        # disponible (qualite) si la variante activee n'est pas installee
        if checked and not nllb_provider.is_installed(
                settings.get_nllb_variant()):
            for variant in ("1.3B", "600M"):
                if nllb_provider.is_installed(variant):
                    settings.set_nllb_variant(variant)
                    break
        from core.settings import set_translation_engine
        set_translation_engine("nllb" if checked else "google")
        self._refresh()

    def _test(self) -> None:
        if settings.get_translation_engine() != "nllb":
            self.use_check.setChecked(True)
        try:
            out = translation.translate_text(
                "It was only supposed to be a short jaunt.", target="fr",
                store_in_memory=False)
            self.test_result.setText(t("nllb.test_ok", result=out))
        except Exception as e:
            self.test_result.setText(t("nllb.test_fail", error=e))
