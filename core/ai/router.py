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
Routeur IA : construit la chaine des maillons configures (registre
settings.ai_providers / ai_links), bascule sur le suivant en cas de panne,
de quota ou de plafond budget, et expose une API unique pour la traduction
ET pour le futur assistant.

Politique (demandee le 20/10/2026) :
1. maillons GRATUITS dans l'ordre du registre, en boucle ;
2. maillons PAYANTS si 'Autoriser le payant' est coche ET si le cout estime
   tient dans le plafond ;
3. un payant qui echoue (402/429/plafond) redonne une passe aux gratuits
   encore disponibles, puis la chaine de traduction prend le relais
   (Groq -> DeepL -> Google -> NLLB -> Argos).

Repos : un modele absent est ecarte 30 min, une panne 10 min, un 429 suit
le delai annonce. Un 429 OpenRouter est GLOBAL AU COMPTE (20 req/min,
50-1000 req/jour tous modeles free confondus) : tout le fournisseur est mis
au repos, sinon la boucle martele chaque modele pour rien.
"""
import re
import threading
import time
from dataclasses import dataclass, field

from .. import settings
from ..engine_errors import (AuthError, EngineUnavailableError,
                             QuotaExhaustedError)
from . import budget, client, providers
from .client import ModelUnavailableError

MAX_THROTTLE_WAIT_S = 30.0

# Capacite declaree par une action d'assistant (Q35/D3) : un maillon muet est
# suppose "normal" ; le filtre ecarte seulement ce qui est explicitement
# insuffisant, pour ne jamais rendre une action inutilisable par omission.
CLASS_RANK = {"light": 1, "normal": 2, "strong": 3}


@dataclass(frozen=True)
class Candidate:
    provider_id: str
    provider_label: str
    preset_id: str
    base_url: str
    api_key: str
    model: str
    tier: str
    price_in: float
    price_out: float
    caps: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.provider_id}:{self.model}"

    @property
    def label(self) -> str:
        return f"{self.provider_label} / {self.model}"


_LOCK = threading.Lock()
_LINK_DOWN: dict = {}
_PROVIDER_DOWN: dict = {}
_LAST_CALL: dict = {}
_LAST_LINK: Candidate = None


def _mark(link_key: str, seconds: float) -> None:
    with _LOCK:
        _LINK_DOWN[link_key] = time.monotonic() + max(1.0, seconds)


def _mark_provider(provider_id: str, seconds: float, tier: str) -> None:
    with _LOCK:
        _PROVIDER_DOWN[(provider_id, tier)] = time.monotonic() + max(1.0,
                                                                      seconds)


def _down(candidate: Candidate) -> bool:
    now = time.monotonic()
    with _LOCK:
        return (now < _LINK_DOWN.get(candidate.key, 0.0)
                or now < _PROVIDER_DOWN.get(
                    (candidate.provider_id, candidate.tier), 0.0))


def cooldown_remaining(candidate: Candidate) -> float:
    with _LOCK:
        return max(0.0, _LINK_DOWN.get(candidate.key, 0.0) - time.monotonic())


def reset_link_states() -> None:
    global _LAST_LINK
    with _LOCK:
        _LINK_DOWN.clear()
        _PROVIDER_DOWN.clear()
        _LAST_CALL.clear()
        _LAST_LINK = None


def last_link_label() -> str:
    return _LAST_LINK.label if _LAST_LINK else ""


def _candidates() -> list:
    """Maillons configures, enrichis avec leur compte fournisseur."""
    accounts = {p.get("id"): p for p in settings.get_ai_providers()
                if p.get("id")}
    out = []
    for link in settings.get_ai_links():
        if not link.get("enabled", True):
            continue
        provider = accounts.get(link.get("provider"))
        model = (link.get("model") or "").strip()
        if not provider or not model:
            continue
        # Le type est recalcule depuis le fournisseur (presets verrouilles) :
        # un tier obsolete dans les settings ne peut pas contourner le budget.
        tier = providers.kind_tier(provider, model)
        price_in, price_out = providers.model_prices(provider, model)
        try:
            price_in = float(link.get("price_in", price_in) or price_in or 0.0)
            price_out = float(link.get("price_out", price_out)
                              or price_out or 0.0)
        except (TypeError, ValueError):
            price_in = price_out = 0.0
        caps = link.get("caps")
        out.append(Candidate(
            provider_id=provider["id"],
            provider_label=provider.get("label") or provider["id"],
            preset_id=provider.get("preset") or provider["id"],
            base_url=provider.get("base_url", ""),
            api_key=provider.get("key", ""),
            model=model,
            tier=tier,
            price_in=price_in,
            price_out=price_out,
            caps=caps if isinstance(caps, dict) else {},
        ))
    return out


def _matches(candidate: Candidate, min_class: str,
             require_tools: bool) -> bool:
    """Un maillon ne sert une action que s'il declare au moins le niveau
    demande et, si l'action lit le document, qu'il ne declare pas ne pas
    savoir appeler des outils (muet = on essaie, le repli couvre l'echec)."""
    caps = candidate.caps or {}
    rank = CLASS_RANK.get(str(caps.get("class") or "normal"), 2)
    if min_class and rank < CLASS_RANK.get(min_class, 2):
        return False
    return not (require_tools and caps.get("tools") is False)


def _throttle(candidate: Candidate) -> None:
    """Espace les appels d'un fournisseur gratuit (debit plafonne). Le
    sommeil reste borne : au-dela, on preferait basculer -- ici un gros lot
    doit rester fluide, le delai est court (2-3 s)."""
    interval = providers.min_interval(candidate.preset_id, candidate.tier)
    if interval <= 0:
        return
    key = (candidate.provider_id, candidate.tier)
    with _LOCK:
        last = _LAST_CALL.get(key, 0.0)
        wait = last + interval - time.monotonic()
        if wait > 0:
            time.sleep(min(wait, MAX_THROTTLE_WAIT_S))
        _LAST_CALL[key] = time.monotonic()


def _usable(candidate: Candidate) -> bool:
    if providers.is_local(candidate.base_url):
        return True
    # Un endpoint distant sans cle est une configuration incomplete : le
    # rendre disponible ferait echouer chaque cellule en 401.
    if not candidate.api_key:
        return False
    return settings.get_online_translation_enabled()


def configured() -> bool:
    return any(_usable(c) for c in _candidates())


def has_local_links() -> bool:
    return any(providers.is_local(c.base_url) for c in _candidates())


def has_available_links() -> bool:
    return any(_usable(c) and not _down(c) for c in _candidates())


def _estimate_cost(candidate: Candidate, messages: list,
                   max_tokens: int) -> float:
    chars = sum(len(str(m.get("content") or "")) for m in messages)
    prompt_tokens = max(1, chars // 4)
    completion_tokens = max_tokens or 800
    return (prompt_tokens / 1_000_000.0 * candidate.price_in
            + completion_tokens / 1_000_000.0 * candidate.price_out)


def chat_with_link(messages: list, *, temperature: float = 0.2,
                   tools: list = None, tool_choice: str = None,
                   max_tokens: int = None, purpose: str = "assistant",
                   min_class: str = None, require_tools: bool = False,
                   timeout: float = client.DEFAULT_TIMEOUT_S) -> tuple:
    """Reponse complete + maillon qui l'a servie (assistant : tools).

    `min_class` / `require_tools` filtrent la chaine selon la capacite
    exigee par l'action (voir core/ai/assistant/actions.py) : un maillon
    ecarte ici n'est jamais essaye, donc aucun repli silencieux vers un
    modele qui ne saurait pas faire le travail."""
    global _LAST_LINK
    free = [c for c in _candidates()
            if c.tier == "free" and _usable(c)
            and _matches(c, min_class, require_tools)]
    paid = []
    if settings.get_ai_paid_enabled():
        paid = [c for c in _candidates()
                if c.tier == "paid" and _usable(c)
                and _matches(c, min_class, require_tools)]
    queue = free + paid
    if not queue:
        if min_class or require_tools:
            needed = []
            if min_class:
                needed.append(f"niveau {min_class}")
            if require_tools:
                needed.append("outils")
            raise EngineUnavailableError(
                "Aucun maillon IA configure ne declare la capacite requise ("
                + ", ".join(needed) + ") : ajoute ou modifie un maillon dans "
                "Options > Traduction > Fournisseurs IA.")
        raise EngineUnavailableError(
            "Aucun fournisseur IA disponible : ajoute une cle dans Options > "
            "Traduction > Fournisseurs IA.")
    errors = []
    tried = set()
    retried_free = False
    index = 0
    while index < len(queue):
        candidate = queue[index]
        index += 1
        if candidate.key in tried or _down(candidate):
            continue
        if candidate.tier == "paid":
            if candidate.price_in <= 0 and candidate.price_out <= 0:
                errors.append((candidate.label, "tarif non renseigne"))
                continue
            estimate = _estimate_cost(candidate, messages, max_tokens)
            if not budget.can_spend(candidate.provider_id, estimate):
                errors.append((candidate.label, "plafond budget atteint"))
                continue
        tried.add(candidate.key)
        try:
            _throttle(candidate)
            result = client.chat(
                candidate.base_url, candidate.api_key, candidate.model,
                messages, temperature=temperature, tools=tools,
                tool_choice=tool_choice, max_tokens=max_tokens,
                timeout=timeout)
        except AuthError:
            raise
        except ModelUnavailableError as e:
            _mark(candidate.key, 1800)
            errors.append((candidate.label, str(e)))
            continue
        except QuotaExhaustedError as e:
            delay = float(getattr(e, "retry_after", 0.0) or 60.0)
            _mark(candidate.key, delay)
            # OpenRouter/DeepSeek : un 429 est global au COMPTE pour le tier
            # concerne (free : 20 req/min et 50-1000 req/jour tous modeles
            # confondus) -> tout ce tier du fournisseur au repos, sinon la
            # boucle martele chaque modele pour rien. Le tier payant garde
            # ses credits et reste essayable (repli free -> payant).
            _mark_provider(candidate.provider_id, delay, candidate.tier)
            errors.append((candidate.label, str(e)))
            if candidate.tier == "paid" and not retried_free:
                retried_free = True
                queue.extend(f for f in free if f.key not in tried)
            continue
        except EngineUnavailableError as e:
            _mark(candidate.key, 600)
            errors.append((candidate.label, str(e)))
            continue
        usage = result.get("usage") or {}
        if not (result.get("content") or "").strip() \
                and not result.get("tool_calls"):
            # Reponse VIDE : certains modeles a raisonnement epuisent
            # max_tokens en reflexion et renvoient content="" (vecu 21/10,
            # minimax-m3.1-flash). Ce n'est pas une traduction : maillon
            # ecarte, le suivant prend le relais.
            _mark(candidate.key, 600)
            errors.append((candidate.label, "reponse vide"))
            continue
        if candidate.tier == "paid":
            budget.record(candidate.provider_id,
                          client.usage_cost(usage, candidate.price_in,
                                            candidate.price_out))
        _LAST_LINK = candidate
        return result, candidate
    detail = " | ".join(f"{label} : {msg}" for label, msg in errors) \
        or "aucun maillon disponible"
    raise EngineUnavailableError(
        "Tous les fournisseurs IA ont echoue -- " + detail)


def complete(messages: list, **kwargs) -> str:
    """Texte de la reponse (assistant/traduction sans tools)."""
    result, _candidate = chat_with_link(messages, **kwargs)
    return result["content"]


def stream_with_link(messages: list, *, temperature: float = 0.2,
                     tools: list = None, max_tokens: int = None,
                     purpose: str = "assistant", min_class: str = None,
                     require_tools: bool = False,
                     timeout: float = client.DEFAULT_TIMEOUT_S):
    """Flux de l'assistant : evenements ("start", Candidate) puis
    ("delta", texte).

    Seuls les maillons GRATUITS sont streames : le SSE ne renvoie pas
    d'usage, donc un maillon payant ne pourrait pas etre decompte du budget
    (le plafond deviendrait un mensonge). L'appelant retombe sur
    chat_with_link quand aucun maillon gratuit n'est disponible.

    Une panne AVANT le premier fragment bascule sur le maillon suivant :
    aucun texte n'a ete emis, rien n'est duplique. Apres, l'erreur remonte --
    melanger deux reponses au fil de l'eau serait pire qu'une erreur."""
    global _LAST_LINK
    queue = [c for c in _candidates()
             if c.tier == "free" and _usable(c)
             and _matches(c, min_class, require_tools)]
    if not queue:
        raise EngineUnavailableError(
            "Aucun maillon gratuit disponible pour le flux : reponse "
            "complete necessaire.")
    errors = []
    tried = set()
    for candidate in queue:
        if candidate.key in tried or _down(candidate):
            continue
        tried.add(candidate.key)
        stream = None
        try:
            _throttle(candidate)
            stream = client.stream_chat(
                candidate.base_url, candidate.api_key, candidate.model,
                messages, temperature=temperature, tools=tools,
                max_tokens=max_tokens, timeout=timeout)
            first = next(stream)
        except StopIteration:
            _mark(candidate.key, 600)
            errors.append((candidate.label, "reponse vide"))
            continue
        except AuthError:
            raise
        except ModelUnavailableError as e:
            _mark(candidate.key, 1800)
            errors.append((candidate.label, str(e)))
            continue
        except QuotaExhaustedError as e:
            delay = float(getattr(e, "retry_after", 0.0) or 60.0)
            _mark_provider(candidate.provider_id, delay, candidate.tier)
            errors.append((candidate.label, str(e)))
            continue
        except EngineUnavailableError as e:
            _mark(candidate.key, 600)
            errors.append((candidate.label, str(e)))
            continue
        _LAST_LINK = candidate
        try:
            yield ("start", candidate)
            yield ("delta", first)
            for delta in stream:
                yield ("delta", delta)
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                close()
        return
    detail = " | ".join(f"{label} : {msg}"
                        for label, msg in errors) or "aucun maillon disponible"
    raise EngineUnavailableError(
        "Aucun fournisseur IA n'a pu demarrer le flux -- " + detail)


# ---------------------------------------------------------------------------
# Traduction (memes consignes que le moteur Groq, enrichies du glossaire et
# du style de l'auteur). Le pipeline XXTAG/restauration reste dans
# core/translation.py : le routeur ne voit que du texte deja protege.
# ---------------------------------------------------------------------------
_LANG_NAMES = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "pt-br": "Brazilian Portuguese",
    "ru": "Russian", "pl": "Polish", "ja": "Japanese", "zh": "Chinese",
    "zh-cn": "Simplified Chinese", "zh-tw": "Traditional Chinese",
    "ko": "Korean", "tr": "Turkish", "nl": "Dutch", "uk": "Ukrainian",
    "cs": "Czech", "el": "Greek", "vi": "Vietnamese",
}

_SYSTEM = (
    "You are a professional video game localizer. Translate the user's text "
    "into {lang}. Reply with ONLY the translation, no quotes, no notes. "
    "Preserve the meaning and a concise military/space-opera tone.")

_WHOLE_SYSTEM = (
    "You are a professional video game localizer. Translate the user's text "
    "into {lang}. The text contains placeholders like XXTAG0XX, XXTAG1XX "
    "(they stand for game formatting tags, numbers and variables). Translate "
    "ONLY the words between them: never translate, move, rename, duplicate "
    "or drop a XXTAG token -- keep every token exactly as written, in the "
    "same order. Reply with ONLY the translation, no quotes, no notes. "
    "Preserve line breaks and a concise military/space-opera tone.")

_BATCH_SYSTEM = (
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

_CELL_OPEN_RE = re.compile(r"<\s*CELL\s*(\d+)\s*>", re.IGNORECASE)
_CELL_CLOSE_RE = re.compile(r"<\s*/\s*CELL\s*\d+\s*>.*\Z",
                            re.IGNORECASE | re.DOTALL)


def _lang_name(target_code: str) -> str:
    return _LANG_NAMES.get((target_code or "").lower(),
                           f"language code '{target_code}'")


def _style_directive() -> str:
    style = (settings.get_ai_style() or settings.get_groq_style() or "").strip()
    if not style:
        return ""
    return " Style directive from the game author (follow it): " + style


def _glossary_directive(target: str) -> str:
    """Termes verrouilles passes au modele en CONTEXTE (les jetons XXGLOS
    les protegent deja ; voir les paires aide a accorder le reste de la
    phrase)."""
    try:
        from .. import glossary
        # Glossaire trop gros = memoire de traduction auto-alimentee : il
        # n'est pas applique (core/glossary.MAX_APPLY_ENTRIES) et ses paires
        # ne doivent pas polluer la consigne non plus.
        if glossary.apply_skipped():
            return ""
        pairs = glossary.active_entries(target)[:40]
    except Exception:
        return ""
    if not pairs:
        return ""
    return (" Glossary (source => required translation): "
            + "; ".join(f"{src} => {dst}" for src, dst in pairs) + ".")


def _messages(system: str, target: str, text: str) -> list:
    return [
        {"role": "system",
         "content": system.format(lang=_lang_name(target))
                    + _style_directive() + _glossary_directive(target)},
        {"role": "user", "content": text},
    ]


def translate(text: str, source_code: str, target_code: str) -> str:
    """Fragment de texte libre (pipeline XXTAG en amont)."""
    return complete(_messages(_SYSTEM, target_code, text),
                    temperature=0.2, purpose="translation", max_tokens=1500)


def translate_whole(protected_text: str, target_code: str) -> str:
    """Cellule entiere protegee en jetons XXTAG."""
    return complete(_messages(_WHOLE_SYSTEM, target_code, protected_text),
                    temperature=0.2, purpose="translation", max_tokens=2000)


def translate_batch(protected_texts: list, target_code: str) -> list:
    """Mode lots : plusieurs cellules par requete, enveloppes <CELLn>."""
    if not protected_texts:
        return []
    user_content = "\n".join(
        f"<CELL{n}>{text}</CELL{n}>" for n, text in enumerate(protected_texts))
    response = complete(_messages(_BATCH_SYSTEM, target_code, user_content),
                        temperature=0.2, purpose="translation",
                        max_tokens=4000)
    out = [None] * len(protected_texts)
    matches = list(_CELL_OPEN_RE.finditer(response))
    ids = [int(m.group(1)) for m in matches]
    if len(set(ids)) != len(ids) or any(i < 0 or i >= len(out) for i in ids):
        return out
    for k, match in enumerate(matches):
        start = match.end()
        end = matches[k + 1].start() if k + 1 < len(matches) else len(response)
        body = response[start:end]
        close = _CELL_CLOSE_RE.search(body)
        out[int(match.group(1))] = (
            body[:close.start()] if close is not None else body.rstrip()
        ).strip("\r\n")
    return out


def quick_check() -> str:
    """Test du dialogue : traduit une phrase courte et dit quel maillon a
    servi. Leve une exception explicite si aucun maillon ne repond."""
    out = translate_whole("The generators are overloaded.", "fr")
    return f"[{last_link_label()}] {out}"
