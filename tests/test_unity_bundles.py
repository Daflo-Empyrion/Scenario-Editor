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

"""Comparaison de bundles Unity (core/unity_bundles.py, demande du
29/09/2026) : diff PUR testable sans UnityPy + lecture container si
UnityPy est installe (dependance optionnelle)."""
import pytest

from core.unity_bundles import BundleDiff, diff_asset_maps


def test_diff_pure_added_removed_changed_same():
    a = {"x/prefab1.prefab": "GameObject", "x/tex1.png": "Texture2D",
         "x/mesh1": "Mesh"}
    b = {"x/prefab1.prefab": "GameObject", "x/tex1.png": "Mesh",
         "x/new.png": "Texture2D"}
    d = diff_asset_maps(a, b)
    assert d.added == {"x/new.png": "Texture2D"}
    assert d.removed == {"x/mesh1": "Mesh"}
    assert d.changed == {"x/tex1.png": ("Texture2D", "Mesh")}
    assert d.same == 1
    assert (d.na, d.nb) == (3, 3)
    assert d.differences == 3


def test_diff_empty_maps():
    d = diff_asset_maps({}, {})
    assert d.differences == 0 and d.same == 0 and (d.na, d.nb) == (0, 0)


def test_bundle_diff_dataclass_defaults():
    d = BundleDiff()
    assert d.added == {} and d.removed == {} and d.changed == {}
    assert d.same == 0 and d.differences == 0


def test_bundle_assets_non_bundle_file(tmp_path):
    """Comportement documente : UnityPy ne leve PAS sur un non-bundle, il
    rend un container VIDE — le dialogue affiche l'avertissement."""
    pytest.importorskip("UnityPy")
    from core.unity_bundles import bundle_assets
    f = tmp_path / "notabundle.bin"
    f.write_text("ceci n'est pas un bundle", encoding="utf-8")
    assert bundle_assets(f) == {}


def test_compare_bundles_missing_module(monkeypatch):
    """compare_bundles leve ValueError('UnityPy') si le module absent —
    le dialogue traduit en message d'installation."""
    import sys
    from core import unity_bundles
    monkeypatch.setitem(sys.modules, "UnityPy", None)
    with pytest.raises(ValueError) as e:
        unity_bundles.bundle_assets(__file__)   # fichier quelconque
    assert str(e.value) == "UnityPy"
