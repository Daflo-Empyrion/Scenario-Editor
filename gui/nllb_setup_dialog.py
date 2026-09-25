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
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QVBoxLayout,
)

from core import nllb_provider, settings, translation
from core.i18n import t
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
        self.resize(620, 560)
        from gui.window_geometry import track
        track(self, "nllb_setup")

        layout = QVBoxLayout(self)
        intro = QLabel(t("nllb.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.variant_labels = {}
        self.variant_radios = {}
        for variant, (label_key, tip_key) in _VARIANT_LABELS.items():
            row = QHBoxLayout()
            # Radio "utiliser celle-ci" (demande 17/09/2026) : le ✔ seul ne
            # disait pas quelle variante SERVIT -- le telechargement en
            # changeait sans rien afficher.
            radio = QRadioButton()
            radio.setToolTip(t("nllb.variant_use_tip"))
            radio.toggled.connect(
                lambda checked, v=variant: self._set_variant(v, checked))
            row.addWidget(radio)
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
            self.variant_radios[variant] = radio
            layout.addLayout(row)

        self.use_check = QCheckBox(t("nllb.use_as_engine"))
        self.use_check.toggled.connect(self._toggle_engine)
        layout.addWidget(self.use_check)

        # Finesse du decodage (demande 17/09/2026) : beam search
        # DETERMINISTE du decodeur NLLB -- pas de "temperature" (NLLB n'est
        # pas un generateur creatif ; le beam search est le mode recommande
        # pour la traduction). 2 rapide / 4 equilibre / 8 qualite.
        beam_row = QHBoxLayout()
        beam_label = QLabel(t("nllb.beam.label"))
        beam_row.addWidget(beam_label)
        self.beam_buttons = {}
        for size, key in ((2, "nllb.beam.fast"), (4, "nllb.beam.balanced"),
                          (8, "nllb.beam.quality")):
            rb = QRadioButton(t(key))
            rb.setToolTip(t("nllb.beam.tip"))
            rb.setChecked(settings.get_nllb_beam_size() == size)
            rb.toggled.connect(
                lambda checked, s=size: self._set_beam(s, checked))
            self.beam_buttons[size] = rb
            beam_row.addWidget(rb)
        beam_row.addStretch()
        layout.addLayout(beam_row)

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
        """Repeint l'etat installe de chaque variante, la radio de la variante
        ACTIVE (celle que la traduction utilise) et la case moteur."""
        for variant, (label, _btn) in self.variant_labels.items():
            installed = nllb_provider.is_installed(variant)
            mark = "✔ " if installed else ""
            label.setText(mark + t(_VARIANT_LABELS[variant][0]))
            _btn.setText(t("nllb.reinstall") if installed
                         else t("nllb.download_btn"))
            radio = self.variant_radios[variant]
            radio.setEnabled(installed)
            radio.blockSignals(True)
            radio.setChecked(settings.get_nllb_variant() == variant)
            radio.blockSignals(False)
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
            from gui.busy import run_long
            # telechargement de plusieurs Go : la gerbe plasma animee
            # remplace l'ancienne boite figee (23/09/2026)
            run_long(self, lambda: nllb_provider.download_and_install(variant),
                     "nllb.downloading")
            settings.set_nllb_variant(variant)
        finally:
            button.setEnabled(True)
        self._refresh()

    def _set_beam(self, size: int, checked: bool) -> None:
        """Persiste la finesse du decodage. Ne fait quelque chose que quand
        une radio se COCHE (toggled(False) est aussi emis pour celle qui se
        decoche -- persistervia ce signal ecraserait la valeur par l'ancienne
        radio selon l'ordre d'emission de Qt)."""
        if checked:
            settings.set_nllb_beam_size(size)

    def _set_variant(self, variant: str, checked: bool) -> None:
        """Radio « utiliser celle-ci » : sélectionne la variante que la
        traduction NLLB utilisera (les deux peuvent être installées). Ne fait
        quelque chose que quand une radio se COCHE (même piège toggled(False)
        que _set_beam)."""
        if checked and nllb_provider.is_installed(variant):
            settings.set_nllb_variant(variant)

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
