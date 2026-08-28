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
Systeme de traduction de l'interface (FR/EN). Usage :

    from core.i18n import t
    label = QLabel(t("menu.file"))

La langue active est lue/ecrite via core.settings (persistee entre sessions). Bascule
en direct via set_language() -- les widgets deja crees doivent etre reconstruits ou
avoir leur texte reassigne manuellement pour refleter le changement (voir
gui/main_window.py, _apply_language()).
"""
from core import settings

from core.resource_loading import load_json_data

# Charge depuis data/i18n_strings.json (voir core/resource_loading.py) --
# Format : "cle" -> {"fr": "...", "en": "..."}
STRINGS = load_json_data("i18n_strings.json")


def get_language() -> str:
    return settings.get_language()


def set_language(lang: str) -> None:
    settings.set_language(lang)


def t(translation_key: str, **kwargs) -> str:
    """Traduit `translation_key` dans la langue active. Si la cle est absente, retourne
    la cle elle-meme (visible et sans plantage -- signale qu'une chaine reste a
    traduire). Le parametre s'appelle volontairement `translation_key` et non `key` :
    plusieurs chaines traduites ont elles-memes un placeholder nomme {key} (ex: la cle
    d'une ligne CSV), et un appel comme t("...", key=ma_valeur) entrerait sinon en
    collision avec le nom du premier parametre positionnel -- erreur reelle deja
    rencontree en production (TypeError: t() got multiple values for argument 'key')."""
    entry = STRINGS.get(translation_key)
    if entry is None:
        return translation_key
    lang = get_language()
    text = entry.get(lang, entry.get("fr", translation_key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
