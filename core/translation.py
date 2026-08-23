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
Traduction de texte via Google Translate (bibliotheque deep-translator, gratuite, sans
cle API). Point d'entree unique reutilise par TOUTES les fonctions de traduction de
l'application -- traduction ponctuelle d'une cellule (clic droit -> Traduire), traduction
en lot, et "Combler les langues manquantes..." : aucune ne passe par un systeme different
ou hors ligne, toutes envoient le texte a traduire aux serveurs Google (voir PRIVACY.md et
le reglage Options > Traduction en ligne pour desactiver completement cette fonctionnalite).

IMPORTANT -- protection du BBCode et des placeholders : le texte Empyrion contient
souvent des balises de mise en forme ([b]...[/b], [color=#FF0000]...[/color]) et des
jetons de substitution ({PlayerName}, %s, {0}...) qui ne doivent JAMAIS etre traduits
ni alteres. Avant d'envoyer le texte au traducteur, on les extrait et on les remplace
par des jetons neutres insensibles a la traduction, puis on les reinjecte a leur place
dans le resultat -- meme principe que le "segment-splitting" deja utilise dans l'outil
de traduction CSV.
"""
import re
from typing import List, Tuple

try:
    from deep_translator import GoogleTranslator
    _AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:
    # Capture toute erreur au chargement, pas seulement ImportError -- une
    # dependance manquante sur Windows peut aussi remonter comme OSError
    # (echec de chargement d'une DLL) ou une autre exception selon la cause
    # exacte. Le message precis est garde dans _IMPORT_ERROR pour diagnostic
    # (voir get_import_error() plus bas) -- l'ancien code avalait completement
    # cette information et affichait toujours le meme message generique "pip
    # install deep-translator", inutile pour quelqu'un utilisant la version
    # installee (executable) sans Python sur sa machine.
    _AVAILABLE = False
    _IMPORT_ERROR = f"{type(e).__name__}: {e}"


COMMON_LANGUAGES = [
    ("Francais", "fr"),
    ("Anglais", "en"),
    ("Allemand", "de"),
    ("Espagnol", "es"),
    ("Italien", "it"),
    ("Russe", "ru"),
    ("Portugais (Europe)", "pt"),
    ("Portugais (Bresil)", "pt-BR"),
    ("Neerlandais", "nl"),
    ("Polonais", "pl"),
    ("Japonais", "ja"),
    ("Coreen", "ko"),
    ("Turc", "tr"),
    ("Grec", "el"),
    ("Vietnamien", "vi"),
    ("Chinois (simplifie)", "zh-CN"),
    ("Chinois (traditionnel)", "zh-TW"),
]

# Alias possibles pour reperer la colonne d'une langue dans l'en-tete d'un CSV --
# les fichiers Empyrion reels utilisent des conventions variees (nom anglais, nom
# natif, code ISO...), donc on accepte plusieurs formes par langue. La comparaison
# se fait sans tenir compte des accents (voir _normalize).
LANGUAGE_ALIASES = {
    "fr": ["fr", "french", "francais", "français"],
    "en": ["en", "english", "anglais"],
    "de": ["de", "german", "deutsch", "allemand"],
    "es": ["es", "spanish", "espanol", "español", "espagnol"],
    "it": ["it", "italian", "italiano", "italien"],
    "ru": ["ru", "russian", "russe"],
    "pt": ["pt", "portuguese (euro)", "portuguese", "portugues", "português", "portugais"],
    "pt-BR": ["pt-br", "portuguese (brazil)", "portugues (brasil)", "português (brasil)"],
    "nl": ["nl", "dutch", "nederlands", "neerlandais"],
    "pl": ["pl", "polish", "polski", "polonais"],
    "ja": ["ja", "japanese", "japonais"],
    "ko": ["ko", "korean", "coreen"],
    "tr": ["tr", "turkish", "turc"],
    "el": ["el", "greek", "grec"],
    "vi": ["vi", "vietnamese", "vietnamien"],
    "zh-CN": ["zh-cn", "chinese (simplified)", "chinois (simplifie)"],
    "zh-TW": ["zh-tw", "chinese (traditional)", "chinois (traditionnel)"],
}


def _normalize(s: str) -> str:
    """Normalise une chaine pour comparaison : sans accents, sans espaces superflus,
    en majuscules -- pour que 'Français' == 'Francais' == 'FRANCAIS'."""
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.strip().upper()


def find_language_aliases(target_code: str, target_label: str) -> list:
    """Retourne toutes les formes acceptees (normalisees) pour reperer la colonne
    d'une langue donnee dans un en-tete CSV."""
    aliases = set(LANGUAGE_ALIASES.get(target_code, [target_code]))
    aliases.add(target_code)
    aliases.add(target_label)
    return [_normalize(a) for a in aliases]

# Balises BBCode : [b], [/b], [color=#FF0000], [url=...], etc.
_BBCODE_RE = r'\[/?[a-zA-Z0-9_]+(?:=[^\]]*)?\]'
# Jetons de substitution courants : {PlayerName}, {0}, %s, %d, %1
_PLACEHOLDER_RE = r'\{[^{}]*\}|%[a-zA-Z0-9]+'

_PROTECTED_RE = re.compile(f'(?:{_BBCODE_RE})|(?:{_PLACEHOLDER_RE})')


def protect_segments(text: str) -> Tuple[str, List[str]]:
    """Remplace les balises BBCode et les placeholders par des jetons neutres
    (XXTAGnXX) que Google Translate laisse intacts. Retourne (texte_protege, liste_des_
    segments_originaux_dans_l_ordre)."""
    segments: List[str] = []

    def _replace(m):
        token = f"XXTAG{len(segments)}XX"
        segments.append(m.group(0))
        return token

    protected = _PROTECTED_RE.sub(_replace, text)
    return protected, segments


def restore_segments(translated_text: str, segments: List[str]) -> str:
    """Reinjecte les balises/placeholders d'origine a la place des jetons neutres."""
    result = translated_text
    for i, original in enumerate(segments):
        # Insensible a la casse et aux espaces que le traducteur peut inserer autour
        # du jeton (ex: 'xxtag0xx', 'XX TAG0 XX') -- on reste tolerant.
        pattern = re.compile(r'X{1,3}\s*TAG\s*' + str(i) + r'\s*X{1,3}', re.IGNORECASE)
        result = pattern.sub(original, result, count=1)
    return result


def is_available() -> bool:
    return _AVAILABLE


def get_import_error() -> str:
    """Detail exact de l'erreur de chargement de deep-translator, pour diagnostic --
    vide si tout va bien (voir is_available())."""
    return _IMPORT_ERROR or ""


def translate_text(text: str, target: str = "fr", source: str = "auto") -> str:
    """Traduit `text` vers la langue `target` (code ISO, ex: 'fr', 'en'), en preservant
    le BBCode et les placeholders. Leve une exception explicite si la bibliotheque
    n'est pas installee ou si la requete echoue (ex: pas de connexion internet) -- a
    capturer et afficher clairement cote GUI.

    Consulte d'abord la memoire de traduction (core/translation_memory.py) : si ce
    texte exact a deja ete traduit vers cette langue, renvoie directement le resultat
    memorise (aucun appel reseau) -- plus rapide et garantit une traduction coherente
    du meme texte partout dans le fichier. La memoire est indexee par langue SOURCE
    reelle, jamais 'auto' (sinon deux appels 'auto' pourraient a tort partager un cache
    alors que le texte source n'etait pas dans la meme langue)."""
    if not _AVAILABLE:
        raise RuntimeError(f"deep-translator indisponible ({_IMPORT_ERROR}). "
                            f"Si tu utilises la version installee (executable), "
                            f"ceci est un bug d'empaquetage a signaler avec ce "
                            f"detail exact. Si tu lances depuis les sources : "
                            f"pip install deep-translator")
    if not text or not text.strip():
        return text

    from . import translation_memory
    cached = translation_memory.get_cached(text, source, target)
    if cached is not None:
        return cached

    # Verifie le reglage de confidentialite AVANT tout appel reseau -- le cache
    # ci-dessus reste utilisable meme desactive (aucune donnee n'est envoyee,
    # juste une reutilisation locale d'un resultat deja obtenu precedemment).
    # Voir core/settings.py:get_online_translation_enabled() et PRIVACY.md.
    from . import settings
    if not settings.get_online_translation_enabled():
        raise RuntimeError(
            "Traduction en ligne desactivee (Options > Traduction en ligne "
            "(Google Translate)). Cette fonctionnalite envoie le texte a "
            "traduire aux serveurs Google -- voir PRIVACY.md. Reactive-la "
            "dans le menu Options si tu veux t'en servir."
        )

    protected, segments = protect_segments(text)
    translated = GoogleTranslator(source=source, target=target).translate(protected)
    if segments:
        translated = restore_segments(translated, segments)

    translation_memory.store(text, source, target, translated)
    return translated
