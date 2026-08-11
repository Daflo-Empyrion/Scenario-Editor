"""
Traduction de texte via Google Translate (bibliotheque deep-translator, gratuite, sans
cle API). Utilise pour la traduction ponctuelle d'une valeur (clic droit -> Traduire),
en complement du systeme de traduction CSV de masse (outil separe, hors ligne via Ollama).
"""
from typing import Optional

try:
    from deep_translator import GoogleTranslator
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


# Langues courantes proposees dans le menu -- (libelle affiche, code langue)
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


def is_available() -> bool:
    return _AVAILABLE


def translate_text(text: str, target: str = "fr", source: str = "auto") -> str:
    """Traduit `text` vers la langue `target` (code ISO, ex: 'fr', 'en'). Leve une
    exception explicite si la bibliotheque n'est pas installee ou si la requete echoue
    (ex: pas de connexion internet) -- a capturer et afficher clairement cote GUI."""
    if not _AVAILABLE:
        raise RuntimeError("deep-translator n'est pas installe. Lance : pip install deep-translator")
    if not text or not text.strip():
        return text
    return GoogleTranslator(source=source, target=target).translate(text)
