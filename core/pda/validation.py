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

"""Validation du PDA (paquet A du backlog 12/09/2026) -- regles tirees du
guide officiel de creation de missions (doc/EMPYRION_GALACTIC_SURVIVAL/PDA).

Logique PURE (aucun Qt) : validate_model(model) -> liste de PdaIssue
(severite + chemin lisible + entree navigable). L'editeur GUI l'affiche
(bandeau live de l'action + bouton Verifier) ; les messages passent par
t() pour suivre la langue de l'interface.

Regles implementees (codes stables) :
  PDA-A2  action : CompletedMessage obligatoire ($ ou texte) ; un seul
          Check par action ; NAMES/TYPES requis selon le Check
  PDA-A4  Visibility/Activatable WhenRewarded sur le PREMIER chapitre
          (aucun precedent) ; precedent jamais completable
  PDA-A5  cibles de chainage inexistantes (ActivateChapterOnCompletion/
          OnSkip/RewardedChapters/RewardedTasks)
  PDA-A6  jeton utilise dans le YAML absent du PDA.csv ; jeton du CSV
          plus reference par le YAML (orphelin)
  PDA-A7  valeur LEFTOVER dans un champ non supporte par le Check
          (ex: Types renseigne sur un Check sans TYPES)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from core.i18n import t
from core.pda import schema
from core.yamllite.model import YamlEntry

TITLE_LIMITS = {"TaskTitle": 26, "ActionTitle": 24}
_TOKEN_RE = re.compile(r"^pda_[A-Za-z0-9]{5,}$")
_BBCODE_RE = re.compile(r"\[/?.{1,32}?\]")


def visible_len(text: str) -> int:
    """Longueur VISIBLE d'un titre : les balises BBCode Empyrion
    ([c][ffffff], [b], [-]...) n'occupent pas de place a l'ecran."""
    return len(_BBCODE_RE.sub("", text or ""))


@dataclass
class PdaIssue:
    severity: str                 # "error" | "warning"
    code: str                     # "PDA-A2", ...
    path: str                     # chaine lisible (titres resolvus)
    message: str                  # texte pret a afficher (langue de l'UI)
    entry: Optional[YamlEntry] = None   # cible navigable (double-clic)


def _title(model, entry: YamlEntry) -> str:
    token = entry.value or ""
    text = model.csv_text(token, "English") if token else ""
    return text or token


def _chain(model, chapter, task=None, action=None) -> str:
    c = _title(model, chapter)
    parts = [c or "?"]
    if task is not None:
        parts.append(_title(model, task) or "?")
    if action is not None:
        parts.append(_title(model, action) or "?")
    return " > ".join(parts)


def _child(entry: YamlEntry, key: str) -> Optional[YamlEntry]:
    for child in entry.children:
        if isinstance(child, YamlEntry) and child.key == key:
            return child
    return None


def _scalar(entry: YamlEntry, key: str) -> str:
    node = _child(entry, key)
    return (node.value or "").strip() if node is not None else ""


def _count_children(entry: YamlEntry, key: str) -> int:
    return sum(1 for c in entry.children
               if isinstance(c, YamlEntry) and c.key == key)


def _list_values(entry: YamlEntry, key: str) -> List[str]:
    node = _child(entry, key)
    if node is None:
        return []
    return [(c.value or "").strip() for c in node.children
            if isinstance(c, YamlEntry)]


# ------------------------------------------------------------------ action

def validate_action(model, chapter, task, action) -> List[PdaIssue]:
    """A2 + A7 pour UNE action -- utilise en live par le panneau d'edition
    et dans la passe globale."""
    issues: List[PdaIssue] = []
    path = _chain(model, chapter, task, action)
    check = model.action_check(action)
    spec = schema.check_spec(check)
    known = check in schema.CHECKS

    # -- A2 : CompletedMessage conseille ($ = message par defaut du jeu).
    # AVERTISSEMENT et non erreur : la VANILLE elle-meme en est depourvue
    # sur la plupart des actions (865/2209) et ses missions fonctionnent.
    cm = _child(action, "CompletedMessage")
    if cm is None or not (cm.value or "").strip():
        issues.append(PdaIssue(
            "warning", "PDA-A2", path,
            t("pda.val.no_completed_message"), action))

    # -- A2 : un seul Check par action (structure anormale sinon)
    if _count_children(action, "Check") > 1:
        issues.append(PdaIssue(
            "error", "PDA-A2", path,
            t("pda.val.multiple_checks"), action))

    if not check:
        # action purement informative : CompletedMessage suffit
        return issues

    names = _list_values(action, "Names")
    types = _list_values(action, "Types")

    # -- A2 : NAMES / TYPES requis selon le Check
    if known:
        # AVERTISSEMENT et non erreur : le contenu officiel contient des
        # actions avec Check sans Names/Types (16 ItemsPickedUp sur les 3
        # corpus) qui fonctionnent (completion manuelle ou trigger libre).
        if spec.uses_names and spec.uses_types:
            if not names and not types:
                issues.append(PdaIssue(
                    "warning", "PDA-A2", path,
                    t("pda.val.needs_names_or_types",
                      check=t(spec.label_key)), action))
        elif spec.uses_names and not names:
            issues.append(PdaIssue(
                "warning", "PDA-A2", path,
                t("pda.val.needs_names", check=t(spec.label_key)), action))
        elif spec.uses_types and not types:
            issues.append(PdaIssue(
                "warning", "PDA-A2", path,
                t("pda.val.needs_types", check=t(spec.label_key)), action))

        # -- A7 : valeurs dans un champ non supporte par le Check
        # (residus d'edition, jamais utilises par le jeu)
        if names and not spec.uses_names:
            issues.append(PdaIssue(
                "warning", "PDA-A7", path,
                t("pda.val.unused_names_field", check=t(spec.label_key)), action))
        if types and not spec.uses_types:
            issues.append(PdaIssue(
                "warning", "PDA-A7", path,
                t("pda.val.unused_types_field", check=t(spec.label_key)), action))
    return issues


# ------------------------------------------------------------------ chapitre

def validate_chapter(model, chapter, index: int,
                     chapter_tokens: set) -> List[PdaIssue]:
    """A4 (WhenRewarded sur le premier chapitre) + A5 (cibles de chainage)."""
    issues: List[PdaIssue] = []
    path = _chain(model, chapter)

    if _scalar(chapter, "Visibility") == "WhenRewarded" and index == 0:
        issues.append(PdaIssue(
            "error", "PDA-A4", path,
            t("pda.val.when_rewarded_first"), chapter))

    # A5 : les cibles de chainage doivent exister
    for key in ("ActivateChapterOnCompletion", "ActivateChapterOnSkip"):
        target = _scalar(chapter, key)
        if target and target not in chapter_tokens:
            issues.append(PdaIssue(
                "error", "PDA-A5", path,
                t("pda.val.chain_target_missing",
                  key=key, target=target), chapter))

    rewarded = _list_values(chapter, "RewardedChapters")
    for target in rewarded:
        if target and target not in chapter_tokens:
            issues.append(PdaIssue(
                "error", "PDA-A5", path,
                t("pda.val.chain_target_missing",
                  key="RewardedChapters", target=target), chapter))
    return issues


# ------------------------------------------------------------------ global

def _title_issues(model, title_key: str, entry: YamlEntry,
                  parent_chain: str = "") -> List[PdaIssue]:
    """A1 : titre depassant la limite du HUD (TaskTitle 26, ActionTitle 24)."""
    limit = TITLE_LIMITS.get(title_key)
    if limit is None:
        return []
    token = entry.value or ""
    visible = visible_len(model.csv_text(token, "English") or token)
    if visible <= limit:
        return []
    path = f"{parent_chain} > {visible}/{limit} {title_key}" \
        if parent_chain else f"{title_key} : {visible}/{limit}"
    return [PdaIssue(
        "warning", "PDA-A1", path,
        t("pda.val.title_over", key=title_key, n=visible, max=limit), entry)]


def validate_model(model) -> List[PdaIssue]:
    """Passe complete : chapitres -> taches -> actions + A6 (tokens CSV)."""
    issues: List[PdaIssue] = []
    chapters = model.chapters()
    chapter_tokens = {model.chapter_title_token(c) for c in chapters}
    chapter_tokens.discard("")

    for index, chapter in enumerate(chapters):
        issues.extend(validate_chapter(model, chapter, index, chapter_tokens))

        # -- A1 : titres trop longs (le HUD passe a la ligne au-dela)
        for task in model.tasks(chapter):
            for action in model.actions(task):
                issues.extend(validate_action(model, chapter, task, action))

    # -- A6 : jetons utilises absents du PDA.csv + jetons orphelins
    issues.extend(validate_csv_tokens(model))

    # Agr egation : un contenu reel contient des CENTAINES d'avertissements
    # du meme type (vecu 12/09/2026 : 862 actions sans CompletedMessage sur
    # la vanille, 242 jetons sur RE2) -- une ligne resume chacun, les cas
    # individuels restent disponibles via validate_action()/validate_csv_tokens().
    def _aggregate(code: str, msg_key: str, entries: List[PdaIssue]):
        if len(entries) <= 3:
            return
        issues[:] = [i for i in issues if i not in entries]
        issues.insert(0, PdaIssue("warning", code, "",
                                  t(msg_key, n=len(entries))))

    _aggregate("PDA-A2", "pda.val.no_completed_message.many",
               [i for i in issues if i.code == "PDA-A2"
                and i.severity == "warning"])
    a6 = [i for i in issues if i.code == "PDA-A6" and i.severity == "warning"]
    if len(a6) > 3:
        issues[:] = [i for i in issues if i not in a6]
        missing = sum(1 for i in a6 if "absent" in i.message
                      or "missing" in i.message.lower())
        orphans = len(a6) - missing
        parts = []
        if missing:
            parts.append(t("pda.val.tokens_missing_many", n=missing))
        if orphans:
            parts.append(t("pda.val.tokens_orphan_many", n=orphans))
        issues.insert(0, PdaIssue("warning", "PDA-A6", "",
                                  " ; ".join(parts)))
    return issues


def validate_csv_tokens(model) -> List[PdaIssue]:
    """A6 : tout jeton du YAML doit avoir sa ligne dans le PDA.csv ; tout
    jeton pda_* du CSV non reference dans le YAML est un orphelin.
    NB : collect_all_tokens() inclut les cles du CSV -- inutilisable ici,
    le cote YAML doit etre marche separement."""
    issues: List[PdaIssue] = []
    from core.pda.model import _TOKEN_RE, split_token_value
    used = set()

    def walk(nodes):
        for node in nodes:
            if isinstance(node, YamlEntry):
                if node.value:
                    _prefix, token = split_token_value(node.value)
                    if _TOKEN_RE.match(token):
                        used.add(token)
                walk(node.children)

    walk(model.yaml_doc.nodes)

    defined = set()
    if model.csv_doc is not None:
        for row in model.csv_doc.rows:
            if row and row[0].strip():
                defined.add(row[0].strip())
    for token in sorted(used - defined):
        issues.append(PdaIssue(
            "warning", "PDA-A6", token,
            t("pda.val.token_missing", token=token)))
    orphans = sorted(tok for tok in defined - used if _TOKEN_RE.match(tok))
    for token in orphans:
        issues.append(PdaIssue(
            "warning", "PDA-A6", token,
            t("pda.val.token_orphan", token=token)))
    return issues
