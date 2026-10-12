# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""Assistant « Ajouter un POI » : insertion core (add_poi_block via le
moteur de fusion generique), import poi_units, construction du dialogue
et chemin connecte depuis l'arbre de la copie de travail."""

from pathlib import Path

BLOCK_RANDOM = ("- GroupName: NouveauPOI\n"
                "  Faction: Zirax\n"
                "  CountMinMax: [ 1, 1 ]\n"
                "  Properties:\n"
                "    - Key: RegenAfter\n"
                "      Value: 720\n")


def _write_pf(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


_PF_NO_POIS = ("# En-tete preserve\n"
               "AtmosphereLevel: 1\n"
               "Gravity: 0.85\n")

_PF_WITH_RANDOM = ("# En-tete preserve\n"
                   "AtmosphereLevel: 1\n"
                   "POIs:\n"
                   "    Random:\n"
                   "        - GroupName: Existante\n"
                   "          Faction: Zirax\n")


def test_add_poi_creates_pois_section(tmp_path):
    from core.poi_add import add_poi_block
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_NO_POIS)
    n = add_poi_block(pf, BLOCK_RANDOM, "Random")
    assert n >= 1
    out = pf.read_text(encoding="utf-8")
    assert "# En-tete preserve" in out          # commentaires preserved
    assert "POIs:" in out and "Random:" in out
    assert "GroupName: NouveauPOI" in out
    assert "GroupName: Existante" not in out
    # re-indentation calquee sur le fichier (8 espaces pour les items)
    assert "\n        - GroupName: NouveauPOI" in out


def test_add_poi_appends_to_existing_random(tmp_path):
    from core.poi_add import add_poi_block
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_WITH_RANDOM)
    assert add_poi_block(pf, BLOCK_RANDOM, "Random") >= 1
    out = pf.read_text(encoding="utf-8")
    assert "GroupName: Existante" in out
    assert "GroupName: NouveauPOI" in out
    assert out.index("Existante") < out.index("NouveauPOI")


_PF_EMPTY_RANDOM = ("# POI section vide + liste a 2 esp ailleurs (vecu\n"
                    "# Starter_Akua_V2 : le bloc finissait hors de Random)\n"
                    "AtmosphereLevel: 1\n"
                    "Groups:\n"
                    "  - Material: Stone\n"
                    "POIs:\n"
                    "    Random:\n"
                    "# commentaire col 0 DANS la section\n"
                    "\n"
                    "FixedPlayerStart:\n"
                    "    - Mode: Survival\n")


def test_add_poi_empty_random_section(tmp_path):
    """POIs/Random SANS aucun item + une liste a 2 esp ailleurs : le bloc
    doit arriver DANS Random (items plus indentes que la sous-cle), pas
    en enfant direct de POIs (vecu, 09/10)."""
    from core.poi_add import add_poi_block
    from core.yamllite.parser import parse_yaml_file
    from core.yaml_merge import (_child_entries, _identity, _seq_items,
                                 _top_entries)
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_EMPTY_RANDOM)
    assert add_poi_block(pf, BLOCK_RANDOM, "Random") >= 1
    doc = parse_yaml_file(pf)
    pois = next(e for e in _top_entries(doc) if e.key == "POIs")
    rnd = next(c for c in _child_entries(pois) if c.key == "Random")
    assert ("GroupName", "NouveauPOI") in [_identity(i) for i in
                                           _seq_items(rnd)]
    out = pf.read_text(encoding="utf-8")
    assert out.count("GroupName: NouveauPOI") == 1
    assert add_poi_block(pf, BLOCK_RANDOM, "Random") == 0


def test_add_poi_is_idempotent(tmp_path):
    from core.poi_add import add_poi_block
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_WITH_RANDOM)
    add_poi_block(pf, BLOCK_RANDOM, "Random")
    before = pf.read_bytes()
    assert add_poi_block(pf, BLOCK_RANDOM, "Random") == 0
    assert pf.read_bytes() == before


def test_add_poi_fixed_section(tmp_path):
    from core.poi_add import add_poi_block
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_WITH_RANDOM)
    block = ("- Name: MaBase\n"
             "  Type: BA_Alien\n"
             "  Prefab: BAF_X\n"
             "  Pos: [ 100, 35, -200 ]\n")
    assert add_poi_block(pf, block, "Fixed") >= 1
    out = pf.read_text(encoding="utf-8")
    assert "Fixed:" in out and "Prefab: BAF_X" in out
    # l'identite Fixed = Name (premiere cle), un 2e POI de meme Type passe
    block2 = block.replace("MaBase", "MaBase2")
    assert add_poi_block(pf, block2, "Fixed") >= 1


def test_poi_units_filter(tmp_path):
    from core.poi_add import poi_units
    dest = _write_pf(tmp_path / "Playfields" / "A" / "playfield_static.yaml",
                     _PF_WITH_RANDOM)
    src = _write_pf(
        tmp_path / "Playfields" / "B" / "playfield_static.yaml",
        "AtmosphereLevel: 2\n"
        "POIs:\n"
        "    Random:\n"
        "        - GroupName: Existante\n"
        "          Faction: Zirax\n"
        "        - GroupName: Importable\n"
        "          Faction: Pirates\n"
        "    Fixed:\n"
        "        - Name: FixeSource\n"
        "          Type: BA\n")
    units = poi_units(dest, src)
    names = {u.name for u in units}
    # Importable = item absent ; Fixed absente du dest = sous-liste ENTIERE
    # proposee (YAML-009), FixeSource voyage dedans
    assert "Importable" in names and "Fixed" in names
    assert "Existante" not in names              # deja present : propose non
    assert all(u.kind in ("key", "subkey", "item") for u in units)
    assert all(u.root.startswith("POIs")
               or (u.root == "" and u.name == "POIs") for u in units)


def test_scan_and_pool(tmp_path):
    from core.poi_add import field_pool, scan_playfield_statics, \
        scan_prefab_names
    _write_pf(tmp_path / "Playfields" / "A" / "playfield_static.yaml",
              _PF_WITH_RANDOM)
    (tmp_path / "Prefabs").mkdir()
    (tmp_path / "Prefabs" / "MonPrefab.epb").write_bytes(b"x")
    assert scan_playfield_statics(tmp_path) == [
        tmp_path / "Playfields" / "A" / "playfield_static.yaml"]
    assert scan_prefab_names(tmp_path / "Prefabs",
                             tmp_path / "Inexistant") == ["MonPrefab"]
    pf = tmp_path / "Playfields" / "A" / "playfield_static.yaml"
    assert field_pool(pf, "Faction") == ["Zirax"]
    assert field_pool(pf, "Inconnue") == []


# ------------------------------------------------------------------ GUI

def test_list_and_remove_pois(tmp_path):
    """list_pois voit tous les POIs ; remove_pois retire par IDENTITE,
    preserve le reste (commentaires inclus) et ne repasse pas deux fois."""
    from core.poi_add import list_pois, remove_pois
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   "# Entete\n"
                   "POIs:\n"
                   "    Random:\n"
                   "        - GroupName: GarderRandom\n"
                   "          Faction: Zirax\n"
                   "# commentaire entre POIs\n"
                   "        - GroupName: SupprimerMoi\n"
                   "          Faction: Pirates\n"
                   "    Fixed:\n"
                   "        - Name: GarderFixed\n"
                   "          Type: BA\n")
    pois = list_pois(pf)
    assert ("Random", ("GroupName", "GarderRandom"),
            "Faction: Zirax") in pois
    assert ("Random", ("GroupName", "SupprimerMoi"),
            "Faction: Pirates") in pois
    assert ("Fixed", ("Name", "GarderFixed"), "GarderFixed") in pois

    n = remove_pois(pf, {("Random", ("GroupName", "SupprimerMoi"))})
    assert n == 1
    out = pf.read_text(encoding="utf-8")
    assert "SupprimerMoi" not in out
    assert "GarderRandom" in out and "GarderFixed" in out
    assert "# commentaire entre POIs" in out      # le reste est intact
    # Fixed n'est pas touche par une cible Random
    assert remove_pois(pf, {("Fixed", ("Name", "Inexistant"))}) == 0
    assert remove_pois(pf, {("Random",
                             ("GroupName", "SupprimerMoi"))}) == 0


def test_dialog_remove_tab(qapp, tmp_path, monkeypatch):
    """Onglet Supprimer : rien de coche par defaut (jamais implicite),
    le plan porte les (section, identite) cochees, le bouton principal
    change de libelle."""
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    # _accept_plan sans selection ouvre la boite modale info() : bloquee
    import gui.msgboxes as msgboxes
    monkeypatch.setattr(msgboxes, "info", lambda *a, **k: None)
    from gui.poi_add_dialog import PoiAddDialog
    from core.i18n import t
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   "POIs:\n"
                   "    Random:\n"
                   "        - GroupName: Un\n"
                   "          Faction: Zirax\n"
                   "        - GroupName: Deux\n"
                   "          Faction: Pirates\n")
    dlg = PoiAddDialog(None, pf)
    dlg.tabs.setCurrentIndex(2)
    assert dlg.tree_remove.topLevelItemCount() == 2
    # decoche par defaut : accepter sans cocher est refuse (plan None)
    dlg._accept_plan()
    assert dlg.plan is None
    # cocher le 2e POI -> plan remove avec la bonne identite
    dlg.tree_remove.topLevelItem(1).setCheckState(
        0, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked)
    assert dlg.btn_add.text() == t("poi.remove_button")
    dlg._accept_plan()
    assert dlg.plan[0] == "remove"
    assert dlg.plan[1] == [("Random", ("GroupName", "Deux"))]


def test_dialog_construction_and_block(qapp, tmp_path, monkeypatch):
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    from gui.poi_add_dialog import PoiAddDialog
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_WITH_RANDOM)
    dlg = PoiAddDialog(None, pf, working_root=str(tmp_path))
    dlg.cb_prefab.setText("MonPrefab")
    assert dlg.cb_group.text() == "MonPrefab"    # GroupName pre-rempli
    assert dlg.plan is None
    # mode Random par defaut : bloc GroupName, apercu vivant
    assert "- GroupName: MonPrefab" in dlg.preview.toPlainText()
    assert dlg.rb_fixed.isChecked() is False
    # bascule Fixed : bloc Name d'abord (identite moteur), Prefab present
    dlg.rb_fixed.setChecked(True)
    txt = dlg.preview.toPlainText()
    assert txt.index("Name:") < txt.index("Prefab:")
    assert "Pos: [ 0, 0, 0 ]" in txt
    # plan new construit
    dlg._accept_plan()
    assert dlg.plan[0] == "new" and dlg.plan[1] == "Fixed"
    assert "Prefab: MonPrefab" in dlg.plan[2]


def test_dialog_import_flow(qapp, tmp_path, monkeypatch):
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    from gui.poi_add_dialog import PoiAddDialog
    dest = _write_pf(tmp_path / "Playfields" / "A" / "playfield_static.yaml",
                     _PF_WITH_RANDOM)
    src = _write_pf(tmp_path / "Playfields" / "B" / "playfield_static.yaml",
                    "POIs:\n"
                    "    Random:\n"
                    "        - GroupName: Importable\n"
                    "          Faction: Pirates\n")
    dlg = PoiAddDialog(None, dest, working_root=str(tmp_path))
    dlg.tabs.setCurrentIndex(1)
    assert dlg.cb_source.count() == 1            # le dest est exclu
    dlg._load_source()
    assert dlg.tree.topLevelItemCount() == 1
    assert dlg.tree.topLevelItem(0).text(1) == "Importable"
    dlg._accept_plan()
    assert dlg.plan[0] == "import"
    assert Path(dlg.plan[1]) == src
    assert [u.name for u in dlg.plan[2]] == ["Importable"]


def test_working_tree_context_menu_poi(qapp, tmp_path, monkeypatch):
    """Chemin connecte : clic droit sur un playfield_static dans l'arbre
    de la copie de travail -> assistant -> plan applique (ecriture reelle
    du fichier + undo espace de travail)."""
    import core.settings as settings
    import gui.fluent_pilot as fluent_pilot
    import gui.poi_add_dialog as poi_mod
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QMenu, QTreeWidgetItem
    from gui.main_window import MainWindow
    from gui.theme import apply_theme

    monkeypatch.setattr(settings, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    fluent_pilot.set_enabled(True)
    apply_theme(qapp, "classic")
    pf = _write_pf(tmp_path / "Playfields" / "Test" / "playfield_static.yaml",
                   _PF_NO_POIS)
    win = MainWindow()
    win.show()
    try:
        class _Working:
            root_path = tmp_path

        class _WS:
            working_root = str(tmp_path)
            working = _Working()

            def rescan_working(self):
                pass

        win.workspace = _WS()

        class _FakeDlg:
            plan = ("new", "Random", BLOCK_RANDOM)

            def __init__(self, parent, dest_yaml, working_root=None):
                assert Path(dest_yaml) == pf

            def exec(self):
                return 1                              # Accepted

        monkeypatch.setattr(poi_mod, "PoiAddDialog", _FakeDlg)
        item = QTreeWidgetItem([pf.name])
        item.setData(0, Qt.ItemDataRole.UserRole, ["file", pf])
        win.tree_working.addTopLevelItem(item)

        def fake_exec(menu, gpos):
            from core.i18n import t
            return next(a for a in menu.actions()
                        if a.text() == t("poi.add_action"))

        monkeypatch.setattr(QMenu, "exec", fake_exec)
        pos = win.tree_working.visualItemRect(item).center()
        win._show_working_context_menu(pos)

        out = pf.read_text(encoding="utf-8")
        assert "POIs:" in out and "GroupName: NouveauPOI" in out
        assert win.workspace_undo.can_undo()
    finally:
        win.close()
        fluent_pilot.set_enabled(False)
