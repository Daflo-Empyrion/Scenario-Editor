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

"""Marque des captures du jeu pour en faire des ecrans de chargement.

Reprend la mise en forme des ecrans de chargement de reference (titre en haut
a gauche : remplissage metal brosse, contour sombre, ombre portee, initiales
colorees), avec le libelle du scenario.

    python tools/brand_loading_screens.py "<dossier captures>" --out "<sortie>"
    python tools/brand_loading_screens.py <dossier> --out <sortie> --preview
    python tools/brand_loading_screens.py <dossier> --out <sortie> --label RE2-FR

Les PNG d'origine ne sont JAMAIS touches : sortie en JPEG dans --out, numerotee
a la suite des ecrans existants (`p07.jpg`...) pour tomber directement dans
`LoadingScreenshots/` (le jeu ajoute l'extension lui-meme).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT = Path("C:/Windows/Fonts/ariblk.ttf")      # Arial Black : base lourde
SQUEEZE = 0.86                                   # comprime en largeur (aspect technique)
CAP_RATIO = 0.086                                # hauteur de capitale / hauteur d'image
MARGIN_X = 0.045                                 # aligne sur les ecrans de reference
MARGIN_Y = 0.075
SUPERSAMPLE = 3

WHITE = (252, 253, 255)
GREY = (208, 212, 220)
RED = ((214, 42, 30), (120, 12, 8))
BLUE = ((58, 148, 226), (16, 62, 120))
OUTLINE = (12, 13, 16)


def _gradient(size, top, bottom):
    """Degrade vertical (couleur haut -> couleur bas)."""
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img.resize((w, h), Image.BILINEAR)


def _brushed(size, top, bottom):
    """Degrade + bruit fin : l'aspect metal brosse des ecrans d'origine."""
    base = _gradient(size, top, bottom)
    noise = Image.effect_noise(size, 46).convert("L")
    noise = noise.filter(ImageFilter.GaussianBlur(0.6))
    shade = noise.point(lambda v: 128 + (v - 128) // 2)
    return ImageChops.multiply(base, Image.merge("RGB", (shade, shade, shade)))


def _text_mask(canvas, text, font, origin, tracking, stroke=0):
    """Masque du texte, dessine glyphe par glyphe avec le MEME interlettrage
    que le remplissage (sinon contour et remplissage divergent)."""
    mask = Image.new("L", canvas, 0)
    draw = ImageDraw.Draw(mask)
    x, y = origin
    for char in text:
        draw.text((x, y), char, font=font, fill=255,
                  stroke_width=stroke, stroke_fill=255)
        x += font.getlength(char) + tracking
    return mask


def render_label(label: str, size: int, accent: dict) -> Image.Image:
    """Etiquette RGBA : ombre, contour fin, metal brosse, accents colores."""
    s = size * SUPERSAMPLE
    font = ImageFont.truetype(str(FONT), s)
    tracking = s // 44
    width = int(sum(font.getlength(c) for c in label)
                + tracking * (len(label) - 1)) + s
    canvas = (width, s * 2)
    origin = (s // 2, s // 4)

    base = _text_mask(canvas, label, font, origin, tracking)
    box = base.getbbox()
    if box is None:
        raise ValueError(f"libelle vide : {label!r}")

    # 1. ombre : meme masque, legerement dilate, flou et decale
    shadow = _text_mask(canvas, label, font, origin, tracking,
                        stroke=max(2, s // 70)).filter(
        ImageFilter.GaussianBlur(s // 34))
    shadow_rgba = Image.new("RGBA", canvas, (0, 0, 0, 0))
    shadow_rgba.putalpha(shadow.point(lambda v: int(v * 0.5)))

    # 2. contour : trait fin, presque noir
    outline = Image.new("RGBA", canvas, OUTLINE + (0,))
    outline.putalpha(_text_mask(canvas, label, font, origin, tracking,
                                stroke=max(1, s // 90)))

    # 3. remplissage metal, un glyphe a la fois (accents colores)
    body = Image.new("RGBA", canvas, (0, 0, 0, 0))
    x = origin[0]
    for i, char in enumerate(label):
        if char.strip():
            one = Image.new("L", canvas, 0)
            ImageDraw.Draw(one).text((x, origin[1]), char, font=font, fill=255)
            top, bottom = accent.get(i, (WHITE, GREY))
            # le degrade couvre la hauteur reelle des capitales, pas le canvas
            band = _brushed((canvas[0], box[3] - box[1]), top, bottom)
            metal = Image.new("RGB", canvas, top)
            metal.paste(band, (0, box[1]))
            painted = metal.convert("RGBA")
            painted.putalpha(one)
            body = Image.alpha_composite(body, painted)
        x += font.getlength(char) + tracking

    comp = Image.new("RGBA", canvas, (0, 0, 0, 0))
    shifted = Image.new("RGBA", canvas, (0, 0, 0, 0))
    shifted.paste(shadow_rgba, (max(2, s // 45), max(2, s // 45)))
    comp = Image.alpha_composite(comp, shifted)
    comp = Image.alpha_composite(comp, outline)
    comp = Image.alpha_composite(comp, body)
    comp = comp.crop(comp.getbbox())
    return comp.resize((max(1, comp.width // SUPERSAMPLE),
                        max(1, comp.height // SUPERSAMPLE)), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="RE2-FR")
    ap.add_argument("--start", type=int, default=7, help="numero du premier pNN")
    ap.add_argument("--quality", type=int, default=94)
    ap.add_argument("--preview", action="store_true",
                    help="une seule image, suffixee -preview")
    args = ap.parse_args()

    src = Path(args.folder)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    images = sorted(src.glob("*.png")) + sorted(src.glob("*.jpg"))
    images = [p for p in images if not p.name.startswith("p")]
    if args.preview:
        images = images[:1]
    if not images:
        print(f"aucune capture dans {src}")
        return 2

    # accents : 1re lettre en rouge, les deux dernieres en bleu (comme la ref)
    accent = {0: (RED[0], RED[1]), len(args.label) - 2: (BLUE[0], BLUE[1]),
              len(args.label) - 1: (BLUE[0], BLUE[1])}

    number = args.start
    for path in images:
        image = Image.open(path).convert("RGB")
        w, h = image.size
        label = render_label(args.label, int(h * CAP_RATIO), accent)
        image = image.convert("RGBA")
        image.alpha_composite(label, (int(w * MARGIN_X), int(h * MARGIN_Y)))
        name = f"{path.stem}-preview.jpg" if args.preview else f"p{number:02d}.jpg"
        target = out / name
        image.convert("RGB").save(target, "JPEG", quality=args.quality,
                                  subsampling=0, optimize=True)
        print(f"{path.name} -> {target.name} ({target.stat().st_size // 1024} Ko)")
        number += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
