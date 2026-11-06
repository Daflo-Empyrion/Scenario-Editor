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

"""Dialogue des planetes de depart : liste cochable, kit, fiche, application
en une action (Sectors.yaml + playfield_static.yaml + undo multi-fichiers)."""
from pathlib import Path

from PyQt6.QtCore import Qt
from test_starters import PLAIN, STARTER, _build, _playfield, _sectors


def _row_index(dialog, name: str) -> int:
    for index in range(dialog.tree.topLevelItemCount()):
        if dialog.tree.topLevelItem(index).text(3) == name:
            return index
    raise AssertionError(f"{name} absent de la liste")


class Main:
    workspace = None

    def __init__(self):
        self.pushed = []

    def _push_workspace_undo(self, undo):
        self.pushed.append(undo)

    def _reload_tab_if_open_and_unmodified(self, path):
        pass


def _dialog(monkeypatch, root, main=None):
    from gui import starters_dialog as mod
    monkeypatch.setattr(mod, "ask_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(mod, "async_call", lambda *a, **k: None)
    return mod.StartersDialog(root, main_window=main or Main())


def test_dialog_lists_planets_with_their_state(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    root = _build(tmp_path)
    dialog = _dialog(monkeypatch, root)
    try:
        assert dialog.tree.topLevelItemCount() == 2
        akua = _row_index(dialog, "Akua")
        eden = _row_index(dialog, "Eden")
        assert dialog.tree.topLevelItem(akua).checkState(0) == Qt.CheckState.Checked
        assert dialog.tree.topLevelItem(eden).checkState(0) == Qt.CheckState.Unchecked
        # premiere ouverture : l'initialisation (ask_yes_no -> True) marque
        # les departs deja presents comme valides
        assert dialog.tree.topLevelItem(akua).text(5) == "validé en jeu"
        assert dialog.tree.topLevelItem(eden).text(5) == ""
        assert dialog.tree.topLevelItem(akua).text(6) == "oui"    # kit present
        assert dialog.tree.topLevelItem(eden).text(6) == "non"
        dialog.search.setText("akua")
        assert dialog.tree.topLevelItem(eden).isHidden()
    finally:
        sip.delete(dialog)


def test_dialog_seed_and_validate_button(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    from core.starters import load_validated
    root = _build(tmp_path)
    dialog = _dialog(monkeypatch, root)
    try:
        akua = _row_index(dialog, "Akua")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(akua))
        assert dialog.btn_validated.isEnabled()       # un depart est selectionne
        dialog._mark_validated()
        validated, exists = load_validated(root)
        assert validated == {"Starter_Akua_V2"} and exists
        assert dialog.tree.topLevelItem(akua).text(5) == "validé en jeu"
        assert "enregistré comme validé" in dialog.status.text()
    finally:
        sip.delete(dialog)


def test_dialog_repairs_the_final_newline_of_an_enabled_planet(
        qapp, tmp_path, monkeypatch):
    """Le cas vecu du 05/11 : on coche une planete dont le playfield n'a pas de
    saut de ligne final, sans toucher au kit — le fichier doit etre repare,
    sinon le client plante au menu Nouvelle partie."""
    from PyQt6 import sip
    root = _build(tmp_path)
    path = root / "Playfields" / "EdenOcean2" / "playfield_static.yaml"
    path.write_bytes(PLAIN.rstrip("\n").encode("utf-8"))
    main = Main()
    dialog = _dialog(monkeypatch, root, main)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog.card_check.setChecked(False)
        dialog._apply()
        assert path.read_bytes().endswith(b"\n")
        # undo couvre le Sectors ET le playfield repare
        assert len(main.pushed[0].entries) == 2
        assert "saut de ligne final" in dialog.status.text()
    finally:
        sip.delete(dialog)


def test_dialog_refuses_a_playfield_the_client_cannot_load(
        qapp, tmp_path, monkeypatch):
    """Un playfield dont la donnee ne se charge pas (cle racine dupliquee sans
    valeur) ne doit JAMAIS etre declare : le menu perdrait tous les departs."""
    from PyQt6 import sip
    root = _build(tmp_path)
    (root / "Playfields" / "EdenOcean2" / "playfield_dynamic.yaml").write_text(
        "GroundShapes:\n\n\nGroundShapes: \n - GroundShape_Mercury, 1\n",
        encoding="utf-8")
    before = _sectors(root)
    dialog = _dialog(monkeypatch, root)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog._apply()
        assert "refusé" in dialog.status.text()
        assert "GroundShapes" in dialog.status.text()
        assert _sectors(root) == before          # rien n'a ete ecrit
    finally:
        sip.delete(dialog)


def test_dialog_apply_writes_marker_kit_and_card(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    root = _build(tmp_path)
    main = Main()
    dialog = _dialog(monkeypatch, root, main)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog.items_edit.setPlainText(
            "CombatKnife\nCombatKnife\nCombatKnife\n#FreshStart: CombatKnife")
        dialog._preview()
        assert "'Human:1'" in dialog.preview_box.toPlainText()
        assert dialog.btn_apply.isEnabled()
        dialog._apply()
        assert dialog.applied == 1
        assert "['0, 0, 0', Eden, EdenOcean2, 'Human:1', '', '', '']" in _sectors(root)
        playfield = _playfield(root)
        assert "        - Mode: Survival" in playfield
        assert '          Items: [ \n          "CombatKnife",' in playfield
        assert "Start Location:" in playfield          # fiche du menu
        assert "Vast oceans cover the planet." in playfield
        assert len(main.pushed) == 1
        assert len(main.pushed[0].entries) == 2        # Sectors + playfield
    finally:
        sip.delete(dialog)


def test_dialog_warns_about_unknown_items(qapp, tmp_path, monkeypatch):
    """Faute de frappe dans un item : le jeu l'ignorerait en silence, l'apercu
    le signale (sans bloquer l'application)."""
    from PyQt6 import sip
    root = _build(tmp_path)
    conf = root / "Content" / "Configuration"
    conf.mkdir(parents=True)
    (conf / "ItemsConfig.ecf").write_text(
        "{ +Item Id: 1, Name: SurvivalTool }\n", encoding="utf-8")
    dialog = _dialog(monkeypatch, root)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog.items_edit.setPlainText("SurvivalToolx: 5\n\n\n")
        dialog._preview()
        assert "inconnu" in dialog.status.text()
        assert dialog.btn_apply.isEnabled()          # avertissement, pas blocage
    finally:
        sip.delete(dialog)


def test_dialog_warns_on_untested_starts(qapp, tmp_path, monkeypatch):
    """Un depart jamais joue est « a tester » : le client peut refuser sa
    donnee au menu (vecu 05/11 sur Lava ET StarterRandom_Arid_V2, donnees du
    mod intactes) — l'apercu doit le dire avant l'ecriture."""
    from PyQt6 import sip
    root = _build(tmp_path)
    dialog = _dialog(monkeypatch, root)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog.card_check.setChecked(False)
        dialog._preview()
        assert "non validé" in dialog.status.text()
        assert "Eden" in dialog.status.text()
        assert dialog.btn_apply.isEnabled()          # avertissement, pas blocage
    finally:
        sip.delete(dialog)


def test_dialog_writes_the_shown_kit_when_the_planet_has_none(
        qapp, tmp_path, monkeypatch):
    """Activer un depart SANS kit = joueur sans items : le kit affiche dans
    les editeurs (repli Akua) doit etre ecrit a l'activation, sans edition."""
    from PyQt6 import sip
    root = _build(tmp_path)
    dialog = _dialog(monkeypatch, root)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog.card_check.setChecked(False)
        dialog._apply()
        playfield = _playfield(root)
        assert "        - Mode: Survival" in playfield
        assert "SurvivalTool" in playfield            # kit Akua de repli
        assert "#FreshStart:" in playfield
        assert "1 kit(s)" in dialog.status.text()
    finally:
        sip.delete(dialog)


def test_dialog_ignores_a_visited_but_unchanged_kit(qapp, tmp_path, monkeypatch):
    """Un depart deja coche, kit existant non modifie : aucune ecriture dans
    le playfield (l'activation d'Akua ne doit pas reecrire son kit)."""
    from PyQt6 import sip
    root = _build(tmp_path)
    before = _playfield(root, "Starter_Akua_V2")
    dialog = _dialog(monkeypatch, root)
    try:
        akua = _row_index(dialog, "Akua")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(akua))
        dialog.tree.topLevelItem(akua).setCheckState(0, Qt.CheckState.Checked)
        dialog.card_check.setChecked(False)
        dialog._apply()
        assert "Rien à appliquer" in dialog.status.text()
        assert _playfield(root, "Starter_Akua_V2") == before
    finally:
        sip.delete(dialog)


def test_dialog_canvas_renders_the_menu_card(qapp, tmp_path, monkeypatch):
    """Canevas : la carte telle que le jeu la lira, balisage converti."""
    from PyQt6 import sip
    root = _build(tmp_path)
    dialog = _dialog(monkeypatch, root)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        assert "Start Location:" in dialog.card_view.toPlainText()
        assert "Vast oceans cover the planet." in dialog.card_view.toPlainText()
        assert "color:#" in dialog.card_view.toHtml()      # balisage converti
        dialog.card_check.setChecked(False)
        assert "Start Location:" not in dialog.card_view.toPlainText()
        assert "Vast oceans cover the planet." in dialog.card_view.toPlainText()
    finally:
        sip.delete(dialog)


def test_dialog_leaves_an_unchanged_kit_untouched(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    root = _build(tmp_path)
    before = _playfield(root, "Starter_Akua_V2")
    dialog = _dialog(monkeypatch, root)
    try:
        akua = _row_index(dialog, "Akua")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(akua))
        dialog.tree.topLevelItem(akua).setCheckState(0, Qt.CheckState.Unchecked)
        dialog._apply()
        # desactive le depart, sans reecrire le playfield (kit inchange)
        assert "['0, 0, 0', Akua, Starter_Akua_V2,'', '', '', '']" in _sectors(root)
        assert _playfield(root, "Starter_Akua_V2") == before
    finally:
        sip.delete(dialog)


def test_dialog_keeps_the_card_off_when_unchecked(qapp, tmp_path, monkeypatch):
    from PyQt6 import sip
    root = _build(tmp_path)
    dialog = _dialog(monkeypatch, root)
    try:
        eden = _row_index(dialog, "Eden")
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(eden))
        dialog.tree.topLevelItem(eden).setCheckState(0, Qt.CheckState.Checked)
        dialog.card_check.setChecked(False)
        dialog._apply()
        assert "'Human:1'" in _sectors(root)
        assert "Start Location:" not in _playfield(root)
    finally:
        sip.delete(dialog)
