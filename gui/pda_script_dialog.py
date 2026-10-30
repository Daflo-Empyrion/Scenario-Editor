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

"""Scripts de gameplay (PDA) : choix d'un modele, parametres (listes
deroulantes EDITABLES : vocabulaire officiel du moteur + POIs reels du
scenario), APERCU MODIFIABLE du C# genere, verification de compilation
reelle (csc + assemblies du jeu) et ecriture dans Extras/PDA/Scripts/.
Moteur : core/pda/script_gen.py."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton,
                             QVBoxLayout, QWidget)

from core.i18n import t
from core.pda.script_gen import (TEMPLATES, VOCABULAIRE, build,
                                 compile_scripts, write_script)
from gui.ewa_async import async_call
from gui.msgboxes import ask_yes_no, info
from gui.window_geometry import track


def _poi_names(content_root: Path) -> list:
    """POIs du scenario : noms referenceables des prefabs (.epb). Le
    playfield/PDA reference le Name INTERNE de l'en-tete OU le nom de
    fichier (les deux different souvent — 89 % sur RE2 : fichier
    'Anvil_CV_ColYardWreck1' = Name 'Eden_ColSpaceYardWreck') — les deux
    sont proposes, dedoublonnes tries."""
    from core.epb_blueprint import read_header
    for prefabs in (content_root / "Prefabs", content_root / "Content" / "Prefabs"):
        if not prefabs.is_dir():
            continue
        names: set = set()
        for path in prefabs.rglob("*.epb"):
            names.add(path.stem)
            header = read_header(path)
            if header and header[0]:
                names.add(header[0])
        return sorted(names)
    return []


def _vanilla_content_dir() -> Path | None:
    """Dossier Content de l'installation du jeu (reglages), pour enrichir
    les pools de POIs avec la vanille."""
    from core.settings import get_vanilla_content_path
    raw = get_vanilla_content_path()
    path = Path(raw) if raw else None
    return path if path and path.is_dir() else None


class PdaScriptDialog(QDialog):
    def __init__(self, parent, working_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("pdas.title"))
        self._running = False
        self._edits = {}
        self._poi_cache: list | None = None
        self._poi_loading = False

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("yamlcheck.scenario")))
        self.path_edit = QLineEdit(working_root)
        self.path_edit.setPlaceholderText(t("yamlcheck.scenario_hint"))
        row.addWidget(self.path_edit, 1)
        self.btn_browse = QPushButton(t("yamlcheck.browse"))
        self.btn_browse.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_browse)
        lay.addLayout(row)

        top = QHBoxLayout()
        top.addWidget(QLabel(t("pdas.template")))
        self.cmb_template = QComboBox()
        for template in TEMPLATES.values():
            self.cmb_template.addItem(t(template.label_key), template.template_id)
        self.cmb_template.currentIndexChanged.connect(self._template_changed)
        top.addWidget(self.cmb_template, 1)
        top.addWidget(QLabel(t("pdas.file_name")))
        self.edit_file = QLineEdit("MissionScript")
        self.edit_file.setMaximumWidth(220)
        top.addWidget(self.edit_file)
        lay.addLayout(top)

        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        lay.addWidget(self.desc_label)

        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        lay.addWidget(self.form_host)

        lay.addWidget(QLabel(t("pdas.preview_label")))
        self.preview = QPlainTextEdit()
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.preview, 1)

        buttons = QHBoxLayout()
        self.btn_build = QPushButton(t("pdas.build"))
        self.btn_build.clicked.connect(self._rebuild)
        buttons.addWidget(self.btn_build)
        self.btn_check = QPushButton(t("pdas.check"))
        self.btn_check.clicked.connect(self._check)
        buttons.addWidget(self.btn_check)
        buttons.addStretch(1)
        self.btn_write = QPushButton(t("pdas.write"))
        self.btn_write.clicked.connect(self._write)
        buttons.addWidget(self.btn_write)
        lay.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        track(self, "pda_scripts", (1000, 760))
        self._template_changed()

    # ------------------------------------------------------------ widgets

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("yamlcheck.scenario"), self.path_edit.text() or ".")
        if path:
            self.path_edit.setText(path)

    def _template_changed(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        template = TEMPLATES[self.cmb_template.currentData()]
        self.desc_label.setText(t(template.desc_key))
        self._edits = {}
        for spec in template.params:
            if spec.choices:
                edit = self._make_choice_edit(spec)
            else:
                edit = QLineEdit(spec.default)
            self._edits[spec.key] = edit
            self.form.addRow(t(spec.label_key), edit)
        self.edit_file.setText(template.params[0].default)
        self._rebuild()

    def _make_choice_edit(self, spec) -> QComboBox:
        """Liste deroulante EDITABLE : le vocabulaire du moteur en premier,
        les POIs du scenario ensuite ; la saisie libre reste possible
        (editable) — meme discipline que les combos du module PDA."""
        combo = QComboBox()
        combo.setEditable(True)
        values = list(VOCABULAIRE.get(spec.choices, ()))
        if spec.choices == "poi":
            values += self._scenario_poi_names()
        seen = set()
        for value in values:
            if value not in seen:
                combo.addItem(value)
                seen.add(value)
        combo.setCurrentText(spec.default)
        return combo

    def _scenario_poi_names(self) -> list:
        """POIs du scenario : lecture des en-tetes .epb HORS THREAD GUI
        (5802 prefabs sur RE2 = ~17 s au premier appel, cache ensuite).
        Tant que la lecture court, la combo reste sur sa valeur par defaut
        (editable : l'utilisateur peut deja saisir) et se remplit a l'arrivee."""
        if self._poi_cache is not None:
            return self._poi_cache
        if self._poi_loading:
            return []
        self._poi_loading = True
        root = Path(self.path_edit.text().strip())
        vanilla = _vanilla_content_dir()

        def work():
            names = _poi_names(root) if root.is_dir() else []
            if vanilla is not None:
                known = set(names)
                names += [n for n in _poi_names(vanilla) if n not in known]
            return names

        async_call(self, work, on_done=self._poi_names_ready,
                   on_fail=lambda _exc: None, name="pda-script-pois")
        return []

    def _poi_names_ready(self, names: list):
        self._poi_cache = names
        self._poi_loading = False
        # rafraichit les combos POI deja construites sans ecraser la saisie
        template = TEMPLATES[self.cmb_template.currentData()]
        for spec in template.params:
            if spec.choices != "poi":
                continue
            combo = self._edits.get(spec.key)
            if not isinstance(combo, QComboBox):
                continue
            current = combo.currentText()
            combo.clear()
            combo.addItem(VOCABULAIRE["poi"][0] if VOCABULAIRE["poi"] else current)
            for name in names:
                combo.addItem(name)
            combo.setCurrentText(current)

    def _params(self) -> dict:
        return {key: (edit.currentText() if isinstance(edit, QComboBox)
                      else edit.text())
                for key, edit in self._edits.items()}

    def _rebuild(self):
        text = build(self.cmb_template.currentData(), self._params())
        self.preview.setPlainText(text)
        self.status_label.setText(t("pdas.generated", n=len(text.splitlines())))

    # ------------------------------------------------------------- actions

    def _check(self):
        if self._running:
            return
        text = self.preview.toPlainText()
        if not text.strip():
            self.status_label.setText(t("pdas.empty"))
            return
        self._running = True
        self.btn_check.setEnabled(False)
        self.status_label.setText(t("pdas.checking"))
        tmp = Path(tempfile.mkdtemp())
        target = tmp / f"{self.edit_file.text().strip() or 'Script'}.cs"
        target.write_text(text, encoding="utf-8")

        def work():
            return compile_scripts([target], out_dir=tmp)

        async_call(self, work, on_done=self._checked,
                   on_fail=self._failed, name="pda-script-check")

    def _checked(self, result):
        self._running = False
        self.btn_check.setEnabled(True)
        if result.skipped:
            self.status_label.setText(t("pdas.skipped", reason=result.skipped))
        elif result.ok:
            self.status_label.setText(t("pdas.check_ok"))
        else:
            first = result.output.splitlines()[0] if result.output else ""
            self.status_label.setText(t("pdas.check_failed", diag=first))

    def _failed(self, exc: Exception):
        self._running = False
        self.btn_check.setEnabled(True)
        self.status_label.setText(f"{t('yamlcheck.failed')}  ({exc})")

    def _write(self):
        root = self.path_edit.text().strip()
        if not root:
            self.status_label.setText(t("yamlcheck.need_scenario"))
            return
        name = self.edit_file.text().strip()
        if not name:
            self.status_label.setText(t("pdas.empty"))
            return
        text = self.preview.toPlainText()
        try:
            path = write_script(Path(root), name, text)
        except FileExistsError as exc:
            if not ask_yes_no(self, t("pdas.title"),
                              t("pdas.overwrite", name=str(exc))):
                return
            path = write_script(Path(root), name, text, overwrite=True)
        except Exception as exc:                  # noqa: BLE001 - remonte a l'UI
            info(self, t("pdas.title"), str(exc))
            return
        info(self, t("pdas.title"), t("pdas.written", path=str(path)))
        self._check()
