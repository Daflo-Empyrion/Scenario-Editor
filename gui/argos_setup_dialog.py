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

"""Assistant d'installation de la traduction hors ligne Argos Translate
(demande du 10/09/2026). Trois etapes dans un seul dialogue :

  1. MOTEUR      : detection automatique (import), sinon installation pip
                   automatique avec la TAILLE EXACTE lue de PyPI, journal de
                   pip streamE en direct + barre de progression ; repli =
                   commande console a copier + bouton "Verifier".
  2. MODELES     : paires de langues de l'index officiel affichees
                   IMMEDIATEMENT (retour utilisateur du 10/09/2026 : la page
                   restait vide pendant la mesure des tailles) ; chaque
                   taille reelle arrive en tache de fond item par item ; les
                   mises a jour d'UI passent par des SIGNAUX Qt (jamais par
                   des widgets depuis le thread de fond).
  3. IMPORT      : .argosmodel local (ex bundle torrent) installable ici.
"""
import queue
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QProgressBar, QPlainTextEdit, QCheckBox, QFileDialog,
    QStackedWidget, QWidget,
)

from core import argos_provider
from core.i18n import t


class _Signals(QObject):
    models_ready = pyqtSignal(list, set)      # paires (taille 0), installees
    model_size = pyqtSignal(str, int)         # lien, octets
    engine_done = pyqtSignal(bool)
    models_done = pyqtSignal(int)


class ArgosSetupDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle(t("argos.title"))
        self.resize(700, 560)
        self.signals = _Signals()
        self.signals.models_ready.connect(self._fill_models)
        self.signals.model_size.connect(self._update_model_size)
        self.signals.engine_done.connect(self._after_engine_install)
        self.signals.models_done.connect(self._after_models)
        self._log_queue = queue.Queue()
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._drain_log)
        self._timer.start()
        self._link_by_row = {}
        self._build_ui()
        self._refresh_engine_state(auto=True)

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        layout.addWidget(self._build_log_box())

        # --- page 0 : moteur ---
        page = QVBoxLayout()
        self.engine_status = QLabel("")
        self.engine_status.setWordWrap(True)
        page.addWidget(self.engine_status)
        self.engine_size_label = QLabel("")
        self.engine_size_label.setObjectName("mutedLabel")
        self.engine_size_label.setWordWrap(True)
        page.addWidget(self.engine_size_label)
        self.engine_progress = QProgressBar()
        self.engine_progress.setRange(0, 0)  # indeterminee : pip stream lui-meme
        self.engine_progress.setVisible(False)
        page.addWidget(self.engine_progress)
        self.btn_install_engine = QPushButton(t("argos.install_engine"))
        self.btn_install_engine.clicked.connect(self._install_engine)
        page.addWidget(self.btn_install_engine)
        self.console_cmd = QPlainTextEdit()
        self.console_cmd.setReadOnly(True)
        self.console_cmd.setMaximumHeight(60)
        self.console_cmd.setVisible(False)
        page.addWidget(self.console_cmd)
        self.btn_verify = QPushButton(t("argos.verify"))
        self.btn_verify.clicked.connect(lambda: self._refresh_engine_state(auto=False))
        self.btn_verify.setVisible(False)
        page.addWidget(self.btn_verify)
        self.stack.addWidget(self._wrap(page))

        # --- page 1 : modeles ---
        page = QVBoxLayout()
        self.models_status = QLabel(t("argos.loading_models"))
        self.models_status.setWordWrap(True)
        page.addWidget(self.models_status)
        self.models_list = QListWidget()
        page.addWidget(self.models_list, 1)
        self.models_progress = QProgressBar()
        self.models_progress.setVisible(False)
        page.addWidget(self.models_progress)
        row = QHBoxLayout()
        self.btn_import = QPushButton(t("argos.import_model"))
        self.btn_import.clicked.connect(self._import_model)
        self.btn_download = QPushButton(t("argos.download_install"))
        self.btn_download.setObjectName("primaryButton")
        self.btn_download.clicked.connect(self._download_checked)
        row.addWidget(self.btn_import)
        row.addWidget(self.btn_download)
        page.addLayout(row)

        # ACTIVATION (retour utilisateur du 10/09/2026 : le reglage existait
        # mais aucune UI pour le piloter) : case cochee = Argos devient LE
        # moteur de traduction de l'application (glossaire, traducteur
        # integre...). Grisee tant qu'aucune paire n'est installee.
        from core.settings import get_translation_engine
        self.use_argos_check = QCheckBox(t("argos.use_as_engine"))
        self.use_argos_check.setToolTip(t("argos.use_as_engine_tip"))
        self.use_argos_check.setChecked(get_translation_engine() == "argos")
        self.use_argos_check.setEnabled(False)  # active apres le chargement
        self.use_argos_check.toggled.connect(self._toggle_argos_engine)
        page.addWidget(self.use_argos_check)
        self.engine_state_label = QLabel("")
        self.engine_state_label.setWordWrap(True)
        page.addWidget(self.engine_state_label)
        self.stack.addWidget(self._wrap(page))

    def _wrap(self, layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _build_log_box(self) -> QPlainTextEdit:
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        self.log_box.setPlaceholderText(t("argos.log"))
        return self.log_box

    def _log(self, msg: str):
        self._log_queue.put(msg)

    def _drain_log(self):
        shown = False
        while True:
            try:
                msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_box.appendPlainText(msg)
            shown = True
        if shown:
            self.log_box.verticalScrollBar().setValue(
                self.log_box.verticalScrollBar().maximum())

    # ------------------------------------------------------------ etape 1

    def _refresh_engine_state(self, auto: bool = False):
        if argos_provider.is_engine_available():
            self.stack.setCurrentIndex(1)
            self._load_models()
            return
        self.stack.setCurrentIndex(0)
        if getattr(sys, "frozen", False):
            # Version installee : pip n'existe pas dans un exe gelee et la
            # bibliotheque n'y est pas embarquee (decision a) -- l'option
            # hors ligne est disponible dans la version sources.
            self.engine_status.setText(t("argos.frozen_msg"))
            self.btn_install_engine.setVisible(False)
            return
        self.engine_status.setText(t("argos.engine_missing"))
        if auto:
            from threading import Thread
            def probe():
                size = argos_provider.estimate_engine_download_bytes()
                if size:
                    self._log(t("argos.engine_size", mb=size // (1024 * 1024)))
            Thread(target=probe, daemon=True).start()

    def _install_engine(self):
        self.btn_install_engine.setEnabled(False)
        self.engine_progress.setVisible(True)
        self.btn_verify.setVisible(True)
        self.console_cmd.setVisible(True)
        self.console_cmd.setPlainText(argos_provider.pip_console_command())
        self.engine_status.setText(t("argos.installing"))

        from threading import Thread
        def run():
            ok = argos_provider.install_engine(progress_cb=self._log)
            self.signals.engine_done.emit(ok)
        Thread(target=run, daemon=True).start()

    def _after_engine_install(self, ok: bool):
        self.engine_progress.setVisible(False)
        self.btn_install_engine.setEnabled(True)
        if ok:
            self.stack.setCurrentIndex(1)
            self._load_models()
        else:
            self.engine_status.setText(t("argos.engine_failed"))

    # ------------------------------------------------------------ etape 2

    def _load_models(self):
        self.models_list.clear()
        self._link_by_row.clear()
        self.models_status.setText(t("argos.loading_models"))
        from threading import Thread
        def run():
            try:
                pairs = argos_provider.available_pairs()
            except Exception as e:
                self._log(f"index : {e}")
                self.models_status.setText(t("argos.index_error"))
                return
            installed = argos_provider.installed_pair_codes()
            self.signals.models_ready.emit(pairs, installed)
            # les tailles reelles arrivent APRES, une requete HEAD par modele,
            # jamais avant l'affichage de la liste (retour du 10/09/2026)
            for p in pairs:
                try:
                    size = argos_provider.url_size_bytes(p["link"])
                except Exception:
                    size = 0
                self.signals.model_size.emit(p["link"], size)
        Thread(target=run, daemon=True).start()

    def _fill_models(self, pairs, installed):
        self.models_list.clear()
        self._link_by_row.clear()
        # la case d'activation devient manipulable : au moins une paire peut
        # etre installee (et la detection du moteur a deja reussi pour etre ici)
        self.use_argos_check.setEnabled(len(installed) > 0)
        self._refresh_engine_state_label()
        for p in pairs:
            item = QListWidgetItem(
                f"{p['from_name']} -> {p['to_name']} "
                f"({t('argos.size_pending')})")
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            pair_codes = (p["from_code"], p["to_code"])
            checked = pair_codes in {("en", "fr"), ("fr", "en")} \
                or pair_codes in installed
            item.setCheckState(Qt.CheckState.Checked if checked
                               else Qt.CheckState.Unchecked)
            if pair_codes in installed:
                item.setText(item.text() + f" — {t('argos.installed')}")
            self._link_by_row[self.models_list.count()] = p["link"]
            self.models_list.addItem(item)
        self.models_status.setText(t("argos.pick_models_hint"))

    def _refresh_engine_state_label(self):
        from core.settings import get_translation_engine
        if len(argos_provider.installed_pair_codes()) == 0:
            self.engine_state_label.setText(t("argos.engine_state_none"))
        elif get_translation_engine() == "argos":
            self.engine_state_label.setText(t("argos.engine_state_argos"))
        else:
            self.engine_state_label.setText(t("argos.engine_state_google"))

    def _toggle_argos_engine(self, checked: bool):
        """(De)active Argos comme moteur de traduction de l'application."""
        from core.settings import set_translation_engine
        set_translation_engine("argos" if checked else "google")
        self._refresh_engine_state_label()
        mw = self.main_window
        if mw is not None and hasattr(mw, "_refresh_argos_menu_action"):
            mw._refresh_argos_menu_action()
            mw.statusBar().showMessage(
                t("argos.engine_switched",
                  engine=t("argos.engine_name_argos" if checked
                           else "argos.engine_name_google")), 8000)

    def _update_model_size(self, link: str, size: int):
        row = self._link_by_row.get(link)
        if row is None or size <= 0:
            return
        item = self.models_list.item(row)
        if item is None:
            return
        item.setText(item.text().replace(t("argos.size_pending"),
                                         f"{size / (1024 * 1024):.0f} Mo"))

    def _download_checked(self):
        jobs = []
        for i in range(self.models_list.count()):
            item = self.models_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                jobs.append(item.data(Qt.ItemDataRole.UserRole))
        if not jobs:
            return
        self.btn_download.setEnabled(False)
        self.models_progress.setVisible(True)
        self.models_progress.setRange(0, len(jobs) * 100)
        from threading import Thread
        def run():
            tmp = Path.home() / ".empyrion_editor" / "cache" / "argos"
            for idx, job in enumerate(jobs):
                def cb(done, total, _idx=idx):
                    pct = int(done / total * 100) if total else 0
                    value = _idx * 100 + pct
                    QTimer.singleShot(0,
                                      lambda v=value: self.models_progress.setValue(v))
                fname = f"translate-{job['from_code']}_{job['to_code']}.argosmodel"
                try:
                    dest = argos_provider.download_model(
                        job["link"], tmp / fname, progress_cb=cb)
                    ok = argos_provider.install_model_file(dest)
                    self._log(f"{job['from_code']}->{job['to_code']} : "
                              + ("installe" if ok else "echec installation"))
                except Exception as e:
                    self._log(f"{job['from_code']}->{job['to_code']} : {e}")
            self.signals.models_done.emit(len(jobs))
        Thread(target=run, daemon=True).start()

    def _after_models(self, _n_jobs):
        self.btn_download.setEnabled(True)
        self.models_progress.setVisible(False)
        n = len(argos_provider.installed_pair_codes())
        self.models_status.setText(t("argos.models_done", n=n))
        # l'entree cochable du menu Options devient usable
        mw = self.main_window
        if mw is not None and hasattr(mw, "_refresh_argos_menu_action"):
            mw._refresh_argos_menu_action()
        self._load_models()

    def _import_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("argos.import_model"), "", "Argos model (*.argosmodel)")
        if not path:
            return
        if argos_provider.install_model_file(Path(path)):
            self.models_status.setText(t("argos.import_ok", name=Path(path).name))
            self._load_models()
        else:
            self.models_status.setText(t("argos.import_failed"))
