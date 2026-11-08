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

"""Coherence affichage <-> modules : un dialogue ne doit jamais afficher le
message metier d'un AUTRE module (vecu 06/11 : « Ondes de spawn » demandait
« Appliquer N corrections aux marchands ? », et annoncait « N prix ecrits »).

Regle verifiee ici : une cle i18n d'un domaine peut etre partagee entre
modules SEULEMENT si son texte reste neutre (Tout cocher, Exporter CSV,
Type, Item...). Des qu'elle nomme un metier (marchand, prix, jeton, recette,
spawn, playfield, blueprint...), seul le module proprietaire peut l'utiliser.
"""

import json
import re
from pathlib import Path

GUI = Path(__file__).resolve().parent.parent / "gui"
I18N = Path(__file__).resolve().parent.parent / "data" / "i18n_strings.json"

# prefixe i18n -> fragments de nom de fichier qui en sont propriétaires
OWNERS = {
    "market": ("market_price_dialog",),
    "taudit": ("trader_audit_dialog",),
    "eco": ("economy_editor_dialog", "economy_check_dialog"),
    "ecocheck": ("economy_check_dialog",),
    "ecoedit": ("economy_editor_dialog",),
    "sw": ("spawn_waves_dialog",),
    "codex": ("codex_",),
    "starters": ("starters_dialog",),
    "epb": ("epb_check_dialog", "epb_3d_window"),
    "epb3d": ("epb_3d_window",),
    "coh": ("coherence_dialog",),
    "launchcheck": ("launch_check_dialog",),
    "corr": ("correlation_dialog",),
    "recipe": ("recipe_balance_dialog",),
    "realism": ("recipe_realism_dialog",),
    "unlockcost": ("unlock_cost_dialog",),
    "diff": ("difficulty_dialog",),
    "tokens": ("token_config_dialog",),
    "poi": ("poi_add_dialog", "poi_inspector_dialog", "yaml_merge_review_dialog"),
    "prog": ("progression_dialog",),
    "bundles": ("bundles_dialog",),
    "cartoon": ("cartoon_dialog",),
    "backup": ("backup_dialog",),
    "digest": ("scenario_digest_dialog",),
    "sectors": ("sectors_merge_flow",),
    "galaxy": ("galaxy_viewer_dialog", "galaxy_merge_dialog",
               "sectors_merge_flow", "name_merge_dialog"),
    "dash": ("dashboard_dialog",),
    "tradaud": ("trader_audit_dialog",),
}

# mots qui trahissent le metier d'un module
BUSINESS_WORDS = ("marchand", "prix", "jeton", "recette", "spawn", "onde",
                  "deblocage", "déblocage", "blueprint", "playfield", "economie",
                  "économie", "codex", "depart", "départ")

KEY_RE = re.compile(r't\(\s*"([a-z0-9_]+\.[^"]+)"')

# agregateurs : le menu principal ouvre les modules, il cite donc leurs titres
AGGREGATORS = {"main_window"}


def _texts():
    return json.loads(I18N.read_text(encoding="utf-8"))


def _used_keys():
    """{fichier: {cle}} pour tous les modules GUI."""
    out = {}
    for path in sorted(GUI.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        out[path.stem] = set(KEY_RE.findall(text))
    return out


def _foreign_messages():
    """Liste des (fichier, cle, mots metier) qui trahissent un autre module."""
    texts = _texts()
    problems = []
    for stem, keys in _used_keys().items():
        if stem in AGGREGATORS:
            continue
        for key in sorted(keys):
            domain = key.split(".")[0]
            owners = OWNERS.get(domain)
            if not owners or any(owner in stem for owner in owners):
                continue
            french = (texts.get(key) or {}).get("fr", "").lower()
            hits = [word for word in BUSINESS_WORDS if word in french]
            if hits:
                problems.append((stem, key, hits, french))
    return problems


def test_no_module_shows_another_modules_business_message():
    problems = _foreign_messages()
    report = "\n".join(
        f"{stem} affiche {key} ({', '.join(hits)}) : « {french[:70]} »"
        for stem, key, hits, french in problems)
    assert not problems, (
        "Message métier d'un autre module affiché dans un dialogue :\n" + report)


def test_every_used_key_exists_and_is_translated():
    texts = _texts()
    missing = []
    for stem, keys in _used_keys().items():
        for key in sorted(keys):
            # cles construites dynamiquement (« prog.status_ » + nom) : le
            # script d'audit les couvre par la valeur reelle, pas ce test
            if key.endswith(("_", ".")) or "(" in key or ")" in key:
                continue
            entry = texts.get(key)
            if not entry or not entry.get("fr") or not entry.get("en"):
                missing.append(f"{stem}: {key}")
    assert not missing, "Clés absentes ou incomplètes :\n" + "\n".join(missing)


def test_window_titles_name_their_own_module():
    """Titres releves faux le 06/11 : le visualiseur de galaxie s'annoncait
    « Fusion GalaxyConfig », le formulaire de signalement « Comparaison de
    scenarios »."""
    texts = _texts()
    assert "Fusion" not in texts["galaxy.viewer_title"]["fr"]
    keys = _used_keys()
    assert "galaxy.title" not in keys["galaxy_viewer_dialog"]
    assert "report.title" not in keys["report_issue_dialog"]
    assert "issue" in texts["report.window_title"]["en"].lower()


def test_spawn_waves_wording_is_its_own():
    """Le cas signale : le dialogue des ondes de spawn ne parle ni de
    marchands ni de prix."""
    keys = _used_keys()["spawn_waves_dialog"]
    assert not [key for key in keys if key.startswith(("taudit.", "market.applied"))]
    texts = _texts()
    for key in ("sw.apply_confirm", "sw.applied"):
        french = texts[key]["fr"].lower()
        assert "marchand" not in french and "prix" not in french
