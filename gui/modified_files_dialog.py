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

"""Vue « fichiers modifies » (demande du 10/09/2026) : liste des fichiers de
la copie de travail qui different du scENARIO A d'origine -- ajoutes ou
modifies. Comparaison par TAILLE puis par contenu (les fichiers identiques
re-ecrits a l'octet pres ne sont pas signales). Double-clic ou « Ouvrir » :
charge le fichier dans un onglet de la copie de travail."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel,
)

from core.i18n import t


def _hash(path: Path) -> bytes:
    import hashlib
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.digest()


# ---------------------------------------------------------------------------
# Cache de hachages persiste (demande du 31/10) : eviter de recalculer le MD5
# de milliers de fichiers au demarrage quand rien n'a change. Un fichier
# cache par racine (<racine>/.cache_hashes, JSON) : {rel: [taille, mtime_ns,
# md5hex]} -- une entree est reutilisee si taille ET mtime_ns correspondent
# EXACTEMENT (semantique identique au raccourci mtime ci-dessus : re-ecrit a
# l'octet pres + mtime conserve = non signale, chose deja supposee par le
# scan actuel). Cache corrompu = ignore silencieusement.
# ---------------------------------------------------------------------------
_CACHE_NAME = ".cache_hashes"


def _load_hash_cache(root: Path) -> dict:
    import json
    try:
        raw = (Path(root) / _CACHE_NAME).read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_hash_cache(root: Path, cache: dict) -> None:
    import json
    from core.fsutil import atomic_write_text
    try:
        atomic_write_text(Path(root) / _CACHE_NAME,
                          json.dumps(cache, ensure_ascii=False))
    except OSError:
        pass  # le cache est une optimisation, jamais une obligation


def _cached_hash(path: Path, root: Path, cache: dict, dirty: list) -> bytes:
    """Hash du fichier, servi par le cache si (taille, mtime_ns) correspond
    exactement a l'entree memorisee ; sinon calcule et met a jour le cache."""
    rel = path.relative_to(root).as_posix()
    st = path.stat()
    entry = cache.get(rel)
    if (isinstance(entry, list) and len(entry) == 3
            and entry[0] == st.st_size and entry[1] == st.st_mtime_ns):
        try:
            return bytes.fromhex(entry[2])
        except ValueError:
            pass
    h = _hash(path)
    cache[rel] = [st.st_size, st.st_mtime_ns, h.hex()]
    dirty.append(True)
    return h


def list_changed_files(working_root: Path, source_root: Path):
    """Retourne [(chemin_copie, 'added'|'modified')] tries par chemin. Les
    fichiers presents seulement dans A sont ignores (suppressions
    volontaires rares -- et les signaler doublerait la liste). Les *.bak
    (sauvegardes internes des operations de l'editeur) et les *.yaml.bin
    (caches compiles du JEU, derives des yaml — vecu 05/10 : un cache
    synchronise peut resservir un playfield perime) ne sont JAMAIS
    proposes a la synchronisation.

    Comparaison TAILLE puis MTIME (copy2 de la sync le conserve : apres un
    sync reussi, zero hash — vecu 17/10 : 64 s de scan pour zero changement
    parce que tout etait hashé des deux cotes) puis HASH SEULEMENT si les
    horloges divergent — hash SERVI PAR LE CACHE persiste .cache_hashes quand
    rien n'a change (demande du 31/10 : eviter de recalculer des milliers de
    SHA/MD5 au demarrage). La semantique « re-ecrit a l'octet pres = non
    signale » reste garantie par le hash, et le cas mtime egal/contenu
    different est theoriquement impossible (resolutions ns)."""
    changes = []
    cache_w = _load_hash_cache(working_root)
    cache_s = _load_hash_cache(source_root)
    dirty: list = []
    for path in sorted(Path(working_root).rglob('*')):
        if not path.is_file():
            continue
        if path.name == _CACHE_NAME:
            continue          # le cache lui-meme : jamais synchronise
        if path.suffix.lower() == '.bak':
            continue          # sauvegarde interne : jamais a synchroniser
        if path.name.lower().endswith('.yaml.bin'):
            continue          # cache compile du jeu : derive du yaml
        rel = path.relative_to(working_root)
        counterpart = Path(source_root) / rel
        if not counterpart.exists():
            changes.append((path, 'added'))
            continue
        st = path.stat()
        ct = counterpart.stat()
        if st.st_size != ct.st_size:
            changes.append((path, 'modified'))
            continue
        if st.st_mtime_ns == ct.st_mtime_ns:
            continue
        if _cached_hash(path, working_root, cache_w, dirty) != \
                _cached_hash(counterpart, source_root, cache_s, dirty):
            changes.append((path, 'modified'))
    if dirty:
        _save_hash_cache(working_root, cache_w)
        _save_hash_cache(source_root, cache_s)
    return changes


class ModifiedFilesDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle(t("modfiles.title"))
        self.resize(720, 500)
        from gui.window_geometry import track
        track(self, "modified_files")
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.summary = QLabel("")
        layout.addWidget(self.summary)
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.list_widget)
        buttons = QHBoxLayout()
        btn_open = QPushButton(t("modfiles.open"))
        btn_open.clicked.connect(self._open_selected)
        btn_refresh = QPushButton(t("dash.refresh"))
        btn_refresh.clicked.connect(self._refresh)
        buttons.addWidget(btn_open)
        buttons.addWidget(btn_refresh)
        layout.addLayout(buttons)

    def _refresh(self):
        self.list_widget.clear()
        ws = self.main_window.workspace
        if not ws:
            self.summary.setText(t("status.no_project"))
            return
        from gui.busy import run_long
        changes = run_long(self, lambda: list_changed_files(
            ws.working_root, ws.source_a_root))
        for path, state in changes:
            key = "modfiles.state_added" if state == 'added' else "modfiles.state_modified"
            item = QListWidgetItem(f"[{t(key)}] {path.relative_to(ws.working_root)}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.list_widget.addItem(item)
        self.summary.setText(t("modfiles.summary", n=len(changes)))

    def _open_selected(self, *_args):
        item = self.list_widget.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.main_window.open_working_file_tab(path)
