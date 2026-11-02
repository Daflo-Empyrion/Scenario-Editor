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

"""Vue web du tableau CSV (pilote 2026, demande du 01/11) : un QWebEngineView
remplace la QTableWidget a la demande (bouton « Vue web » de la barre) pour
les gros fichiers (Localization.csv : 13 000+ lignes).

REPARTITION STRICTE :
  - la QTableWidget RESTE la source de verite : chaque edition web est
    MIRROIREE dans la table (signaux bloques) -- toutes les fonctions
    existantes (sauvegarde, undo, orthographe, traduction, BBCode) lisent
    donc des donnees a jour sans aucun changement ;
  - la page HTML (gui/web/csv/index.html) ne fait AUCUN acces fichier :
    viewport de lignes demande au pont, edition renvoyee au pont ;
  - le pont passe par le widget CsvEditWidget existant (snapshot undo une
    fois par salve, mark_modified, _set_modified).

Tests : le pont et le basculement sont testes hors ligne (tests/test_csv_
web_view.py) ; le rendu Chromium ne l'est pas (meme parti pris que la vue
web de l'arbre technologique).
"""
import json
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, QFile, QIODevice, pyqtSignal, pyqtSlot

WEB_DIR = Path(__file__).resolve().parent / "web" / "csv"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    """True si le moteur web est utilisable (voir tech_tree_web.is_available)."""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
            _AVAILABLE = (WEB_DIR / "index.html").is_file()
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


class CsvWebBridge(QObject):
    """Objet expose a la page via QWebChannel : lecture par viewport,
    edition de cellule (miroir dans la table Qt), recherche."""

    data_changed = pyqtSignal(str)  # Python -> page : la table a change

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget  # CsvEditWidget (la table Qt reste la source)

    @pyqtSlot(result=str)
    def get_meta(self) -> str:
        w = self._widget
        header = w.doc.header or [str(i) for i in range(w.table.columnCount())]
        from core.i18n import t
        return json.dumps({
            "rows": w.table.rowCount(),
            "cols": w.table.columnCount(),
            "header": header,
            "editable": bool(w.editable),
            "name": w.path.name,
            # libelles de la barre d'actions web (tout texte visible via t())
            "labels": {
                "add": t("btn.add_row"),
                "del": t("btn.delete_selected_row"),
                "undo": t("btn.undo"),
                "replace": t("btn.find_replace"),
                "spell": t("btn.spellcheck"),
                "bbcode": t("btn.bbcode_check"),
                "fill": t("btn.fill_missing_translations"),
                "save": t("btn.save"),
            },
            # menu contextuel (tout via t() -- EN/FR, demande du 01/11)
            "ctx": {
                "edit": t("csvmenu.edit"),
                "copy": t("ctx.copy"),
                "cut": t("ctx.cut"),
                "paste": t("ctx.paste"),
                "clear": t("ctx.clear_content"),
                "del_rows": t("ctx.delete_rows"),
                "spell_cell": t("spellcheck.cell_action"),
                "translate_to": t("ctx.translate_to"),
                "explain": t("ctx.explain_ai"),
                "bbcode_tool": t("ctx.bbcode"),
                "bold": t("csvmenu.bold"),
                "italic": t("csvmenu.italic"),
                "underline": t("csvmenu.underline"),
                "sup": t("csvmenu.sup"),
                "color": t("csvmenu.color"),
                "undo": t("btn.undo"),
            },
            "languages": __import__("core.translation", fromlist=["COMMON_LANGUAGES"]).COMMON_LANGUAGES,
        }, ensure_ascii=False)

    @pyqtSlot(int, int, result=str)
    def get_rows(self, start: int, count: int) -> str:
        """Fenetre de lignes lues depuis la table Qt (source de verite) --
        bornes serrees pour ne jamais sortir du tableau."""
        w = self._widget
        total = w.table.rowCount()
        cols = w.table.columnCount()
        if start < 0 or start >= total:
            return json.dumps({"start": max(0, start), "rows": []})
        count = max(0, min(count, total - start))
        out = []
        for r in range(start, start + count):
            out.append([w.table.item(r, c).text()
                        if w.table.item(r, c) else ""
                        for c in range(cols)])
        return json.dumps({"start": start, "rows": out}, ensure_ascii=False)

    @pyqtSlot(int, int, str)
    def set_cell(self, row: int, col: int, text: str) -> None:
        """Edition depuis la page : MIRROIR dans la table Qt (source de
        verite) via widget._web_set_cell -- snapshot undo une fois par
        salve, mark_modified, drapeau modifie."""
        self._widget._web_set_cell(row, col, text)

    # Actions de barre exposees a la page -> methodes EXISTANTES du widget
    # (liste blanche : jamais getattr libre sur un nom venu du web)
    _ACTIONS = {
        "add_row": "_add_row",
        "delete_row": "_delete_selected_row",
        "delete_rows": "_do_delete_rows",
        "undo": "undo",
        "find_replace": "_open_find_replace_dialog",
        "spellcheck": "_open_spellcheck_menu",
        "bbcode": "_open_bbcode_check",
        "fill_missing": "_open_fill_missing_dialog",
        "save": "save",
    }

    def push_reset(self) -> None:
        """Re-pousse la forme du tableau a la page par le CANAL (signal) --
        jamais runJavaScript('window.appReset(...)') : il s'execute dans un
        AUTRE monde JS que les scripts de la page (piege verifie deux fois :
        arbre tech 31/10, vue CSV 01/11 -- l'erreur 'appReset is not a
        function' en console trahit exactement cela)."""
        self.data_changed.emit(json.dumps(json.loads(self.get_meta()),
                                          ensure_ascii=False))

    @pyqtSlot(str)
    def run_action(self, name: str) -> None:
        """Action de barre demandee par la page -> methode existante du
        CsvEditWidget (meme chemin que les boutons Qt). Apres coup, la
        forme du tableau est re-poussee a la page (lignes ajoutees,
        undo...)."""
        method_name = self._ACTIONS.get(name)
        w = self._widget
        if method_name is None or not w.editable:
            return
        try:
            if name == "spell_cell":
                w._run_spellcheck("cell")   # la cellule courante Qt est mirroiree
            else:
                getattr(w, method_name)()
        except Exception:
            pass  # les dialogues affichent eux-memes leurs erreurs
        meta = json.loads(self.get_meta())
        self.data_changed.emit(json.dumps(meta, ensure_ascii=False))

    @pyqtSlot(int)
    def set_current_row(self, row: int) -> None:
        """Ligne courante choisie dans la page -> selection Qt (les actions
        selection-dependantes comme la suppression de ligne restent
        exactement les memes des deux cotes)."""
        w = self._widget
        if 0 <= row < w.table.rowCount():
            w.table.selectRow(row)

    # -- menu contextuel (clic droit de la page) ----------------------------

    def _item(self, row: int, col: int):
        table = self._widget.table
        if 0 <= row < table.rowCount() and 0 <= col < table.columnCount():
            return table.item(row, col)
        return None

    def _push_meta(self) -> None:
        """Re-pousse la forme du tableau a la page : APPELE APRES CHAQUE
        slot de menu qui modifie la table (vecu 01/11 : le wrap BBCode
        changeait la table Qt mais la page ne se redessinait jamais)."""
        self.data_changed.emit(json.dumps(json.loads(self.get_meta()),
                                          ensure_ascii=False))

    @pyqtSlot(int, int)
    def select_cell(self, row: int, col: int) -> None:
        w = self._widget
        if self._item(row, col) is not None:
            w.table.setCurrentCell(row, col)

    @pyqtSlot(int, int)
    def copy_cell(self, row: int, col: int) -> None:
        from PyQt6.QtGui import QGuiApplication
        item = self._item(row, col)
        if item is not None:
            QGuiApplication.clipboard().setText(item.text())

    @pyqtSlot(int, int)
    def cut_cell(self, row: int, col: int) -> None:
        from PyQt6.QtGui import QGuiApplication
        item = self._item(row, col)
        if item is None or not self._widget.editable:
            return
        QGuiApplication.clipboard().setText(item.text())
        self._widget._web_set_cell(row, col, "")
        self._push_meta()

    @pyqtSlot(int, int)
    def paste_cell(self, row: int, col: int) -> None:
        from PyQt6.QtGui import QGuiApplication
        if not self._widget.editable:
            return
        text = QGuiApplication.clipboard().text()
        if text:
            self._widget._web_set_cell(row, col, text)
            self._push_meta()

    @pyqtSlot(int, int)
    def clear_cell(self, row: int, col: int) -> None:
        if self._widget.editable:
            self._widget._web_set_cell(row, col, "")
            self._push_meta()

    @pyqtSlot(int, int, str, str)
    def translate_cell(self, row: int, col: int, code: str, label: str) -> None:
        """Traduction d'une cellule web -> MÊME chemin que le menu Qt
        (_translate_single_cell ouvre son propre dialogue d'apercu et
        gere ses erreurs)."""
        item = self._item(row, col)
        if item is None:
            return
        self._widget._translate_single_cell(item, item.text(), code, label)
        self._push_meta()   # le dialogue a pu modifier la cellule

    @pyqtSlot(int, int)
    def explain_cell(self, row: int, col: int) -> None:
        self._widget._explain_cell(row, col)

    @pyqtSlot(int, int)
    def bbcode_tool(self, row: int, col: int) -> None:
        """Assistant BBCode existant (gui/text_tools.open_bbcode_tool) --
        dialogue qui retourne le texte retravaille."""
        from gui.text_tools import open_bbcode_tool
        item = self._item(row, col)
        if item is None or not self._widget.editable:
            return
        new_text = open_bbcode_tool(self._widget, item.text())
        if new_text is not None:
            self._widget._snapshot_undo()
            self._widget._web_set_cell(row, col, new_text)
            self._push_meta()

    @pyqtSlot(int, int, str, str)
    def wrap_bbcode(self, row: int, col: int,
                    open_tag: str, close_tag: str) -> None:
        """Enveloppement BBCode applique par la page (gras, couleur...).
        Les balises sont CONTRUITES COTE PYTHON (la page n'envoie que le
        nom de l'effet -> jamais d'injection de balise via le web)."""
        w = self._widget
        if not w.editable:
            return
        item = self._item(row, col)
        if item is None:
            return
        text = item.text()
        w._web_set_cell(row, col, f"{open_tag}{text}{close_tag}")
        self._push_meta()

    @pyqtSlot(str, int, result=str)
    def search(self, query: str, col: int) -> str:
        """Cellules contenant `query` (insensible a la casse), au format
        [[ligne, colonne], ...] -- une entree PAR CELLULE trouvee pour le
        surlignage (demande du 01/11), plafonne a 500 hits. col -1 = toutes."""
        w = self._widget
        q = (query or "").lower()
        hits = []
        if q:
            total = w.table.rowCount()
            cols = w.table.columnCount()
            scope = range(cols) if col < 0 else [col]
            for r in range(total):
                for c in scope:
                    item = w.table.item(r, c)
                    if item is not None and q in item.text().lower():
                        hits.append([r, c])
                        if len(hits) >= 500:
                            return json.dumps(hits)
        return json.dumps(hits)


def make_web_view(widget, parent=None):
    """Construit (QWidget vue, bridge) -- a n'appeler que si is_available().
    Meme recette que la vue web de l'arbre technologique : qwebchannel.js
    injecte depuis les ressources Qt, pas de serveur local."""
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QWidget, QVBoxLayout

    bridge = CsvWebBridge(widget)

    class _View(QWidget):
        def __init__(self):
            super().__init__(parent)
            self._bridge = bridge
            self.view = QWebEngineView(self)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.view)
            channel = QWebChannel(self)
            channel.registerObject("csvbridge", bridge)
            self.view.page().setWebChannel(channel)
            html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
            f = QFile(":/qtwebchannel/qwebchannel.js")
            js = ""
            if f.open(QIODevice.OpenModeFlag.ReadOnly):
                js = bytes(f.readAll()).decode("utf-8")
            html = html.replace("__QWEBCHANNEL_JS__", js)
            self.view.setHtml(html, QUrl("http://localhost/"))

        def refresh(self) -> None:
            """Re-pousse la forme du tableau (nom, dimensions) apres un
            changement cote Python (populate) -- par le canal QWebChannel."""
            bridge.push_reset()

    return _View(), bridge
