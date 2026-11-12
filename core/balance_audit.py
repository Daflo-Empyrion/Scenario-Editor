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

"""Correctifs de balance P1 (audit du 08/11, docs/audit_balance_re2fr.md) :
13 anomalies de dégâts/PV/XP de RE2-FR, chacune corrigée avec GARDE sur la
valeur actuelle (si le fichier ne correspond plus à l'état audité, la
correction est SAUTÉE avec la raison — jamais d'édition à l'aveugle).

Même contrat que core/ai_realism.py : dry-run par défaut, BackupStore avant
écriture, EOL préservé, chirurgie ECF en texte brut. Chaque correctif est
indépendant et réversible. Les valeurs cibles sont celles documentées dans
docs/audit_balance_re2fr.md (section P1) — modifier le doc ET le code
ensemble si un choix change.
"""
import re
from pathlib import Path

from core.ai_realism import (
    BackupStore, _set_in_span, child_span, entity_spans, read_text_raw,
    write_text_raw,
)

_HEADER_PATTERNS = {
    "Entity": r"\{ \+?Entity Name:\s*(\w+)",
    "Item": r"\{ \+?Item Id:\s*\d+,\s*Name:\s*(\w+)",
    "StatusEffect": r"\{ StatusEffect Name:\s*(\w+)",
    "DamageMultiplier": r"\{ \+?DamageMultiplier(?:Group)? Name:\s*(\w+)",
    "Block": r"\{ \+?(?:Block Id:\s*\d+,\s*|\s+)Name:\s*(\w+)",
}


def named_block_spans(text: str, kind: str) -> dict:
    """{nom: (start, end)} des blocs `{ <Kind> ... Name: X ... }`."""
    pat = re.compile(_HEADER_PATTERNS[kind])
    spans = {}
    for m in pat.finditer(text):
        depth = 0
        end = len(text)
        for mm in re.finditer(r"[{}]", text[m.start():]):
            depth += 1 if mm.group() == "{" else -1
            if depth == 0:
                end = m.start() + mm.end()
                break
        spans[m.group(1)] = (m.start(), end)
    return spans


def set_block_prop(text: str, kind: str, name: str, prop: str,
                   new_value: str, child: str | None = None):
    spans = named_block_spans(text, kind)
    if name not in spans:
        return text, 0
    s, e = spans[name]
    block = text[s:e]
    if child:
        inner = child_span(block, child)
        if not inner:
            return text, 0
        span = (s + inner[0], s + inner[1])
    else:
        span = (s, e)
    return _set_in_span(text, span, prop, new_value)


def block_body(text: str, kind: str, name: str) -> str:
    spans = named_block_spans(text, kind)
    if name not in spans:
        return ""
    s, e = spans[name]
    return text[s:e]


def _entity_body(text: str, name: str) -> str:
    spans = entity_spans(text)
    return text[spans[name][0]:spans[name][1]] if name in spans else ""


def _body_of(text: str, kind: str, name: str) -> str:
    return block_body(text, kind, name)


def _fix_ecf_prop(scenario: Path, relpath: str, kind: str, name: str,
                  prop: str, expected: str, new_value: str,
                  apply: bool = False, store=None, id_: str = "") -> dict:
    """Correctif générique avec double garde : bloc + valeur actuelle."""
    rep = {"id": id_ or f"{name}.{prop}", "edits": 0, "details": []}
    path = scenario / relpath
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    body = block_body(text, kind, name)
    if not body:
        rep["details"].append(f"{kind} « {name} » introuvable — sauté")
        return rep
    if f"{prop}: {expected}" not in body:
        rep["details"].append(
            f"garde non satisfaite (attendu « {prop}: {expected} ») — sauté")
        return rep
    new_text, k = set_block_prop(text, kind, name, prop, new_value)
    if not k:
        rep["details"].append("ligne non trouvée dans le bloc — sauté")
        return rep
    rep["edits"] = 1
    rep["details"].append(f"{prop}: {expected} -> {new_value}")
    if apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, new_text, eol)
    return rep


# ---------------------------------------------------------------------------
# Les 13 correctifs P1 (ordre du doc audit_balance_re2fr.md)
# ---------------------------------------------------------------------------

def fix_xp_heavy_minigun(scenario, apply=False, store=None) -> dict:
    """P1.1 : DroneBaseAttackHeavyMinigun XpFactor 69 -> 6 (farm d'XP)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/EClassConfig.ecf",
                         "Entity", "DroneBaseAttackHeavyMinigun",
                         "XpFactor", "69", "6", apply=apply, store=store,
                         id_="xp_heavy_minigun")


def fix_megalonops_melee(scenario, apply=False, store=None) -> dict:
    """P1.2 : MeleeMegalonopsGrey 550 -> 55 (proie qui one-shot le joueur)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "MeleeMegalonopsGrey",
                         "Damage", "550", "55", apply=apply, store=store,
                         id_="megalonops_melee")


def fix_dissolver_rof(scenario, apply=False, store=None) -> dict:
    """P1.3 : Eden_Dissolver_Weapon2 ROF 0,1 -> 1,0 (1250 -> 125 DPS)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "Eden_Dissolver_Weapon2",
                         "ROF", "0.1", "1.0", apply=apply, store=store,
                         id_="dissolver_rof")


def fix_abyssal_laser_ammo(scenario, apply=False, store=None) -> dict:
    """P1.4 : Eden_DroneAbyssalLaser_Ammo 1200 -> 400 (2857 -> ~950 DPS)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "Eden_DroneAbyssalLaser_Ammo",
                         "Damage", "1200", "400", apply=apply, store=store,
                         id_="abyssal_laser_ammo")


def fix_royal_commander_weapon(scenario, apply=False, store=None) -> dict:
    """P1.5 : Eden_RoyalZiraxCommander porte MinigunEpic du joueur (1053 DPS,
    sans multiplicateur Player) -> arme Zirax standard."""
    return _fix_ecf_prop(scenario, "Content/Configuration/EClassConfig.ecf",
                         "Entity", "Eden_RoyalZiraxCommander",
                         "ItemsOnEnterGame", "MinigunEpic", "ZiraxMinigunWeapon",
                         apply=apply, store=store,
                         id_="royal_commander_weapon")


INFECTED_EASY_HP = {
    "Eden_ZiraxInfectedGreenEasy": ("1000", "300"),
    "Eden_ZiraxInfectedRedEasy": ("1000", "400"),
    "Eden_ZiraxInfectedYellowEasy": ("1000", "450"),
    "Eden_ZiraxInfectedPurpleEasy": ("1000", "500"),
    "Eden_ZiraxInfectedCommanderEasy": ("2000", "550"),
}


def fix_infected_easy_hp(scenario, apply=False, store=None) -> dict:
    """P1.6 : infectés « Easy » plus solides que les normales."""
    rep = {"id": "infected_easy_hp", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/EClassConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, (expected, new_value) in INFECTED_EASY_HP.items():
        if f"MaxHealth: {expected}" not in _entity_body(text, name):
            rep["details"].append(f"{name} : garde non satisfaite — sauté")
            continue
        text, k = set_block_prop(text, "Entity", name, "MaxHealth", new_value)
        n += k
        rep["details"].append(f"{name}: {expected} -> {new_value}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_pirate_drones_hp(scenario, apply=False, store=None) -> dict:
    """P1.7 : PirateGatling/Rocket « en papier » 1500/2000 PV -> 8000."""
    rep = {"id": "pirate_drones_hp", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/EClassConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, (expected, new_value) in (
            ("Eden_SpaceDronePirateGatling", ("1500", "8000")),
            ("Eden_SpaceDronePirateRocket", ("2000", "8000"))):
        if f"MaxHealth: {expected}" not in _entity_body(text, name):
            rep["details"].append(f"{name} : garde non satisfaite — sauté")
            continue
        text, k = set_block_prop(text, "Entity", name, "MaxHealth", new_value)
        n += k
        rep["details"].append(f"{name}: {expected} -> {new_value}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_sentry2_rof(scenario, apply=False, store=None) -> dict:
    """P1.8 : Eden_AbyssalSentry2_Weapon ROF 8 -> 0,8 (faute de frappe probable)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "Eden_AbyssalSentry2_Weapon",
                         "ROF", "8", "0.8", apply=apply, store=store,
                         id_="sentry2_rof")


_PLASMA_MOD_EDITS = (
    ("Player.Skills['PlasmaT1AmmoDamage'] = 300",
     "Player.Skills['PlasmaT1AmmoDamage'] = 45"),
    ("Player.Skills['PlasmaT1AmmoBlastDamage'] = -300",
     "Player.Skills['PlasmaT1AmmoBlastDamage'] = -75"),
    ("Impact Damage +300 / Blast Damage -100%",
     "Impact Damage +45 / Blast Damage -25%"),
)


def fix_plasma_mod_dialogue(scenario, apply=False, store=None) -> dict:
    """P1.9 : mod +300 calibré pour le ScifiCannon (ROF 1,0) appliqué à une
    arme ROF 0,15 -> +45 / -25 % (le blast ne descend plus en négatif)."""
    rep = {"id": "plasma_mod_dialogue", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/Dialogues.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for old, new in _PLASMA_MOD_EDITS:
        if old not in text:
            rep["details"].append(f"garde non satisfaite : « {old[:44]}… » — sauté")
            continue
        text = text.replace(old, new, 1)
        n += 1
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_swarm_xp(scenario, apply=False, store=None) -> dict:
    """P1.10 : Eden_DroneBaySwarm_Drone 25 000 PV / XP 0 -> 15."""
    return _fix_ecf_prop(scenario, "Content/Configuration/EClassConfig.ecf",
                         "Entity", "Eden_DroneBaySwarm_Drone",
                         "XpFactor", "0", "15", apply=apply, store=store,
                         id_="swarm_xp")


ORPHAN_MATERIALS = (
    ("Material: MechArmored", "Material: Mechanical"),
    ("Material: DroneArmored", "Material: DronePlanet"),
    ("Material: HumanLight", "Material: HumanSoft"),
    ("Material: DroneLight", "Material: DronePlanet"),
)


def fix_orphan_materials(scenario, apply=False, store=None) -> dict:
    """P1.11 : matériaux absents de DamageMultiplierConfig -> les entités
    Abyssal ignoraient roquettes ×15 et laser ×8 (5-15× trop résistantes).
    Retour aux matériaux standards couverts."""
    rep = {"id": "orphan_materials", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/EClassConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for old, new in ORPHAN_MATERIALS:
        k = text.count(old)
        if k:
            text = text.replace(old, new)
            n += k
            rep["details"].append(f"{old.split(': ')[1]} -> "
                                  f"{new.split(': ')[1]} (×{k})")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_immunity_shield(scenario, apply=False, store=None) -> dict:
    """P1.12 : Eden_RegenerationImmunity 500 PV/0,1 s (5000 PV/s, enchaînable)
    -> 25 PV/0,5 s (50 PV/s, niveau des autres kits de régénération)."""
    rep = {"id": "immunity_shield", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/StatusEffects.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    body = block_body(text, "StatusEffect", "Eden_RegenerationImmunity")
    if "Amount: 500" not in body or "Rate: 0.1" not in body:
        rep["details"].append(
            "garde non satisfaite (attendu 500 @ 0,1 s) — sauté")
        return rep
    n = 0
    text, k = set_block_prop(text, "StatusEffect", "Eden_RegenerationImmunity",
                             "Amount", "25")
    n += k
    text, k = set_block_prop(text, "StatusEffect", "Eden_RegenerationImmunity",
                             "Rate", "0.5")
    n += k
    rep["edits"] = n
    rep["details"].append("500 PV/0,1 s -> 25 PV/0,5 s (50 PV/s)")
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_resurrected_floor(scenario, apply=False, store=None) -> dict:
    """P1.13 : Resurrected retire -300 de PV max (avec InfectedWound -200 :
    PV max 0) -> -100, dans le child Modify1 (health) uniquement."""
    rep = {"id": "resurrected_floor", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/StatusEffects.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    spans = named_block_spans(text, "StatusEffect")
    if "Resurrected" not in spans:
        rep["details"].append("bloc Resurrected introuvable — sauté")
        return rep
    s = spans["Resurrected"][0]
    block = text[spans["Resurrected"][0]:spans["Resurrected"][1]]
    inner = child_span(block, "Modify1")
    if inner is None or "Stat: health" not in block[inner[0]:inner[1]] \
            or "ModifyMaxValue: -300" not in block[inner[0]:inner[1]]:
        rep["details"].append(
            "garde non satisfaite (Modify1 health -300) — sauté")
        return rep
    span = (s + inner[0], s + inner[1])
    new_text, k = _set_in_span(text, span, "ModifyMaxValue", "-100")
    rep["edits"] = k
    rep["details"].append("ModifyMaxValue health : -300 -> -100")
    if k and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, new_text, eol)
    return rep




# ---------------------------------------------------------------------------
# P2 — progression et cohérence (choix de design validés le 08/11)
# ---------------------------------------------------------------------------

def add_block_lines(text: str, kind: str, name: str, lines: list):
    """Insère des lignes dans un bloc nommé (avant son '}' fermant) — pour
    les propriétés HÉRITÉES qui n'existent pas localement (ex: Armor des
    armures T2/Epic). Retourne (text, nb)."""
    spans = named_block_spans(text, kind)
    if name not in spans:
        return text, 0
    s, e = spans[name]
    block = text[s:e]
    m = re.search(r"(?m)^([ \t]+)\w+:", block)
    ind = m.group(1) if m else "  "
    add = "".join(f"{ind}{ln}\n" for ln in lines)
    close = block.rfind("}")
    block = block[:close] + add + block[close:]
    return text[:s] + block + text[e:], len(lines)


def fix_p2_weapons_progression(scenario, apply=False, store=None) -> dict:
    """P2.A : restaure la progression T1<T2<T3/Epic (inversions mesurées)."""
    rep = {"id": "p2_weapons_progression", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/ItemsConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, (expected, new_value) in (
            ("PistolT2", ("90", "120")),
            ("SubmachineGunT3", ("66", "80")),
            ("PulseRifleT3", ("100", "120")),
            ("Eden_ShotgunDouble", ("153", "110"))):
        if f"Damage: {expected}" not in block_body(text, "Item", name):
            rep["details"].append(f"{name} : garde non satisfaite — sauté")
            continue
        text, k = set_block_prop(text, "Item", name, "Damage", new_value)
        n += k
        rep["details"].append(f"{name}: {expected} -> {new_value}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_p2_minigun_t2_hard(scenario, apply=False, store=None) -> dict:
    """P2.A : MinigunEpic redevient > Minigun contre CreatureHard
    (DamageMultiplier_7 du groupe MinigunT2 : 0,80 -> 1,2 = valeur MinigunT1)."""
    rep = {"id": "p2_minigun_t2_hard", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/DamageMultiplierConfig.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    body = block_body(text, "DamageMultiplier", "MinigunT2")
    m = re.search(r"(DamageMultiplier_\d+: )0\.80(, param1: CreatureHard)", body)
    if not m:
        rep["details"].append("garde non satisfaite (0.80/CreatureHard) — sauté")
        return rep
    new_body = body[:m.start()] + m.group(1) + "1.2" + m.group(2) + body[m.end():]
    rep["edits"] = 1
    rep["details"].append("MinigunT2 CreatureHard : 0.80 -> 1.2")
    if apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text.replace(body, new_body, 1), eol)
    return rep


def fix_p2_titan_armor(scenario, apply=False, store=None) -> dict:
    """P2.B : ArmorCombat « Titan » 500 -> 650 (redevient le top tank)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "ArmorCombat", "Armor", "500", "650",
                         apply=apply, store=store, id_="p2_titan_armor")


def fix_p2_armor_t2(scenario, apply=False, store=None) -> dict:
    """P2.B : armures T2 reprennent +50 d'Armor sur le T1 (héritaient tout)."""
    rep = {"id": "p2_armor_t2", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/ItemsConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, armor in (("ArmorLightT2", "150"), ("ArmorMediumT2", "225"),
                        ("ArmorHeavyT2", "300")):
        body = block_body(text, "Item", name)
        if "Armor:" in body:
            rep["details"].append(f"{name} : Armor local déjà présent — sauté")
            continue
        text, k = add_block_lines(text, "Item", name,
                                  [f"Armor: {armor}, type: int, display: true"])
        if k:
            n += k
            rep["details"].append(f"{name}: +Armor {armor}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_p2_armor_epic(scenario, apply=False, store=None) -> dict:
    """P2.B : armures Epic reprennent +100 d'Armor sur le T1."""
    rep = {"id": "p2_armor_epic", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/ItemsConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, armor in (("ArmorLightEpic", "200"), ("ArmorMediumEpic", "300"),
                        ("ArmorHeavyEpic", "400")):
        body = block_body(text, "Item", name)
        if "Armor:" in body:
            rep["details"].append(f"{name} : Armor local déjà présent — sauté")
            continue
        text, k = add_block_lines(text, "Item", name,
                                  [f"Armor: {armor}, type: int, display: true"])
        if k:
            n += k
            rep["details"].append(f"{name}: +Armor {armor}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_p2_heal_food(scenario, apply=False, store=None) -> dict:
    """P2.C : soins spamables -> 75 PV par usage (BrafusFungi 481, Salad 150)."""
    rep = {"id": "p2_heal_food", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/ItemsConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, expected in (("BrafusFungi", "481"), ("Salad", "150")):
        if f"AddHealth: {expected}" not in block_body(text, "Item", name):
            rep["details"].append(f"{name} : garde non satisfaite — sauté")
            continue
        text, k = set_block_prop(text, "Item", name, "AddHealth", "75")
        n += k
        rep["details"].append(f"{name}: {expected} -> 75")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_p2_boss_weapons(scenario, apply=False, store=None) -> dict:
    """P2.D : boss à DPS de troupe -> armes réelles (Cultist 1 -> 60,
    Weston 15 -> 30)."""
    rep = {"id": "p2_boss_weapons", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/ItemsConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, (expected, new_value) in (
            ("Eden_CultistOverseer_Weapon", ("1", "60")),
            ("Eden_Weston_Weapon", ("15", "30"))):
        if f"Damage: {expected}" not in block_body(text, "Item", name):
            rep["details"].append(f"{name} : garde non satisfaite — sauté")
            continue
        text, k = set_block_prop(text, "Item", name, "Damage", new_value)
        n += k
        rep["details"].append(f"{name}: {expected} -> {new_value}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


P2_XP_COHERENCE = {
    "Eden_AssaultMechT2": ("35", "10"),
    "Eden_AbyssalAssaultMech": ("100", "20"),
    "LightBomberBase": ("15", "7.5"),
    "FastTransport": ("10", "2"),
    "Eden_AlienBugQueenStatic": ("25", "10"),
    "Eden_SpaceDroneLaserEasy": ("9", "6"),
}


def fix_p2_xp_coherence(scenario, apply=False, store=None) -> dict:
    """P2.E : XP alignée sur le danger (clones payés comme leur original)."""
    rep = {"id": "p2_xp_coherence", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/EClassConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, (expected, new_value) in P2_XP_COHERENCE.items():
        if f"XpFactor: {expected}" not in _entity_body(text, name):
            rep["details"].append(f"{name} : garde non satisfaite — sauté")
            continue
        text, k = set_block_prop(text, "Entity", name, "XpFactor", new_value)
        n += k
        rep["details"].append(f"{name}: {expected} -> {new_value}")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep

# ---------------------------------------------------------------------------
# P3 — vaisseau, tourelles de POI, FactionWarfare (audits du 08/11 soir)
# ---------------------------------------------------------------------------

def _group_span(text: str, group: str):
    m = re.search(r"\{ \+?DamageMultiplier(?:Group)? Name:\s*" + re.escape(group) + r"\b", text)
    if not m:
        return None
    depth = 0
    for mm in re.finditer(r"[{}]", text[m.start():]):
        depth += 1 if mm.group() == "{" else -1
        if depth == 0:
            return (m.start(), m.start() + mm.end())
    return None


def _set_shield_mult(scenario: Path, group: str, new_value: str,
                     apply: bool, store) -> dict:
    """Remplace la valeur de la ligne 'ShieldSmall|ShieldLarge|shield' d'un
    groupe de multiplicateurs (pas la ligne ShieldPlanet isolée)."""
    rep = {"id": f"shield.{group}", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/DamageMultiplierConfig.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    span = _group_span(text, group)
    if span is None:
        rep["details"].append("groupe introuvable — sauté")
        return rep
    block = text[span[0]:span[1]]
    target = None
    for mm in re.finditer(r"(?m)^([ \t]*)(DamageMultiplier_\d+: )[0-9.]+(, param1: [^\n]*)$", block):
        p1 = mm.group(3).lower()
        if "shieldsmall" in p1 or "|shield" in p1 or p1.endswith("shield"):
            if mm.group(0).split(",")[0].endswith(new_value):
                return rep  # déjà à la valeur cible
            target = mm
            break
    if target is None:
        rep["details"].append("ligne bouclier introuvable — sauté")
        return rep
    new_block = (block[:target.start()]
                 + f"{target.group(1)}{target.group(2)}{new_value}{target.group(3)}"
                 + block[target.end():])
    rep["edits"] = 1
    rep["details"].append(f"{group}: bouclier -> {new_value}")
    if apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text[:span[0]] + new_block + text[span[1]:], eol)
    return rep


def fix_s1_antishield_t1(scenario, apply=False, store=None) -> dict:
    """P3.S1 : le bouclier T1 est un mur (411 DPS anti-bouclier vs 20-40k).
    Monte les multiplicateurs bouclier des armes T1 (le plasma fixe, déjà à
    ×30 vs bouclier, reste inchangé)."""
    rep = {"id": "s1_antishield_t1", "edits": 0, "details": []}
    for group, new in (("CVGatlingTurretT1", "0.35"), ("CVCannonTurretT1", "0.45"),
                       ("CVLaserTurretT1", "0.75"), ("CVRocketTurretT1", "0.6"),
                       ("CVCannonT1", "0.45"), ("CVLaserCannonT1", "0.75"),
                       ("CVRailgunT1", "0.35"), ("SVGatlingGunT1", "0.35"),
                       ("SVRocketT1", "0.6"), ("SVRailgunT1", "0.35"),
                       ("SVLaserCannonT1", "0.75"), ("HVGatlingTurretT1", "0.35"),
                       ("HVRocketTurretT1", "0.6")):
        r = _set_shield_mult(scenario, group, new, apply, store)
        if r["edits"]:
            rep["edits"] += 1
            rep["details"].append(r["details"][0])
    return rep


def fix_s2_cutter_weapons(scenario, apply=False, store=None) -> dict:
    """P3.S2 : les groupes planétaires frappent les grands blocs (donc les CV)
    à ×2,25 — asymétrie ×10 mesurée face au « ×2 annoncé ». -> 1,5."""
    rep = {"id": "s2_cutter_weapons", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/DamageMultiplierConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for group in ("PlanetGatlingTurretT1", "PlanetRocketTurretT1",
                  "PlanetLaserTurretT1", "PlanetPlasmaTurretT1"):
        span = _group_span(text, group)
        if span is None:
            continue
        block = text[span[0]:span[1]]
        new_block, k = re.subn(r"2\.25(, param1: [^\n]*weaponlarge)",
                               r"1.5\1", block, count=1)
        if k:
            text = text[:span[0]] + new_block + text[span[1]:]
            n += 1
            rep["details"].append(f"{group}: 2.25 -> 1.5")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_t_purple_ammo(scenario, apply=False, store=None) -> dict:
    """P3.T1 : munition Purple 7 500 de blast -> 1 250 (11 688 -> 3 571 DPS,
    l'équivalent de Black)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "TurretEnemyLaserChargePurple",
                         "BlastDamage", "7500", "1250",
                         apply=apply, store=store, id_="t_purple_ammo")


def fix_t_t4_rof(scenario, apply=False, store=None) -> dict:
    """P3.T2 : ROF du T4 revenu à la valeur d'origine commentée (9 804 ->
    4 132 DPS)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/ItemsConfig.ecf",
                         "Item", "Eden_TurretAlienLaserT4_Weapon",
                         "ROF", "0.5", "1.2", apply=apply, store=store,
                         id_="t_t4_rof")


PLAYER_MULT_GROUPS = (
    "POILaserTurretT1", "POILaserTurretT2", "POIPlasmaTurretT1",
    "POIPlasmaTurretT2", "POIRocketTurretT1", "POIRocketTurretT2",
    "POIDisruptorTurret", "POILegacyMissile", "POILegacyLaser",
    "POIOrangeTurret", "EdenNovaPOI",
)


def fix_t_player_mults(scenario, apply=False, store=None) -> dict:
    """P3.T3 : les groupes de tourelles les plus forts frappent le joueur à
    100 % (les Gatling sont à ×0,5) -> aligne tout sur ×0,5."""
    rep = {"id": "t_player_mults", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/DamageMultiplierConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for group in PLAYER_MULT_GROUPS:
        span = _group_span(text, group)
        if span is None:
            continue
        block = text[span[0]:span[1]]
        if "param1: Player" in block:
            continue
        idx = max(int(x) for x in re.findall(r"DamageMultiplier_(\d+):", block))
        m = re.search(r"(?m)^([ \t]*)", block[block.find("\n") + 1:])
        ind = m.group(1) if m else "  "
        line = f"{ind}DamageMultiplier_{idx + 1}: 0.5, param1: Player\n"
        close = block.rfind("}")
        block = block[:close] + line + block[close:]
        text = text[:span[0]] + block + text[span[1]:]
        n += 1
        rep["details"].append(f"{group}: Player 0.5")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def _insert_block_line(text: str, name: str, line: str):
    """Insère une ligne de propriété dans un bloc Block nommé (avant son '}').
    Retourne (text, nb) — 0 si le bloc est introuvable."""
    spans = named_block_spans(text, "Block")
    if name not in spans:
        return text, 0
    s, e = spans[name]
    block = text[s:e]
    m = re.search(r"(?m)^([ \t]+)\w+:", block)
    ind = m.group(1) if m else "  "
    add = f"{ind}{line}\n"
    close = block.rfind("}")
    block = block[:close] + add + block[close:]
    return text[:s] + block + text[e:], 1


def _set_or_insert_block_prop(text: str, name: str, prop: str, new_value: str):
    """Modifie HitPoints/XpFactor/... d'un bloc Block ; si la propriété
    n'existe pas localement (héritage Ref), l'insère."""
    new_text, k = set_block_prop(text, "Block", name, prop, new_value)
    if k:
        return new_text, k
    # HitPoints/Armor sont lus en int par le moteur : sans 'type: int',
    # la valeur reste DataItem<string> -> 'Error converting' + valeur ignorée.
    suffix = ", type: int" if prop in ("HitPoints", "Armor") else ""
    return _insert_block_line(new_text, name, f"{prop}: {new_value}{suffix}")


def fix_t_raider_ladder(scenario, apply=False, store=None) -> dict:
    """P3.T4 : Raider T1=T2=T3 (25 000 PV, ~660 DPS) -> vraie progression.
    Les PV sont HÉRITÉS du parent (BC:57976) : insertion de lignes locales."""
    rep = {"id": "t_raider_ladder", "edits": 0, "details": []}
    bpath = scenario / "Content/Configuration/BlocksConfig.ecf"
    path_ItemsConfig = scenario / "Content/Configuration/ItemsConfig.ecf"
    if not bpath.exists() or not path_ItemsConfig.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(bpath)
    itext, ieol = read_text_raw(path_ItemsConfig)
    n = 0
    for block_name, hp in (("Eden_TurretRaiderLaserT2", "37500"),
                           ("Eden_TurretRaiderLaserT3", "50000")):
        text, k = _set_or_insert_block_prop(text, block_name, "HitPoints", hp)
        n += k
    for item_name, dmg in (("Eden_TurretRaiderLaserT2_Weapon", "500"),
                           ("Eden_TurretRaiderLaserT3_Weapon", "1000")):
        if f"Damage: {dmg}" in _body_of(itext, "Item", item_name):
            continue
        itext, k = set_block_prop(itext, "Item", item_name, "Damage", dmg)
        n += k
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(bpath)
            store.snapshot(path_ItemsConfig)
        write_text_raw(bpath, text, eol)
        write_text_raw(path_ItemsConfig, itext, ieol)
    return rep


def fix_t_boss_weapons(scenario, apply=False, store=None) -> dict:
    """P3.T5 : armes de boss invulnérables (matériau Foundation = ×0 partout,
    11-50 PV) -> BossLegacy/BossMetal + vrais PV."""
    rep = {"id": "t_boss_weapons", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/BlocksConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name, material, hp in (
            ("ProtoInfectorWeaponLaser", "BossLegacy", "2500"),
            ("RocketBossGun", "BossMetal", "5000"),
            ("LaserBossGun", "BossMetal", "5000")):
        text, k = set_block_prop(text, "Block", name, "Material", material)
        n += k
        text, k2 = set_block_prop(text, "Block", name, "HitPoints", hp)
        n += k2
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_t_plasma_exploit(scenario, apply=False, store=None) -> dict:
    """P3.T6 : Eden_TurretPlasmaSmall est ramassable et rend une tourelle
    joueur (TurretBaseLaserBlocks) -> rend une épave, XP 10 -> 2."""
    rep = {"id": "t_plasma_exploit", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/BlocksConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    if "Name: Eden_SalvageTurretEnergy" not in text:
        rep["details"].append("Eden_SalvageTurretEnergy introuvable — sauté")
        return rep
    n = 0
    for prop_name in ("PickupTarget", "TemplateRoot"):
        text, k = set_block_prop(text, "Block", "Eden_TurretPlasmaSmall",
                                 prop_name, "Eden_SalvageTurretEnergy")
        n += k
    text, k = set_block_prop(text, "Block", "Eden_TurretPlasmaSmall",
                             "XpFactor", "2")
    n += k
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_t_colored_hp(scenario, apply=False, store=None) -> dict:
    """P3.T7 : les T3 colorées héritent 35 000 PV du Disruptor (< T2 50 000)
    -> 50 000 sur le parent TurretLegacyDisruptor (élève les 7 colorées)."""
    return _fix_ecf_prop(scenario, "Content/Configuration/BlocksConfig.ecf",
                         "Block", "TurretLegacyDisruptor",
                         "HitPoints", "35000", "50000",
                         apply=apply, store=store, id_="t_colored_hp")


def fix_t_yellow_hp(scenario, apply=False, store=None) -> dict:
    """P3.T8 : TurretEnemyYellow 35 000 PV pour 296 DPS -> 25 000."""
    return _fix_ecf_prop(scenario, "Content/Configuration/BlocksConfig.ecf",
                         "Block", "TurretEnemyYellow",
                         "HitPoints", "35000", "25000",
                         apply=apply, store=store, id_="t_yellow_hp")


def fix_t_xp_boss(scenario, apply=False, store=None) -> dict:
    """P3.T9 : Purple et T4 (3 500-9 800 DPS) valent XP 2 comme une T1 -> 15."""
    rep = {"id": "t_xp_boss", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/BlocksConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    n = 0
    for name in ("TurretEnemyPurple", "Eden_TurretAlienLaserT4"):
        if "XpFactor: 15" in _body_of(text, "Block", name):
            continue
        text, k = _set_or_insert_block_prop(text, name, "XpFactor", "15")
        n += k
        rep["details"].append(f"{name}: XP 15" if k else f"{name} : sauté")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


TURRET_ALIASES = (
    ("TurretBABeamLaser", "TurretBAPulseLaserT2"),
    ("TurretBaseFlakT2", "TurretBAFlakT2"),
    ("TurretBasePulseLaserT2", "TurretBAPulseLaserT2"),
    ("TurretBaseRocketT2", "TurretBARocketT2"),
    ("TurretBaseArtilleryT2", "TurretBaseArtillery"),
    ("TurretAlien", "TurretLegacyDisruptor"),
    ("TurretPulsarAlien", "TurretEnemyCyan"),
)


def fix_t_turret_aliases(scenario, apply=False, store=None) -> dict:
    """P3.T10 : 82+38+31... playfields placent des tourelles dont le nom
    n'existe pas dans BlocksConfig (blocs ignorés au chargement, POI
    désarmés) -> blocs alias vers les tourelles existantes. À confirmer en
    jeu (log IdMapping)."""
    rep = {"id": "t_turret_aliases", "edits": 0, "files": 0, "details": []}
    path = scenario / "Content/Configuration/BlocksConfig.ecf"
    text, eol = read_text_raw(path)
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    existing = set(re.findall(r"\{ \+?Block(?: Id:\s*\d+,\s*|\s+)Name:\s*(\w+)", text))
    added = []
    for alias, target in TURRET_ALIASES:
        if alias in existing:
            continue
        if target not in existing:
            rep["details"].append(f"{alias} : cible {target} absente — sauté")
            continue
        # ECF : '{' et '}' sur une même ligne = ligne malformée
        text += f"{{ Block Name: {alias}, Ref: {target}{eol}}}{eol}{eol}"
        added.append(alias)
    rep["edits"] = len(added)
    if added:
        rep["details"].insert(0, "alias : " + ", ".join(added))
        rep["files"] = 1
        if apply:
            if store:
                store.snapshot(path)
            write_text_raw(path, text, eol)
    return rep


def fix_fw_scaling(scenario, apply=False, store=None) -> dict:
    """P3.F1 : les vagues d'attaque ne montent jamais (295/333 playfields
    bloqués [1,2], prix 15-35) -> multiplicateur vanille 0,1 et prix de
    départ 25-40 : Surv3/Surv6 redeviennent atteignables sur les planètes
    difficiles."""
    rep = {"id": "fw_scaling", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/FactionWarfare.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    n = 0
    for old, new in (
            ("TargetBaseStrengthToPriceMultiplier: 0.025",
             "TargetBaseStrengthToPriceMultiplier: 0.1"),
            ("PlayFieldLvl1Min:15", "PlayFieldLvl1Min:25"),
            ("PlayFieldLvl1Max:30", "PlayFieldLvl1Max:40")):
        if old in text:
            text = text.replace(old, new, 1)
            n += 1
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_fw_reputation(scenario, apply=False, store=None) -> dict:
    """P3.F2 : la réputation n'a aucun effet (72 h à rep0 ET rep max) ->
    24 h à rep 0, 96 h à rep max (sémantique vanille)."""
    rep = {"id": "fw_reputation", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/FactionWarfare.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    n1 = text.count("HoursAtRep0: 72")
    text = text.replace("HoursAtRep0: 72", "HoursAtRep0: 24")
    n2 = text.count("HoursAtRepMax: 72")
    text = text.replace("HoursAtRepMax: 72", "HoursAtRepMax: 96")
    rep["edits"] = n1 + n2
    rep["details"].append(f"Rep0 ×{n1}, RepMax ×{n2}")
    if rep["edits"] and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_fw_talon_prices(scenario, apply=False, store=None) -> dict:
    """P3.F3 : Talon3 demande 800-1 200 points, jamais atteignable (plafond
    des scénarios ~120) -> 40/60/150/200 (proche vanille)."""
    rep = {"id": "fw_talon_prices", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/FactionWarfare.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    n = 0
    for old, new in (("Lvl1MinPrice:80", "Lvl1MinPrice:40"),
                     ("Lvl1MaxPrice:120", "Lvl1MaxPrice:60"),
                     ("Lvl10MinPrice:800", "Lvl10MinPrice:150"),
                     ("Lvl10MaxPrice:1200", "Lvl10MaxPrice:200")):
        if old in text:
            text = text.replace(old, new, 1)
            n += 1
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_fw_space_defense(scenario, apply=False, store=None) -> dict:
    """P3.F4 : défense spatiale Zirax à 5 points (3 drones de 10 000 PV pour
    presque rien) -> 20 ; transports hérités à 1+1 -> 24+2,5."""
    rep = {"id": "fw_space_defense", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/FactionWarfare.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    n = 0
    # drones Zirax de défense spatiale : replacement par ClassName (espacement
    # libre, pas de hard-coding)
    def _drone_sub(m):
        nonlocal n
        n += 1
        return m.group(1) + "20"
    text = re.sub(
        r"((?:ClassName: DroneSpaceZirax(?:Laser|Rocket|Plasma)[\s\S]*?"
        r"CommandPointsLvl1: )5)(?=\s)",
        _drone_sub, text)
    # transports hérités : exact "\n" pour éviter les faux positifs
    cnt = text.count("CommandPointsLvl1: 1" + chr(10))
    if cnt:
        text = text.replace("CommandPointsLvl1: 1" + chr(10),
                            "CommandPointsLvl1: 24" + chr(10))
        n += cnt
    rep["edits"] = n
    rep["details"].append(f"drones ×{n}, transports ×{cnt}")
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


def fix_fw_dead_categories(scenario, apply=False, store=None) -> dict:
    """P3.F5 : 11 scénarios BALevel* citent la catégorie inexistante
    DroneBaseAttackHeavyMinigun -> DroneHeavyMinigunSurv (déclarée FW:260)."""
    rep = {"id": "fw_dead_categories", "edits": 0, "details": []}
    path = scenario / "Content/Configuration/FactionWarfare.ecf"
    if not path.exists():
        rep["details"].append("fichier absent")
        return rep
    text, eol = read_text_raw(path)
    n = text.count("Category: DroneBaseAttackHeavyMinigun")
    if n:
        text = text.replace("Category: DroneBaseAttackHeavyMinigun",
                            "Category: DroneHeavyMinigunSurv")
    rep["edits"] = n
    if n and apply:
        if store:
            store.snapshot(path)
        write_text_raw(path, text, eol)
    return rep


EASY_MOON_PFS = ("EdenMoonIce2", "EdenMoonIceOuter", "EdenMoonIceOuter2",
                 "EdenMoonIceOuter3", "EdenMoonIceOuter4", "MoonIce",
                 "MoonIce2", "StarterRandom_IceMoon",
                 "StarterRandom_MoonIce2")


def fix_easy_moon_patrol(scenario, apply=False, store=None) -> dict:
    """P3.G1 : la patrouille ZiraxMechanoidPatrol (AssaultMech 7 000 PV)
    tombe sur 9 lunes tier early où le joueur n'a que du T1 (~24 s de tir
    par AssaultMech) -> groupe Easy (Mechanoid seul) sur ces lunes."""
    rep = {"id": "easy_moon_patrol", "edits": 0, "files": 0, "details": []}
    gpath = scenario / "Content/Configuration/EGroupsConfig.ecf"
    text, eol_g = read_text_raw(gpath)
    if "ZiraxMechanoidPatrolEasy" not in text:
        text += ("{ EGroup Name: ZiraxMechanoidPatrolEasy" + "\n"
                 '  Mechanoid: "3, 5"' + "\n}" + "\n\n")
        rep["edits"] += 1
        rep["details"].append("EGroups + ZiraxMechanoidPatrolEasy")
        if apply:
            if store:
                store.snapshot(gpath)
            gpath.write_bytes(text.encode("utf-8"))
    n = 0
    for pfname in EASY_MOON_PFS:
        pf = scenario / "Playfields" / pfname / "playfield_static.yaml"
        if not pf.exists():
            continue
        ptext, peol = read_text_raw(pf)
        if "ZiraxMechanoidPatrolEasy" in ptext:
            continue  # déjà remplacé
        if "ZiraxMechanoidPatrol" in ptext:
            ptext = ptext.replace("ZiraxMechanoidPatrol",
                                  "ZiraxMechanoidPatrolEasy")
            n += 1
            if apply:
                if store:
                    store.snapshot(pf)
                pf.write_bytes(ptext.encode("utf-8"))
    if n:
        rep["files"] = rep.get("files", 0) + n
        rep["edits"] += n
        rep["details"].append(f"{n} lunes tier early -> patrouille Easy")
    return rep


ALL_BALANCE_FIXES = {
    "xp_heavy_minigun": fix_xp_heavy_minigun,
    "megalonops_melee": fix_megalonops_melee,
    "dissolver_rof": fix_dissolver_rof,
    "abyssal_laser_ammo": fix_abyssal_laser_ammo,
    "royal_commander_weapon": fix_royal_commander_weapon,
    "infected_easy_hp": fix_infected_easy_hp,
    "pirate_drones_hp": fix_pirate_drones_hp,
    "sentry2_rof": fix_sentry2_rof,
    "plasma_mod_dialogue": fix_plasma_mod_dialogue,
    "swarm_xp": fix_swarm_xp,
    "orphan_materials": fix_orphan_materials,
    "immunity_shield": fix_immunity_shield,
    "resurrected_floor": fix_resurrected_floor,
    # --- P3 (vaisseau / tourelles / FactionWarfare, audits du 08/11 soir) ---
    "s1_antishield_t1": fix_s1_antishield_t1,
    "s2_cutter_weapons": fix_s2_cutter_weapons,
    "t_purple_ammo": fix_t_purple_ammo,
    "t_t4_rof": fix_t_t4_rof,
    "t_player_mults": fix_t_player_mults,
    "t_raider_ladder": fix_t_raider_ladder,
    "t_boss_weapons": fix_t_boss_weapons,
    "t_plasma_exploit": fix_t_plasma_exploit,
    "t_colored_hp": fix_t_colored_hp,
    "t_yellow_hp": fix_t_yellow_hp,
    "t_xp_boss": fix_t_xp_boss,
    "t_turret_aliases": fix_t_turret_aliases,
    "fw_scaling": fix_fw_scaling,
    "fw_reputation": fix_fw_reputation,
    "fw_talon_prices": fix_fw_talon_prices,
    "fw_space_defense": fix_fw_space_defense,
    "fw_dead_categories": fix_fw_dead_categories,
    "easy_moon_patrol": fix_easy_moon_patrol,
    # --- P2 (choix de design validés par l'utilisateur le 08/11) ---
    "p2_weapons_progression": fix_p2_weapons_progression,
    "p2_minigun_t2_hard": fix_p2_minigun_t2_hard,
    "p2_titan_armor": fix_p2_titan_armor,
    "p2_armor_t2": fix_p2_armor_t2,
    "p2_armor_epic": fix_p2_armor_epic,
    "p2_heal_food": fix_p2_heal_food,
    "p2_boss_weapons": fix_p2_boss_weapons,
    "p2_xp_coherence": fix_p2_xp_coherence,
}


def run_balance_fixes(scenario: Path, names: list, apply: bool = False) -> list:
    store = BackupStore(scenario) if apply else None
    return [ALL_BALANCE_FIXES[name](scenario, apply=apply, store=store)
            for name in names]
