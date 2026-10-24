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
Presets de fournisseurs IA et catalogue de modeles. Tout fournisseur
OpenAI-compatible se declare : l'URL de base suffit, la cle est facultative
pour un moteur local. Aucune liste de fournisseurs n'est figee dans le code :
les presets ne servent qu'a pre-remplir le registre (core/settings.py).
"""
from . import client

# Modeles gratuits OpenRouter tries par qualite de localisation
# (catalogue reel du 20/10/2026 : 17 modeles ':free'). Le dialogue
# rafraichit ce catalogue avec la cle de l'utilisateur.
OPENROUTER_FREE_MODELS = [
    "minimax/minimax-m3.1-flash:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
    "dots-studio/dots-3-note-preview:free",
]
# NB : thinkingmachines/inkling[:free] renvoie 403 'only available on
# agentic harnesses' via l'API -- jamais dans la liste.
# Payant suggere : bon rapport qualite/prix pour la localisation.
OPENROUTER_PAID_MODEL = "deepseek/deepseek-chat-v3.1"
# Tarifs indicatifs ($/million) tant que le catalogue n'a pas ete rafraichi.
OPENROUTER_PAID_PRICE = (0.25, 0.95)

PRESETS = {
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "kind": "mixed",
        "docs": "https://openrouter.ai/keys",
        "models": list(OPENROUTER_FREE_MODELS) + [OPENROUTER_PAID_MODEL],
        # tarif indicatif du modele payant suggere, remplace par le
        # catalogue live au premier "Rafraichir"
        "prices": {OPENROUTER_PAID_MODEL: OPENROUTER_PAID_PRICE},
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "kind": "free",
        "docs": "https://console.groq.com/keys",
        "models": ["qwen/qwen3.8-27b"],
    },
    "deepseek": {
        "label": "DeepSeek (direct)",
        "base_url": "https://api.deepseek.com",
        "kind": "paid",
        "docs": "https://platform.deepseek.com/api_keys",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        # tarifs indicatifs a verifier dans l'UI (prix editable)
        "prices": {"deepseek-chat": (0.30, 1.20)},
    },
    "mistral": {
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "kind": "paid",
        "docs": "https://console.mistral.ai/api-keys",
        "models": ["mistral-small-latest"],
    },
    "local": {
        "label": "Unsloth local",
        "base_url": "http://127.0.0.1:8888/v1",
        "kind": "free",
        "docs": "",
        "models": [],
    },
    "ollama": {
        "label": "Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "kind": "free",
        "docs": "",
        "models": [],
    },
    "custom": {
        "label": "Fournisseur personnalise",
        "base_url": "",
        "kind": "paid",
        "docs": "",
        "models": [],
    },
}

PRESET_ORDER = ["openrouter", "groq", "deepseek", "mistral", "local",
                "ollama", "custom"]


def preset(preset_id: str) -> dict:
    return PRESETS.get(preset_id, PRESETS["custom"])


def new_provider(preset_id: str, key: str = "") -> dict:
    """Compte vierge a partir d'un preset (id unique dérivé du nom)."""
    data = preset(preset_id)
    base = preset_id
    pid = base
    n = 2
    from .. import settings
    existing = {p.get("id") for p in settings.get_ai_providers()}
    while pid in existing:
        pid = f"{base}{n}"
        n += 1
    return {
        "id": pid,
        "preset": preset_id,
        "label": data["label"],
        "base_url": data["base_url"],
        "kind": data["kind"],
        "key": key,
        "cap_usd": 0.0,
        "models_order": list(data.get("models", [])),
        # OpenRouter : la boucle free est pre-remplie ; les autres presets
        # n'activent qu'un modele pour ne pas doubler les appels payants.
        "models": (list(OPENROUTER_FREE_MODELS) if preset_id == "openrouter"
                   else list(data.get("models", []))[:1]),
    }


# Espacement minimal entre deux appels (secondes) : les tiers gratuits
# plafonnent le DEBIT. Sans throttle, un lot de cellules part en rafale et
# prend un 429 des la 21e requete OpenRouter (20 req/min, compte free).
MIN_INTERVAL_S = {"openrouter": 3.1, "groq": 2.2}


def min_interval(preset_id: str, tier: str = "free") -> float:
    if preset_id == "openrouter" and tier == "paid":
        return 0.0
    return MIN_INTERVAL_S.get(preset_id, 0.0)


def is_local(base_url: str) -> bool:
    """Un endpoint local (127.0.0.1/localhost) ne sort pas du reseau : il
    n'est pas soumis a la permission 'Traduction en ligne'."""
    low = (base_url or "").lower()
    return ("127.0.0.1" in low or "localhost" in low or "::1" in low)


def model_prices(provider: dict, model: str) -> tuple:
    """(prix entree, prix sortie) $/M pour un modele : catalogue live si
    connu, sinon tarif du preset, sinon 0 (maillon payant refuse)."""
    cat = provider.get("_catalog") or {}
    info = cat.get(model)
    if info and info.get("price_in") is not None:
        return info["price_in"], info.get("price_out") or 0.0
    prices = preset(provider.get("preset", "custom")).get("prices", {})
    return prices.get(model, (0.0, 0.0))


def list_models(provider: dict) -> list:
    """Catalogue reel du fournisseur, normalise : [{id, context_length,
    price_in, price_out}]. Reseau : a appeler hors du thread GUI."""
    raw = client.list_models(provider.get("base_url", ""),
                             provider.get("key", ""))
    out = []
    for item in raw:
        pricing = item.get("pricing") or {}
        try:
            price_in = float(pricing.get("prompt")) * 1_000_000
            price_out = float(pricing.get("completion")) * 1_000_000
        except (TypeError, ValueError):
            price_in = price_out = None
        out.append({
            "id": item["id"],
            "name": item.get("name") or item["id"],
            "context_length": item.get("context_length"),
            "price_in": price_in,
            "price_out": price_out,
        })
    out.sort(key=lambda m: m["id"])
    return out


def account_info(provider: dict) -> str:
    """Solde/limites lisibles quand le fournisseur les expose. OpenRouter
    (/key) et DeepSeek (/user/balance) sinon chaine vide."""
    pid = provider.get("preset") or provider.get("id")
    base = provider.get("base_url", "").rstrip("/")
    key = provider.get("key", "")
    if pid == "openrouter":
        data = client.key_info(base, key)
        limit = data.get("limit_remaining")
        usage = data.get("usage")
        parts = []
        if usage is not None:
            parts.append(f"utilise {usage} $")
        if limit is not None:
            parts.append(f"restant {limit} $")
        free = data.get("free_model_daily_requests") or {}
        if free:
            parts.append(f"free {free.get('remaining')}/{free.get('limit')}")
        return " | ".join(parts)
    if pid == "deepseek":
        data, _h = client.get_json(base, "/user/balance", key)
        infos = data.get("balance_infos") or []
        if infos:
            info = infos[0]
            return (f"solde {info.get('total_balance')} "
                    f"{info.get('currency', '')}").strip()
    return ""


def kind_tier(provider: dict, model: str) -> str:
    """free ou paid pour un modele donne (OpenRouter : suffixe ':free').

    Pour un preset connu, le type du PRESET fait foi : passer DeepSeek en
    'free' dans l'UI ne doit pas contourner le budget alors que l'API
    facture. Le champ 'kind' n'est libre que pour un fournisseur custom."""
    preset_id = provider.get("preset")
    kind = (PRESETS[preset_id]["kind"] if preset_id in PRESETS
            else provider.get("kind", "paid"))
    if kind in ("free", "local"):
        return "free"
    if kind == "mixed":
        return "free" if (model or "").endswith(":free") else "paid"
    return "paid"
