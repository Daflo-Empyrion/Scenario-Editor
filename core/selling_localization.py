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
Localisation de SellingText (v1.10.0, demande utilisateur) : le jeu
accepte une CLE de Localization.csv comme valeur de SellingText -- c'est
documente dans le TraderNPCConfig.ecf vanille lui-meme (ligne commentee
sous le trader par défaut : # SellingText: "trwDefaultSellingText") --
et affiche alors le texte dans la langue du joueur, les jetons
<NAME>/<GOODS>/<PAYMENT>/<DISCOUNTTEXT> etant substitues APRES la
resolution de la cle.

Ce module cree la cle (`scn_Selling_<NomSanitise>`) et la ligne
correspondante dans Extras/Localization.csv de la copie de travail
(convention confirmee par core/ecf/creation_check.py : la localisation
d'un scenario vit dans Extras/Localization.csv).
"""
import re
from pathlib import Path

from .csv_handler import CsvHandler, CsvDocument, parse_csv_text, render_csv
from .fsutil import atomic_write_text
from .translation import find_language_aliases, _normalize, repair_mojibake

# En-tete canonique du Localization.csv (copie exacte de l'ordre vanille ;
# l'important est KEY en colonne 0 et English en colonne 1).
CANONICAL_HEADER = [
    "KEY", "English", "Deutsch", "Français", "Italiano", "Spanish",
    "Portuguese (Euro)", "Portuguese (Brazil)", "Polish", "Russian",
    "Japanese", "Chinese (simplified)", "Chinese (traditional)", "Korean",
    "Turkish", "Greek", "Dutch", "Vietnamese",
]


def build_key(trader_name: str) -> str:
    """Cle de localisation `scn_Selling_<NomSanitise>` (alphanumerique
    uniquement, comme les cles vanille). Leve ValueError si le nom ne
    produit aucun caractere utilisable."""
    safe = re.sub(r"[^A-Za-z0-9]", "", trader_name or "")
    if not safe:
        raise ValueError("nom de trader vide ou sans caractere alphanumerique")
    return f"scn_Selling_{safe}"


def localization_csv_path(ecf_path: Path, root: Path = None) -> Path:
    """Chemin du Localization.csv du scenario pour un ECF de
    Configuration.

    Les structures de scenario VARIENT (vecu 20/09/2026 sur RE2 ATL) :
    - <scenario>/Extras/Localization.csv (convention dominante : le
      dossier du scenario mime Content) ;
    - <scenario>/Content/Extras/Localization.csv (variante avec dossier
      Content imbrique).

    Priorite : un fichier EXISTANT gagne (on complete la localisation
    existante plutot que d'en creer une seconde que le jeu ignorerait
    peut-etre) ; sinon creation dans Extras du scenario quand la racine
    est connue (convention du scanner), sinon a cote de l'ECF."""
    ecf_path = Path(ecf_path)
    candidates = []
    if root:
        candidates.append(Path(root) / "Extras" / "Localization.csv")
    content_extras = ecf_path.parent.parent / "Extras" / "Localization.csv"
    candidates.append(content_extras)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if root:
        return Path(root) / "Extras" / "Localization.csv"
    return content_extras


def _english_column(header: list) -> int:
    for i, name in enumerate(header):
        norm = _normalize(repair_mojibake(name.strip()))
        if norm in find_language_aliases("en", "English"):
            return i
    return 1 if len(header) > 1 else 0


def _write(path: Path, doc: CsvDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_csv(doc))


def ensure_localization_entry(ecf_path: Path, key: str,
                              english_text: str, root: Path = None) -> str:
    """Ajoute la ligne `key` dans le Localization.csv du scenario avec
    `english_text` en colonne English (les autres langues restent vides,
    a traduire ensuite via le flux CSV existant). `root` = racine de la
    copie de travail (priorite des emplacements : voir
    localization_csv_path).

    Retourne :
    - 'created' : ligne ajoutee (fichier cree au passage si absent) ;
    - 'updated' : la cle existait avec la colonne English VIDE, remplie ;
    - 'exists'  : la cle existait deja avec une traduction -- rien modifie
      (jamais ecraser une traduction existante).

    Leve ValueError si `key` est vide ou si `english_text` est vide.
    """
    key = (key or "").strip()
    english_text = (english_text or "").strip()
    if not key:
        raise ValueError("cle de localisation vide")
    if not english_text:
        raise ValueError("texte English vide")
    path = localization_csv_path(ecf_path, root)

    if not path.exists():
        header = list(CANONICAL_HEADER)
        row = [""] * len(header)
        row[0] = key
        row[1] = english_text
        doc = CsvDocument(header=header, rows=[row], lineterminator="\r\n")
        _write(path, doc)
        return "created"

    doc = parse_csv_text(CsvHandler().load(path))
    header = doc.header or list(CANONICAL_HEADER)
    en_col = _english_column(header)
    for row in doc.rows:
        if row and row[0].strip() == key:
            current = row[en_col].strip() if en_col < len(row) else ""
            if current:
                return "exists"
            while len(row) <= en_col:
                row.append("")
            row[en_col] = english_text
            _write(path, doc)
            return "updated"
    width = max(len(header), en_col + 1)
    row = [""] * width
    row[0] = key
    row[en_col] = english_text
    doc.rows.append(row)
    _write(path, doc)
    return "created"


def key_exists_in(path: Path, key: str) -> bool:
    """Vrai si la cle existe deja dans CE Localization.csv (scenario ou
    vanille) -- garde-fou d'unicite avant creation."""
    path = Path(path)
    if not path.exists():
        return False
    try:
        doc = parse_csv_text(CsvHandler().load(path))
    except Exception:
        return False
    return any(row and row[0].strip() == key for row in doc.rows)
