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

"""
Genere les icones de l'application a partir d'une image source (JPG/PNG)
fournie par l'artiste :
- assets/icon.ico       : multi-tailles (16-256), utilise par PyInstaller
                          (exe) et l'installeur Inno Setup ;
- assets/icon_512.png   : logo pour le README / GitHub (max 1 Mo) ;
- assets/icon_1024.png  : source PNG conservee (max 1 Mo -- limite GitHub).

L'image source est un carre pose sur un damier (fond transparent rendu) :
le script detecte les bornes du CONTENU (pixels sombres < 160 -- le damier
est clair : blanc 255 / gris ~205), recadre a l'interieur du cadre de
l'artwork, applique un masque a coins arrondis ERODE (aucun damier ne doit
rester visible en bordure -- verification automatique), et exporte avec
compression controlee (PNG <= 1 Mo).

UTILISATION :
    python tools/generate_icones.py <image_source> [dossier_assets]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAYON_RELATIF = 0.185          # rayon des coins, fraction du cote
SEUIL_CONTENU = 160            # luminosite max du contenu (damier ~205-255)
INSET_RELATIF = 0.006          # recadrage interieur (se cale sur le cadre)
TAILLES_ICO = [(16, 16), (24, 24), (32, 32), (48, 48),
               (64, 64), (128, 128), (256, 256)]
SUPERSAMPLING = 4              # lissage du masque (dessin 4x puis reduction)
LIMITE_PNG = 1_000_000         # octets : limite GitHub pour une image


def bornes_contenu(img: Image.Image) -> tuple:
    """Bounding box du contenu : pixels SOMBRES uniquement (le damier est
    clair). Les zones floues/jpeg ne doivent pas creer de faux positifs."""
    gris = img.convert("L")
    masque = gris.point(lambda v: 255 if v < SEUIL_CONTENU else 0)
    return masque.getbbox()


def carre_avec_inset(img: Image.Image) -> Image.Image:
    """Recadre les bornes du contenu puis resserre legerement a l'interieur
    du cadre de l'artwork (le masque arrondi se posera SUR le cadre noir,
    cachant tout residu de damier)."""
    bbox = bornes_contenu(img)
    if bbox is None:
        raise SystemExit("ERREUR : aucun contenu detecte (image toute claire ?)")
    inset = int(max(bbox[2] - bbox[0], bbox[3] - bbox[1]) * INSET_RELATIF)
    bbox = (bbox[0] + inset, bbox[1] + inset, bbox[2] - inset, bbox[3] - inset)
    crop = img.crop(bbox).convert("RGBA")
    cote = max(crop.size)
    carre = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    ox = (cote - crop.size[0]) // 2
    oy = (cote - crop.size[1]) // 2
    carre.paste(crop, (ox, oy))
    return carre


def _masque_arrondi(cote: int, rayon: int, erosion: int) -> Image.Image:
    gros = cote * SUPERSAMPLING
    masque = Image.new("L", (gros, gros), 0)
    ImageDraw.Draw(masque).rounded_rectangle(
        (0, 0, gros - 1, gros - 1), radius=rayon * SUPERSAMPLING, fill=255)
    if erosion:
        masque = masque.filter(ImageFilter.MinFilter(1 + 2 * erosion))
    return masque.resize((cote, cote), Image.LANCZOS)


def _damier_residuel(img: Image.Image) -> int:
    """Nombre de pixels OPAQUES et CLAIRS dans l'anneau externe (4 % du
    cote) : c'est la que le damier residuel apparaitrait. L'interieur de
    l'artwork contient du blanc legitime, on ne le scanne pas."""
    cote = img.size[0]
    anneau = max(4, int(cote * 0.04))
    px = img.load()
    n = 0
    for y in range(cote):
        for x in range(cote):
            bord = min(x, y, cote - 1 - x, cote - 1 - y)
            if bord >= anneau:
                continue
            r, g, b, a = px[x, y]
            if a > 100 and r > 210 and g > 210 and b > 210:
                n += 1
    return n


def coins_arrondis(img: Image.Image) -> Image.Image:
    """Masque a coins arrondis, ERODE progressivement jusqu'a ce qu'aucun
    damier clair ne reste dans l'anneau externe."""
    cote = img.size[0]
    rayon = int(cote * RAYON_RELATIF)
    for erosion in (2, 4, 6, 9, 12):
        out = img.convert("RGBA")
        out.putalpha(_masque_arrondi(cote, rayon, erosion))
        residu = _damier_residuel(out)
        if residu == 0:
            print(f"  coins arrondis OK (erosion {erosion}px, damier residuel: 0)")
            return out
        print(f"  erosion {erosion}px : {residu} pixels clairs residuels, on renforce")
    return out


def sauver_png_sous_limite(img: Image.Image, path: Path) -> None:
    """Sauve le PNG en respectant la limite de taille (quantification
    adaptative en dernier recours)."""
    img.save(path, optimize=True)
    couleurs = 256
    while path.stat().st_size > LIMITE_PNG and couleurs >= 32:
        qimg = img.quantize(couleurs, method=Image.Quantize.FASTOCTREE,
                            dither=Image.Dither.FLOYDSTEINBERG)
        qimg.save(path, optimize=True)
        couleurs //= 2
    taille = path.stat().st_size
    etat = "OK" if taille <= LIMITE_PNG else "TROP GROS"
    print(f"  {path.name}: {taille} octets ({etat})")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    source = Path(sys.argv[1])
    dossier = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "assets"
    dossier.mkdir(parents=True, exist_ok=True)

    img = Image.open(source)
    icon = coins_arrondis(carre_avec_inset(img))

    ico_path = dossier / "icon.ico"
    icon.save(ico_path, format="ICO", sizes=TAILLES_ICO)
    sauver_png_sous_limite(icon.resize((512, 512), Image.LANCZOS),
                           dossier / "icon_512.png")
    sauver_png_sous_limite(icon, dossier / "icon_1024.png")
    print(f"icones generees dans {dossier} (tailles ico: {TAILLES_ICO})")


if __name__ == "__main__":
    main()
