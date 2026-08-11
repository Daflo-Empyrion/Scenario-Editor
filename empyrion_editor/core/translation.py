"""
Traduction de texte via Google Translate (bibliotheque deep-translator, gratuite, sans
cle API). Utilise pour la traduction ponctuelle d'une valeur (clic droit -> Traduire),
en complement du systeme de traduction CSV de masse (outil separe, hors ligne via Ollama).

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
except ImportError:
    _AVAILABLE = False


COMMON_LANGUAGES = [
    ("Francais", "fr"),
    ("Anglais", "en"),
    ("Allemand", "de"),
    ("Espagnol", "es"),
    ("Italien", "it"),
    ("Russe", "ru"),
    ("Portugais", "pt"),
    ("Neerlandais", "nl"),
    ("Polonais", "pl"),
    ("Chinois (simplifie)", "zh-CN"),
]

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


def translate_text(text: str, target: str = "fr", source: str = "auto") -> str:
    """Traduit `text` vers la langue `target` (code ISO, ex: 'fr', 'en'), en preservant
    le BBCode et les placeholders. Leve une exception explicite si la bibliotheque
    n'est pas installee ou si la requete echoue (ex: pas de connexion internet) -- a
    capturer et afficher clairement cote GUI."""
    if not _AVAILABLE:
        raise RuntimeError("deep-translator n'est pas installe. Lance : pip install deep-translator")
    if not text or not text.strip():
        return text

    protected, segments = protect_segments(text)
    translated = GoogleTranslator(source=source, target=target).translate(protected)
    if segments:
        translated = restore_segments(translated, segments)
    return translated
