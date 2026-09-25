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

"""Dialogue de controle des blueprints .epb : construction (PyQt6 : une
exception en slot = crash natif, teste obligatoirement) + cycle d'analyse
complet sur un .epb synthetique."""

import struct

import pytest

from core.i18n import t

from gui.epb_check_dialog import EpbCheckDialog
from test_epb_blueprint import build_epb


@pytest.fixture
def bp_file(tmp_path):
    return build_epb(tmp_path / "test.epb")


@pytest.fixture
def ecf(tmp_path):
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n", encoding="utf-8")
    return ecf


def test_dialog_construction(qapp, bp_file, ecf):
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    # le champ de chemin demarre VIDE (retour utilisateur 23/09 : un long
    # chemin de test restait affiche d'une session a l'autre)
    assert dlg.path_edit.text() == ""
    assert dlg.path_edit.placeholderText() != ""
    assert dlg.btn_analyze.isEnabled()
    assert not dlg.btn_remove.isEnabled()


def t_unknown_count(n: int) -> str:
    from core.i18n import t
    return t("epb.unknown_count", n=n)


def test_dialog_analyze_and_removal_flag(qapp, bp_file, ecf, monkeypatch):
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    assert dlg.tree.topLevelItemCount() == 1
    item = dlg.tree.topLevelItem(0)
    assert item.text(1) == "3"
    assert item.text(2) == t_unknown_count(2)
    # arbre complet : TOUS les ids listes (412 connu + 2050/7500 inconnus)
    assert item.childCount() == 3
    unknown_children = [item.child(i) for i in range(item.childCount())
                        if item.child(i).text(2) == t("epb.unknown_tag")]
    assert sorted(c.text(3) for c in unknown_children) == ["2050", "7500"]
    assert dlg.btn_remove.isEnabled()


def test_dialog_analyze_all_ok(qapp, tmp_path, monkeypatch):
    # blueprint ne referencant QUE des blocs connus du catalogue
    from core.epb_blueprint import EpbBlueprint
    p = build_epb(tmp_path / "ok.epb", cells={0: 412})
    dlg = EpbCheckDialog(None, catalog_paths=[str(_ecf_with(412, tmp_path))])
    dlg.path_edit.setText(str(p))
    dlg._analyze()
    assert dlg.tree.topLevelItemCount() == 1
    assert "aucun" in dlg.tree.topLevelItem(0).text(2)
    assert not dlg.btn_remove.isEnabled()


def test_main_window_epb_catalog_paths_use_working_root(tmp_path, monkeypatch):
    """LE bug des 4 tentatives (v1.11.0 -> v1.12.0) : le dialogue recevait
    str(workspace.working) — la REPRESENTATION d'un objet WorkingCopy, pas
    un chemin — donc le repertoire du scenario n'a jamais figure dans le
    catalogue (analyse en vanille seule, 1891 ids) et CPUExtenderCVT4 /
    CoreNoCPU n'etaient jamais marques inconnu/interdit."""
    import types

    from gui.main_window import MainWindow
    fake_self = types.SimpleNamespace(
        workspace=types.SimpleNamespace(working_root=tmp_path))
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(tmp_path / "vanilla_content"))
    assert MainWindow._epb_catalog_paths(fake_self) == [
        str(tmp_path / "vanilla_content" / "Configuration"),
        str(tmp_path / "Content" / "Configuration")]
    # sans projet ouvert : la vanille seule, explicitement
    fake_solo = types.SimpleNamespace(workspace=None)
    assert MainWindow._epb_catalog_paths(fake_solo) == [
        str(tmp_path / "vanilla_content" / "Configuration")]


def test_analyze_applies_problem_filter_and_selects_first(qapp, bp_file, ecf):
    """Vecu 23/09 (v2) : les lignes colorees etaient rendues mais HORS ECRAN
    (enterrees en bas des lignes triees par quantite) et le filtre
    « problemes uniquement » coche par defaut n'etait jamais applique.
    Apres analyse : filtre actif, problemes visibles, connus masques,
    premiere ligne probleme selectionnee."""
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    assert dlg.chk_problems.isChecked()
    item = dlg.tree.topLevelItem(0)
    assert not item.isHidden()
    states = {c.text(3): c.isHidden() for i in range(item.childCount())
              for c in [item.child(i)]}
    assert states["412"] is True            # connu : masque par le filtre
    assert states["2050"] is False          # inconnu : visible (rouge)
    assert states["7500"] is False          # inconnu : visible (rouge)
    current = dlg.tree.currentItem()
    assert current is not None and current.text(2) == t("epb.unknown_tag")


def test_analyze_clean_auto_unchecks_filter(qapp, tmp_path):
    """Blueprint totalement propre : le filtre ne laisserait qu'un arbre
    vide — il est decoche automatiquement pour montrer le resultat."""
    p = build_epb(tmp_path / "ok.epb", cells={0: 412})
    dlg = EpbCheckDialog(None, catalog_paths=[str(_ecf_with(412, tmp_path))])
    dlg.path_edit.setText(str(p))
    dlg._analyze()
    assert not dlg.chk_problems.isChecked()
    item = dlg.tree.topLevelItem(0)
    assert not item.isHidden()
    assert all(not item.child(i).isHidden()
               for i in range(item.childCount()))


def test_dialog_replace_then_save(qapp, bp_file, ecf):
    from core.epb_blueprint import EpbBlueprint
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    item = dlg.tree.topLevelItem(0)
    child = next(item.child(i) for i in range(item.childCount())
                 if item.child(i).text(3) == "2050")
    dlg.tree.setCurrentItem(child)      # declenche le panneau de remplacement
    assert dlg.combo_replace.isEnabled()
    idx = dlg.combo_replace.findData(412)
    assert idx >= 0
    dlg.combo_replace.setCurrentIndex(idx)
    dlg._replace_current()

    # en memoire : plus d'inconnu pour 2050, sauvegarde proposee
    assert dlg.btn_save.isEnabled()
    dlg._save_modified()
    assert not dlg.btn_save.isEnabled()

    after = EpbBlueprint(bp_file).parse()
    assert sorted(b.block_id for b in after.blocks) == [412, 412, 7500]
    item = dlg.tree.topLevelItem(0)
    assert item.childCount() == 2       # 412 (agrege) + 7500


def test_dialog_block_click_updates_label(qapp, bp_file, ecf):
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
    # clic sur un bloc inconnu : nom via le mapping blueprint (absent ici)
    dlg._on_block_clicked({"id": 7500})
    assert "7500" in dlg.lbl_block.text()
    # clic sur un bloc connu : nom du catalogue
    dlg._on_block_clicked({"id": 412})
    assert "412" in dlg.lbl_block.text() and "HullTest" in dlg.lbl_block.text()
    # clic dans le vide : retour au message par defaut
    dlg._on_block_clicked(None)
    assert dlg.lbl_block.text() == t_no_selection()


def t_no_selection() -> str:
    from core.i18n import t
    return t("epb.no_selection")


def test_view_block_at_hits_projected_point(qapp, bp_file):
    from gui.epb_view_3d import EpbView3D
    view = EpbView3D()
    view.resize(320, 320)
    view.set_data((3, 2, 2), [], known_ids=None)
    # stream vide : bloc_at doit repondre None hors donnees
    assert view.block_at(10, 10) is None

    blocks = [EpbBlockLike(0, 0, 0, 412), EpbBlockLike(2, 1, 1, 7500)]
    view.set_data((3, 2, 2), blocks, known_ids=None)
    pts = view._content_points(view._zoom, *view._origin)
    assert pts, "points projetes absents"
    sx, sy, _depth, bid = pts[0]
    assert view.block_at(sx, sy) == bid
    assert view.block_at(-5000, -5000) is None


def test_resolve_replacement_free_text(qapp, bp_file, ecf):
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
    dlg._refresh_replace_panel()
    # saisie libre : id numerique, nom exact (insensible casse), nom partiel
    assert dlg._resolve_replacement("412") == 412
    assert dlg._resolve_replacement("hulltest") == 412
    assert dlg._resolve_replacement("HullTest (412)") == 412
    assert dlg._resolve_replacement("hull") == 412
    assert dlg._resolve_replacement("inconnu_au_bataillon") is None
    # le combo est editable avec un completer installe
    assert dlg.combo_replace.isEditable()


def test_replace_combo_sorted_alphabetically(qapp, tmp_path):
    """Demande 24/09/2026 : la liste triee PAR NOM — en tapant « core »,
    tous les blocs contenant core apparaissent groupes."""
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 900, Name: Zed\n}\n"
                   "{ Block Id: 558, Name: CoreB\n}\n"
                   "{ Block Id: 2050, Name: CoreA\n}\n"
                   "{ Block Id: 412, Name: HullTest\n}\n", encoding="utf-8")
    p = build_epb(tmp_path / "b.epb", cells={0: 412})
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(p))
    dlg._analyze()
    dlg._populate_replace_combo()
    items = [dlg.combo_replace.itemText(i)
             for i in range(dlg.combo_replace.count())]
    assert items == sorted(items, key=str.lower)
    core_idx = [i for i, txt in enumerate(items) if "core" in txt.lower()]
    assert core_idx == list(range(core_idx[0], core_idx[0] + len(core_idx)))


def test_replace_corenocpu_with_core_via_typed_text(qapp, tmp_path):
    """Flux exact vecu 24/09 : CoreNoCPU -> « Core (558) ». Apres
    remplacement, le bloc ne doit PLUS etre inconnu (mapping embarque mis
    a jour) et le .epb sauvegarde doit recharger avec le mapping Core."""
    from core.epb_blueprint import EpbBlueprint
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n"
                   "{ Block Id: 558, Name: Core\n}\n", encoding="utf-8")
    p = build_epb(tmp_path / "anubis.epb", cells={0: 7, 5: 999},
                  mapping={7: "HullTest", 999: "CoreNoCPU"})
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(p))
    dlg._analyze()
    item = dlg.tree.topLevelItem(0)
    child = next(item.child(i) for i in range(item.childCount())
                 if item.child(i).text(3) == "999")
    dlg.tree.setCurrentItem(child)
    dlg.combo_replace.setEditText("Core (558)")
    dlg._replace_current()
    # plus aucun inconnu : 999 -> 558 connu via le mapping mis a jour
    assert dlg._targets[0]["unknown"] == {}
    assert dlg._targets[0]["bp"].id_mapping[558] == "Core"
    assert 999 not in dlg._targets[0]["bp"].id_mapping
    dlg._save_modified()
    after = EpbBlueprint(p, ecf_paths=[ecf]).parse()
    assert after.id_mapping == {7: "HullTest", 558: "Core"}
    assert after.unknown_counts({412, 558}, {"HullTest", "Core"}) == {}


def test_dialog_replace_via_typed_text(qapp, bp_file, ecf):
    from core.epb_blueprint import EpbBlueprint
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    item = dlg.tree.topLevelItem(0)
    child = next(item.child(i) for i in range(item.childCount())
                 if item.child(i).text(3) == "7500")
    dlg.tree.setCurrentItem(child)
    dlg.combo_replace.setEditText("HullTest")
    dlg._replace_current()
    assert dlg.btn_save.isEnabled()
    dlg._save_modified()                      # sauvegarde explicite
    after = EpbBlueprint(bp_file).parse()
    assert sorted(b.block_id for b in after.blocks) == [412, 412, 2050]


def test_color_index_dialog(qapp, bp_file, ecf):
    from PyQt6.QtWidgets import QDialog, QListWidget
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp_file))
    dlg._analyze()
    dlg._current_target = dlg._targets[0]
    index_dlg = dlg._build_color_index_dialog()
    assert isinstance(index_dlg, QDialog)
    lst = index_dlg.findChild(QListWidget)
    assert lst is not None and lst.count() == 3    # 3 ids distincts


def test_forbidden_by_name_via_mapping(qapp, tmp_path):
    """Cas RE2 ATL vecu : un bloc interdit (AllowedInBlueprint: false, SANS
    Id) reference par un blueprint a mapping embarque. Les ids des cellules
    etant LOCAUX, la detection doit se faire PAR NOM (CoreNoCPU)."""
    from core.epb_blueprint import load_block_catalog
    ecf = tmp_path / "BlocksConfig.ecf"
    ecf.write_text("{ Block Id: 412, Name: HullTest\n}\n"
                   "{ Block Name: CoreNoCPU, AllowedInBlueprint: false\n}\n",
                   encoding="utf-8")
    bp = build_epb(tmp_path / "anubis.epb",
                   cells={0: 7, 5: 999},
                   mapping={7: "HullTest", 999: "CoreNoCPU"})
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.path_edit.setText(str(bp))
    dlg._analyze()
    assert dlg.catalog.forbidden == set()
    assert dlg.catalog.forbidden_names == {"CoreNoCPU"}
    item = dlg.tree.topLevelItem(0)
    child = next(item.child(i) for i in range(item.childCount())
                 if item.child(i).text(3) == "999")
    assert child.text(2) == t("epb.forbidden_tag")
    assert child.text(4) == "CoreNoCPU"
    # ni inconnu : le nom existe dans les ECF fusionnes
    assert dlg._targets[0]["unknown"] == {}
    assert dlg._targets[0]["forb"] == {999: 1}
    # filtre 'problemes uniquement' (actif par defaut, applique au refresh) :
    # le bloc interdit reste visible, le bloc connu est masque
    dlg._apply_filter()
    assert not child.isHidden()
    known = next(item.child(i) for i in range(item.childCount())
                 if item.child(i).text(3) == "7")
    assert known.isHidden()


def test_tagged_rows_render_under_theme_stylesheet(qapp, bp_file, ecf):
    """REPRODUCTION DU VECU : avec la feuille de style du theme appliquee,
    QStyleSheetStyle ignore les roles Background/Foreground des items
    (lignes restees blanches dans l'appli alors que les tests hors ecran
    sans theme voyaient du rouge). Le delegate doit peindre lui-meme :
    le fond sombre de l'inconnu doit etre REELLEMENT rendu."""
    from core.themes import DEFAULT_THEME_ID, get_palette
    from gui.theme import build_stylesheet
    from gui.epb_check_dialog import _UNKNOWN_BG
    dlg = EpbCheckDialog(None, catalog_paths=[str(ecf)])
    dlg.setStyleSheet(build_stylesheet(get_palette(DEFAULT_THEME_ID)))
    # 30 cellules d'un id inconnu -> premiere ligne enfant tagguee rouge
    bp = build_epb(bp_file.parent / "many.epb",
                   cells={i: 2050 for i in range(30)}, size=(5, 5, 2))
    dlg.path_edit.setText(str(bp))
    dlg._analyze()
    dlg.tree.expandAll()
    dlg.tree.resize(800, 400)
    img = dlg.tree.grab().toImage()
    target = _UNKNOWN_BG.color().rgb() & 0xFFFFFF
    hits = sum(1 for x in range(0, img.width(), 2)
               for y in range(0, img.height(), 2)
               if img.pixel(x, y) & 0xFFFFFF == target)
    assert hits >= 40, f"fond inconnu absent sous theme ({hits} px)"


class EpbBlockLike:
    """Mini substitut d'EpbBlock pour la vue (x, y, z, id)."""

    def __init__(self, x, y, z, block_id):
        self.x, self.y, self.z = x, y, z
        self.block_id = block_id


def test_view_3d_render_and_signal(qapp, bp_file):
    from PyQt6.QtCore import Qt
    from core.epb_blueprint import EpbBlock
    from gui.epb_view_3d import EpbView3D
    view = EpbView3D()
    view.resize(300, 300)
    blocks = [EpbBlock(0, 0, 0, 412, 0, 0),
              EpbBlock(1, 1, 0, 7500, 0, 0)]
    view.set_data((2, 2, 1), blocks, known_ids={412})
    pm = view.grab()
    assert not pm.isNull() and pm.size().width() > 0
    # pivoter ne doit pas lever
    view.set_quarter(1)
    assert view.get_quarter() == 1


def _ecf_with(bid: int, tmp_path):
    ecf = tmp_path / f"BlocksConfig_{bid}.ecf"
    ecf.write_text(f"{{ Block Id: {bid}, Name: Bloc{bid}\n}}\n",
                   encoding="utf-8")
    return ecf
