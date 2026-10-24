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

from core.i18n import t

_KEY_COLUMN_NAMES = {"key"}

# Colonne de langue -> cle i18n du nom de langue (le libelle suit la
# langue de l'interface, pas celle du fichier ouvert).
_LANGUAGE_KEYS = {
    "english": "lang.english", "en": "lang.english",
    "français": "lang.french", "francais": "lang.french",
    "fr": "lang.french",
    "deutsch": "lang.german", "de": "lang.german", "german": "lang.german",
    "español": "lang.spanish", "espanol": "lang.spanish",
    "es": "lang.spanish", "spanish": "lang.spanish",
    "italiano": "lang.italian", "it": "lang.italian",
    "italian": "lang.italian",
    "polski": "lang.polish", "pl": "lang.polish", "polish": "lang.polish",
    "русский": "lang.russian", "russian": "lang.russian",
    "ru": "lang.russian",
    "português": "lang.portuguese", "portugues": "lang.portuguese",
    "portuguese": "lang.portuguese", "pt": "lang.portuguese",
    "中文": "lang.chinese", "chinese": "lang.chinese", "zh": "lang.chinese",
    "日本語": "lang.japanese", "japanese": "lang.japanese",
    "ja": "lang.japanese",
}


def get_csv_column_tooltip(column_name: str) -> str:
    """Retourne le texte d'infobulle pour un en-tete de colonne CSV,
    coherent avec le format REEL observe sur tous les CSV de ce projet
    (fichiers de traduction KEY + langues) -- pas une explication generee
    au hasard, un format constant verifie sur plusieurs vrais fichiers.
    Retourne une chaine vide si la colonne ne correspond a aucun motif
    connu (mieux vaut aucune infobulle qu'une explication incertaine).
    Les PHRASES suivent la langue de l'interface (vecu 22/10 : elles
    etaient en francais en dur, donc en francais dans l'UI anglaise)."""
    if not column_name:
        return ""
    normalized = column_name.strip().lower()
    if normalized in _KEY_COLUMN_NAMES:
        return (f"<b>{column_name}</b><br>"
                + t("csv.tooltip_key_column"))
    language_key = _LANGUAGE_KEYS.get(normalized)
    if language_key:
        return (f"<b>{column_name}</b><br>"
                + t("csv.tooltip_language_column",
                    language=t(language_key)))
    return ""
