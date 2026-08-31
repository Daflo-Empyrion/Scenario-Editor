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
Resolution des textes affiches dans l'encart d'information d'un bloc/item
(voir gui/block_info_card_widget.py) -- CONFIRME sur de vrais
BlocksConfig.ecf/Localization.csv (session du 29/08/2026) : le NOM DE LA
PROPRIETE ECF est directement la cle de traduction de son LABEL affiche en
jeu (ex: cle 'HitPoints' -> 'Points dommages' en francais), et le Name d'un
bloc/item est directement la cle de traduction de son NOM AFFICHE (ex: cle
'FuelTankMSLarge' -> 'Réservoir de carburant v2'). Meme mecanisme pour les
textes d'aide plus longs, references via la propriete 'Info:' d'un bloc (ex:
'Info: bkiConstructorAdvanced' -> cle 'bkiConstructorAdvanced').

Deux sources, recherchees dans cet ordre (la premiere qui contient la cle
gagne -- MEME PRIORITE que core/tech_tree_icons.py) :
1. Localization.csv du SCENARIO (Extras/Localization.csv a la racine du
   scenario, voir Scenario.extras) -- ne contient que les cles
   AJOUTEES/MODIFIEES par ce scenario, prioritaire pour permettre le modding.
2. data/localization_vanilla.pak -- archive complete (compressee, jamais
   extraite sur disque) du Localization.csv VANILLA du jeu de base, generee
   par cli/pack_localization.py. Repli pour toute cle absente du scenario.
"""
import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set

LOCALIZATION_PACK_FILENAME = "localization_vanilla.pak"
LOCALIZATION_PACK_NOTICE_MEMBER = "NOTICE.txt"
LOCALIZATION_PACK_CSV_MEMBER = "Localization.csv"

# Correspondance code de langue de l'appli (voir core.i18n.get_language(),
# 'fr'/'en' uniquement) -> nom de colonne dans Localization.csv (confirme sur
# le vrai fichier vanilla : colonnes 'English'/'Français' entre autres).
_LANGUAGE_COLUMN = {'fr': 'Français', 'en': 'English'}
_FALLBACK_COLUMN = 'English'

# Alias de NOMS DE COLONNES reelslement rencontres dans la nature : les
# Localization.csv de SCENARIO (workshop, Reforged Eden...) ecrivent souvent
# l'en-tete en anglais ('French') au lieu du vanilla ('Français') -- sans
# alias, la colonne francaise du scenario n'etait JAMAIS lue et les
# descriptions de fiches restaient en anglais (bug signale par l'utilisateur
# le 30/08/2026). Comparaison insensible a la casse/apres strip.
_COLUMN_ALIASES = {
    'french': 'Français', 'français': 'Français', 'francais': 'Français',
    'english': 'English', 'anglais': 'English',
    'german': 'Deutsch', 'deutsch': 'Deutsch',
    'spanish': 'Spanish', 'italian': 'Italiano', 'italiano': 'Italiano',
}


def _normalize_column(name: str) -> str:
    """Nom de colonne canonique : 'French'/'francais' -> 'Français', etc.
    Les colonnes sans alias connus gardent leur nom d'origine."""
    canonical = _COLUMN_ALIASES.get(name.strip().lower())
    return canonical or name


def localization_pack_path() -> Optional[Path]:
    """Chemin de l'archive distribuee data/localization_vanilla.pak, si elle
    existe reellement, sinon None -- meme logique dev/frozen que
    core.resource_loading.resolve_data_path."""
    if getattr(sys, 'frozen', False):
        candidate = Path(sys._MEIPASS) / "data" / LOCALIZATION_PACK_FILENAME
        return candidate if candidate.is_file() else None
    candidate = Path(__file__).resolve().parent.parent / "data" / LOCALIZATION_PACK_FILENAME
    return candidate if candidate.is_file() else None


def _parse_csv_text(text: str) -> Dict[str, Dict[str, str]]:
    """Parse un Localization.csv (texte complet) en
    {cle: {nom_colonne: valeur}}. Cles en double (rare) : la DERNIERE
    occurrence gagne (comportement standard d'un dict, coherent avec un
    fichier ou une correction ulterieure dans le fichier doit prevaloir).
    Les noms de colonnes sont normalises via _normalize_column (alias
    'French' -> 'Français'...)."""
    index: Dict[str, Dict[str, str]] = {}
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return {}
    normalized = ["KEY"] + [_normalize_column(h) for h in header[1:]]
    for row in reader:
        if not row or not row[0]:
            continue
        key = row[0]
        row_dict = {normalized[i]: row[i] for i in range(1, min(len(row), len(normalized)))}
        index[key] = row_dict
    return index


SCENARIO_LOCALIZATION_RELATIVE_PATH = ("Extras", "Localization.csv")

# Colonnes minimales pour un NOUVEAU Extras/Localization.csv (le scenario
# n'en a pas encore) -- cree seulement si besoin d'ecrire une entree alors
# qu'aucun fichier scenario n'existe. Reprend les memes NOMS de colonnes que
# le fichier vanilla (confirme reel : 'KEY,English,Deutsch,Français,...')
# pour rester coherent si le fichier est complete manuellement plus tard --
# mais ne peuple que Francais/Anglais, les deux seules langues que
# l'application elle-meme gere (voir core.i18n).
_DEFAULT_NEW_FILE_HEADER = ["KEY", "English", "Deutsch", "Français"]


def write_scenario_localization_entries(working_root: Path, entries: Dict[str, Dict[str, str]]) -> None:
    """Ecrit/met a jour des entrees dans Extras/Localization.csv DU SCENARIO
    (jamais le fichier vanilla, distribue en lecture seule -- voir docstring
    du module) -- utilise pour donner un nom affiche traduit a un bloc/item
    nouvellement duplique (demande explicite de l'utilisateur, session du
    29/08/2026 : le nom affiche/description dans Localization.csv fait
    partie des 'fichiers lies' a ajuster en meme temps que la duplication).

    `entries` : {cle: {nom_colonne: valeur}}, ex:
    {'FuelTankMSLargeCopy': {'English': 'Fuel Tank Copy',
                              'Français': 'Réservoir copié'}}.

    Si le fichier existe deja, PRESERVE integralement ses entrees et
    colonnes existantes (y compris les langues qu'on ne gere pas
    nous-memes) -- ne modifie/ajoute QUE les cles fournies, et seulement les
    colonnes English/Français (les autres langues d'une ligne EXISTANTE
    restent inchangees). Si le fichier n'existe pas encore, le cree avec un
    en-tete minimal (voir _DEFAULT_NEW_FILE_HEADER)."""
    csv_path = working_root.joinpath(*SCENARIO_LOCALIZATION_RELATIVE_PATH)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if csv_path.is_file():
        raw_rows = list(csv.reader(io.StringIO(csv_path.read_text(encoding='utf-8-sig'))))
        header = raw_rows[0] if raw_rows else list(_DEFAULT_NEW_FILE_HEADER)
        data_rows = [list(r) for r in raw_rows[1:]] if raw_rows else []
    else:
        header = list(_DEFAULT_NEW_FILE_HEADER)
        data_rows = []

    for col in ("English", "Français"):
        if col not in header:
            header.append(col)
            for row in data_rows:
                row.append("")

    by_key = {row[0]: row for row in data_rows if row}

    for key, values in entries.items():
        row = by_key.get(key)
        if row is None:
            row = [""] * len(header)
            row[0] = key
            data_rows.append(row)
            by_key[key] = row
        for col_name, value in values.items():
            if col_name not in header:
                continue
            idx = header.index(col_name)
            while len(row) <= idx:
                row.append("")
            row[idx] = value

    # Rendu en memoire puis ecriture ATOMIQUE (cf. core.fsutil) -- un crash
    # pendant l'ecriture ne doit pas couper en deux le Localization.csv du
    # scenario. csv.writer ecrit dans un StringIO avec les memes regles qu'un
    # fichier ouvert en newline='' (fins de ligne \r\n par defaut du module csv).
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(data_rows)
    from .fsutil import atomic_write_text
    atomic_write_text(csv_path, buffer.getvalue())


def _load_scenario_csv(working_root: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if working_root is None:
        return {}
    candidate = working_root / "Extras" / "Localization.csv"
    if not candidate.is_file():
        return {}
    try:
        return _parse_csv_text(candidate.read_text(encoding='utf-8-sig'))
    except OSError:
        return {}


def _load_vanilla_pack() -> Dict[str, Dict[str, str]]:
    pack = localization_pack_path()
    if pack is None:
        return {}
    try:
        with zipfile.ZipFile(pack) as zf:
            text = zf.read(LOCALIZATION_PACK_CSV_MEMBER).decode('utf-8-sig')
        return _parse_csv_text(text)
    except (OSError, KeyError, zipfile.BadZipFile):
        return {}


class LocalizationIndex:
    """Index fusionne (scenario prioritaire, vanilla en repli) construit UNE
    FOIS par appelant -- voir build_localization_index()."""

    def __init__(self, entries: Dict[str, Dict[str, str]]):
        self._entries = entries

    def has(self, key: Optional[str]) -> bool:
        """True si la CLE existe dans l'index (scenario ou vanilla), meme si sa
        traduction est vide -- distinct de get(), qui retourne None quand la
        traduction est absente : ici on ne veut savoir que si l'entree existe
        (controle de creation : une cle sans traduction est deja declaree)."""
        return bool(key) and key in self._entries

    def all_keys(self) -> Set[str]:
        """Toutes les cles connues de l'index (scenario + vanilla)."""
        return set(self._entries.keys())

    def get(self, key: Optional[str], language: str) -> Optional[str]:
        """Traduction de `key` dans `language` ('fr'/'en'). Retombe sur la
        colonne anglaise si la cellule de la langue demandee est vide ou
        absente (frequent : certaines langues ne sont pas integralement
        traduites dans le fichier reel -- confirme, ex: colonne Turkish/Greek
        souvent vide sur de nombreuses lignes). Retourne None si la cle
        elle-meme est introuvable (l'appelant doit alors afficher un repli,
        ex: la cle brute ou masquer le champ)."""
        if not key:
            return None
        row = self._entries.get(key)
        if row is None:
            return None
        column = _LANGUAGE_COLUMN.get(language, _FALLBACK_COLUMN)
        value = row.get(column)
        if value:
            return value
        return row.get(_FALLBACK_COLUMN) or None


def build_localization_index(working_root: Optional[Path]) -> LocalizationIndex:
    """Construit l'index fusionne -- fusion COLONNE PAR COLONNE (depuis le
    30/08/2026, bug signale par l'utilisateur : une ligne du scenario ne
    contenant que l'anglais ecrasait TOUTE la ligne vanilla et masquait sa
    traduction francaise). Regles :
      - une cle presente SEULEMENT dans le scenario : ligne scenario telle
        quelle ;
      - une cle presente dans les DEUX : chaque cellule scenario NON VIDE
        remplace la cellule vanilla ; une cellule scenario VIDE herite de la
        vanilla. Le scenario reste prioritaire pour le modding, mais ne peut
        plus masquer par omission une traduction qu'il ne fournit pas.

    CACHE MODULE (31/08/2026, retour utilisateur : latence globale) -- cette
    fonction etait appelee une fois par onglet/dialogue, en dezippant le pak
    vanilla et relisant le CSV scenario A CHAQUE FOIS. Resultat partage par
    racine de scenario, invalide par (mtime_ns, taille) des deux sources :
    une modification du CSV du scenario est donc vue immediatement.
    LocalizationIndex est en lecture seule (voir sa classe), le partage est
    sur."""
    csv_path = (working_root / "Extras" / "Localization.csv") if working_root else None
    stamps = (_source_stamp(csv_path), _source_stamp(localization_pack_path()))
    cache_key = str(working_root or "")
    cached = _index_cache.get(cache_key)
    if cached is not None and cached[0] == stamps:
        return cached[1]

    merged: Dict[str, Dict[str, str]] = {}
    merged.update(_load_vanilla_pack())
    for key, scenario_row in _load_scenario_csv(working_root).items():
        base = merged.get(key)
        if base is None:
            merged[key] = scenario_row
            continue
        filled = dict(base)
        for column, value in scenario_row.items():
            if value and value.strip():  # cellule reellement fournie
                filled[column] = value
        merged[key] = filled
    index = LocalizationIndex(merged)
    _index_cache[cache_key] = (stamps, index)
    return index


def _source_stamp(path: Optional[Path]) -> Optional[tuple]:
    """(mtime_ns, taille) d'une source de localisation, None si absente --
    cle d'invalidation du cache module (voir build_localization_index)."""
    if path is None or not path.is_file():
        return None
    st = path.stat()
    return (st.st_mtime_ns, st.st_size)


# str(racine ou "") -> (stamps, index partage)
_index_cache: Dict[str, tuple] = {}
