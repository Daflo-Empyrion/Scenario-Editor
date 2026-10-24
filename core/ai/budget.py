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
Budget des fournisseurs IA payants : cumul MENSUEL en dollars, plafond
global (settings.ai_monthly_cap_usd) et plafond optionnel par fournisseur
(provider.cap_usd, 0 = plafond global).

Le compteur vit en memoire pendant un lot et n'est ecrit dans settings.json
que tous les _FLUSH_EVERY appels ou a la fin du lot (regle projet : aucune
I/O disque dans un chemin appele par cellule). Un crash en plein lot peut
donc perdre les derniers centimes -- jamais le plafond lui-meme, qui reste
lu depuis les settings.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_STATE = None
_FLUSH_EVERY = 10
_PENDING = 0


def _month_now() -> str:
    return time.strftime("%Y-%m")


def _fresh() -> dict:
    return {"month": _month_now(), "total": 0.0, "providers": {}}


def _load() -> dict:
    global _STATE
    if _STATE is None:
        from .. import settings
        state = settings.get_ai_spend()
        if not isinstance(state, dict) or state.get("month") != _month_now():
            state = _fresh()
        else:
            try:
                state["total"] = float(state.get("total") or 0.0)
            except (TypeError, ValueError):
                state["total"] = 0.0
            if not isinstance(state.get("providers"), dict):
                state["providers"] = {}
        _STATE = state
    return _STATE


def reset() -> None:
    """Vide le cache memoire (tests, changement de mois, remise a zero UI).
    Ne supprime PAS le compteur persiste : voir reset_spend()."""
    global _STATE, _PENDING
    with _LOCK:
        _STATE = None
        _PENDING = 0


def reset_spend() -> None:
    """Remise a zero du compteur du mois (bouton du dialogue)."""
    global _STATE, _PENDING
    with _LOCK:
        _STATE = _fresh()
        _PENDING = 0
        from .. import settings
        settings.set_ai_spend(dict(_STATE))


def _provider_cap(provider_id: str) -> float:
    from .. import settings
    for provider in settings.get_ai_providers():
        if provider.get("id") == provider_id:
            try:
                return float(provider.get("cap_usd") or 0.0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def cap(provider_id: str = None) -> float:
    """Plafond effectif ($), 0 = aucun plafond defini (payant refuse)."""
    own = _provider_cap(provider_id) if provider_id else 0.0
    if own > 0:
        return own
    from .. import settings
    try:
        return float(settings.get_ai_monthly_cap_usd() or 0.0)
    except (TypeError, ValueError):
        return 0.0


def spent(provider_id: str = None) -> float:
    with _LOCK:
        state = _load()
        if provider_id:
            return float(state["providers"].get(provider_id, 0.0))
        return float(state["total"])


def can_spend(provider_id: str, estimate: float) -> bool:
    """Vrai si le prochain appel payant tient dans le plafond. Plafond non
    defini = refus (un plafond inconnu ne protege de rien)."""
    plafond = cap(provider_id)
    return plafond > 0 and spent(provider_id) + max(0.0, estimate) <= plafond


def record(provider_id: str, cost: float) -> None:
    """Cumule un cout REEL (usage.cost ou estimation). Ecriture differee."""
    global _PENDING
    if not provider_id or cost <= 0:
        return
    with _LOCK:
        state = _load()
        state["total"] = float(state["total"]) + cost
        state["providers"][provider_id] = (
            float(state["providers"].get(provider_id, 0.0)) + cost)
        _PENDING += 1
        if _PENDING >= _FLUSH_EVERY:
            _flush_locked()


def _flush_locked() -> None:
    global _PENDING
    if _STATE is None:
        return
    from .. import settings
    try:
        settings.set_ai_spend(dict(_STATE))
        _PENDING = 0
    except Exception as e:
        # Le compteur en memoire reste juste (le plafond tient pendant la
        # session) ; seule la persistance est retentee au prochain appel.
        logger.warning("Ecriture du budget IA impossible : %s", e)


def flush() -> None:
    """Ecrit le compteur en attente (fin de lot, fermeture du dialogue)."""
    with _LOCK:
        _flush_locked()


def summary() -> dict:
    with _LOCK:
        state = _load()
        return {
            "month": state["month"],
            "total": float(state["total"]),
            "providers": dict(state["providers"]),
            "cap": cap(),
            "remaining": max(0.0, cap() - float(state["total"])),
        }
