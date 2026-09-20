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
Moteur de traduction GROQ (api.groq.com) -- LLM en ligne compatible OpenAI
(tier gratuit permanent, plafonne en debit : ~30 req/min et un plafond
journalier de tokens selon le modele).

Utilise le modele settings.get_groq_model() (defaut : qwen/qwen3.8-27b,
SANS raisonnement -- le meilleur rapport qualite/vitesse/tokens teste le
17/09/2026 ; les gpt-oss consomment des tokens de raisonnement sauf
reasoning_effort='low').

Recoit les FRAGMENTS de texte libre du pipeline (core/translation.py : les
balises, nombres et placeholders ne partent jamais au moteur). La consigne
systeme fixe le ton (localisateur de jeu) et la langue cible.

ATTENTION EN-TETE : sans User-Agent, certaines passerelles (Cloudflare)
bloquent la requete avant l'API (vecu reel sur Felo, 17/09/2026).
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from . import settings
from .engine_errors import (AuthError, EngineUnavailableError,
                            QuotaExhaustedError)
from .i18n import t

BASE = "https://api.groq.com/openai/v1"
# models listes dans le combo de l'assistant (editable : le catalogue evolue)
KNOWN_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]

# TIER GRATUIT (modeles texte, doc console.groq.com/docs/rate-limits) :
# 30 requetes/min, 1 000 requetes/jour, 8 000 tokens/min, 200 000
# tokens/jour. Cooldown client : espace les appels d'au moins
# MIN_INTERVAL_S pour rester sous les 30 RPM avec marge (0 = desactive,
# utilise par les tests).
MIN_INTERVAL_S = 2.2
# Attente MAXIMALE dans le throttle (v1.10.0, blocage vecu 19/09/2026) :
# au-dela, ECHOUE IMMEDIATEMENT (QuotaExhaustedError) au lieu de dormir --
# un 429 journalier (200K TPD) annonce un reset en HEURES et l'ancienne
# boucle figeait le worker pendant tout ce temps (progression bloquee a
# 2 %, "QThread destroyed" a l'annulation). La chaine de secours prend le
# relais pendant ce temps.
_MAX_THROTTLE_WAIT_S = 30.0

_THROTTLE_LOCK = threading.Lock()
_last_call: float = 0.0
_cooldown_until: float = 0.0
_last_limits: Optional[dict] = None  # en-tetes x-ratelimit de la derniere reponse

_RESET_RE = re.compile(r"(?:(?P<m>[\d.]+)m)?(?:(?P<s>[\d.]+)s)?")


def cooldown_remaining() -> float:
    """Secondes restantes avant la fin du cooldown pose par un 429 (0 si
    aucun) -- la chaine de secours saute le maillon Groq tant que ce
    delai court, au lieu de le laisser dormir dans le throttle."""
    with _THROTTLE_LOCK:
        return max(0.0, _cooldown_until - time.monotonic())


def _parse_duration(s: str) -> float:
    """'2m59.56s' -> 179.56 ; '7.66s' -> 7.66 ; '6m0s' -> 360."""
    m = _RESET_RE.fullmatch((s or "").strip())
    if not m:
        return 0.0
    return float(m.group("m") or 0) * 60 + float(m.group("s") or 0)


def _fmt_duration(seconds: float) -> str:
    seconds = max(1, round(seconds))
    minutes, sec = divmod(seconds, 60)
    return f"{minutes}m{sec:02d}s" if minutes else f"{sec}s"


def _throttle() -> None:
    """Espace les appels d'au moins MIN_INTERVAL_S et respecte le cooldown
    pose par un 429 (retry-after) -- le tier gratuit est plafonne en
    requetes/minute ET tokens/minute. Sommeil sous verrou : les appels Groq
    sont sequentiels (worker batch), jamais concurrents en pratique.

    UNBOUNDED WAIT INTERDITE (v1.10.0) : si le cooldown depasse
    _MAX_THROTTLE_WAIT_S (reset journalier = heures), on leve AU LIEU de
    dormir -- le worker reste vivant, l'annulation est honoree et la
    chaine de secours sert les cellules."""
    global _last_call
    with _THROTTLE_LOCK:
        while True:
            now = time.monotonic()
            wait = max(_cooldown_until - now,
                       _last_call + MIN_INTERVAL_S - now, 0.0)
            if wait <= 0:
                break
            if wait > _MAX_THROTTLE_WAIT_S:
                raise QuotaExhaustedError(
                    t("groq.rate_limited", delay=_fmt_duration(wait)))
            time.sleep(min(wait, 1.0))
            if wait > 1.0:  # reevaluer le cooldown (il ne diminue pas, mais
                continue     # restons simple et re-boucler)
        _last_call = time.monotonic()


def _capture_limits(resp) -> None:
    """Memorise les en-tetes x-ratelimit de la reponse pour l'affichage
    (compteur de la barre de progression, demande 18/09/2026)."""
    global _last_limits
    h = resp.headers
    _last_limits = {
        "limit_requests": h.get("x-ratelimit-limit-requests", ""),
        "limit_tokens": h.get("x-ratelimit-limit-tokens", ""),
        "requests_remaining": h.get("x-ratelimit-remaining-requests", ""),
        "tokens_remaining": h.get("x-ratelimit-remaining-tokens", ""),
        "reset": h.get("x-ratelimit-reset-tokens",
                       h.get("x-ratelimit-reset-requests", "")),
    }


def limits_text() -> str:
    """Suffixe d'interface (barre de progression) : requetes/tokens
    restants d'apres la derniere reponse Groq. Chaine vide si aucune
    information (autre moteur, ou pas encore d'appel)."""
    if not _last_limits:
        return ""
    return "  -- " + t("groq.limits_text",
                       requests=_last_limits.get("requests_remaining", "?"),
                       tokens=_last_limits.get("tokens_remaining", "?"),
                       reset=_last_limits.get("reset", "?"))

# noms anglais pour la consigne de traduction (codes courants du jeu)
_LANG_NAMES = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "pl": "Polish",
    "ja": "Japanese", "zh": "Chinese", "ko": "Korean", "tr": "Turkish",
    "nl": "Dutch", "uk": "Ukrainian", "cs": "Czech",
}

_SYSTEM_TEMPLATE = (
    "You are a professional video game localizer. Translate the user's text "
    "into {lang}. Reply with ONLY the translation, no quotes, no notes. "
    "Preserve the meaning and a concise military/space-opera tone.")

_WHOLE_SYSTEM_TEMPLATE = (
    "You are a professional video game localizer. Translate the user's text "
    "into {lang}. The text contains placeholders like XXTAG0XX, XXTAG1XX "
    "(they stand for game formatting tags, numbers and variables). Translate "
    "ONLY the words between them: never translate, move, rename, duplicate "
    "or drop a XXTAG token -- keep every token exactly as written, in the "
    "same order. Reply with ONLY the translation, no quotes, no notes. "
    "Preserve line breaks and a concise military/space-opera tone.")

_BATCH_SYSTEM_TEMPLATE = (
    "You are a professional video game localizer. The user's message contains "
    "several numbered game texts to translate into {lang}, each wrapped as "
    "<CELL0>...</CELL0>, <CELL1>...</CELL1> and so on. The texts contain "
    "placeholders like XXTAG0XX, XXTAG1XX (they stand for game formatting "
    "tags, numbers and variables). Translate ONLY the words between them: "
    "never translate, move, rename, duplicate or drop a XXTAG token. Reply "
    "with EVERY input cell translated, wrapped exactly the same way "
    "(<CELLn>...</CELLn>, same count, same order, same numbers), no extra "
    "cell, no quotes, no notes. Preserve line breaks and a concise "
    "military/space-opera tone.")

# Reponse du mode lots : enveloppes <CELLn> ouvertes (la balise fermante et
# le bavardage eventuel apres elle sont supprimes au decodage).
_BATCH_CELL_OPEN_RE = re.compile(r"<\s*CELL\s*(\d+)\s*>", re.IGNORECASE)
_BATCH_CELL_CLOSE_RE = re.compile(r"<\s*/\s*CELL\s*\d+\s*>.*\Z",
                                  re.IGNORECASE | re.DOTALL)


def _style_directive() -> str:
    """Conseigne de style/ton de l'auteur (settings.groq_style), ajoutee a
    la consigne systeme de chaque requete. Vide = consigne par defaut."""
    style = (settings.get_groq_style() or "").strip()
    if not style:
        return ""
    return " Style directive from the game author (follow it): " + style


def _lang_name(target_code: str) -> str:
    return _LANG_NAMES.get((target_code or "").lower(),
                           f"language code '{target_code}'")


def is_configured() -> bool:
    """Vrai si une cle API est enregistree (test sans reseau)."""
    return bool(settings.get_groq_api_key())


def _post(payload: dict, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(
        BASE + "/chat/completions", method="POST",
        headers={"Authorization": f"Bearer {settings.get_groq_api_key()}",
                 "Content-Type": "application/json",
                 # SANS User-Agent : blocage Cloudflare 1010 avant l'API
                 "User-Agent": "EmpyrionScenarioEditor"},
        data=json.dumps(payload).encode("utf-8"))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        _capture_limits(r)
        return json.loads(r.read())


def list_models() -> list:
    """Modeles disponibles pour cette cle ( appel /models reel) ; liste de
    secours = KNOWN_MODELS si l'appel echoue. Les modeles non-texte
    (audio, moderation, agentique) sont filtres."""
    try:
        req = urllib.request.Request(
            BASE + "/models",
            headers={"Authorization": f"Bearer {settings.get_groq_api_key()}",
                     "User-Agent": "EmpyrionScenarioEditor"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        skip = ("whisper", "guard", "compound", "orpheus", "allam", "tts")
        ids = sorted(m["id"] for m in data.get("data", [])
                     if not any(s in m["id"] for s in skip))
        return ids or list(KNOWN_MODELS)
    except Exception:
        return list(KNOWN_MODELS)


def _chat(payload: dict) -> str:
    """POST /chat/completions avec throttle/cooldown et erreurs explicites.
    Retourne le contenu du message reponse."""
    if not is_configured():
        raise RuntimeError("Aucune cle API Groq configuree (Options > "
                           "Traduction > Traduction IA Groq).")
    _throttle()
    try:
        data = _post(payload)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            body = json.loads(e.read().decode(errors="replace"))
            detail = body.get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code in (401, 403):
            # cle refusee : JAMAIS de bascule silencieuse (auth)
            raise AuthError(f"Cle API Groq refusee ({e.code}). {detail}")
        if e.code == 402:
            raise QuotaExhaustedError(f"Quota Groq epuise. {detail}")
        if e.code == 429:
            # Depassement du tier gratuit : calculer le delai (retry-after
            # en secondes, sinon en-tete reset au format '2m59.56s'), poser
            # un cooldown LOCAL pour que les fragments suivants attendent
            # automatiquement, et l'annoncer dans l'erreur affichee par la
            # revue (demande 18/09/2026 : le temps a attendre pour relancer).
            h = e.headers or {}
            delay = 0.0
            retry_after = h.get("retry-after")
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 0.0
            if delay <= 0:
                delay = max(_parse_duration(h.get("x-ratelimit-reset-tokens",
                                                  "")),
                            _parse_duration(h.get("x-ratelimit-reset-requests",
                                                  "")))
            if delay > 0:
                global _cooldown_until
                with _THROTTLE_LOCK:
                    _cooldown_until = time.monotonic() + delay + 1.0
                raise QuotaExhaustedError(t("groq.rate_limited",
                                            delay=_fmt_duration(delay)))
            raise QuotaExhaustedError("Limite de debit Groq atteinte (tier "
                                      "gratuit) -- reessaie plus tard.")
        raise EngineUnavailableError(f"Erreur Groq {e.code}. {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise EngineUnavailableError(f"Reseau indisponible pour Groq : {e}")
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Reponse Groq inattendue : {e}")


def translate(text: str, source_code: str, target_code: str) -> str:
    """Traduit un FRAGMENT de texte libre (le pipeline en amont a deja
    protege balises/nombres/placeholders). Leve RuntimeError avec un
    message clair si la cle est invalide, le quota epuise ou le reseau
    indisponible."""
    payload = {
        "model": settings.get_groq_model(),
        "temperature": 0.2,  # sobre : consistence sans figer le style
        "messages": [
            {"role": "system",
             "content": _SYSTEM_TEMPLATE.format(lang=_lang_name(target_code))
                        + _style_directive()},
            {"role": "user", "content": text},
        ],
    }
    return _chat(payload)


def translate_whole(protected_text: str, target_code: str) -> str:
    """Mode CELLULE ENTIERE (demande 18/09/2026) : traduit un texte protege
    par jetons XXTAGnXX en UNE requete au lieu d'un appel par fragment --
    coherence linguistique (le modele voit la phrase complete), requetes et
    consigne systeme uniques. La coherence STRUCTURELLE (sequence de jetons)
    est verifiee par core/translation.py, qui retombe sur le pipeline
    fragments pour cette cellule si le LLM a ecarte ou bave un jeton."""
    payload = {
        "model": settings.get_groq_model(),
        "temperature": 0.2,
        "messages": [
            {"role": "system",
             "content": _WHOLE_SYSTEM_TEMPLATE.format(
                 lang=_lang_name(target_code)) + _style_directive()},
            {"role": "user", "content": protected_text},
        ],
    }
    return _chat(payload)


def translate_batch(protected_texts: list, target_code: str) -> list:
    """Mode LOTS (v1.8.0, tier gratuit plafonne en debit ~30 req/min) :
    traduit PLUSIEURS textes proteges (jetons XXTAG deja poses par le
    pipeline) en UNE requete. Chaque texte part enveloppe dans
    <CELLn>...</CELLn> ; la reponse doit restituer les memes enveloppes.

    Retourne la liste parallele : traduction, ou None pour une cellule
    manquante/dupliquee/deviante (core/translation.py verifie le squelette
    de jetons de chaque cellule et retombe alors sur le mode cellule
    entiere -- puis fragments -- pour cette cellule seule). Les erreurs
    API (cle, quota, reseau) remontent : l'interface les affiche avec le
    delai d'attente."""
    if not protected_texts:
        return []
    user_content = "\n".join(
        f"<CELL{n}>{text}</CELL{n}>" for n, text in enumerate(protected_texts))
    payload = {
        "model": settings.get_groq_model(),
        "temperature": 0.2,
        "messages": [
            {"role": "system",
             "content": _BATCH_SYSTEM_TEMPLATE.format(
                 lang=_lang_name(target_code)) + _style_directive()},
            {"role": "user", "content": user_content},
        ],
    }
    response = _chat(payload)
    out: list = [None] * len(protected_texts)
    matches = list(_BATCH_CELL_OPEN_RE.finditer(response))
    ids = [int(m.group(1)) for m in matches]
    if len(set(ids)) != len(ids) or any(i < 0 or i >= len(out) for i in ids):
        # doublons ou numerotation hors champ : reponse structurellement
        # bavee, toutes les cellules None -> repli cellule entiere
        return out
    for k, m in enumerate(matches):
        start = m.end()
        end = matches[k + 1].start() if k + 1 < len(matches) else len(response)
        body = response[start:end]
        close = _BATCH_CELL_CLOSE_RE.search(body)
        # la balise fermante ET le bavardage eventuel apres elle sont
        # jetes ; sans balise fermante (derniere cellule tronquee), on
        # garde le corps tel quel -- le squelette de jetons tranchera.
        body = body[:close.start()] if close is not None else body.rstrip()
        out[int(m.group(1))] = body.strip("\r\n")
    return out


def quick_check() -> str:
    """Test reel utilise par l'assistant : traduit une phrase courte et
    retourne le texte + le modele pour affichage. RuntimeError si echoue."""
    model = settings.get_groq_model()
    out = translate("The generators are overloaded.", "en", "fr")
    return f"[{model}] {out}"
