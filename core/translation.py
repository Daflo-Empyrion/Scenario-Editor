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
import threading
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


# Chiffres cyrilliques (А-Я, а-я, Ё, ё) : signature d'un en-tete "double-encode"
# (UTF-8 decode par erreur en CP1251 -- voir repair_mojibake).
_CYRILLIC_RE = re.compile('[\u0410-\u044f\u0401\u0451]')


def repair_mojibake(s: str) -> str:
    """Tente de reparer une chaine 'double-encodee' : 'Français' stocke en UTF-8
    puis decode par erreur en CP1251 donne 'FranГ§ais' (vecu reel sur
    atlantis/Extras/PDA/PDA.csv, scenario d'origine russe -- la colonne FR
    n'etait plus reconnue par find_language_aliases et la traduction ecrasait
    la cellule source). Re-encode en CP1251 puis decode en UTF-8 ; retourne
    la chaine originale si aucun cyrillique ou si l'aller-retour echoue
    (la chaine n'etait alors pas un mojibake)."""
    if not _CYRILLIC_RE.search(s):
        return s
    try:
        return s.encode('cp1251').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

# Balises BBCode : [b], [/b], [color=#FF0000], [url=...], etc.
_BBCODE_RE = r'\[/?[a-zA-Z0-9_]+(?:=[^\]]*)?\]'
# Balise de dialogue Empyrion ('[IDA :]', '[NPC:]') : nom + ':' DANS la
# balise -- jamais du BBCode legitime, jamais du texte a traduire. Vecu reel
# (17/09/2026, PDA.csv Atlantis) : '[IDA :]' parti au moteur comme fragment
# de texte libre, ressorti 'Je vous en prie.' (hallucination).
_DIALOG_TAG_RE = r'\[[A-Za-z0-9_]+ ?:\]'
# Jetons du glossaire (XXGLOS<n>XX poses par core/glossary.apply_glossary) :
# s'ils traversent un moteur ils y sont deformes (casse, ponctuation) et la
# restauration echoue -- le terme du glossaire serait traduit quand meme.
_GLOSS_TOKEN_RE = r'XXGLOS\d+XX'
# Nombres ISOLLES (entiers, decimaux, dates pointees) : jamais du texte a
# traduire, et les moteurs hallucinent dessus ('29827602.55' ressorti
# "Le montant de l'impot sur le revenu", vecu reel 17/09/2026). Les nombres
# COLLES a des lettres ('x50', '1A', '1969B') restent au moteur : ils font
# partie du mot.
_NUMBER_RE = r'(?<![\w])\d+(?:[.,]\d+)*(?![\w])'
# [-] : balise de fermeture Empyrion (fin de couleur) -- le tiret n'est pas
# couvert par _BBCODE_RE, et elle doit rester hors du texte envoye au moteur.
_CLOSING_DASH_RE = r'\[-\]'
# Retours a la ligne LITTERAUX des CSV Empyrion ('\n' ecrit backslash + n) :
# sans protection, le moteur mangait le backslash et laissait un 'n' orphelin
# dans la traduction (vecu reel, PDA.csv Atlantis, 12/09/2026).
_LITERAL_NEWLINE_RE = r'(?:\\n)+'
# Jetons de substitution courants : {PlayerName}, {0}, %s, %d, %1
_PLACEHOLDER_RE = r'\{[^{}]*\}|%[a-zA-Z0-9]+'

_PROTECTED_RE = re.compile(
    f'(?:{_BBCODE_RE})|(?:{_DIALOG_TAG_RE})|(?:{_CLOSING_DASH_RE})'
    f'|(?:{_LITERAL_NEWLINE_RE})|(?:{_PLACEHOLDER_RE})|(?:{_GLOSS_TOKEN_RE})'
    f'|(?:{_NUMBER_RE})')

# Protection pour l'ANALYSE GRAMMALECTE (core/spellcheck.py::_rebuild_lines)
# : SANS les nombres -- ils doivent rester du texte visible pour la
# grammaire (aucune faute dans un nombre, mais la ponctuation AUTOUR nous
# interesse : espace avant ':' d'une heure 'Time: 1900'). Les nombres ne
# sont masques que pour l'ENVOI aux moteurs de traduction.
_PROTECTED_RE_GRAMMAR = re.compile(
    f'(?:{_BBCODE_RE})|(?:{_DIALOG_TAG_RE})|(?:{_CLOSING_DASH_RE})'
    f'|(?:{_LITERAL_NEWLINE_RE})|(?:{_PLACEHOLDER_RE})')


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


# Entite HTML numerique eventuellement COUPEE par le tokenizer d'Argos :
# 'Heure&#160;: ' sort en 'Heure & #160;:' (vecu reel, PDA.csv Atlantis).
# On la resserre et on la decode en vrai caractere (160 = espace insecable
# francaise legitime devant ':', on consomme donc l'espace qui la precede).
_ARGOS_ENTITY_RE = re.compile(r' ?&\s*#\s*(\d+)\s*;')


def _clean_argos_entities(s: str) -> str:
    return _ARGOS_ENTITY_RE.sub(lambda m: chr(int(m.group(1))), s)


def _translate_offline_fragments(text: str, source: str, target: str,
                                 translate_fn=None) -> str:
    """Pipeline en DEUX temps (approche "Google" : on n'envoie au moteur
    que le texte, jamais le BBCode) :

    1. protect_segments(text) remplace balises/placeholders par des jetons ;
    2. seuls les fragments de TEXTE LIBRE restants sont traduits, un par un ;
    3. le texte final est reconstruit avec les balises d'origine a leur place
       exacte -- la structure BBCode est garantie par construction, alors
       qu'envoyer la chaine entiere a un moteur le fait RECOPIER sans
       traduire des que la densite de balises est forte (vecu reel : ligne
       'Prologue: Journey into the unknown' du PDA.csv Atlantis, entiere
       renvoyee en anglais, 12/09/2026).

    translate_fn(frag, source, target) : fonction de traduction d'un
    fragment (defaut : Argos). NLLB passe la sienne (core/nllb_provider).
    Argos est local : les appels multiples par fragment ne coutent rien.
    Leve une exception si le moteur sous-jacent echoue."""
    from . import argos_provider
    translate_fn = translate_fn or argos_provider.translate_offline
    protected, segments = protect_segments(text)
    parts = re.split(r'(XXTAG\d+XX)', protected)
    out: List[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            out.append(segments[idx // 2] if idx // 2 < len(segments) else part)
        elif part.strip() and re.search(r"[^\W_]", part, re.UNICODE):
            # conserver les espaces de bord du fragment original autour de la
            # traduction (le modele n'a pas a les decider). Les fragments SANS
            # aucun caractere alphanumerique (un '!' isole entre deux balises,
            # '===', ...) ne partent PAS au moteur : les moteurs hallucinent
            # dessus ('!' -> '- Oui.', vecu 12/09/2026) et il n'y a rien a
            # traduire.
            lead = part[:len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            core = translate_fn(part.strip(), source, target)
            out.append(lead + _clean_argos_entities(core) + trail)
        else:
            out.append(part)
    return "".join(out)


def is_available() -> bool:
    return _AVAILABLE


def get_import_error() -> str:
    """Detail exact de l'erreur de chargement de deep-translator, pour diagnostic --
    vide si tout va bien (voir is_available())."""
    return _IMPORT_ERROR or ""


# Duree maximale d'attente d'une reponse de Google Translate. deep-translator
# 1.11 ne passe AUCUN timeout a requests : sans cette garde, une connexion
# pendante (reseau tombe, pare-feu silencieux, VPN capricieux...) figerait
# l'appelant indefiniment -- sur l'interface, tout l'editeur serait gele.
DEFAULT_TRANSLATION_TIMEOUT_S = 15.0


def translate_text(text: str, target: str = "fr", source: str = "auto",
                   timeout_seconds: float = DEFAULT_TRANSLATION_TIMEOUT_S,
                   store_in_memory: bool = True) -> str:
    """Traduit `text` vers la langue `target` (code ISO, ex: 'fr', 'en'), en preservant
    le BBCode et les placeholders. Leve une exception explicite si la bibliotheque
    n'est pas installee ou si la requete echoue (ex: pas de connexion internet) -- a
    capturer et afficher clairement cote GUI. Leve TimeoutError si Google ne repond
    pas dans `timeout_seconds` (voir DEFAULT_TRANSLATION_TIMEOUT_S).

    MEMOIRE DE TRADUCTION (core/translation_memory.py) consultee en PREMIER,
    quel que soit le moteur choisi : meme texte -> meme traduction, partout,
    sans rappeler l'API ; puis memoire VANILLE (core/vanilla_memory.py) : les
    textes identiques a la localisation officielle du jeu ressortent avec la
    traduction Eleon. L'ALIMENTATION de la memoire, elle, ne se fait plus
    automatiquement ici : les revues passent store_in_memory=False et
    l'interface enregistre la traduction au moment ou l'utilisateur LA VALIDE
    (cases cochees de la revue) -- demande du 12/09/2026.

    GLOSSAIRE (core/glossary.py) : les termes actifs sont proteges par jetons
    avant l'envoi au moteur et reinjectes dans la reponse, quel que soit le
    moteur -- la terminologie imposee n'est jamais traduite a tort.

    IMPLEMENTATION DU TIMEOUT : l'appel reseau tourne dans un thread daemon sur
    lequel on joint avec un delai -- deep-translator n'exposant pas de timeout dans
    sa version courante. En cas de depot, TimeoutError est levee cote appelant
    pendant que la requete orpheline finit par echouer toute seule dans son thread
    (daemon : ne bloque jamais la sortie de l'application)."""
    if not _AVAILABLE:
        raise RuntimeError(f"deep-translator indisponible ({_IMPORT_ERROR}). "
                            f"Si tu utilises la version installee (executable), "
                            f"ceci est un bug d'empaquetage a signaler avec ce "
                            f"detail exact. Si tu lances depuis les sources : "
                            f"pip install deep-translator")
    if not text or not text.strip():
        return text

    from . import glossary

    from . import translation_memory
    cached = translation_memory.get_cached(text, source, target)
    if cached is not None:
        return cached
    from . import vanilla_memory
    vanilla_cached = vanilla_memory.get_vanilla_cached(text, target)
    if vanilla_cached is not None:
        return vanilla_cached

    gtext, gloss_replacements = glossary.apply_glossary(text)

    # Moteur HORS LIGNE prefere (Options > Moteur de traduction) : si Argos
    # est installe avec la paire demandee, on traduit localement -- aucune
    # donnee ne quitte le poste, aucun appel Google. Si la paire manque, on
    # retombe en ligne SEULEMENT si la traduction en ligne est permise ; sinon
    # le message combine les DEUX causes (retour utilisateur 10/09/2026 : le
    # message "Google non active" apparaissait a tort sur un echec Argos).
    from . import settings as _settings
    _offline_error: Optional[str] = None
    engine = _settings.get_translation_engine()
    if engine == "nllb":
        from . import lang_detect, nllb_provider
        variant = _settings.get_nllb_variant()
        if not nllb_provider.is_installed(variant):
            from .i18n import t
            raise RuntimeError(t("nllb.not_installed", variant=variant))

        def _nllb_frag(frag: str, src: str, tgt: str) -> str:
            # NLLB n'a pas de mode 'auto' : detection lexicale par fragment
            # (core/lang_detect.py) quand la source n'est pas connue.
            code = src
            if code in (None, "auto"):
                scores = lang_detect.language_scores(frag)
                code = "en" if scores.get("en", 0) >= scores.get("fr", 0) else "fr"
            return nllb_provider.translate(frag, code, tgt, variant)

        result = _translate_offline_fragments(gtext, source, target,
                                              translate_fn=_nllb_frag)
        return glossary.restore_glossary(result, gloss_replacements)

    if engine == "argos":
        try:
            # Ne jamais envoyer le BBCode brut a Argos : le modele le recopie
            # sans traduire (bug vecu PDA.csv Atlantis, 12/09/2026) -- seuls
            # les fragments de texte libre partent au moteur, la structure est
            # reconstruite apres coup (voir _translate_offline_fragments).
            argos_result = _translate_offline_fragments(gtext, source, target)
        except Exception as e:
            _offline_error = str(e) or "moteur Argos ou paire de langues absente"
        else:
            # chemin Argos reussi : retour IMMEDIAT, ne jamais traverser le
            # garde "traduction en ligne desactivee" (qui ne le concerne pas)
            return glossary.restore_glossary(argos_result, gloss_replacements)

    # Verifie le reglage de confidentialite AVANT tout appel reseau -- le cache
    # ci-dessus reste utilisable meme desactive (aucune donnee n'est envoyee,
    # juste une reutilisation locale d'un resultat deja obtenu precedemment).
    # Voir core/settings.py:get_online_translation_enabled() et PRIVACY.md.
    from . import settings
    if not settings.get_online_translation_enabled():
        if _offline_error:
            raise RuntimeError(
                f"Traduction hors ligne impossible ({_offline_error}) -- "
                f"ajoute la langue manquante dans Options > Traduction hors "
                f"ligne (Argos) -- ET la traduction en ligne est desactivee "
                f"(voir Options). Au moins un des deux moteurs est requis."
            )
        raise RuntimeError(
            "Traduction en ligne desactivee (Options > Traduction en ligne "
            "(Google Translate)). Cette fonctionnalite envoie le texte a "
            "traduire aux serveurs Google -- voir PRIVACY.md. Reactive-la "
            "dans le menu Options si tu veux t'en servir."
        )

    protected, segments = protect_segments(gtext)

    result_holder: dict = {}

    def _call():
        try:
            result_holder['value'] = GoogleTranslator(source=source, target=target).translate(protected)
        except BaseException as e:
            # Volontairement large : l'exception doit traverser le join pour etre
            # relevee dans le thread appelant (jamais silencieuse).
            result_holder['error'] = e

    worker = threading.Thread(target=_call, daemon=True, name="empyrion-translate")
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        raise TimeoutError(
            f"Google Translate n'a pas repondu en {timeout_seconds:.0f} s "
            f"(reseau indisponible ou pare-feu ?). Reessaie plus tard, ou "
            f"desactive la traduction en ligne dans les options (voir PRIVACY.md).")
    if 'error' in result_holder:
        raise result_holder['error']

    translated = result_holder['value']
    # deep-translator peut RENVOYER la page d'erreur HTML de Google comme si
    # c'etait la traduction (observe en reel : "Error 500 (Server Error)!!1")
    # -- jamais afficher ce garbage dans un fichier de jeu (retour du
    # 10/09/2026).
    lowered = (translated or "").lower()
    if not translated or "that's an error" in lowered or "error 5" in lowered \
            or "google.com" in lowered or "<html" in lowered:
        raise RuntimeError(
            "Le service de traduction en ligne a renvoye une page d'erreur "
            "(limitation Google). Reessaie plus tard, ou bascule sur le "
            "moteur hors ligne Argos (Options > Traduction hors ligne "
            "(Argos)...).")
    if segments:
        translated = restore_segments(translated, segments)

    translated = glossary.restore_glossary(translated, gloss_replacements)
    if store_in_memory:
        translation_memory.store(text, source, target, translated)
    return translated


def translate_text_with_source(text: str, target: str = "fr", source: str = "auto",
                               timeout_seconds: float = DEFAULT_TRANSLATION_TIMEOUT_S
                               ) -> Tuple[str, str]:
    """Pareil que translate_text (jamais de store automatique : la memoire est
    alimentee a la VALIDATION) mais retourne (traduction, source) ou source
    vaut 'memory' (memoire utilisateur), 'vanilla' (localisation officielle
    Eleon) ou 'engine' (moteur) -- la revue distingue visuellement les
    traductions vanille (demande 17/09/2026). Source vide si rien n'a ete
    traduit (texte vide)."""
    if not text or not text.strip():
        return text, ""
    from . import translation_memory, vanilla_memory
    cached = translation_memory.get_cached(text, source, target)
    if cached is not None:
        return cached, "memory"
    vanilla_cached = vanilla_memory.get_vanilla_cached(text, target)
    if vanilla_cached is not None:
        return vanilla_cached, "vanilla"
    translated = translate_text(text, target=target, source=source,
                                timeout_seconds=timeout_seconds,
                                store_in_memory=False)
    return translated, "engine"
