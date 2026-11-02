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

"""Vue HTML de l'arbre technologique (pilote 2026, decision du 31/10).

Remplace l'onglet QTabWidget de TechTreeDialog par UN ecran web
(QWebEngineView + QWebChannel) quand le reglage `tech_tree_web_enabled`
est actif -- sinon TechTreeDialog construit les vues Qt historiques et ce
module n'est PAS importe par l'application (degrade gracieux, meme logique
que gui/fluent_pilot.py).

REPARTITION STRICTE :
  - le HTML/JS (gui/web/tech_tree/index.html) ne fait AUCUN calcul d'arbre
    et ne touche AUCUN fichier : il place les noeuds a la position fournie
    par core/tech_tree_layout.compute_layout() (meme disposition que la vue
    Qt) et renvoie toute ecriture au pont ;
  - toute ecriture passe par les signaux du pont, branches sur les memes
    handlers de TechTreeDialog que la vue Qt (garde fichier modifie, pile
    d'annulation, rechargement de l'onglet ouvert) ;
  - apres chaque ecriture (reussie ou refusee), le dialogue appelle
    refresh() : le payload de la categorie affichee est recalcule cote
    Python et pousse vers la page -- la vue web ne se met a jour que par la.

Tests : le payload, le pont et les libelles sont testes hors ligne
(tests/test_tech_tree_web.py) ; TechTreeWebView n'est JAMAIS construit dans
les tests (QWebEngineView lance Chromium, hostile a l'offscreen).
"""
import json
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, QFile, QIODevice, pyqtSignal, pyqtSlot

WEB_DIR = Path(__file__).resolve().parent / "web" / "tech_tree"

_AVAILABLE = None  # cache du test d'import (None = pas encore teste)


def is_available() -> bool:
    """True si le moteur web est utilisable. Piege (verifie 31/10) : importer
    QtWebEngineWidgets APRES la creation du QApplication leve — le test
    degrade donc en False dans ce cas (la vraie activation se fait a main(),
    avant QApplication, voir gui/main_window.py)."""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            from PyQt6.QtWebChannel import QWebChannel  # noqa: F401
            _AVAILABLE = (WEB_DIR / "index.html").is_file()
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


def build_labels() -> dict:
    """Libelles de la page, tous via t() (regle i18n du projet) : le HTML
    ne contient AUCUN texte en dur, il recupere ce dict au demarrage."""
    from core.i18n import t
    return {
        "search_placeholder": t("webtree.search_placeholder"),
        "legend_dep": t("webtree.legend_dep"),
        "legend_root": t("webtree.legend_root"),
        "fit": t("webtree.fit"),
        "inspector": t("webtree.inspector"),
        "name": t("webtree.name"),
        "level": t("webtree.level"),
        "cost": t("webtree.cost"),
        "category": t("webtree.category"),
        "parent": t("webtree.parent"),
        "no_parent": t("webtree.no_parent"),
        "unlocks": t("webtree.unlocks"),
        "leaf": t("webtree.leaf"),
        "open_card": t("webtree.open_card"),
        "definition": t("webtree.definition"),
        "icon": t("webtree.icon"),
        "def_item": t("webtree.def_item"),
        "def_block": t("webtree.def_block"),
        "source_note": t("webtree.source_note"),
        "paliers": t("webtree.paliers"),
        "nodes": t("webtree.nodes"),
        "empty": t("webtree.empty"),
        "source_caption": t("webtree.source_caption"),
        "card_unavailable": t("webtree.card_unavailable"),
        "card_untranslated": t("webtree.card_untranslated"),
        "card_unlock": t("webtree.card_unlock"),
        "card_stats": t("webtree.card_stats"),
        "ing_add": t("webtree.ing_add"),
        "ing_remove": t("webtree.ing_remove"),
        "ing_name_ph": t("webtree.ing_name_ph"),
        "ing_qty_ph": t("webtree.ing_qty_ph"),
        "ok_btn": t("webtree.ok_btn"),
    }


def build_category_payload(tree, category: str) -> dict:
    """Payload complet d'une categorie pour la page : paliers + noeuds avec
    leur position EXACTE de compute_layout (meme disposition que le F3 du
    jeu et que la vue Qt). Pure : ne touche aucun fichier."""
    from core.tech_tree_layout import compute_layout
    lay = compute_layout(tree, category)
    nodes = []
    for n in lay.draw_order:
        p = lay.positions[n.name]
        nodes.append({
            "name": n.name,
            "lv": n.unlock_level,
            "cost": n.unlock_cost,
            "col": int(p.x_fraction),
            "row": p.row,
            "parent": p.parent_name or "",
            "src": n.source,
            "icon": n.icon_key,
        })
    return {"cat": category, "levels": lay.levels, "nodes": nodes}


def _strip_tags(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html or "").strip()


def card_to_payload(card) -> dict:
    """Serialize une BlockInfoCard (core/block_info_card.py) pour la page :
    affichage LECTURE SEULE integre au style de l'inspecteur (demande du
    31/10) ; l'edition reste dans la fiche Qt (vue web phase 2)."""
    return {
        # title est deja du HTML (produit par _bbcode_to_html) : la page
        # recoit la version SANS balises et echappe elle-meme ; la
        # description brute (BBCode) est convertie cote page APRES echappement
        # (le texte vient du scenario : jamais injecte tel quel).
        "title_text": _strip_tags(card.title),
        "description_text": card.description_text,
        "untranslated": bool(card.description_untranslated),
        # source_key/source_raw_value : navigation vers la propriete ECF
        # source (meme mecanisme que la fiche Qt) -- absent = champ calcule,
        # non editable dans la page.
        "stats": [_field(f) for f in card.stat_fields],
        "unlock": [_field(f) for f in card.unlock_fields],
        "crafting_header": card.crafting_header,
        "ingredients_label": card.input_items_label,
        # qty_raw = valeur BRUTE du Template (le HTML affiche est recalcule
        # cote page) ; key = nom brut de l'ingredient (edition possible)
        "ingredients": [{"name": i.name, "qty": i.quantity,
                         "key": i.source_key or i.name,
                         "qty_raw": i.source_raw_value or i.quantity}
                        for i in card.ingredients],
        "output": _field(card.output_count) if card.output_count else None,
        "price": _field(card.market_price) if card.market_price else None,
    }


def _field(f) -> dict:
    d = {"label": f.label, "value": f.value}
    if f.source_key:
        d["source_key"] = f.source_key
        d["source_raw_value"] = f.source_raw_value
    return d


class TechTreeBridge(QObject):
    """Objet expose a la page via QWebChannel. Les slots de lecture
    retournent du JSON ; les slots d'ecriture EMETTENT seulement un signal
    -- TechTreeDialog le branche sur ses handlers existants, qui font la
    garde/undo/ecriture/rechargement, puis rappellent refresh()."""

    node_selected = pyqtSignal(str)
    node_activated = pyqtSignal(str)
    level_changed = pyqtSignal(str, int)
    cost_changed = pyqtSignal(str, int)
    parent_changed = pyqtSignal(str, str)   # "" = racine (convention vue Qt)
    category_changed = pyqtSignal(str, str)
    category_displayed = pyqtSignal(str)    # la page affiche cette categorie
    data_changed = pyqtSignal(str)          # Python -> page : payload recalcule
    # edition d'une valeur de la fiche integree (lecture -> ecriture reelle,
    # meme chemin que la fiche Qt) : nom, cle source, ancien, nouveau
    card_value_changed = pyqtSignal(str, str, str, str)
    # edition d'un ingredient de fabrication : nom, cle, champ ('name'/'qty'),
    # quantite brute, ancien, nouveau
    card_ingredient_changed = pyqtSignal(str, str, str, str, str, str)
    # edition de la description (Info de Localization.csv) : nom, ancien, nouveau
    card_description_changed = pyqtSignal(str, str, str)

    def __init__(self, tech_tree, labels: dict, card_provider=None,
                 values_provider=None, names_provider=None, parent=None):
        super().__init__(parent)
        self._tree = tech_tree
        self._labels = labels
        self._card_provider = card_provider  # name -> dict | None (fourni par le dialogue)
        self._values_provider = values_provider  # name -> {cle: [valeurs observees]}
        self._names_provider = names_provider    # -> [noms craftables]

    @pyqtSlot(result=str)
    def get_categories(self) -> str:
        return json.dumps(self._tree.categories(), ensure_ascii=False)

    @pyqtSlot(result=str)
    def get_labels(self) -> str:
        return json.dumps(self._labels, ensure_ascii=False)

    @pyqtSlot(str, result=str)
    def get_category(self, category: str) -> str:
        try:
            payload = build_category_payload(self._tree, category)
        except Exception:
            return json.dumps({"cat": category, "levels": [], "nodes": []})
        return json.dumps(payload, ensure_ascii=False)

    @pyqtSlot(str, result=str)
    def get_card(self, name: str) -> str:
        """Fiche du bloc (lecture seule) -- None -> 'null' JSON, la page
        affiche 'fiche indisponible'."""
        if self._card_provider is None:
            return "null"
        try:
            payload = self._card_provider(name)
        except Exception:
            return "null"
        return json.dumps(payload, ensure_ascii=False) if payload else "null"

    @pyqtSlot(str)
    def select_node(self, name: str) -> None:
        self.node_selected.emit(name)

    @pyqtSlot(str)
    def activate_node(self, name: str) -> None:
        self.node_activated.emit(name)

    @pyqtSlot(str)
    def notify_category(self, category: str) -> None:
        self.category_displayed.emit(category)

    @pyqtSlot(str, int)
    def set_unlock_level(self, name: str, level: int) -> None:
        self.level_changed.emit(name, level)

    @pyqtSlot(str, int)
    def set_unlock_cost(self, name: str, cost: int) -> None:
        self.cost_changed.emit(name, cost)

    @pyqtSlot(str, str)
    def set_parent(self, name: str, parent: str) -> None:
        self.parent_changed.emit(name, parent)

    @pyqtSlot(str, str)
    def set_category(self, name: str, category: str) -> None:
        self.category_changed.emit(name, category)

    @pyqtSlot(str, str, str, str)
    def set_card_value(self, name: str, source_key: str,
                       old_value: str, new_value: str) -> None:
        """Valeur de la fiche integree modifiee dans la page -> meme chemin
        que la fiche Qt (TechTreeDialog._on_card_value_edit)."""
        self.card_value_changed.emit(name, source_key, old_value, new_value)

    @pyqtSlot(result=str)
    def get_names(self) -> str:
        """Pool des noms d'items/blocs craftables (pour l'autocomplete des
        ingredients) -- calculé une fois par le dialogue, mis en cache JS."""
        if self._names_provider is None:
            return "[]"
        try:
            return json.dumps(list(self._names_provider()), ensure_ascii=False)
        except Exception:
            return "[]"

    @pyqtSlot(str, result=str)
    def get_values(self, name: str) -> str:
        """{cle_propriete: [valeurs observees]} pour les listes deroulantes
        des champs de la fiche -- meme source que la fiche Qt."""
        if self._values_provider is None:
            return "{}"
        try:
            return json.dumps(self._values_provider(name), ensure_ascii=False)
        except Exception:
            return "{}"

    @pyqtSlot(str, str, str, str, str, str)
    def set_card_ingredient(self, name: str, key: str, field: str,
                            qty: str, old_value: str, new_value: str) -> None:
        """Ingredient de fabrication edite dans la page (nom ou quantite)
        -> Templates.ecf via le dialogue. field : 'name' ou 'qty'."""
        self.card_ingredient_changed.emit(name, key, field, qty, old_value, new_value)

    @pyqtSlot(str, str, str)
    def set_card_description(self, name: str, old_text: str, new_text: str) -> None:
        """Description (texte Info de Localization.csv) editee dans la page.
        Le dialogue propose ensuite de traduire vers les autres langues."""
        self.card_description_changed.emit(name, old_text, new_text)


class TechTreeWebView:
    """Conteneur QWebEngineView. Pas un QWidget herite pour rester
    importable sans WebEngine : la classe reelle est construite par
    _build() apres le test is_available()."""

    @staticmethod
    def _qwebchannel_js() -> str:
        # La lib est embarquee dans les ressources Qt, disponibles APRES
        # l'import de QtWebEngineWidgets (verifie le 31/10/2026).
        f = QFile(":/qtwebchannel/qwebchannel.js")
        if f.open(QIODevice.OpenModeFlag.ReadOnly):
            return bytes(f.readAll()).decode("utf-8")
        return ""


def make_web_view(tech_tree, labels: dict, card_provider=None,
                  values_provider=None, names_provider=None, parent=None):
    """Construit (QWidget, TechTreeBridge). A n'appeler que si
    is_available() ; l'import WebEngine est fait ici, pas au niveau module."""
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QWidget, QVBoxLayout

    bridge = TechTreeBridge(tech_tree, labels, card_provider=card_provider,
                            values_provider=values_provider,
                            names_provider=names_provider)

    class _View(QWidget):
        node_selected = bridge.node_selected
        node_activated = bridge.node_activated
        level_changed = bridge.level_changed
        cost_changed = bridge.cost_changed
        parent_changed = bridge.parent_changed
        category_changed = bridge.category_changed

        def __init__(self):
            super().__init__(parent)
            self._bridge = bridge
            self._tree = tech_tree
            self.displayed_category = ""
            bridge.category_displayed.connect(lambda c: setattr(self, "displayed_category", c))
            self.view = QWebEngineView(self)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.view)
            channel = QWebChannel(self)
            channel.registerObject("techtree", bridge)
            self.view.page().setWebChannel(channel)
            html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
            html = html.replace("__QWEBCHANNEL_JS__", TechTreeWebView._qwebchannel_js())
            # fond nebuleuse (genere par _maquettes/make_bg.py) embarque en
            # data-URI : la page est servie via setHtml (origine http://localhost),
            # une image RELATIVE ne se chargerait pas
            bg = WEB_DIR / "bg.jpg"
            if bg.is_file():
                import base64
                b64 = base64.b64encode(bg.read_bytes()).decode("ascii")
                html = html.replace("__BG_DATA_URI__", f"data:image/jpeg;base64,{b64}")
            self.view.setHtml(html, QUrl("http://localhost/"))

        def refresh(self) -> None:
            """Recalcule le payload de la categorie affichee et l'envoie a la
            page via le signal data_changed. PIEGE (vecu 31/10) : impossible
            de passer par runJavaScript("window.appApplyData(...)") —
            runJavaScript execute dans un AUTRE monde JS que les scripts de
            la page (window.appApplyData y est invisible). Le pont QWebChannel
            (signal Qt -> callback JS) est la seule voie fiable."""
            cat = self.displayed_category
            if not cat:
                return
            bridge.data_changed.emit(
                json.dumps(build_category_payload(self._tree, cat), ensure_ascii=False))

    return _View(), bridge
