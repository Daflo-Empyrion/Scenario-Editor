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
Traduction de texte par IA (fournisseurs configures dans Options > Traduction
> Fournisseurs IA -- Groq, OpenRouter, serveur local... via core/ai/router).
Point d'entree unique reutilise par TOUTES les fonctions de traduction de
l'application -- traduction ponctuelle d'une cellule (clic droit -> Traduire),
traduction en lot, et "Combler les langues manquantes...". Les moteurs
Google/DeepL/Argos/NLLB et le moteur Groq direct ont ete RETIRES (decision du
31/10 : qualite de traduction superieure via les modeles IA, une seule
architecture a maintenir) -- voir la fiche cerveau si besoin de les retrouver.

IMPORTANT -- protection du BBCode et des placeholders : le texte Empyrion contient
souvent des balises de mise en forme ([b]...[/b], [color=#FF0000]...[/color]) et des
jetons de substitution ({PlayerName}, %s, {0}...) qui ne doivent JAMAIS etre traduits
ni alteres. Avant d'envoyer le texte au modele, on les extrait et on les remplace
par des jetons neutres insensibles a la traduction, puis on les reinjecte a leur place
dans le resultat.
"""
import re
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .engine_errors import (AuthError, EngineUnavailableError,
                            QuotaExhaustedError)

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
# couvert par _BBCODE_RE, et elle doit rester hors du texte envoye au modele.
_CLOSING_DASH_RE = r'\[-\]'
# Retours a la ligne LITTERAUX des CSV Empyrion ('\n' ecrit backslash + n) :
# sans protection, le modele mangeait le backslash et laissait un 'n' orphelin
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
# sont masques que pour l'ENVOI au modele de traduction.
_PROTECTED_RE_GRAMMAR = re.compile(
    f'(?:{_BBCODE_RE})|(?:{_DIALOG_TAG_RE})|(?:{_CLOSING_DASH_RE})'
    f'|(?:{_LITERAL_NEWLINE_RE})|(?:{_PLACEHOLDER_RE})')


def protect_segments(text: str) -> Tuple[str, List[str]]:
    """Remplace les balises BBCode et les placeholders par des jetons neutres
    (XXTAGnXX) que le modele laisse intacts. Retourne (texte_protege,
    liste_des_segments_originaux_dans_l_ordre)."""
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
        # Sinon variante TOLERANTE (casse/espaces inseres par le modele,
        # ex: 'xxtag0xx', 'XX TAG0 XX').
        pattern = re.compile(r'X{1,3}\s*TAG\s*' + str(i) + r'\s*X{1,3}', re.IGNORECASE)
        # Remplacement PAR FONCTION, jamais par chaine : un template chaine
        # ferait interpreter les echappements du segment par re (\n du CSV
        # devenait un VRAI retour a la ligne -- vecu 19-20/09/2026, pertes
        # de \n sur tous les chemins "texte entier"). Une fonction de
        # remplacement n'est jamais escapee.
        result = pattern.sub(lambda m, _orig=original: _orig, result, count=1)
    return result


# Entite HTML numerique eventuellement COUPEE par un modele ('Heure&#160;: '
# sorti en 'Heure & #160;:' -- vecu reel, PDA.csv Atlantis). On la resserre
# et on la decode en vrai caractere (160 = espace insecable legitime devant
# ':', on consomme donc l'espace qui la precede).
_ENTITY_RE = re.compile(r' ?&\s*#\s*(\d+)\s*;')


def _clean_html_entities(s: str) -> str:
    return _ENTITY_RE.sub(lambda m: chr(int(m.group(1))), s)


_TOKEN_SCAN_RE = re.compile(r"X{1,3}\s*TAG\s*(\d+)\s*X{1,3}", re.IGNORECASE)


# Page d'erreur de service renvoyee COMME traduction par un modele (observe
# a l'ere Google via des entrees de memoire polluees). Sert de filet final
# sur TOUT resultat moteur et sur les hits memoire.
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
    espaces que le modele peut inserer autour)."""
    return [int(n) for n in _TOKEN_SCAN_RE.findall(text)]


def _translate_fragments(text: str, target: str, translate_fn) -> str:
    """Pipeline FRAGMENTS (approche "Google" : on n'envoie au modele que le
    texte, jamais le BBCode) :

    1. protect_segments(text) remplace balises/placeholders par des jetons ;
    2. seuls les fragments de TEXTE LIBRE restants sont traduits, un par un ;
    3. le texte final est reconstruit avec les balises d'origine a leur place
       exacte -- la structure BBCode est garantie par construction, alors
       qu'envoyer la chaine entiere peut faire RECOPIER le texte sans le
       traduire des que la densite de balises est forte (vecu reel : ligne
       'Prologue: Journey into the unknown' du PDA.csv Atlantis, entiere
       renvoyee en anglais, 12/09/2026).

    translate_fn(frag, source, target) : traduction d'un fragment. Leve une
    exception si le modele sous-jacent echoue."""
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
            # '===', ...) ne partent PAS au modele : hallucination garantie et
            # il n'y a rien a traduire.
            lead = part[:len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            core = translate_fn(part.strip(), "", target)
            out.append(lead + _clean_html_entities(core) + trail)
        else:
            out.append(part)
    return "".join(out)


def is_available() -> bool:
    """Traduction possible : au moins un fournisseur IA configure (Options >
    Traduction > Fournisseurs IA). Un maillon LOCAL (Unsloth/Ollama) suffit."""
    from .ai import router as ai_router
    return ai_router.configured()


def get_import_error() -> str:
    """Explication affichable quand is_available() est False (les anciens
    moteurs n'avaient plus de dependance a importer)."""
    if is_available():
        return ""
    from .i18n import t
    return t("trans.configure_hint")


# Duree maximale d'attente d'une reponse -- les appels IA sont dejas bornes
# par core/ai/client ; le parametre reste expose pour les appelants.
DEFAULT_TRANSLATION_TIMEOUT_S = 15.0


def _translate_llm_whole_cell(gtext: str, source: str, target: str,
                              translate_whole, translate_fn) -> str:
    """Mode CELLULE ENTIERE (18/09/2026) : UNE requete par cellule -- le
    texte entier, protege en jetons XXTAG (balises, nombres, placeholders),
    part d'un bloc. Coherence linguistique (le modele voit la phrase
    complete), requetes et consigne systeme uniques.

    Squelette verifie : la sequence de jetons de la reponse doit etre
    EXACTEMENT celle de l'entree (meme count, meme ordre) ; sinon REPLI
    automatique sur le pipeline fragments pour cette cellule -- jamais de
    fichier corrompu. Les erreurs API (quota, reseau, cle) remontent : l'UI
    les affiche avec le delai."""
    protected, segments = protect_segments(gtext)
    expected = list(range(len(segments)))
    translated = translate_whole(protected, target)
    if _token_sequence(translated) != expected:
        return _translate_fragments(gtext, target, translate_fn)
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
    """Mode LOTS (v1.8.0) : tous les textes d'un lot partent en UNE requete
    (translate_batch). Le squelette de jetons de CHAQUE cellule est verifie
    comme en mode cellule entiere : une cellule manquante ou deviante dans la
    reponse repasse AUTOMATIQUEMENT en mode cellule entiere (qui lui-meme
    retombe sur les fragments) -- jamais de fichier corrompu, et une
    deviation du modele ne coute qu'un appel supplementaire sur la cellule
    fautive. Les erreurs API remontent (le worker les affiche pour chaque
    cellule du lot)."""
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


def _raise_online_disabled():
    """Message de la garde confidentialite : la traduction EN LIGNE est une
    permission. Un maillon LOCAL (Unsloth/Ollama) n'est pas concerne."""
    raise RuntimeError(
        "Traduction en ligne desactivee (Options > Traduction en ligne). "
        "Cette fonctionnalite envoie le texte a traduire au fournisseur IA "
        "configure -- voir PRIVACY.md. Reactive-la dans le menu Options si "
        "tu veux t'en servir, ou configure un fournisseur LOCAL "
        "(Unsloth/Ollama) qui ne fait sortir aucune donnee.")


def _translate_via_ai(gtext: str, gloss_replacements: list, target: str,
                      source: str) -> str:
    """Chemin UNIQUE (31/10) : le routeur IA (core/ai/router) choisit le
    maillon configure (fournisseur + modele), gere lui-meme les repos par
    maillon (429, quota, plafond budgetaire) et la bascule vers les maillons
    suivants. Une AuthError (cle refusee) remonte : erreur de configuration
    que l'utilisateur doit voir."""
    from . import glossary
    from . import settings as _settings
    from .ai import router as ai_router
    # Garde confidentialite AVANT le test de configuration : un fournisseur
    # distant + permission coupee doit dire « traduction en ligne desactee »
    # (actionnable), pas « aucun fournisseur » (vecu en tests 31/10 —
    # router.configured() filtre deja les distants quand la permission manque).
    if (not _settings.get_online_translation_enabled()
            and not ai_router.has_local_links()):
        _raise_online_disabled()
    if not ai_router.configured():
        raise EngineUnavailableError(
            "Aucun fournisseur IA configure (Options > Traduction > "
            "Fournisseurs IA...).")
    translated = _translate_llm_whole_cell(
        gtext, source, target,
        translate_whole=ai_router.translate_whole,
        translate_fn=ai_router.translate)
    _debug_note("ai", gtext, translated)
    return glossary.restore_glossary(translated, gloss_replacements)


# JOURNAL DE DIAGNOSTIC (v1.10.0, apres les pertes de \n difficiles a
# attribuer) : chaque traduction moteur est appendue en JSONL
# (~/.empyrion_editor/translation_debug.jsonl) -- entree et sortie
# (tronquees). Permet de dire EXACTEMENT ce qui a ete envoye au modele.
# Jamais bloquant : toute erreur d'ecriture est ignoree.
_DEBUG_LOG_PATH = Path.home() / ".empyrion_editor" / "translation_debug.jsonl"
_DEBUG_MAX_LEN = 800
_DEBUG_LOCK = threading.Lock()


def _debug_note(engine: str, gtext: str, translated: str,
                fallback: bool = False) -> None:
    """Append une ligne JSONL de diagnostic (entree, sortie).
    Rotation simple a 2 Mo (vieilles lignes jetees : c'est un anneau de
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


def reset_link_states() -> None:
    """Compat : les repos par moteur disparaissent avec la chaine de secours
    (le routeur IA gere ses propres cooldowns PAR FOURNISSEUR). No-op."""
    return None


def last_fallback_note() -> str:
    """Note d'interface affichee pendant les lots : le fournisseur IA qui a
    servi la derniere requete ('' si aucun)."""
    from .ai import router as ai_router
    label = ai_router.last_link_label()
    return f"IA : {label}" if label else ""


def translate_text(text: str, target: str = "fr", source: str = "auto",
                   timeout_seconds: float = DEFAULT_TRANSLATION_TIMEOUT_S,
                   store_in_memory: bool = True) -> str:
    """Traduit `text` vers la langue `target` (code ISO, ex: 'fr', 'en'), en
    preservant le BBCode et les placeholders. Leve une exception explicite si
    aucun fournisseur IA n'est configure ou si la requete echoue (quota,
    reseau, cle refusee) -- a capturer et afficher clairement cote GUI.

    MEMOIRE DE TRADUCTION (core/translation_memory.py) consultee en PREMIER :
    meme texte -> meme traduction, partout, sans rappeler l'API ; puis memoire
    VANILLE (core/vanilla_memory.py) : les textes identiques a la localisation
    officielle du jeu ressortent avec la traduction Eleon. L'ALIMENTATION de
    la memoire, elle, ne se fait plus automatiquement ici : les revues passent
    store_in_memory=False et l'interface enregistre la traduction au moment ou
    l'utilisateur LA VALIDE (cases cochees de la revue) -- demande du 12/09/2026.

    GLOSSAIRE (core/glossary.py) : les termes actifs sont proteges par jetons
    avant l'envoi au modele et reinjectes dans la reponse -- la terminologie
    imposee n'est jamais traduite a tort."""
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

    translated = _translate_via_ai(gtext, gloss_replacements, target, source)
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
    resolues par texte (sans rappeler le modele), et le reste part au modele
    EN UNE SEULE requete quand le mode lots est active (Options > Traduction)
    -- les tiers gratuits sont plafonnes en debit, grouper les cellules
    divise d'autant le nombre de requetes. Squelette de jetons verifie par
    cellule, repli cellule entiere puis fragments (voir
    _translate_llm_cells_batch).

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
    # Mode LOTS IA : une requete pour plusieurs cellules. Le routeur
    # enchaine ses propres fournisseurs (free puis payant).
    if _settings.get_ai_batch_enabled() and len(still) > 1:
        from .ai import budget as _ai_budget
        from .ai import router as _ai_router
        if _ai_router.has_available_links():
            from . import glossary
            gtexts, gloss_replacements = [], []
            for _i, text in still:
                gtext, replacements = glossary.apply_glossary(text, target)
                gtexts.append(gtext)
                gloss_replacements.append(replacements)
            try:
                translated_list = _translate_llm_cells_batch(
                    gtexts, source, target,
                    translate_batch=_ai_router.translate_batch,
                    translate_whole=_ai_router.translate_whole,
                    translate_fn=_ai_router.translate)
            except AuthError:
                raise
            except (QuotaExhaustedError, EngineUnavailableError, TimeoutError):
                # Pas de repos moteur ici : le routeur a deja mis au repos
                # les maillons fautifs ; les cellules suivantes doivent
                # pouvoir retenter l'IA (un autre maillon free, un 429
                # expire).
                pass
            else:
                _ai_budget.flush()
                for (i, _text), translated, replacements, gtext in zip(
                        still, translated_list, gloss_replacements, gtexts):
                    _debug_note("ai", gtext, translated)
                    results[i] = (glossary.restore_glossary(
                        translated, replacements), "engine")
                return results

    # Chemin classique, cellule par cellule (mode lots desactive, ou lot
    # restant a une seule cellule, ou echec du lot).
    from . import glossary
    for i, text in still:
        gtext, replacements = glossary.apply_glossary(text, target)
        translated = _translate_via_ai(gtext, replacements, target, source)
        results[i] = (translated, "engine")
    from .ai import budget as _ai_budget
    _ai_budget.flush()
    return results
