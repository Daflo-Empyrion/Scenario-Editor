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

"""Dialogue « Comparer des bundles Unity » (gui/bundles_dialog.py,
demande du 29/09/2026) : regle projet = test de CONSTRUCTION + flux
compare (compare_bundles monkeyparche : pas besoin d'UnityPy) + erreurs
+ export CSV."""
import csv

from core.unity_bundles import BundleDiff


def _diff(added=1, removed=1, changed=1, same=700, na=None, nb=None):
    d = BundleDiff(na=na if na is not None else 700 + added,
                   nb=nb if nb is not None else 700 + added)
    for i in range(added):
        d.added[f"x/new{i}.prefab"] = "GameObject"
    for i in range(removed):
        d.removed[f"x/old{i}.prefab"] = "GameObject"
    for i in range(changed):
        d.changed[f"x/tex{i}.png"] = ("Texture2D", "Mesh")
    d.same = same
    return d


def test_dialog_construction(qapp):
    from gui.bundles_dialog import BundlesDialog
    dlg = BundlesDialog()
    assert dlg.btn_compare.isEnabled()
    assert dlg.btn_export.isEnabled() is False
    assert dlg.tree.columnCount() == 4


def test_dialog_compare_flow(qapp, monkeypatch, tmp_path):
    from gui.bundles_dialog import BundlesDialog
    monkeypatch.setattr("core.unity_bundles.compare_bundles",
                        lambda pa, pb: _diff())
    dlg = BundlesDialog()
    dlg.edits["a"].setText("A_bundle")
    dlg.edits["b"].setText("B_bundle")
    dlg._compare()
    assert dlg.tree.topLevelItemCount() == 3     # 1 ajout + 1 retrait + 1 type
    paths = {dlg.tree.topLevelItem(i).text(1)
             for i in range(dlg.tree.topLevelItemCount())}
    assert paths == {"x/new0.prefab", "x/old0.prefab", "x/tex0.png"}
    assert dlg.btn_export.isEnabled()
    assert "700" in dlg.status_label.text()
    assert dlg._diff.differences == 3


def test_dialog_compare_zero_assets_warns(qapp, monkeypatch):
    from gui.bundles_dialog import BundlesDialog
    monkeypatch.setattr("core.unity_bundles.compare_bundles",
                        lambda pa, pb: _diff(added=0, removed=0, changed=0,
                                             same=0, na=0, nb=0))
    dlg = BundlesDialog()
    dlg.edits["a"].setText("A")
    dlg.edits["b"].setText("B")
    dlg._compare()
    assert dlg.tree.topLevelItemCount() == 0
    assert "0 asset" in dlg.status_label.text()   # avertissement non-bundle


def test_dialog_errors(qapp, monkeypatch):
    from gui.bundles_dialog import BundlesDialog
    dlg = BundlesDialog()
    dlg.edits["a"].setText("A")
    dlg.edits["b"].setText("")
    dlg._compare()
    assert dlg.tree.topLevelItemCount() == 0      # need_paths

    def boom(pa, pb):
        raise ValueError("UnityPy")
    monkeypatch.setattr("core.unity_bundles.compare_bundles", boom)
    dlg.edits["b"].setText("B")
    dlg._compare()
    assert "UnityPy" in dlg.status_label.text()

    def bad(pa, pb):
        raise ValueError("crc mismatch")
    monkeypatch.setattr("core.unity_bundles.compare_bundles", bad)
    dlg._compare()
    assert "crc mismatch" in dlg.status_label.text()
    assert dlg.btn_export.isEnabled() is False


def test_dialog_export_csv(qapp, monkeypatch, tmp_path):
    from gui import bundles_dialog
    from gui.bundles_dialog import BundlesDialog
    monkeypatch.setattr("core.unity_bundles.compare_bundles",
                        lambda pa, pb: _diff())
    out = tmp_path / "diff.csv"
    monkeypatch.setattr(
        bundles_dialog.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")))
    dlg = BundlesDialog()
    dlg.edits["a"].setText("A_bundle")
    dlg.edits["b"].setText("B_bundle")
    dlg._compare()
    dlg._export_csv()
    rows = list(csv.reader(open(out, encoding="utf-8"), delimiter=";"))
    assert rows[0][0] and len(rows) == 4          # entete + 3 differences
    assert {r[0] for r in rows[1:]} == {  # statuts traduits presents
        bundles_dialog.t("bundles.added"),
        bundles_dialog.t("bundles.removed"),
        bundles_dialog.t("bundles.changed")}
