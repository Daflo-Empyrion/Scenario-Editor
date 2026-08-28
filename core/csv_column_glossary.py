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
Glossaire des en-tetes de colonnes CSV -- contrairement aux fichiers ECF
(voir core/ecf_header_glossary.py, glossaire riche par fichier), les CSV
rencontres dans ce projet suivent TOUS le meme format simple : une colonne
'KEY'/'Key' (jeton technique) suivie d'une colonne par langue (English,
Français, Deutsch...) -- confirme sur PDA.csv, Dialogues.csv,
Localization.csv. Un seul glossaire generique suffit donc, plutot qu'un
glossaire par nom de fichier comme pour les ECF.
"""

_KEY_COLUMN_NAMES = {"key"}

# Nom de colonne (normalise en minuscules) -> nom de langue affichable.
_LANGUAGE_COLUMNS = {
    "english": "anglais", "en": "anglais",
    "français": "français", "francais": "français", "fr": "français",
    "deutsch": "allemand", "de": "allemand", "german": "allemand",
    "español": "espagnol", "espanol": "espagnol", "es": "espagnol", "spanish": "espagnol",
    "italiano": "italien", "it": "italien", "italian": "italien",
    "polski": "polonais", "pl": "polonais", "polish": "polonais",
    "русский": "russe", "russian": "russe", "ru": "russe",
    "português": "portugais", "portugues": "portugais", "portuguese": "portugais", "pt": "portugais",
    "中文": "chinois", "chinese": "chinois", "zh": "chinois",
    "日本語": "japonais", "japanese": "japonais", "ja": "japonais",
}


def get_csv_column_tooltip(column_name: str) -> str:
    """Retourne le texte d'infobulle pour un en-tete de colonne CSV,
    coherent avec le format REEL observe sur tous les CSV de ce projet
    (fichiers de traduction KEY + langues) -- pas une explication generee
    au hasard, un format constant verifie sur plusieurs vrais fichiers.
    Retourne une chaine vide si la colonne ne correspond a aucun motif
    connu (mieux vaut aucune infobulle qu'une explication incertaine)."""
    if not column_name:
        return ""
    normalized = column_name.strip().lower()
    if normalized in _KEY_COLUMN_NAMES:
        return (f"<b>{column_name}</b><br>Identifiant technique unique (jeton) "
                f"reference ailleurs dans le scenario -- ne pas traduire, ne pas modifier.")
    language = _LANGUAGE_COLUMNS.get(normalized)
    if language:
        return f"<b>{column_name}</b><br>Texte affiche aux joueurs configures en {language}."
    return ""
