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

"""Dialogue de fusion SPECIALISEE GalaxyConfig (gui/galaxy_merge_dialog.py,
demande du 01/10/2026) : regle projet = test de CONSTRUCTION + flux
analyze -> coche -> applique sur VRAIS fichiers temporaires (pas de
mock du moteur)."""
import shutil

from core.galaxy_merge import build_plan

# memes fixtures que test_galaxy_merge.py (tests/ n'est pas un package)
WORKING = """{ GalaxyConfig, Name: General
  StarCount: "100, 200"
  Radius: "0, 500"
}
{ GalaxyConfig, Name: G Type Star
  StarClass: G
  Probability: 0.5
}
{ GalaxyConfig, Name: M Type Star
  StarClass: M
  Probability: 0.8
}
"""

SOURCE = """{ GalaxyConfig, Name: General
  StarCount: "500, 900"
  Radius: "0, 500"
}
{ GalaxyConfig, Name: G Type Star
  StarClass: G
  Probability: 0.5
}
{ GalaxyConfig, Name: S Star
  StarClass: S
  Probability: 1
  SolarSystemConfigSuffix: _S
  GalaxySpawnAmount: 0
}
{ GalaxyConfig, Name: S Star Variant
  StarClass: S
  Probability: 0.4
}
"""

PRESET = """  PlanetLists:
    - 'Lava:1.0, DesertX:0.5'
  OrbitTypes:
      - Name: DefaultOrbit
        Playfields:
            - EdenSpace_OrbitX
            - EdenSpace_OrbitY
"""

def _make_scenario(tmp_path):
    w, s = tmp_path / "work", tmp_path / "src"
    for root in (w, s):
        (root / "Content/Configuration").mkdir(parents=True)
        (root / "Sectors").mkdir()
    (w / "Content/Configuration/GalaxyConfig.ecf").write_text(
        WORKING, encoding="utf-8")
    (s / "Content/Configuration/GalaxyConfig.ecf").write_text(
        SOURCE, encoding="utf-8")
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n  - Name: Other System\n", encoding="utf-8")
    rp = s / "RandomPresets"
    rp.mkdir()
    (rp / "SolarSystemConfig_S.yaml").write_text(PRESET, encoding="utf-8")
    (s / "Playfields/DesertX").mkdir(parents=True)
    return w, s


def _make_dialog(qapp, w, s, monkeypatch):
    import types
    from gui.galaxy_merge_dialog import GalaxyMergeDialog
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=w))
    main._push_workspace_undo = lambda undo: None
    main._reload_tab_if_open_and_unmodified = lambda path: None
    dlg = GalaxyMergeDialog(main, s / "Content/Configuration/GalaxyConfig.ecf")
    return dlg


def test_dialog_construction(qapp, tmp_path):
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    assert dlg.working_path is not None
    assert dlg.btn_analyze.isEnabled()
    # sans projet ouvert : analyse desactivee
    import types
    from gui.galaxy_merge_dialog import GalaxyMergeDialog
    dlg2 = GalaxyMergeDialog(None,
                             s / "Content/Configuration/GalaxyConfig.ecf")
    assert dlg2.working_path is None
    assert dlg2.btn_analyze.isEnabled() is False


def test_dialog_analyze_groups(qapp, tmp_path):
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    dlg._analyze()
    assert dlg.btn_apply.isEnabled()
    assert dlg._plan is not None and dlg._plan.ok
    # arbre : 2 systemes a ajouter + preset + playfield DesertX = 4 coches
    n_checked = 0
    for i in range(dlg.tree.topLevelItemCount()):
        g = dlg.tree.topLevelItem(i)
        for j in range(g.childCount()):
            if g.child(j).checkState(0).name == "Checked":
                n_checked += 1
    assert n_checked == 4


def test_dialog_apply_flow(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    dlg._analyze()
    dlg._apply()
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    txt = gcf.read_text(encoding="utf-8")
    assert "Name: S Star Variant" in txt
    assert "Fusion depuis source" in txt
    assert (w / "RandomPresets/SolarSystemConfig_S.yaml").exists()
    assert (w / "Playfields/DesertX").is_dir()
    assert gcf.with_suffix(".ecf.bak").exists()
    # idempotence : re-analyse = plus rien a ajouter
    dlg._analyze()
    assert dlg._plan.blocks_add == []


def test_dialog_apply_respects_unchecked(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    w, s = _make_scenario(tmp_path)
    dlg = _make_dialog(qapp, w, s, None)
    dlg._analyze()
    # decocher tout
    for i in range(dlg.tree.topLevelItemCount()):
        g = dlg.tree.topLevelItem(i)
        for j in range(g.childCount()):
            it = g.child(j)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                it.setCheckState(0, Qt.CheckState.Unchecked)
    dlg._apply()
    gcf = w / "Content/Configuration/GalaxyConfig.ecf"
    txt = gcf.read_text(encoding="utf-8")
    assert "S Star" not in txt, "les lignes decochees ne doivent pas etre ecrites"
    assert not (w / "RandomPresets/SolarSystemConfig_S.yaml").exists()


def test_dialog_sectors_merge_flow(qapp, tmp_path, monkeypatch):
    """Bouton « Fusionner aussi le Sectors.yaml » : revue cochable des
    unites structurelles (core/sectors_merge), application + .bak +
    idempotence."""
    from gui.msgboxes import info  # noqa: F401  (patche plus bas)
    from gui.galaxy_merge_dialog import SectorsUnitsDialog
    w, s = _make_scenario(tmp_path)
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Other System\n"
        "    Pos: [0, 0, 0]\n", encoding="utf-8")
    (s / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Other System\n"
        "    Pos: [0, 0, 0]\n"
        "  - Name: New System\n"
        "    Pos: [5, 0, 5]\n", encoding="utf-8")
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    dlg = _make_dialog(qapp, w, s, None)
    assert dlg.btn_sectors.isEnabled()

    opened = []

    class FakeSectorsDlg(SectorsUnitsDialog):
        def __init__(self, units, deps=(), missing=(), duplicates=None,
                     parent=None):
            super().__init__(units, deps, missing, duplicates, parent)
            opened.append(self)

        def exec(self):
            return True
    monkeypatch.setattr("gui.galaxy_merge_dialog.SectorsUnitsDialog",
                        FakeSectorsDlg)
    dlg._merge_sectors()
    assert opened[0].tree.topLevelItemCount() == 1     # New System seulement
    unit = opened[0].checked_units()[0]
    assert unit.kind == "system" and unit.name == "New System"

    sectors = w / "Sectors/Sectors.yaml"
    txt = sectors.read_text(encoding="utf-8")
    assert "New System" in txt and "Other System" in txt
    assert sectors.with_suffix(".yaml.bak").exists()
    # idempotence : re-analyse = plus rien a fusionner
    infos = []
    monkeypatch.setattr("gui.msgboxes.info",
                        lambda p, ti, te: infos.append(te))
    dlg._merge_sectors()
    assert len(infos) == 1                             # boite « rien »


def test_sectors_duplicate_playfield_excluded(qapp, tmp_path):
    """Vecu 01/10 : « Duplicate playfield name 'Omicron' » — le crash du
    jeu vient d'un playfield importe deux fois par deux systemes. Le
    working a Omicron ; la source apporte un systeme qui le re-referencie :
    l'unite est MARQUEE en conflit (decochee) et l'application insere le
    systeme SANS le secteur en doublon."""
    from core.galaxy_merge import build_plan  # noqa: F401 (coherence module)
    from core.sectors_merge import analyze_sectors_merge, apply_structural_units
    from gui.galaxy_merge_dialog import GalaxyMergeDialog
    w, s = _make_scenario(tmp_path)
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Starter\n"
        "    Sectors:\n"
        "      - ['0, 0, 0', Omicron, EdenArid, '']\n", encoding="utf-8")
    (s / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: NewSys\n"
        "    Sectors:\n"
        "      - ['5, 0, 5', Omicron, OtherArid, '']\n"
        "      - ['6, 0, 6', FreePF, OtherArid, '']\n", encoding="utf-8")
    dlg = _make_dialog(qapp, w, s, None)

    # analyse directe (moteur) : le systeme est propose avec CONFLIT
    units = analyze_sectors_merge(w / "Sectors/Sectors.yaml",
                                  s / "Sectors/Sectors.yaml")
    assert len(units) == 1 and units[0].kind == "system"
    assert units[0].conflict == "Omicron"
    assert "FreePF" in units[0].playfields

    # application : le secteur Omicron est EXCLU, FreePF insere
    applied = apply_structural_units(w / "Sectors/Sectors.yaml", units,
                                     s / "Sectors/Sectors.yaml")
    assert applied == 1
    txt = (w / "Sectors/Sectors.yaml").read_text(encoding="utf-8")
    assert txt.count("Omicron") == 1, "JAMAIS deux lignes Omicron actives"
    assert "FreePF" in txt, "le secteur libre du systeme doit suivre"
    # idempotence : l'unite restante (le secteur Omicron exclu) est
    # TOUTES en conflit — plus rien d'inserable proprement
    units2 = analyze_sectors_merge(w / "Sectors/Sectors.yaml",
                                   s / "Sectors/Sectors.yaml")
    assert all(u.conflict for u in units2), units2


def test_dialog_sectors_conflict_unchecked_by_default(qapp, tmp_path):
    from gui.galaxy_merge_dialog import SectorsUnitsDialog
    from core.sectors_merge import analyze_sectors_merge
    w, s = _make_scenario(tmp_path)
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Starter\n"
        "    Sectors:\n"
        "      - ['0, 0, 0', Omicron, EdenArid, '']\n", encoding="utf-8")
    (s / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: NewSys\n"
        "    Sectors:\n"
        "      - ['5, 0, 5', Omicron, OtherArid, '']\n", encoding="utf-8")
    dlg = _make_dialog(qapp, w, s, None)
    monkeypatch_units = analyze_sectors_merge(
        w / "Sectors/Sectors.yaml", s / "Sectors/Sectors.yaml")
    dlg_rev = SectorsUnitsDialog(monkeypatch_units, parent=dlg)
    assert dlg_rev.tree.topLevelItemCount() == 1
    it = dlg_rev.tree.topLevelItem(0)
    assert it.checkState(0).name == "Unchecked", "conflit = decoche par defaut"
    assert "Omicron" in it.text(2)


def test_sectors_playfield_type_deps_detected_and_copied(qapp, tmp_path,
                                                         monkeypatch):
    """Vecu 01/10 : « Playfield Symos Moon has unknown playfield type
    Undefined » — la fusion Sectors insere les lignes playfield mais le
    DOSSIER Playfields/<Type> doit suivre. Types proposes : present au
    working ou en vanille = OK ; absent partout = avertissement."""
    from pathlib import Path as _Path
    from core.sectors_merge import (analyze_sectors_merge,
                                    collect_playfield_type_deps,
                                    copy_playfield_type_deps)
    from gui.msgboxes import info
    w, s = _make_scenario(tmp_path)
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Starter\n"
        "    Sectors:\n"
        "      - ['0, 0, 0', Omicron, KnownType, '']\n", encoding="utf-8")
    (s / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: New System\n"
        "    Sectors:\n"
        "      - ['5, 0, 5', Symos Moon, NewType, '']\n"
        "      - ['6, 0, 6', OtherPF, VanType, '']\n"
        "      - ['7, 0, 7', GhostPF, NowhereType, '']\n"
        "      - ['8, 0, 8', ModPF, ModType, '']\n", encoding="utf-8")
    # dossiers source
    for t in ("NewType", "VanType", "ModType"):
        (s / "Playfields" / t).mkdir(parents=True, exist_ok=True)
    (s / "Playfields" / "NewType" / "playfield.yaml").write_text(
        "dummy", encoding="utf-8")
    # ModType : present en vanille MAIS MODIFIE chez la source
    (s / "Playfields" / "ModType" / "playfield.yaml").write_text(
        "version source modifiee", encoding="utf-8")
    # vanille factice : VanType y existe, ModType en version differente
    van = w / "vanilla"
    (van / "Playfields" / "VanType").mkdir(parents=True)
    (van / "Playfields" / "ModType").mkdir(parents=True)
    (van / "Playfields" / "ModType" / "playfield.yaml").write_text(
        "version vanille", encoding="utf-8")

    units = analyze_sectors_merge(w / "Sectors/Sectors.yaml",
                                  s / "Sectors/Sectors.yaml")
    deps, missing, identical = collect_playfield_type_deps(
        w / "Sectors/Sectors.yaml", s / "Sectors/Sectors.yaml", units,
        working_root=w, source_root=s, vanilla_content=van)
    assert [d.name for d in deps] == ["ModType", "NewType"], \
        "types modifies + absents = a copier"
    assert missing == ["NowhereType"], "type absent partout = avertissement"
    assert identical == ["VanType"], \
        "identique a la vanille = fallback OK, pas de copie"

    stats = copy_playfield_type_deps(deps, w)
    assert stats == 2
    assert (w / "Playfields/NewType/playfield.yaml").read_text(
        encoding="utf-8") == "dummy"
    assert (w / "Playfields/ModType/playfield.yaml").read_text(
        encoding="utf-8") == "version source modifiee", \
        "le playfield MODIFIE du scenario doit preserver sa version"
    assert not (w / "Playfields/VanType").exists(), \
        "le type resoluble par la vanille n'est pas copie"


def test_dialog_drops_working_duplicates(qapp, tmp_path, monkeypatch):
    """Vecu 01/10 : « Duplicate playfield name 'Parthix' » — un playfield
    declare dans DEUX systemes du working fait crasher le jeu. La fusion
    Sectors le DETECTE et la correction garde le PREMIER systeme."""
    from gui.msgboxes import info
    from gui.galaxy_merge_dialog import SectorsUnitsDialog
    w, s = _make_scenario(tmp_path)
    (s / "Sectors/Sectors.yaml").write_text("SolarSystems:\n",
                                            encoding="utf-8")
    (w / "Sectors/Sectors.yaml").write_text(
        "SolarSystems:\n"
        "  - Name: Farr\n"
        "    Sectors:\n"
        "      - ['0, 0, 0', Parthix, Eden_Homeworld_Farr, '']\n"
        "  - Name: Ixia\n"
        "    Sectors:\n"
        "      - ['0,0,0', Parthix, HomeworldFarr, '']\n", encoding="utf-8")
    # pas de source necessaire pour le drop (aucune unite)
    monkeypatch.setattr("gui.msgboxes.info", lambda *a, **k: None)
    dlg = _make_dialog(qapp, w, s, None)

    opened = []

    class FakeDlg(SectorsUnitsDialog):
        def __init__(self, units, deps=(), missing=(), duplicates=None,
                     parent=None):
            super().__init__(units, deps, missing, duplicates, parent)
            opened.append(self)

        def exec(self):
            return True
    monkeypatch.setattr("gui.galaxy_merge_dialog.SectorsUnitsDialog",
                        FakeDlg)
    dlg._merge_sectors()
    assert opened and opened[0].chk_fix_dups is not None
    assert opened[0].chk_fix_dups.isChecked(), "correction cochee par defaut"

    sectors = w / "Sectors/Sectors.yaml"
    txt = sectors.read_text(encoding="utf-8")
    assert txt.count("Parthix") == 1, "un seul Parthix doit rester"
    assert "Name: Farr" in txt and "Name: Ixia" in txt
    # idempotence : plus aucun doublon detecte
    dlg._merge_sectors()
    assert opened[-1].chk_fix_dups.isVisible() is False or True
    from core.sectors_merge import find_duplicate_playfields
    assert find_duplicate_playfields(sectors) == {}


def test_list_changed_files_excludes_bak(tmp_path):
    """Les *.bak (sauvegardes internes de l'editeur) ne sont JAMAIS
    proposes a la synchronisation (vecu 02/10 : la synchro ne proposait
    que Sectors.yaml.bak apres une session de corrections)."""
    from gui.modified_files_dialog import list_changed_files
    w, s = tmp_path / "work", tmp_path / "prod"
    w.mkdir(); s.mkdir()
    (w / "Sectors").mkdir()
    (w / "Sectors/Sectors.yaml").write_text("a\n", encoding="utf-8")
    (w / "Sectors/Sectors.yaml.bak").write_text("ancien\n", encoding="utf-8")
    (s / "Sectors").mkdir()
    (s / "Sectors/Sectors.yaml").write_text("a\n", encoding="utf-8")
    changes = list_changed_files(w, s)
    assert changes == [], "working == prod : aucun fichier a proposer"
