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

"""Marquage des captures en ecrans de chargement : etiquette RGBA correcte et
sortie JPEG a la taille d'origine, numerotee a la suite."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import brand_loading_screens as brand  # noqa: E402


def test_render_label_produces_a_transparent_rgba():
    accent = {0: brand.RED, 4: brand.BLUE, 5: brand.BLUE}
    label = brand.render_label("RE2-FR", 90, accent)
    assert label.mode == "RGBA"
    assert label.width > 40 and label.height > 10
    # le remplissage doit etre opaque quelque part, et l'etiquette garder
    # des zones entierement transparentes (contour + ombre, pas un rectangle)
    alphas = [alpha for *_rgb, alpha in label.getdata()]
    assert max(alphas) >= 250
    assert min(alphas) == 0


def test_branding_keeps_size_and_numbers_after_existing(tmp_path):
    src = tmp_path / "shots"
    src.mkdir()
    Image.new("RGB", (320, 180), (24, 26, 34)).save(src / "capture1.png")
    out = tmp_path / "out"
    argv = sys.argv
    try:
        sys.argv = ["brand", str(src), "--out", str(out), "--start", "7"]
        assert brand.main() == 0
    finally:
        sys.argv = argv
    produit = out / "p07.jpg"
    assert produit.is_file()
    assert Image.open(produit).size == (320, 180)
    assert produit.stat().st_size > 1000          # pas une image vide


def test_no_capture_is_reported(tmp_path):
    src = tmp_path / "vide"
    src.mkdir()
    argv = sys.argv
    try:
        sys.argv = ["brand", str(src), "--out", str(tmp_path / "o")]
        assert brand.main() == 2
    finally:
        sys.argv = argv
