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
Reparation du glossaire (21/10/2026) : tri terminology / phrases,
reference a la localisation officielle (vanille) quand elle existe, puis
retraduction IA des autres entrees. Produit un fichier de PROPOSITIONS
revu dans gui/glossary_repair_dialog.py -- rien n'est ecrit dans le
glossaire sans selection explicite de l'utilisateur.

Principes :
- une entree PHRASE (dialogue, fragment ordinaire) est desactivee : elle
  reste dans le fichier, reactivable, mais ne pollue plus les phrases ;
- une entree TERME est conservee et sa traduction corrigee ;
- la traduction officielle Eleon gagne toujours sur l'IA ;
- les doublons, cibles mojibake et sources non traduites sont signales ;
- l'analyse est reprise apres interruption (fichier de progression).
"""
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Callable, Optional

from . import glossary, settings, vanilla_memory
from .ai import budget, client
from .fsutil import atomic_write_text

PROPOSAL_FILE = Path.home() / ".empyrion_editor" / "glossary_repair.json"
FIXES_FILE = Path(__file__).resolve().parent.parent / "data" / "glossary_fixes_fr.json"
MODEL = "deepseek/deepseek-chat-v3.1"
BATCH_SIZE = 20
_SAVE_EVERY = 5  # lots entre deux ecritures de progression

_SYSTEM = """You repair a French translation glossary for the video game
Empyrion Galactic Survival. Each input line is a JSON object:
{"id": n, "src": "...", "dst": "...", "official": "..." or null}.

For EVERY input id, return:
- "kind": "term" for terminology (proper noun, product/tech/game name,
  fixed label, short noun phrase) or "phrase" for an ordinary sentence or
  dialogue fragment (contains a verb, pronoun, article, punctuation).
- "fr": the correct French translation. If "official" is not null, copy it
  VERBATIM as "fr". Preserve proper nouns, acronyms, numbers and
  capitalization. Never add quotes or explanations.
- "keep": true only if "dst" is already a correct translation.
- "reason": one of "official", "correct", "wrong", "ordinary",
  "proper_noun", "technical".

Reply with ONLY a JSON array, one object per input id, same order:
[{"id":1,"kind":"term","fr":"...","keep":true,"reason":"technical"}]
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

# Tri LOCAL (aucun appel reseau) : mots-outils et verbes courants qui
# signalent une phrase ordinaire plutot qu'une terminologie. Un doute =
# phrase (desactivee), jamais l'inverse : une phrase activee pollue les
# traductions (vecu 'no' -> 'Non', 'Welcome' -> 'Accueillir').
_FUNC = set(
    "a an the and or but if then than so to of in on at by for from with "
    "without into over under about as is are was were be been being am do "
    "does did have has had can could will would shall should may might must "
    "not no yes i you he she it we they me him her us them my your his its "
    "our their this that these those there here what who whom whose which "
    "when where why how all any some each every few many much more most "
    "other such own same very just also only welcome hello hey please thanks "
    "sorry".split())
_VERBS = set(
    "investigate appraise locate approach find send receive boost excavate "
    "transmit explore collect retrieve repair build destroy kill attack "
    "defend talk speak ask tell give take get make use work help need want "
    "know think see look say go come keep let put run sell buy pay play live "
    "die fight fly drop raise open close start stop turn move follow lead "
    "join leave return show call hold bring happen change stay begin seem "
    "feel try".split())


def heuristic_kind(src: str) -> str:
    """'term' (terminologie) ou 'phrase' (fragment ordinaire), sans IA."""
    text = (src or "").strip()
    if not text:
        return "phrase"
    if re.search(r"[.!?;:]", text):
        return "phrase"
    words = [w for w in re.split(r"\s+", text) if w]
    low = [w.lower().strip(".,!?\"'()[]") for w in words]
    if len(words) == 1:
        if low[0] in _FUNC or low[0] in _VERBS:
            return "phrase"
        if any(c.isdigit() for c in words[0]):
            return "term"
        return "term" if words[0][:1].isupper() else "phrase"
    # titre avec article initial : 'The Signal', 'A New Parameter'
    if (low[0] in ("the", "a", "an")
            and all(w[:1].isupper() for w in words[1:] if w[:1].isalpha())):
        return "term"
    if any(w in _FUNC or w in _VERBS for w in low):
        return "phrase"
    return "term"


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def _norm_target(target: str) -> str:
    from .translation import repair_mojibake
    value = (target or "").strip()
    if not value:
        return "fr"
    repaired = repair_mojibake(value)
    low = repaired.lower()
    if low in ("fr", "francais", "français", "french"):
        return "fr"
    return value if value == repaired else repaired


def _provider() -> Optional[dict]:
    for provider in settings.get_ai_providers():
        if provider.get("preset") == "openrouter" and provider.get("key"):
            return provider
    return None


def _signature(items: list) -> str:
    payload = json.dumps([[i.get("src"), i.get("target"), i.get("old")]
                          for i in items], ensure_ascii=False)
    return f"{len(items)}:" + hashlib.sha1(
        payload.encode("utf-8")).hexdigest()[:16]


def _ask_ai(rows: list, model: str = MODEL) -> tuple:
    """({id: {kind, fr, keep, reason}}, cout USD) pour un lot. Leve une
    exception si la reponse est inexploitable."""
    provider = _provider()
    if provider is None:
        raise RuntimeError(
            "Aucun fournisseur OpenRouter configure : ajoute la cle dans "
            "Options > Traduction > Fournisseurs IA.")
    user_content = "\n".join(json.dumps(row, ensure_ascii=False)
                             for row in rows)
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content}]
    result = client.chat(provider["base_url"], provider["key"], model,
                         messages, temperature=0.0, max_tokens=4000,
                         timeout=180)
    cost = float((result.get("usage") or {}).get("cost") or 0.0)
    text = _FENCE_RE.sub("", (result.get("content") or "").strip())
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("Reponse IA sans tableau JSON")
    data = json.loads(text[start:end + 1])
    out = {}
    for item in data:
        try:
            ident = int(item["id"])
            kind = "phrase" if item.get("kind") == "phrase" else "term"
            fr = str(item.get("fr") or "").strip()
            if not fr:
                continue
            out[ident] = {"kind": kind, "fr": fr,
                          "keep": bool(item.get("keep")),
                          "reason": str(item.get("reason") or "")[:40]}
        except (KeyError, TypeError, ValueError):
            continue
    return out, cost


def _base_items(model: str) -> list:
    """Etats structurels + reference vanille, avant l'IA."""
    entries = glossary.entries()
    official_pairs = {}
    try:
        official_pairs = vanilla_memory.vanilla_pairs("fr")
    except Exception:
        pass
    seen = {}
    items = []
    for index, entry in enumerate(entries):
        src = entry.get("src") or ""
        old = entry.get("dst") or ""
        target = _norm_target(entry.get("target"))
        official = official_pairs.get(_norm(src))
        key = (_norm(src).lower(), target)
        item = {
            "id": index,
            "src": src,
            "target": target,
            "orig_target": entry.get("target") or "fr",
            "old": old,
            "new": old,
            "kind": "term",
            "action": "keep",
            "reason": "",
            "official": official,
            "enabled": entry.get("on", True),
        }
        if key in seen:
            item["action"] = "remove"
            item["reason"] = "duplicate"
            items.append(item)
            continue
        seen[key] = index
        if target != (entry.get("target") or "fr"):
            item["reason"] = "target"
        if not _norm(old):
            item["action"] = "translate"
            item["reason"] = "empty"
        elif _norm(src).lower() == _norm(old).lower():
            item["action"] = "translate"
            item["reason"] = "src=dst"
        if official and _norm(official) != _norm(old):
            item["action"] = "translate"
            item["new"] = official
            item["reason"] = "official"
        elif official:
            item["reason"] = "official"
        items.append(item)
    return items


def _merge_ai(items: list, ai: dict) -> None:
    for item in items:
        if item["action"] == "remove":
            continue
        answer = ai.get(item["id"])
        if not answer:
            item["reason"] = item["reason"] or "ai_error"
            continue
        official = item.get("official")
        new = official if official else answer["fr"]
        item["kind"] = answer["kind"]
        item["new"] = new
        if answer["kind"] == "phrase":
            item["action"] = "disable"
            item["reason"] = "ordinary"
            continue
        if _norm(new) != _norm(item["old"]):
            item["action"] = "translate"
            item["reason"] = ("official" if official
                              else (answer["reason"] or "wrong"))
        elif item["action"] not in ("translate", "remove"):
            item["action"] = "keep"
            item["reason"] = item["reason"] or "correct"


def _stats(items: list) -> dict:
    out = {"total": len(items), "term": 0, "phrase": 0, "translate": 0,
           "disable": 0, "remove": 0, "keep": 0}
    for item in items:
        out[item["kind"]] = out.get(item["kind"], 0) + 1
        out[item["action"]] = out.get(item["action"], 0) + 1
    return out


def analyze_local() -> dict:
    """Analyse SANS IA : tri heuristique, phrases desactivees, vanille
    prioritaire, corrections manuelles de data/glossary_fixes_fr.json.
    Cout nul, aucun reseau. Les termes douteux (src=dst, officiel different)
    restent dans la revue pour correction manuelle."""
    fixes, skip_official = _load_fixes()
    items = _base_items(MODEL)
    for item in items:
        if item["action"] == "remove":
            continue
        kind = heuristic_kind(item["src"])
        item["kind"] = kind
        target_fixed = item["target"] != item["orig_target"]
        if kind == "phrase":
            item["action"] = "disable"
            item["reason"] = "ordinary"
            item["new"] = item["old"]
            continue
        manual = fixes.get(item["src"])
        official = item.get("official")
        if manual and _norm(manual) != _norm(item["old"]):
            item["action"] = "translate"
            item["new"] = manual
            item["reason"] = "manual"
        elif (official and item["src"] not in skip_official
              and _norm(official) != _norm(item["old"])):
            item["action"] = "translate"
            item["new"] = official
            item["reason"] = "official"
        else:
            item["action"] = "keep"
            item["new"] = item["old"]
            item["reason"] = "target" if target_fixed else "correct"
    result = {"created": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": "local", "signature": _signature(items),
              "complete": True, "processed": len(items), "cost": 0.0,
              "stats": _stats(items),
              "items": [item for item in items
                        if item["action"] != "keep"
                        or item["reason"] in ("official", "target", "manual")]}
    _save_proposal(items, len(items), True, "local", 0.0)
    return result


def _load_fixes() -> tuple:
    """(terms {src: nouvelle traduction}, skip_official set)."""
    try:
        data = json.loads(FIXES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}, set()
    terms = data.get("terms") if isinstance(data, dict) else {}
    skip = data.get("skip_official") if isinstance(data, dict) else []
    return (terms if isinstance(terms, dict) else {},
            set(skip or []))


def analyze(limit: int = None, progress: Callable[[int, int], None] = None,
            model: str = MODEL, stop: Callable[[], bool] = None) -> dict:
    """Genere les propositions. `limit` = nombre d'entrees (tests).
    Reprend une analyse interrompue si le glossaire n'a pas change."""
    if _provider() is None:
        raise RuntimeError(
            "Aucun fournisseur OpenRouter configure : ajoute la cle dans "
            "Options > Traduction > Fournisseurs IA.")
    items = _base_items(model)
    if limit:
        items = items[:limit]
    signature = _signature(items)
    processed = 0
    old = _load_proposal()
    if (old and not old.get("complete")
            and old.get("signature") == signature
            and old.get("model") == model
            and len(old.get("items", [])) == len(items)):
        items = old["items"]
        processed = int(old.get("processed") or 0)
    pending = [item for item in items
               if item["action"] != "remove" and item["id"] >= processed]
    total = len(pending)
    cost = float(old.get("cost") or 0.0) if processed else 0.0
    if not budget.can_spend("openrouter", 1.0):
        raise RuntimeError(
            "Budget IA insuffisant pour reparer le glossaire : verifie "
            "Options > Traduction > Fournisseurs IA (payant autorise et "
            "plafond disponible).")
    done = 0
    for start in range(0, total, BATCH_SIZE):
        if stop and stop():
            _save_proposal(items, processed, False, model, cost)
            raise InterruptedError("Analyse interrompue")
        batch = pending[start:start + BATCH_SIZE]
        rows = [{"id": item["id"], "src": item["src"],
                 "dst": item["old"], "official": item.get("official")}
                for item in batch]
        spent = 0.0
        try:
            ai, spent = _ask_ai(rows, model)
        except Exception as exc:
            # un lot illisible ne bloque pas les 370 autres : on garde
            # l'existant, la revue signalera ces lignes.
            for item in batch:
                item["reason"] = item["reason"] or f"ai_error:{type(exc).__name__}"
            ai = {}
        if spent:
            cost += spent
            budget.record("openrouter", spent)
        _merge_ai(batch, ai)
        done += len(batch)
        processed = max(processed, batch[-1]["id"] + 1)
        if progress:
            progress(done, total)
        if done % (BATCH_SIZE * _SAVE_EVERY) == 0:
            _save_proposal(items, processed, False, model, cost)
    budget.flush()
    result = {"created": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": model, "signature": signature, "complete": True,
              "processed": processed, "cost": round(cost, 6),
              "stats": _stats(items),
              "items": [item for item in items
                        if item["action"] != "keep"
                        or item["reason"] in ("official", "target", "src=dst")]}
    _save_proposal(items, processed, True, model, cost)
    return result


def _save_proposal(items: list, processed: int, complete: bool,
                   model: str, cost: float) -> None:
    data = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "model": model,
            "signature": _signature(items), "complete": complete,
            "processed": processed, "cost": round(cost, 6),
            "stats": _stats(items), "items": items}
    try:
        PROPOSAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(PROPOSAL_FILE, json.dumps(data, ensure_ascii=False,
                                                    indent=1))
    except Exception:
        pass


def _load_proposal() -> Optional[dict]:
    try:
        data = json.loads(PROPOSAL_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_proposal() -> Optional[dict]:
    """Propositions en cache (None si absentes ou incompletes)."""
    data = _load_proposal()
    if not data or not data.get("complete"):
        return None
    data["items"] = [item for item in data.get("items", [])
                     if item.get("action") != "keep"
                     or item.get("reason") in ("official", "target",
                                               "src=dst")]
    data["stats"] = _stats(data["items"])
    return data


def apply(items: list) -> dict:
    """Applique les lignes selectionnees. Backup horodate AVANT ecriture.
    Les entrees sont retrouvees par (source, langue, ancienne traduction),
    pas par index : une application en plusieurs vagues reste sure meme si
    des doublons ont ete supprimes entre-temps.
    Retourne {'backup', 'updated', 'disabled', 'removed', 'skipped'}."""
    from collections import defaultdict
    from .fsutil import central_backup
    entries = glossary.entries()
    backup = central_backup(glossary.GLOSSARY_FILE, kind="glossary")
    updated = disabled = removed = skipped = 0
    buckets = defaultdict(list)
    for index, entry in enumerate(entries):
        buckets[(_norm(entry.get("src")).lower(),
                 _norm_target(entry.get("target")),
                 _norm(entry.get("dst")))].append(index)
    used = set()
    removals = set()
    for item in items:
        key = (_norm(item.get("src")).lower(),
               item.get("target") or "fr",
               _norm(item.get("old")))
        candidates = [i for i in buckets.get(key, []) if i not in used]
        if not candidates:
            skipped += 1
            continue
        index = candidates[0]
        used.add(index)
        entry = entries[index]
        action = item.get("action")
        if action == "remove":
            removals.add(index)
            continue
        entry["target"] = item.get("target") or "fr"
        entry["dst"] = item.get("new") or entry.get("dst") or ""
        entry["on"] = False if action == "disable" else True
        if action == "translate":
            updated += 1
        elif action == "disable":
            disabled += 1
    # ne jamais supprimer la DERNIERE entree d'une source
    survivors = {}
    for index, entry in enumerate(entries):
        if index in removals:
            continue
        key = (_norm(entry.get("src")).lower(),
               _norm_target(entry.get("target")))
        survivors[key] = survivors.get(key, 0) + 1
    final = []
    protected = set()
    for index, entry in enumerate(entries):
        if index in removals:
            key = (_norm(entry.get("src")).lower(),
                   _norm_target(entry.get("target")))
            if survivors.get(key, 0) == 0 and key not in protected:
                protected.add(key)  # ne jamais vider une source entierement
    for index, entry in enumerate(entries):
        if index in removals:
            key = (_norm(entry.get("src")).lower(),
                   _norm_target(entry.get("target")))
            if key in protected:
                final.append(entry)
                skipped += 1
                continue
            removed += 1
            continue
        final.append(entry)
    atomic_write_text(glossary.GLOSSARY_FILE,
                      json.dumps(final, ensure_ascii=False, indent=1))
    glossary.reset_cache()
    return {"backup": str(backup), "updated": updated, "disabled": disabled,
            "removed": removed, "skipped": skipped}


def export_csv(items: list, path: Path) -> int:
    import csv
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["action", "kind", "src", "old", "new", "reason"])
        for item in items:
            writer.writerow([item.get("action"), item.get("kind"),
                             item.get("src"), item.get("old"),
                             item.get("new"), item.get("reason")])
    return len(items)
