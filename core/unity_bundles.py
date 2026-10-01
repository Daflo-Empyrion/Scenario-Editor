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

"""Comparaison de BUNDLES UNITY des scenarios (demande du 29/09/2026) :
les Prefabs de scenario peuvent embarquer des asset bundles (UnityFS —
`decals`, `eden_decalmodels`...) qui ne se fusionnent pas en binaire ; on
liste les assets du container de chaque bundle et on diff. Lecture via
UnityPy (DEPENDANCE OPTIONNELLE : import paresseux, le reste de
l'editeur n'en depend pas). Le diff pur (dict contre dict) est testable
sans UnityPy."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple


@dataclass
class BundleDiff:
    """Resultat d'une comparaison A -> B (par chemin de container)."""
    added: Dict[str, str] = field(default_factory=dict)   # dans B seulement
    removed: Dict[str, str] = field(default_factory=dict)  # dans A seulement
    changed: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # type A->B
    same: int = 0                                          # communs identiques
    na: int = 0
    nb: int = 0

    @property
    def differences(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)


def diff_asset_maps(a: Dict[str, str], b: Dict[str, str]) -> BundleDiff:
    """Diff pur de deux cartes chemin -> type (sans UnityPy : testable)."""
    d = BundleDiff(na=len(a), nb=len(b))
    for path, ta in a.items():
        tb = b.get(path)
        if tb is None:
            d.removed[path] = ta
        elif tb != ta:
            d.changed[path] = (ta, tb)
        else:
            d.same += 1
    for path, tb in b.items():
        if path not in a:
            d.added[path] = tb
    return d


def unitypy_available() -> bool:
    try:
        import UnityPy  # noqa: F401
        return True
    except ImportError:
        return False


def bundle_assets(path) -> Dict[str, str]:
    """Carte chemin de container -> type d'asset d'un bundle (fichier ou
    dossier UnityFS). Leve ValueError avec message lisible si le fichier
    n'est pas un bundle."""
    try:
        import UnityPy
    except ImportError as e:
        raise ValueError("UnityPy") from e
    try:
        env = UnityPy.load(str(path))
        return {key: obj.type.name for key, obj in env.container.items()}
    except Exception as e:
        raise ValueError(str(e)) from e


def compare_bundles(path_a, path_b) -> BundleDiff:
    return diff_asset_maps(bundle_assets(path_a), bundle_assets(path_b))
