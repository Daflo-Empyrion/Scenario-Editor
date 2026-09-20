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
Moteur de traduction DEEPL (api-free.deepl.com, plan "DeepL API Free" :
500 000 caracteres/mois, sans carte bancaire -- la cle free se termine
par ':fx'). Maillon de la chaine de secours (v1.10.0, inspir du failover
de freellmapi) : Groq -> DEEPL -> Google -> local.

API REST officielle (pas de dependance) : POST /v2/translate avec
l'en-tete 'Authorization: DeepL-Auth-Key <cle>'. Erreurs TYPEES
(core/engine_errors.py) pour que la chaine sache basculer : 403 = cle
refusee (AuthError, jamais de bascule silencieuse), 456 = quota mensuel
epuise (QuotaExhaustedError), 429 = trop de requetes (QuotaExhaustedError),
5xx/reseau = indisponible (EngineUnavailableError).

ATTENTION EN-TETE : sans User-Agent, certaines passerelles bloquent la
requete avant l'API (vecu reel sur Groq/Felo, 17-18/09/2026).
"""
import json
import urllib.error
import urllib.request
from typing import Optional

from . import settings
from .engine_errors import (AuthError, EngineUnavailableError,
                            QuotaExhaustedError)

BASE_FREE = "https://api-free.deepl.com/v2"
# Le plan PRO (api.deepl.com) n'est PAS utilise : cette integrazione vise
# le tier gratuit. Une cle pro saisie par erreur -> 403 -> AuthError
# affichee clairement (message : verifier le plan).

# Codes de langue DeepL (cible, majuscules ; 'en'/'pt' doivent etre
# particularises EN-US/EN-GB et PT-BR/PT-PT -- on choisit les variantes
# US/Bresil, les plus courantes dans les scenarios).
_TARGET_MAP = {
    "fr": "FR", "en": "EN-US", "de": "DE", "es": "ES", "it": "IT",
    "ja": "JA", "ko": "KO", "pl": "PL", "pt": "PT-BR", "pt-BR": "PT-BR",
    "ru": "RU", "zh-CN": "ZH", "zh-TW": "ZH", "nl": "NL", "tr": "TR",
    "el": "EL", "vi": "VI", "cs": "CS", "uk": "UK", "ar": "AR",
    "hu": "HU", "id": "ID", "nb": "NB", "ro": "RO", "sk": "SK",
    "sv": "SV", "da": "DA", "fi": "FI", "et": "ET", "lv": "LV",
    "lt": "LT", "sl": "SL", "bg": "BG",
}


def is_configured() -> bool:
    """Vrai si une cle DeepL est enregistree (test sans reseau)."""
    return bool(settings.get_deepl_api_key())


def target_supported(target_code: str) -> bool:
    """Vrai si DeepL sait traduire vers cette langue (sinon la chaine de
    secours saute ce maillon au lieu d'echouer au milieu d'un lot)."""
    return (target_code or "") in _TARGET_MAP


def translate(protected_text: str, target_code: str) -> str:
    """Traduit un TEXTE DEJA PROTEGE (jetons XXTAG poses par le pipeline,
    comme pour le chemin Google -- DeepL respecte ces jetons neutres).
    Leve des erreurs typees : AuthError (cle), QuotaExhaustedError
    (quota/debit), EngineUnavailableError (reseau/5xx)."""
    target = _TARGET_MAP.get(target_code)
    if not target:
        raise EngineUnavailableError(
            f"DeepL ne couvre pas la langue cible '{target_code}'.")
    req = urllib.request.Request(
        BASE_FREE + "/translate", method="POST",
        headers={"Authorization": f"DeepL-Auth-Key {settings.get_deepl_api_key()}",
                 "Content-Type": "application/json",
                 "User-Agent": "EmpyrionScenarioEditor"},
        data=json.dumps({
            "text": [protected_text],
            "target_lang": target,
            "preserve_formatting": True,
        }).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            body = json.loads(e.read().decode(errors="replace"))
            detail = body.get("message", "")
        except Exception:
            pass
        if e.code == 403:
            raise AuthError(
                "Cle DeepL refusee (403). Verifie la cle (une cle FREE se "
                "termine par ':fx') et le plan souscrit (API Free). "
                + detail)
        if e.code == 456:
            raise QuotaExhaustedError(
                "Quota DeepL epuise (plan API Free : 500 000 caracteres/"
                "mois, remise a zero le 1er du mois). " + detail)
        if e.code == 429:
            raise QuotaExhaustedError(
                "Trop de requetes DeepL (limite de debit) -- la chaine de "
                "secours passe au moteur suivant. " + detail)
        raise EngineUnavailableError(f"Erreur DeepL {e.code}. {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise EngineUnavailableError(f"Reseau indisponible pour DeepL : {e}")
    try:
        return data["translations"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise EngineUnavailableError(f"Reponse DeepL inattendue : {e}")


def quick_check() -> str:
    """Test reel utilise par l'assistant : traduit une phrase courte et
    retourne le texte + un marqueur du plan. RuntimeError si echoue."""
    out = translate("The generators are overloaded.", "fr")
    return f"[DeepL Free] {out}"


def limits_summary() -> Optional[str]:
    """Pas de compteur temps reel chez DeepL (pas d'entete de quota) :
    retourne None -- l'interface n'affiche rien pour ce moteur (le
    libelle du plan 500k/mois est dans l'assistant)."""
    return None
