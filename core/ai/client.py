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
Client HTTP des fournisseurs OpenAI-compatibles (OpenRouter, Groq, DeepSeek,
Mistral, Unsloth/Ollama locaux...). Aucune dependance ajoutee : urllib.

Le client ne connait ni la traduction ni la politique de repli : il envoie
des messages, eventuellement des outils (function calling) et du streaming,
et traduit les erreurs HTTP en erreurs TYPEES (core/engine_errors.py) que le
routeur sait basculer.
"""
import json
import urllib.error
import urllib.request

from ..engine_errors import (AuthError, EngineUnavailableError,
                             QuotaExhaustedError)

USER_AGENT = "EmpyrionScenarioEditor"
DEFAULT_TIMEOUT_S = 60.0


class ModelUnavailableError(EngineUnavailableError):
    """Modele absent/retire chez le fournisseur -- basculable, repos long."""


def _url(base_url: str, path: str) -> str:
    return (base_url or "").rstrip("/") + path


def _headers(api_key: str, extra: dict = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        # SANS User-Agent, certaines passerelles (Cloudflare) bloquent
        # avant l'API (vecu reel sur Felo, 17/09/2026).
        "User-Agent": USER_AGENT,
        "X-Title": "Empyrion Scenario Editor",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra:
        headers.update(extra)
    return headers


def _retry_after(headers) -> float:
    """Delai annonce par le service (secondes) ; 0 si absent/illisible."""
    if not headers:
        return 0.0
    for name in ("retry-after", "x-ratelimit-reset-requests",
                 "x-ratelimit-reset-tokens"):
        value = headers.get(name) if hasattr(headers, "get") else None
        if not value:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            # format Groq/OpenRouter '2m59.56s'
            value = str(value).strip()
            minutes = seconds = 0.0
            if "m" in value:
                head, _, tail = value.partition("m")
                try:
                    minutes = float(head)
                except ValueError:
                    minutes = 0.0
                value = tail
            if value.endswith("s"):
                value = value[:-1]
            try:
                seconds = float(value)
            except ValueError:
                seconds = 0.0
            return minutes * 60 + seconds
    return 0.0


def _error_detail(exc) -> tuple:
    """(message lisible, metadonnees) d'une reponse HTTP en erreur."""
    try:
        body = exc.read().decode(errors="replace")
    except Exception:
        return "", {}
    try:
        data = json.loads(body)
    except Exception:
        return body[:300], {}
    err = data.get("error", data)
    if isinstance(err, dict):
        return (str(err.get("message") or body[:300]),
                err.get("metadata") or {})
    return str(err)[:300], {}


def _raise_http(exc) -> None:
    code = exc.code
    message, _meta = _error_detail(exc)
    if code == 401:
        raise AuthError(f"Cle API refusee ({code}). {message}")
    if code == 403:
        # OpenRouter renvoie 403 pour un MODELE indisponible pour ce type
        # d'acces ('only available on agentic harnesses', vecu 21/10 avec
        # thinkingmachines/inkling:free) : ce n'est pas une mauvaise cle,
        # le maillon suivant doit prendre le relais. Une vraie cle refusee
        # reste AuthError (jamais de bascule silencieuse).
        low = message.lower()
        if any(marker in low for marker in (
                "model", "agentic", "not available", "only available",
                "no endpoints", "restricted")):
            raise ModelUnavailableError(
                f"Modele indisponible pour cette cle ({code}). {message}")
        raise AuthError(f"Cle API refusee ({code}). {message}")
    if code == 402:
        raise QuotaExhaustedError(f"Credits insuffisants (402). {message}")
    if code == 429:
        delay = _retry_after(exc.headers)
        text = f"Limite de debit atteinte (429). {message}"
        raise QuotaExhaustedError(text, retry_after=delay)
    if code == 404 or (code == 400 and "model" in message.lower()):
        raise ModelUnavailableError(f"Modele indisponible ({code}). {message}")
    raise EngineUnavailableError(f"Erreur API {code}. {message}")


def _open(req, timeout: float):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        _raise_http(e)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise EngineUnavailableError(f"Reseau indisponible : {e}")


def post_json(base_url: str, path: str, payload: dict, api_key: str,
              timeout: float = DEFAULT_TIMEOUT_S, extra_headers: dict = None
              ) -> tuple:
    """POST JSON -> (donnees, en-tetes de reponse)."""
    req = urllib.request.Request(
        _url(base_url, path), method="POST",
        headers=_headers(api_key, extra_headers),
        data=json.dumps(payload).encode("utf-8"))
    with _open(req, timeout) as response:
        return json.loads(response.read()), response.headers


def get_json(base_url: str, path: str, api_key: str,
             timeout: float = 30.0) -> tuple:
    req = urllib.request.Request(_url(base_url, path),
                                 headers=_headers(api_key))
    with _open(req, timeout) as response:
        return json.loads(response.read()), response.headers


def chat(base_url: str, api_key: str, model: str, messages: list, *,
         temperature: float = 0.2, tools: list = None,
         tool_choice: str = None, max_tokens: int = None,
         timeout: float = DEFAULT_TIMEOUT_S,
         extra_headers: dict = None) -> dict:
    """Une reponse complete (non streamee) : contenu, tool_calls, usage."""
    payload = {"model": model, "messages": messages,
               "temperature": temperature}
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
    if max_tokens:
        payload["max_tokens"] = max_tokens
    data, _headers_resp = post_json(base_url, "/chat/completions", payload,
                                    api_key, timeout, extra_headers)
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise EngineUnavailableError(f"Reponse inattendue du fournisseur : {e}")
    return {
        "content": message.get("content") or "",
        "tool_calls": message.get("tool_calls") or [],
        "usage": data.get("usage") or {},
        "raw": data,
    }


def stream_chat(base_url: str, api_key: str, model: str, messages: list, *,
                temperature: float = 0.2, tools: list = None,
                max_tokens: int = None, timeout: float = DEFAULT_TIMEOUT_S):
    """Flux SSE des deltas de texte. Reserve a l'assistant (la traduction
    utilise chat() : pas de streaming partiel dans un fichier de jeu)."""
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "stream": True}
    if tools:
        payload["tools"] = tools
    if max_tokens:
        payload["max_tokens"] = max_tokens
    req = urllib.request.Request(
        _url(base_url, "/chat/completions"), method="POST",
        headers=_headers(api_key), data=json.dumps(payload).encode("utf-8"))
    response = _open(req, timeout)
    with response:
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                choice = json.loads(data)["choices"][0]
                delta = choice.get("delta", {}).get("content")
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if delta:
                yield delta


def list_models(base_url: str, api_key: str) -> list:
    """Catalogue brut du fournisseur (id, pricing, context_length)."""
    data, _headers_resp = get_json(base_url, "/models", api_key)
    models = data.get("data", data if isinstance(data, list) else [])
    return [m for m in models if isinstance(m, dict) and m.get("id")]


def key_info(base_url: str, api_key: str) -> dict:
    """Limites/usage de la cle quand le fournisseur l'expose (/key)."""
    data, _headers_resp = get_json(base_url, "/key", api_key)
    return data.get("data", data)


def usage_cost(usage: dict, price_in: float, price_out: float) -> float:
    """Cout USD : valeur reelle annoncee (OpenRouter) sinon estimation au
    tarif declare ($/million de tokens)."""
    usage = usage or {}
    if usage.get("cost") is not None:
        try:
            return float(usage["cost"])
        except (TypeError, ValueError):
            pass
    prompt_tokens = usage.get("prompt_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or 0
    return (prompt_tokens / 1_000_000.0 * (price_in or 0.0)
            + completion_tokens / 1_000_000.0 * (price_out or 0.0))
