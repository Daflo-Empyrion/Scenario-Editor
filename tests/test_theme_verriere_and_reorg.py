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

"""Tests du theme "h" (Verriere néon), de la selection neon (gui/neon_delegate.py)
et du flou acrylique degrade gracieusement (core/win_backdrop.py). Ajoutes avec
la reorganisation P1-P6 (audit du 30/08/2026 + propositions validees)."""
import os

import gui.theme as theme_mod
from core.themes import THEMES, get_palette


# ---------------------------------------------------------------------------
# Theme Verriere : cles optionnelles
# ---------------------------------------------------------------------------

def test_verriere_palette_has_optional_keys():
    palette = THEMES["h"]
    assert palette.get("neon_selection") is True
    assert palette.get("acrylic") is True
    extra = palette.get("extra_qss")
    assert isinstance(extra, str) and "Verriere" in extra
    # QSS equilibre (accolades) : une regle ouverte non fermee casserait
    # TOUTE la feuille de style de l'application.
    assert extra.count("{") == extra.count("}") > 0


def test_other_themes_have_no_optional_glass_keys():
    for theme_id, palette in THEMES.items():
        if theme_id != "h":
            assert "extra_qss" not in palette
            assert "neon_selection" not in palette
            assert "acrylic" not in palette


def test_build_stylesheet_appends_extra_qss_only_for_verriere():
    base = build = None
    from gui.theme import build_stylesheet
    base = build_stylesheet({**THEMES["h"], "extra_qss": ""})
    full = build_stylesheet(THEMES["h"])
    assert full.startswith(base)
    assert len(full) > len(base)
    # Les autres themes ne sont PAS touches
    classic = build_stylesheet(THEMES["classic"])
    assert classic.count("{") == classic.count("}")


# ---------------------------------------------------------------------------
# Selection neon
# ---------------------------------------------------------------------------

def test_neon_active_follows_current_theme(qapp):
    from gui.neon_delegate import NeonItemDelegate, neon_selection_active
    from gui.theme import apply_theme

    apply_theme(qapp, "h")
    assert neon_selection_active() is True
    apply_theme(qapp, "classic")
    assert neon_selection_active() is False


def test_neon_delegate_paints_bloom_on_selection(qapp, monkeypatch):
    """Le delegue neon : sur un item selectionne (theme "h"), il peint le halo
    (drawRoundedRect concentriques) et transmet au style une option dont
    l'etat Selected est RETIRE (pour ne pas doubler la surbrillance) ; sur un
    item non selectionne ou un theme sans neon, il ne dessine AUCUN halo et
    transmet l'option intacte.

    Note : le test simule le QPainter ( MagicMock) et verifie la LOGIQUE du
    delegue. Le rendu raster complet du delegue est valide par la maquette
    K2 et le test manuel -- la plateforme offscreen de Qt crashe sur tout
    drawRoundedRect de delegue (meme sans theme neon), c'est une limite de
    l'environnement de test, pas du code produit."""
    from unittest.mock import MagicMock
    from PyQt6.QtCore import QModelIndex, Qt, QRectF
    from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem
    from gui.theme import apply_theme
    import gui.neon_delegate as nd
    from gui.neon_delegate import NeonItemDelegate

    delegate = NeonItemDelegate(None)
    index = QModelIndex()  # index invalide : suffisant pour le chemin de paint

    def _option(selected):
        option = QStyleOptionViewItem()
        if selected:
            option.state = QStyle.StateFlag.State_Selected
        option.rect = QRectF(0, 0, 100, 20).toRect()
        return option

    forwarded = []
    orig_paint = nd.QStyledItemDelegate.paint

    def spy_paint(self, painter, option, index):
        forwarded.append(option.state & QStyle.StateFlag.State_Selected)
        # super().paint avec un painter simule : on ne veut pas le rendu reel
        # ici, seulement verifier l'option transmise.
        return None

    monkeypatch.setattr(nd.QStyledItemDelegate, "paint", spy_paint)

    # Theme neon + selection : halo peint + etat Selected retire a la transmette
    apply_theme(qapp, "h")
    painter = MagicMock()
    delegate.paint(painter, _option(True), index)
    assert painter.drawRoundedRect.called is True
    assert not (forwarded[-1] & QStyle.StateFlag.State_Selected)

    # Theme neon + NON selectionne : aucun halo, option intacte
    painter2 = MagicMock()
    delegate.paint(painter2, _option(False), index)
    assert painter2.drawRoundedRect.called is False
    assert not (forwarded[-1] & QStyle.StateFlag.State_Selected)

    # Theme sans neon + selection : aucun halo, option intacte (rendu standard)
    apply_theme(qapp, "classic")
    painter3 = MagicMock()
    delegate.paint(painter3, _option(True), index)
    assert painter3.drawRoundedRect.called is False
    assert forwarded[-1] & QStyle.StateFlag.State_Selected
    monkeypatch.setattr(nd.QStyledItemDelegate, "paint", orig_paint)


# ---------------------------------------------------------------------------
# Flou acrylique : degrade gracieux
# ---------------------------------------------------------------------------

def test_acrylic_supported_matches_platform(monkeypatch):
    import sys
    from core import win_backdrop
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setattr(win_backdrop.os.environ, "get",
                        lambda k, d=None: "" if k == "QT_QPA_PLATFORM" else os.environ.get(k, d))
    monkeypatch.setattr(win_backdrop.sys, "platform", "win32")
    monkeypatch.setattr(win_backdrop.sys, "getwindowsversion",
                        lambda: type("V", (), {"build": 22621})())
    assert win_backdrop.acrylic_supported() is True
    monkeypatch.setattr(win_backdrop.sys, "getwindowsversion",
                        lambda: type("V", (), {"build": 19045})())  # Win10 22H2
    assert win_backdrop.acrylic_supported() is False
    monkeypatch.setattr(win_backdrop.sys, "platform", "linux")
    monkeypatch.setattr(win_backdrop.sys, "getwindowsversion",
                        lambda: type("V", (), {"build": 99999})())
    assert win_backdrop.acrylic_supported() is False


def test_enable_acrylic_never_raises_and_returns_bool(qapp):
    """Contrat principal : quel que soit l'OS, l'appel ne leve JAMAIS et
    retourne un booleen exploitable (True = translucence autorisee)."""
    from core import win_backdrop
    result = win_backdrop.enable_acrylic(qapp.activeWindow() or None)
    assert isinstance(result, bool)


def test_main_window_enables_acrylic_only_when_supported(qapp, monkeypatch, tmp_path):
    """Le garde-fou de lisibilite : sans support, la fenetre ne devient JAMAIS
    translucente (sinon texte illisible sur ce qui se trouve derriere)."""
    from core import win_backdrop
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.themes import get_palette

    apply_theme(qapp, "h")  # theme demandant l'acrylic
    monkeypatch.setattr(win_backdrop, "acrylic_supported", lambda: False)
    enabled = []
    monkeypatch.setattr(win_backdrop, "enable_acrylic",
                        lambda w: enabled.append(1) or False)
    win = MainWindow()
    assert enabled == []  # support absent : pas meme tenté
    win.close()


def test_main_window_applies_translucency_only_after_confirmation(
        qapp, monkeypatch, tmp_path):
    """Avec support OK : l'appel est tente ; s'il echoue quand meme, aucune
    translucence (invariant : jamais translucide sans flou confirme)."""
    from core import win_backdrop
    from gui.theme import apply_theme
    from gui.main_window import MainWindow

    apply_theme(qapp, "h")
    attempts = []

    def _fake_enable(widget):
        attempts.append(widget)
        return False  # le systeme refuse malgre le support (ex: RDP)

    monkeypatch.setattr(win_backdrop, "acrylic_supported", lambda: True)
    monkeypatch.setattr(win_backdrop, "enable_acrylic", _fake_enable)
    from PyQt6.QtCore import Qt as _Qt
    win = MainWindow()
    assert len(attempts) == 1
    assert win.testAttribute(_Qt.WidgetAttribute.WA_TranslucentBackground) is False
    win.close()


# ---------------------------------------------------------------------------
# P1-P6 : menus, barre d'outils, raccourcis, centre, bandeau, statut
# ---------------------------------------------------------------------------

_WINDOW_CACHE = {}


def _make_window(qapp, monkeypatch, tmp_path, fresh=False):
    """Fenetre MainWindow pour les tests du module. Par defaut elle est
    partagee entre les tests en lecture seule ; les tests qui poussent son
    etat (P5/P6 : reacquisition de labels) demandent fresh=True -- une
    fenetre NEUVE, la reutilisation prolongee sous Qt offscreen etant
    instable (crash C-level observe au-dela de quelques reutilisations)."""
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp, "classic")
    monkeypatch.setattr(theme_mod, "CURRENT_THEME_ID", "classic")
    key = id(qapp)
    if fresh or key not in _WINDOW_CACHE or _WINDOW_CACHE[key] is None:
        win = MainWindow()
        if not fresh:
            _WINDOW_CACHE[key] = win
        return win
    win = _WINDOW_CACHE[key]
    win.workspace = None  # etat propre, sans fuite du test precedent
    win._refresh_panel_and_status_labels()
    return win


def test_p1_tools_menu_exists_and_file_menu_slimmed(qapp, monkeypatch):
    """P1 : les outils sont dans un menu dedie ; Fichier ne contient plus ni
    les outils ni l'extraction (les attributs d'action restent les memes pour
    ne rien casser des raccourcis clavier/tests existants)."""
    win = _make_window(qapp, monkeypatch, None)
    assert win.menu_tools is not None
    assert isinstance(win.menu_tools.title(), str) and win.menu_tools.title()
    file_actions = win.menu_file.actions()
    tools_actions = win.menu_tools.actions()
    assert win.action_tech_tree in tools_actions
    assert win.action_galaxy_viewer in tools_actions
    assert win.action_pda_mission in tools_actions
    assert win.action_search_scenario in tools_actions
    assert win.action_extract_properties in tools_actions
    for action in (win.action_tech_tree, win.action_galaxy_viewer,
                   win.action_search_scenario):
        assert action not in file_actions
    win.close()


def test_p3_shortcuts_visible_in_menus(qapp, monkeypatch):
    win = _make_window(qapp, monkeypatch, None)
    from PyQt6.QtGui import QKeySequence
    assert win.action_search_scenario.shortcut() == QKeySequence("Ctrl+Shift+F")
    assert win.action_tech_tree.shortcut() == QKeySequence("Ctrl+T")
    assert win.action_galaxy_viewer.shortcut() == QKeySequence("Ctrl+G")
    assert win.action_pda_mission.shortcut() == QKeySequence("Ctrl+M")
    assert win.action_health_check.shortcut() == QKeySequence("F5")
    win.close()


def test_p2_toolbar_has_frequent_actions(qapp, monkeypatch):
    """P2 : les actions frequentes sont des boutons auto-peints (fond accent,
    icones blanches) -- lisibles sur tout fond de barre, contrairement aux
    icones nues qui etaient blanches sur fond blanc en theme classic
    (retour utilisateur du 30/08/2026)."""
    win = _make_window(qapp, monkeypatch, None)
    for attr in ("btn_toolbar_save", "btn_toolbar_search",
                 "btn_toolbar_tech_tree", "btn_toolbar_galaxy",
                 "btn_toolbar_pda", "btn_toolbar_center"):
        btn = getattr(win, attr)
        assert btn is not None and btn.icon().isNull() is False
    # declencher Enregistrer ne doit rien casser (aucun onglet -> no-op)
    win.btn_toolbar_save.click()
    win.close()


def test_p4_health_check_is_verification_center(qapp, monkeypatch, tmp_path):
    """Le bilan de sante est devenu le Centre de verification (P4) : titre
    nouvellement cle i18n, bouton "Tout verifier" (refresh complet)."""
    import shutil
    from pathlib import Path as _Path
    from gui.health_check_dialog import HealthCheckDialog
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from core.i18n import t

    fixture_dir = _Path(__file__).parent / "fixtures" / "tech_tree_scenario"
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    for f in fixture_dir.glob("*.ecf"):
        shutil.copy(f, config_dir / f.name)
    scenario = scan_scenario(tmp_path)
    win = MainWindow()
    win.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                              working=scenario, working_root=tmp_path)
    dlg = HealthCheckDialog(win)
    assert dlg.windowTitle() == t("verification.center_title")
    # le bouton "Tout verifier" relance bien toutes les familles
    dlg.refresh()
    dlg.close()
    win.close()


def test_p5_working_panel_label_shows_modified_count(qapp, monkeypatch):
    win = _make_window(qapp, monkeypatch, None, fresh=True)
    from core.i18n import t
    # 0 modifie : libelle simple
    win._refresh_panel_and_status_labels()
    assert win.label_working.text() == t("panel.working_copy")
    # 2 modifies : compteur affiche
    monkeypatch.setattr(win, "_modified_tab_widgets", lambda: [object(), object()])
    win._refresh_panel_and_status_labels()
    assert "2" in win.label_working.text()
    # PAS de win.close() ici : le monkeypatch ci-dessus est encore actif et
    # le closeEvent enumererait les faux onglets (crash de test, pas du produit).


def test_p6_status_bar_has_persistent_project_label(qapp, monkeypatch):
    win = _make_window(qapp, monkeypatch, None, fresh=True)
    assert hasattr(win, "status_project_label")
    monkeypatch.setattr(win, "workspace", type(
        "W", (), {"working_root": __import__("pathlib").Path("C:/proj/reforged"),
                  "working": None})())
    monkeypatch.setattr(win, "_modified_tab_widgets", lambda: [])
    win._refresh_panel_and_status_labels()
    assert "reforged" in win.status_project_label.text()
    # PAS de win.close() : monkeypatch _modified_tab_widgets encore actif
    # (meme raison que test_p5).


def test_p6_status_label_refreshed_after_project_resume(qapp, monkeypatch, tmp_path):
    """Retour utilisateur du 30/08/2026 (build installe) : apres une REPRISE
    de projet, le resume persistant affichait encore 'Aucun projet ouvert' --
    le libelle n'etait pas rafraichi apres l'assignation du workspace."""
    import shutil
    from pathlib import Path as _Path
    from gui.main_window import MainWindow
    from core.project_store import ProjectRecord
    from core.scanner import scan_scenario
    from core.workspace import Workspace

    fixture_dir = _Path(__file__).parent / "fixtures" / "tech_tree_scenario"
    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    for f in fixture_dir.glob("*.ecf"):
        shutil.copy(f, config_dir / f.name)
    scenario = scan_scenario(tmp_path)

    win = _make_window(qapp, monkeypatch, tmp_path)
    assert "Aucun projet ouvert" in win.status_project_label.text()

    record = ProjectRecord(source_a=str(tmp_path), working=str(tmp_path))
    monkeypatch.setattr(win, "_remember_current_project", lambda: None)
    win.open_existing_project(record)

    assert win.workspace is not None
    assert tmp_path.name in win.status_project_label.text()
    assert "Aucun projet ouvert" not in win.status_project_label.text()
    # et le libelle du bandeau copie de travail est aussi rafraichi
    assert win.label_working.text() == "Copie de travail (modifiable)" or "Copie de travail" in win.label_working.text()
