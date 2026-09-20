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
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .engine_errors import (AuthError, EngineUnavailableError,
                            QuotaExhaustedError)

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
    """Reinjecte les balises/placeholders d'origine a la place des jetons."""
    result = translated_text
    for i, original in enumerate(segments):
        # Correspondance EXACTE d'abord (XXTAGiXX) : la variante tolérante
        # (X{1,3} insensible a la casse) pouvait AVALER un 'x'/'X' reel du
        # texte colle au jeton (ex: '[b]x[/b]' -> '[b][/b]', vecu 20/09).
        exact = re.compile("XXTAG" + str(i) + "XX")
        if exact.search(result):
            result = exact.sub(lambda m, _orig=original: _orig, result, count=1)
            continue
        # Sinon variante TOLERANTE (casse/espaces inseres par le moteur,
        # ex: 'xxtag0xx', 'XX TAG0 XX').
        pattern = re.compile(r'X{1,3}\s*TAG\s*' + str(i) + r'\s*X{1,3}', re.IGNORECASE)
        # Remplacement PAR FONCTION, jamais par chaine : un template chaine
        # ferait interpreter les echappements du segment par re (\n du CSV
        # devenait un VRAI retour a la ligne -- vecu 19-20/09/2026, pertes
        # de \n sur tous les chemins "texte entier"). Une fonction de
        # remplacement n'est jamais escapee.
        result = pattern.sub(lambda m, _orig=original: _orig, result, count=1)
    return result


# Entite HTML numerique eventuellement COUPEE par le tokenizer d'Argos :
# 'Heure&#160;: ' sort en 'Heure & #160;:' (vecu reel, PDA.csv Atlantis).
# On la resserre et on la decode en vrai caractere (160 = espace insecable
# francaise legitime devant ':', on consomme donc l'espace qui la precede).
_ARGOS_ENTITY_RE = re.compile(r' ?&\s*#\s*(\d+)\s*;')


def _clean_argos_entities(s: str) -> str:
    return _ARGOS_ENTITY_RE.sub(lambda m: chr(int(m.group(1))), s)


_TOKEN_SCAN_RE = re.compile(r"X{1,3}\s*TAG\s*(\d+)\s*X{1,3}", re.IGNORECASE)


# Page d'erreur Google renvoyee COMME traduction par deep-translator
# (observe deux fois : 10/09 et 19/09 via des entrees de memoire
# polluees a l'ere de l'auto-stockage). Sert de filet final sur TOUT
# resultat moteur et sur les hits memoire.
_GARBAGE_MARKERS = ("that's an error", "<html", "google.com", "error 500")


def _looks_like_engine_garbage(text: str) -> bool:
    """Vrai si le texte ressemble a une page d'erreur de service plutot
    qu'a une traduction (jamais afficher ce garbage dans un fichier de
    jeu). Marques volontairement specifiques pour ne pas faux-positiver
    sur du texte de jeu legitime."""
    if not text:
        return False
    low = text.lower()
    return any(marker in low for marker in _GARBAGE_MARKERS)


def _token_sequence(text: str) -> list:
    """Indices des jetons XXTAGnXX presents dans le texte (tolerant casse et
    espaces que le moteur peut inserer autour)."""
    return [int(n) for n in _TOKEN_SCAN_RE.findall(text)]


def _translate_llm_whole_cell(gtext: str, source: str, target: str,
                              translate_whole, translate_fn) -> str:
    """Mode CELLULE ENTIERE pour les moteurs LLM (18/09/2026) : UNE requete
    par cellule -- le texte entier, protege en jetons XXTAG (balises,
    nombres, placeholders), part d'un bloc. Coherence linguistique (le
    modele voit la phrase complete), requetes et consigne systeme uniques.

    Squelette verifie : la sequence de jetons de la reponse doit etre
    EXACTEMENT celle de l'entree (meme count, meme ordre) ; sinon REPLI
    automatique sur le pipeline fragments pour cette cellule -- jamais de
    fichier corrompu. Les erreurs API (quota, reseau, cle) remontent : l'UI
    les affiche avec le delai."""
    protected, segments = protect_segments(gtext)
    expected = list(range(len(segments)))
    translated = translate_whole(protected, target)
    if _token_sequence(translated) != expected:
        return _translate_offline_fragments(gtext, source, target,
                                            translate_fn=translate_fn)
    return restore_segments(translated, segments)


# Bornes d'un lot LLM (v1.8.0). Tier gratuit Groq : 8 000 tokens/min -- a
# ~4 caracteres/token sur du texte de jeu EN/FR, 8 cellules / 4 000
# caracteres par requete restent largement sous les plafonds avec la
# consigne systeme et la reponse.
BATCH_MAX_CELLS = 8
BATCH_MAX_CHARS = 4000


def batch_chunks(texts: List[str], max_cells: int = BATCH_MAX_CELLS,
                 max_chars: int = BATCH_MAX_CHARS) -> List[List[int]]:
    """Groupe les indices des textes en lots pour translate_batch : au plus
    `max_cells` cellules et `max_chars` caracteres (enveloppes <CELLn>
    comprises) par requete. Les textes vides ne partent jamais (filtrés en
    amont par translate_batch_with_source) ; un texte plus long que
    `max_chars` part SEUL dans son lot."""
    chunks: List[List[int]] = []
    current: List[int] = []
    current_chars = 0
    for i, text in enumerate(texts):
        size = len(text) + 16  # enveloppe <CELLn></CELLn> + marge
        if current and (len(current) >= max_cells
                        or current_chars + size > max_chars):
            chunks.append(current)
            current, current_chars = [], 0
        current.append(i)
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


def _translate_llm_cells_batch(gtexts: List[str], source: str, target: str,
                               translate_batch, translate_whole,
                               translate_fn) -> List[str]:
    """Mode LOTS pour les moteurs LLM (v1.8.0) : tous les textes d'un lot
    partent en UNE requete (translate_batch). Le squelette de jetons de
    CHAQUE cellule est verifie comme en mode cellule entiere : une cellule
    manquante ou deviante dans la reponse repasse AUTOMATIQUEMENT en mode
    cellule entiere (qui lui-meme retombe sur les fragments) -- jamais de
    fichier corrompu, et une deviation du modele ne coute qu'un appel
    supplementaire sur la cellule fautive. Les erreurs API remontent (le
    worker les affiche pour chaque cellule du lot)."""
    protected_list, seg_list = [], []
    for gtext in gtexts:
        protected, segments = protect_segments(gtext)
        protected_list.append(protected)
        seg_list.append(segments)
    translated_list = translate_batch(protected_list, target)
    out: List[str] = []
    for gtext, segments, translated in zip(gtexts, seg_list, translated_list):
        if translated is None or _token_sequence(translated) != list(range(len(segments))):
            out.append(_translate_llm_whole_cell(gtext, source, target,
                                                 translate_whole, translate_fn))
        else:
            out.append(restore_segments(translated, segments))
    return out


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


# ---------------------------------------------------------------------------
# CHAINE DE SECOURS (v1.10.0, inspiree du failover de freellmapi) : quand le
# moteur principal (radio du sous-menu Moteur) atteint son quota ou tombe en
# panne, on enchaine les autres moteurs disponibles. Ordre canonique a partir
# du principal : Groq -> DeepL -> Google -> NLLB -> Argos. Les moteurs en
# ligne sont filtres par la permission "Traduction en ligne", les moteurs
# non configures/installes sont sautes, et un maillon qui echoue est mis au
# repos (cooldown) pour ne pas marteler un service mort sur chaque cellule.
# ---------------------------------------------------------------------------
_FALLBACK_ORDER = ("groq", "deepl", "google", "nllb", "argos")
_ENGINE_LABELS = {"groq": "Groq", "deepl": "DeepL", "google": "Google",
                  "nllb": "NLLB", "argos": "Argos"}
# Durees de repos apres une erreur basculable : le quota DeepL est MENSUEL
# (inutile de reessayer avant longtemps), les pannes reseau sont brèves.
_LINK_DOWN_S = {"groq": 60, "deepl": 1800, "google": 60,
                "nllb": 120, "argos": 120}
# Groq : cooldown restant annonce par l'API au-dela duquel le maillon est
# SAUTE sans meme tenter l'appel (sinon le throttle dormait jusqu'au
# reset -- journalier = heures -- d'ou les blocages de 10 minutes vecus
# 19/09/2026). En dessous, le throttle dort au plus 30 s : acceptable.
_GROQ_COOLDOWN_SKIP_S = 5.0
_LINK_DOWN_UNTIL: dict = {}
_LINK_LOCK = threading.Lock()
_LAST_FALLBACK_NOTE = ""


def _mark_link_down(engine: str, seconds: float) -> None:
    with _LINK_LOCK:
        _LINK_DOWN_UNTIL[engine] = time.monotonic() + seconds


def _link_available(engine: str) -> bool:
    with _LINK_LOCK:
        return time.monotonic() >= _LINK_DOWN_UNTIL.get(engine, 0.0)


def reset_link_states() -> None:
    """Remet a zero les repos de maillons (tests, ou nouveau lot lance
    par l'utilisateur : on redonne sa chance au moteur principal)."""
    global _LAST_FALLBACK_NOTE
    with _LINK_LOCK:
        _LINK_DOWN_UNTIL.clear()
        _LAST_FALLBACK_NOTE = ""


def last_fallback_note() -> str:
    """Note d'interface ("" si le moteur principal sert) : 'Secours :
    traduction assuree par DeepL' -- affichee dans la barre de
    progression du batch pour que la bascule soit VISIBLE."""
    with _LINK_LOCK:
        return _LAST_FALLBACK_NOTE


def _set_fallback_note(note: str) -> None:
    global _LAST_FALLBACK_NOTE
    with _LINK_LOCK:
        _LAST_FALLBACK_NOTE = note


def _fallback_chain(primary: str, target: str) -> list:
    """Moteurs disponibles, principal en tete : filtre permission en
    ligne, cles configurees, modele installe, langue couverte par DeepL."""
    from . import settings as _settings
    online_ok = _settings.get_online_translation_enabled()
    out = []
    for eng in [primary] + [e for e in _FALLBACK_ORDER if e != primary]:
        if eng in ("groq", "deepl", "google") and not online_ok:
            continue
        if eng == "groq":
            from . import groq_provider
            if not groq_provider.is_configured():
                continue
        elif eng == "deepl":
            from . import deepl_provider
            if not deepl_provider.is_configured() \
                    or not deepl_provider.target_supported(target):
                continue
        elif eng == "nllb":
            from . import nllb_provider
            if not nllb_provider.is_installed(_settings.get_nllb_variant()):
                continue
        out.append(eng)
    return out


def _translate_with_engine(eng: str, gtext: str, target: str, source: str,
                           timeout_seconds: float) -> str:
    """Un maillon de la chaine : traduction SANS glossaire (la restauration
    du glossaire est faite UNE fois par l'appelant). Erreurs typees pour
    les maillons en ligne ; TimeoutError possible sur Google."""
    if eng == "groq":
        from . import groq_provider
        return _translate_llm_whole_cell(
            gtext, source, target,
            translate_whole=groq_provider.translate_whole,
            translate_fn=groq_provider.translate)
    if eng == "deepl":
        from . import deepl_provider
        protected, segments = protect_segments(gtext)
        translated = deepl_provider.translate(protected, target)
        if _token_sequence(translated) == list(range(len(segments))):
            return restore_segments(translated, segments)
        # DeepL a perdu/altere des jetons (vecu reel 19/09/2026 : des \n
        # disparus, surtout quand plusieurs jetons sont colles) --
        # repli FRAGMENTS DeepL : seuls les morceaux de texte libre partent
        # au moteur, les jetons ne voyagent plus, structure garantie.
        return _translate_offline_fragments(
            gtext, source, target,
            translate_fn=lambda frag, src, tgt: deepl_provider.translate(
                frag, tgt))
    if eng == "google":
        return _translate_google(gtext, target, source, timeout_seconds)
    if eng == "nllb":
        return _translate_nllb(gtext, source, target)
    if eng == "argos":
        return _translate_offline_fragments(gtext, source, target)
    raise EngineUnavailableError(f"Moteur inconnu : {eng}")


def _translate_nllb(gtext: str, source: str, target: str) -> str:
    from . import lang_detect, nllb_provider
    from . import settings as _settings
    variant = _settings.get_nllb_variant()
    if not nllb_provider.is_installed(variant):
        from .i18n import t
        raise EngineUnavailableError(t("nllb.not_installed", variant=variant))

    def _nllb_frag(frag: str, src: str, tgt: str) -> str:
        # NLLB n'a pas de mode 'auto' : detection lexicale par fragment
        # (core/lang_detect.py) quand la source n'est pas connue.
        code = src
        if code in (None, "auto"):
            scores = lang_detect.language_scores(frag)
            code = "en" if scores.get("en", 0) >= scores.get("fr", 0) else "fr"
        return nllb_provider.translate(frag, code, tgt, variant)

    return _translate_offline_fragments(gtext, source, target,
                                        translate_fn=_nllb_frag)


def _translate_google(gtext: str, target: str, source: str,
                      timeout_seconds: float) -> str:
    """Chemin Google (deep-translator) : renvoie le texte avec les jetons
    restaures, SANS glossaire. Les pages d'erreur Google remontent en
    EngineUnavailableError (meme texte qu'avant) -> basculables."""
    protected, segments = protect_segments(gtext)
    result_holder: dict = {}

    def _call():
        try:
            result_holder['value'] = GoogleTranslator(
                source=source, target=target).translate(protected)
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
        raise EngineUnavailableError(
            "Le service de traduction en ligne a renvoye une page d'erreur "
            "(limitation Google). Reessaie plus tard, ou bascule sur le "
            "moteur hors ligne Argos (Options > Traduction hors ligne "
            "(Argos)...).")
    # Squelette de jetons : Google peut perdre des XXTAG comme DeepL
    # (v1.10.0) -- sans verification, les \n/balises disparaissaient
    # silencieusement. Structure perdue = erreur basculable.
    if _token_sequence(translated) != list(range(len(segments))):
        raise EngineUnavailableError(
            "Google a perdu ou altere des jetons de structure (\\n, "
            "balises) : traduction jetee, le moteur suivant prend le "
            "relais.")
    if segments:
        translated = restore_segments(translated, segments)
    return translated


def _raise_online_disabled(offline_error: str = None):
    """Messages de la garde confidentialite (identiques au chemin sans
    bascule -- la traduction EN LIGNE est une permission)."""
    if offline_error:
        raise RuntimeError(
            f"Traduction hors ligne impossible ({offline_error}) -- "
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


def _translate_via_chain(gtext: str, gloss_replacements: list, primary: str,
                         target: str, source: str,
                         timeout_seconds: float) -> str:
    """Exécuteur de la chaine de secours : essaie les maillons dans
    l'ordre, met au repos ceux qui echouent (quota/panne), s'arrete au
    premier succes. Une AuthError (cle refusee) ne bascule JAMAIS : c'est
    une erreur de configuration que l'utilisateur doit voir. Les maillons
    en ligne ne sont dans la chaine que si la permission confidentialite
    est donnee."""
    from . import glossary
    chain = _fallback_chain(primary, target)
    if not chain:
        _raise_online_disabled()
    from .i18n import t
    errors = []
    for eng in chain:
        if not _link_available(eng):
            continue
        if eng == "groq":
            from . import groq_provider
            wait = groq_provider.cooldown_remaining()
            if wait > _GROQ_COOLDOWN_SKIP_S:
                # cooldown 429 encore actif : sauter le maillon SANS appel
                # (le throttle dormirait sinon, jusqu'au reset journalier
                # eventuel -- blocage de 10 minutes vecu 19/09/2026)
                from .groq_provider import _fmt_duration
                errors.append((eng, t("groq.rate_limited",
                                      delay=_fmt_duration(wait))))
                continue
        try:
            translated = _translate_with_engine(eng, gtext, target, source,
                                                timeout_seconds)
        except AuthError:
            raise
        except (QuotaExhaustedError, EngineUnavailableError,
                TimeoutError) as e:
            seconds = _LINK_DOWN_S.get(eng, 60)
            if eng == "groq":
                from . import groq_provider
                # aligner le repos sur le reset REELLEMENT annonce (24 s
                # par minute, mais HEURES sur le plafond journalier)
                seconds = max(seconds, groq_provider.cooldown_remaining())
            _mark_link_down(eng, seconds)
            errors.append((eng, str(e)))
            continue
        if _looks_like_engine_garbage(translated):
            # Filet final : une page d'erreur servie "avec succes" par un
            # moteur (LLM hallucinant, MT limite) n'est JAMAIS une
            # traduction -- maillon ecarte, le suivant prend le relais.
            seconds = _LINK_DOWN_S.get(eng, 60)
            _mark_link_down(eng, seconds)
            errors.append((eng, "page d'erreur moteur"))
            continue
        _set_fallback_note("" if eng == primary else
                           t("trans.fallback_used",
                             engine=_ENGINE_LABELS[eng]))
        _debug_note(eng, gtext, translated,
                    fallback=eng != primary)
        return glossary.restore_glossary(translated, gloss_replacements)
    # Tous les maillons disponibles ont echoue : composer une erreur qui
    # dit TOUT (et repasse par les messages historiques si la permission
    # en ligne est la cause racine).
    from . import settings as _settings
    if not _settings.get_online_translation_enabled():
        offline_err = next((msg for eng, msg in errors
                            if eng in ("nllb", "argos")), None)
        _raise_online_disabled(offline_err)
    detail = " | ".join(f"{_ENGINE_LABELS[eng]} : {msg}"
                        for eng, msg in errors) or "aucun moteur disponible"
    raise EngineUnavailableError(
        "Tous les moteurs de traduction ont echoue -- " + detail)


def _translate_legacy_single(gtext: str, gloss_replacements: list,
                             engine: str, target: str, source: str,
                             timeout_seconds: float) -> str:
    """Chemin historique (bascule desactivee) : UN seul moteur, messages
    et replis d'origine (Argos -> Google si permission, combined offline)."""
    from . import glossary
    from . import settings as _settings
    _offline_error: Optional[str] = None
    if engine == "nllb":
        result = _translate_nllb(gtext, source, target)
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
    if not _settings.get_online_translation_enabled():
        _raise_online_disabled(_offline_error)

    if engine == "groq":
        # LLM EN LIGNE (Groq Inc. + fournisseur du modele) : place APRES la
        # garde de confidentialite, comme Google -- la case "Traduction en
        # ligne" autorise/bloque aussi ce moteur.
        from . import groq_provider
        groq_result = _translate_llm_whole_cell(
            gtext, source, target,
            translate_whole=groq_provider.translate_whole,
            translate_fn=groq_provider.translate)
        return glossary.restore_glossary(groq_result, gloss_replacements)

    translated = _translate_google(gtext, target, source, timeout_seconds)
    translated = glossary.restore_glossary(translated, gloss_replacements)
    return translated


# JOURNAL DE DIAGNOSTIC (v1.10.0, apres les pertes de \n difficiles a
# attribuer) : chaque traduction moteur est appendue en JSONL
# (~/.empyrion_editor/translation_debug.jsonl) -- moteur reellement
# utilise, entree et sortie (tronquees), repli ou non. Permet de dire
# EXACTEMENT quel moteur a produit quelle cellule. Jamais bloquant :
# toute erreur d'ecriture est ignoree.
_DEBUG_LOG_PATH = Path.home() / ".empyrion_editor" / "translation_debug.jsonl"
_DEBUG_MAX_LEN = 800
_DEBUG_LOCK = threading.Lock()


def _debug_note(engine: str, gtext: str, translated: str,
                fallback: bool = False) -> None:
    """Append une ligne JSONL de diagnostic (moteur, entree, sortie).
    Rotation simple a 2 Mo (vieux lignes jetees : c'est un anneau de
    diagnostic). Aucune exception ne remonte : le journal est un confort."""
    try:
        import json as _json
        import time as _time
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _DEBUG_LOG_PATH.exists() and \
                _DEBUG_LOG_PATH.stat().st_size > 2 * 1024 * 1024:
            _DEBUG_LOG_PATH.unlink()
        line = _json.dumps({
            "ts": _time.strftime("%H:%M:%S"),
            "engine": engine,
            "fallback": bool(fallback),
            "in": gtext[:_DEBUG_MAX_LEN],
            "out": (translated or "")[:_DEBUG_MAX_LEN],
        }, ensure_ascii=False)
        with _DEBUG_LOCK:
            with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def _engine_dispatch(gtext: str, gloss_replacements: list, target: str,
                     source: str, timeout_seconds: float) -> str:
    """Choix bascule active ? -> chaine de secours ; sinon chemin unique
    historique. Point d'entree commun de translate_text et du lot."""
    from . import settings as _settings
    engine = _settings.get_translation_engine()
    if _settings.get_engine_fallback_enabled():
        return _translate_via_chain(gtext, gloss_replacements, engine,
                                    target, source, timeout_seconds)
    result = _translate_legacy_single(gtext, gloss_replacements, engine,
                                      target, source, timeout_seconds)
    _debug_note(engine, gtext, result)
    return result


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
    if cached is not None and not _looks_like_engine_garbage(cached):
        # 293 entrees "Error 500" de l'ere auto-stockage polluaient la
        # memoire reelle (vecu 19/09/2026) : un hit memoire qui ressemble
        # a une page d'erreur est IGNORE (re-traduit proprement).
        return cached
    from . import vanilla_memory
    vanilla_cached = vanilla_memory.get_vanilla_cached(text, target)
    if vanilla_cached is not None:
        return vanilla_cached

    gtext, gloss_replacements = glossary.apply_glossary(text, target)

    translated = _engine_dispatch(gtext, gloss_replacements, target, source,
                                  timeout_seconds)
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
    if cached is not None and not _looks_like_engine_garbage(cached):
        # Memoire utilisateur prioritaire, MAIS si elle contient
        # exactement la traduction officielle Eleon, la source est
        # 'vanilla' : le vert reste un signal de conformite (retour
        # 19/09/2026 : plus de vert sur les fichiers deja traduits).
        if vanilla_memory.vanilla_matches(text, cached, target):
            return cached, "vanilla"
        return cached, "memory"
    vanilla_cached = vanilla_memory.get_vanilla_cached(text, target)
    if vanilla_cached is not None:
        return vanilla_cached, "vanilla"
    translated = translate_text(text, target=target, source=source,
                                timeout_seconds=timeout_seconds,
                                store_in_memory=False)
    return translated, "engine"


def translate_batch_with_source(texts: List[str], target: str = "fr",
                                source: str = "auto"
                                ) -> List[Tuple[str, str]]:
    """Version LOT de translate_text_with_source, utilisee par le worker de
    traduction en masse (v1.8.0) : memoire utilisateur puis memoire vanille
    resolues par texte (sans rappeler le moteur), et le reste part au
    moteur EN UNE SEULE requete quand le moteur est Groq avec le mode lots
    active (Options > Traduction) -- le tier gratuit est plafonne en
    debit, grouper les cellules divise d'autant le nombre de requetes.
    Squelette de jetons verifie par cellule, repli cellule entiere puis
    fragments (voir _translate_llm_cells_batch).

    Retourne une liste parallele de (traduction, source). Texte vide ->
    (texte, ""). Les erreurs moteur remontent : le worker les affiche pour
    chaque cellule du lot et compte les echecs consecutifs."""
    results: List[Tuple[str, str]] = [(text, "") for text in texts]
    pending: List[Tuple[int, str]] = [
        (i, text) for i, text in enumerate(texts) if text and text.strip()]
    if not pending:
        return results

    from . import translation_memory, vanilla_memory
    still: List[Tuple[int, str]] = []
    for i, text in pending:
        cached = translation_memory.get_cached(text, source, target)
        if cached is not None and not _looks_like_engine_garbage(cached):
            if vanilla_memory.vanilla_matches(text, cached, target):
                results[i] = (cached, "vanilla")
            else:
                results[i] = (cached, "memory")
            continue
        vanilla_cached = vanilla_memory.get_vanilla_cached(text, target)
        if vanilla_cached is not None:
            results[i] = (vanilla_cached, "vanilla")
            continue
        still.append((i, text))
    if not still:
        return results

    from . import settings as _settings
    engine = _settings.get_translation_engine()
    fallback_on = _settings.get_engine_fallback_enabled()
    # _link_available : apres un echec quota, Groq est au repos (aligne
    # sur le reset annonce) -- ne pas repartir en requete lot, la chaine
    # sert les cellules directement (vecu 19/09/2026 : pokes gaspilles).
    if (engine == "groq" and _settings.get_groq_batch_enabled()
            and len(still) > 1 and _link_available("groq")):
        from . import glossary, groq_provider
        gtexts, gloss_replacements = [], []
        for _i, text in still:
            gtext, replacements = glossary.apply_glossary(text, target)
            gtexts.append(gtext)
            gloss_replacements.append(replacements)
        try:
            translated_list = _translate_llm_cells_batch(
                gtexts, source, target,
                translate_batch=groq_provider.translate_batch,
                translate_whole=groq_provider.translate_whole,
                translate_fn=groq_provider.translate)
        except AuthError:
            raise  # cle refusee : jamais de bascule silencieuse
        except (QuotaExhaustedError, EngineUnavailableError, TimeoutError) as e:
            if not fallback_on:
                raise
            # Bascule (v1.10.0) : le lot Groq echoue (quota/panne) -> le
            # repo du maillon est pose (aligne sur le reset REELLEMENT
            # annonce : minutes par quota, HEURES sur le plafond
            # journalier) et TOUTES les cellules du lot continuent par la
            # chaine, cellule par cellule -- le worker ne voit jamais
            # d'echec si un autre moteur peut servir (la note d'interface
            # est posee par la chaine elle-meme).
            from . import groq_provider as _gp
            _mark_link_down("groq", max(_LINK_DOWN_S.get("groq", 60),
                                        _gp.cooldown_remaining()))
        else:
            for (i, _text), translated, replacements, gtext in zip(
                    still, translated_list, gloss_replacements, gtexts):
                _debug_note("groq", gtext, translated)
                results[i] = (glossary.restore_glossary(translated, replacements),
                              "engine")
            return results

    # Chemin classique, cellule par cellule (autres moteurs, mode lots
    # desactive, ou lot restant a une seule cellule) -- passe par le
    # dispatcher commun : chaine de secours incluse quand elle est active.
    from . import glossary
    for i, text in still:
        gtext, replacements = glossary.apply_glossary(text, target)
        translated = _engine_dispatch(gtext, replacements, target, source,
                                      DEFAULT_TRANSLATION_TIMEOUT_S)
        results[i] = (translated, "engine")
    return results
