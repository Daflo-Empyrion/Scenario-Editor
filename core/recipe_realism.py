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

"""Recettes realistes (Templates*.ecf) : la COMPOSITION vient du reel, les
quantites de la masse physique de l'objet (docs/recettes_realistes.md).

LOT 1 = LECTURE SEULE : ce module propose, il n'ecrit rien. L'ecriture
(arrondis entiers, CraftTime, backup) reutilisera
`core.recipe_balance.apply_proposals`.

Doctrine (06/11/2026) :
  - masse cible = `Mass` du jeu (pas la masse physique reelle : celles du
    jeu pilotent transferts et gravite), multipliee par un rendement ;
  - repartition = composition reelle de la classe, exprimee en part de
    masse, resolue vers les composants du jeu ;
  - GRANULARITE : un composant dont la masse unitaire depasse la part est
    ecarte (22 kg de cuivre ne s'ecrit pas "1 PowerCoil" de 185 kg) ;
  - cout libre : rien ne preserve le cout actuel de l'auteur ;
  - idempotence : la cible ne depend jamais de la recette courante.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from core.recipe_balance import RecipeIndex, load_recipe_index

# ------------------------------------------------------------- table reelle
# Chaines FINE -> GROSSIERE : le calcul retient le composant le plus grossier
# dont la masse unitaire tient dans la part, sinon le plus fin (docs §3).
MATERIALS: Dict[str, Tuple[str, ...]] = {
    # Un maillon grossier doit etre la MEME matiere en vrac, pas un autre
    # produit : SteelPlateArmored est une plaque blindee, pas de l'acier en
    # gros (vecu lot 1 : il captait toutes les parts d'acier).
    "ACIER": ("IronIngot", "SteelPlate"),
    "CUIVRE": ("CopperIngot",),
    "ALU": ("AluminiumPowder", "AluminiumCoil"),
    "VERRE": ("GlassPlate",),
    "PLASTIQUE": ("PlasticMaterial",),
    "ELEC": ("Electronics",),
    "MOTEUR": ("Motor",),
    "MECA": ("MechanicalComponents",),
    "BOBINE": ("FluxCoil", "PowerCoil"),
    "SILICIUM": ("SiliconIngot",),
    "TITANE": ("TitanRods", "TitanPlates"),
    "NANO": ("Nanotubes",),
    "AIMANT": ("NeodymiumIngot",),
    "CAPA": ("CapacitorComponent",),
    "SUPRA": ("Superconductor",),
    "QUANT": ("QuantumProcessor",),
    "OR": ("GoldIngot",),
    "CHIMIE": ("NCPowder", "MagnesiumPowder", "Chemicals"),
    "ENGRAIS": ("Fertilizer",),
    "EAU": ("WaterBottle", "WaterJug"),
}

# Part de masse par classe. `src` documente la provenance dans
# docs/recettes_realistes.md §4 : 'source', 'estimation', 'extrapole'.
@dataclass(frozen=True)
class Klass:
    code: str
    parts: Tuple[Tuple[str, float], ...]
    waste: float          # masse_ingredients / masse_produite
    sec_per_kg: float     # CraftTime
    src: str


CLASSES: Dict[str, Klass] = {
    "GENERATOR": Klass("GENERATOR", (("ACIER", 55), ("MOTEUR", 18),
                                    ("ELEC", 12), ("MECA", 8), ("BOBINE", 7)),
                       1.25, 0.5, "source"),
    "SOLAR": Klass("SOLAR", (("VERRE", 50), ("PLASTIQUE", 30), ("ALU", 10),
                             ("SILICIUM", 6), ("ELEC", 4)),
                   1.30, 0.5, "source"),
    "THRUSTER": Klass("THRUSTER", (("TITANE", 45), ("ACIER", 20),
                                   ("CUIVRE", 10), ("MOTEUR", 15),
                                   ("NANO", 5), ("ELEC", 5)),
                      1.30, 0.5, "source"),
    "MOTOR": Klass("MOTOR", (("ACIER", 50), ("ALU", 15), ("CUIVRE", 12),
                             ("MOTEUR", 15), ("AIMANT", 5),
                             ("PLASTIQUE", 3)),
                  1.25, 0.8, "source"),
    "SHIELD": Klass("SHIELD", (("CUIVRE", 30), ("BOBINE", 25), ("ELEC", 15),
                               ("ACIER", 15), ("CAPA", 10), ("VERRE", 5)),
                    1.50, 1.0, "estimation"),
    "WARP": Klass("WARP", (("SUPRA", 30), ("QUANT", 20), ("TITANE", 20),
                           ("BOBINE", 15), ("ELEC", 15)),
                  1.50, 1.0, "extrapole"),
    "CONTAINER": Klass("CONTAINER", (("ACIER", 70), ("PLASTIQUE", 15),
                                     ("MECA", 15)),
                       1.10, 0.05, "estimation"),
    "FUELTANK": Klass("FUELTANK", (("ACIER", 75), ("ALU", 10),
                                   ("PLASTIQUE", 10), ("MECA", 5)),
                      1.10, 0.05, "estimation"),
    "CORE": Klass("CORE", (("ELEC", 30), ("Electronics", 25), ("ACIER", 20),
                           ("CAPA", 15), ("NANO", 10)),
                  1.50, 5.0, "estimation"),
    "CONSTRUCTOR": Klass("CONSTRUCTOR", (("ACIER", 55), ("MOTEUR", 15),
                                         ("MECA", 15), ("ELEC", 10),
                                         ("Computer", 5)),
                         1.30, 0.5, "estimation"),
    "LIGHT": Klass("LIGHT", (("VERRE", 40), ("PLASTIQUE", 35),
                             ("ELEC", 15), ("OpticalFiber", 10)),
                   1.50, 5.0, "estimation"),
    "DOOR": Klass("DOOR", (("ACIER", 65), ("MECA", 20), ("MOTEUR", 10),
                           ("ELEC", 5)),
                  1.10, 0.05, "estimation"),
    "FIREARM": Klass("FIREARM", (("ACIER", 45), ("ALU", 25),
                                 ("PLASTIQUE", 20), ("MECA", 10)),
                     1.30, 2.0, "estimation"),
    "TOOL": Klass("TOOL", (("ACIER", 60), ("PLASTIQUE", 25),
                           ("ELEC", 15)),
                  1.30, 2.0, "estimation"),
    "AMMO": Klass("AMMO", (("CUIVRE", 50), ("ACIER", 30), ("CHIMIE", 20)),
                  1.05, 2.0, "estimation"),
    "MEDICAL": Klass("MEDICAL", (("CHIMIE", 50), ("PLASTIQUE", 30),
                                 ("VERRE", 20)),
                     1.20, 10.0, "estimation"),
    "FOOD": Klass("FOOD", (("CHIMIE", 40), ("PLASTIQUE", 30),
                           ("EAU", 30)),
                  1.20, 10.0, "estimation"),
    "UPGRADEKIT": Klass("UPGRADEKIT", (("ELEC", 30), ("Electronics", 30),
                                       ("CUIVRE", 20), ("OR", 10),
                                       ("ACIER", 10)),
                       1.50, 5.0, "estimation"),
    "PLANT": Klass("PLANT", (("ENGRAIS", 40), ("PLASTIQUE", 30),
                             ("ACIER", 20), ("EAU", 10)),
                   1.20, 10.0, "estimation"),
    "STRUCTURE": Klass("STRUCTURE", (("ACIER", 90), ("PLASTIQUE", 10)),
                       1.10, 0.05, "estimation"),
    "GENERIC_DEVICE": Klass("GENERIC_DEVICE", (("ACIER", 50), ("ELEC", 25),
                                               ("MECA", 25)),
                            1.30, 0.5, "estimation"),
}

# IndexName (blocs) -> classe. Absent = repli par Category, puis GENERIC_DEVICE.
INDEXNAME_CLASS: Dict[str, str] = {
    "Generator": "GENERATOR", "SolarPanel": "SOLAR", "Thruster": "THRUSTER",
    "Turbine": "THRUSTER", "RCS": "MOTOR", "ShieldGenerator": "SHIELD",
    "ShieldBooster": "SHIELD", "WarpDrive": "WARP", "Teleporter": "WARP",
    "Container": "CONTAINER", "AmmoCntr": "CONTAINER",
    "HarvestCntr": "CONTAINER", "Fridge": "CONTAINER",
    "FuelTank": "FUELTANK", "WarpDriveTank": "FUELTANK",
    "O2Tank": "FUELTANK", "Core": "CORE", "Constructor": "CONSTRUCTOR",
    "Light": "LIGHT", "LCD": "LIGHT", "Door": "DOOR",
    "LandingGear": "DOOR", "Gravity": "DOOR", "WeaponShip": "FIREARM",
    "Turret": "FIREARM", "Plant": "PLANT", "Cockpit": "GENERIC_DEVICE",
}

CATEGORY_CLASS: Dict[str, str] = {
    "Food": "FOOD", "Medical": "MEDICAL", "Farming": "PLANT",
    "Devices": "GENERIC_DEVICE", "BuildingBlocks": "STRUCTURE",
    "Deco Blocks": "STRUCTURE",
}

# Tokens de nom pour les items sans IndexName (Category Weapons/Items).
_NAME_CLASS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("rifle", "pistol", "shotgun", "sniper", "minigun", "launcher",
      "submachine", "cannon", "turret", "railgun", "laser"), "FIREARM"),
    (("ammo", "projectile", "rocket", "missile", "grenade"), "AMMO"),
    (("medikit", "injection", "pills", "ointment", "bandage", "stimulant",
      "serum"), "MEDICAL"),
    (("kit",), "UPGRADEKIT"),
    (("drill", "multi", "weld", "tool", "miner"), "TOOL"),
)

# Objets SANS Category ni IndexName : mesures du 06/11 sur RE2-FR (140
# templates, dont 53 `Eden_*`). Regles par token de nom, premier match gagne.
TOKEN_CLASS: Tuple[Tuple[str, str], ...] = (
    ("shieldgenerator", "SHIELD"),          # avant 'generator'
    ("turret", "FIREARM"),
    ("bullet", "AMMO"), ("slammer", "AMMO"),
    ("generator", "GENERATOR"),
    ("thruster", "THRUSTER"), ("hoverengine", "THRUSTER"),
    ("fueltank", "FUELTANK"), ("container", "CONTAINER"),
    ("repairbay", "CONSTRUCTOR"), ("constructor", "CONSTRUCTOR"),
    ("landing", "DOOR"), ("stairs", "STRUCTURE"),
    ("stage1", "PLANT"), ("plantdead", "PLANT"), ("growingpot", "PLANT"),
    ("wine", "FOOD"), ("cake", "FOOD"), ("steak", "FOOD"), ("salt", "FOOD"),
    ("vodka", "FOOD"), ("moonshine", "FOOD"), ("assassin", "FOOD"),
    ("gaussrail", "FIREARM"), ("weapon", "FIREARM"),
    ("device", "GENERIC_DEVICE"), ("dronebay", "GENERIC_DEVICE"),
    ("dockingpad", "GENERIC_DEVICE"), ("detector", "GENERIC_DEVICE"),
    ("builder", "GENERIC_DEVICE"), ("regulator", "GENERIC_DEVICE"),
)

# Ecartes explicitement, avec leur raison (jamais de silence).
SKIP_TOKENS: Tuple[Tuple[str, str], ...] = (
    ("ore", "matiere premiere (minerai)"),
    ("ice", "matiere premiere (glace)"),
    ("slag", "matiere premiere (residu)"),
    ("salvage", "matiere premiere (recyclage)"),
    ("dust", "matiere premiere (poudre)"),
    ("crystal", "matiere premiere (cristal)"),
    ("diamond", "matiere premiere (gemme)"),
    ("gel", "matiere premiere (gel)"),
    ("pellet", "matiere premiere (granule)"),
    ("deuterium", "matiere premiere (carburant)"),
    ("fuel", "matiere premiere (carburant)"),
    ("ingot", "metallurgie (docs §4.3)"),
    ("alloy", "metallurgie (docs §4.3)"),
    ("plate", "composant : sa recette est la matiere (docs §4.5)"),
    ("coil", "composant : sa recette est la matiere (docs §4.5)"),
    ("electromagnet", "composant : sa recette est la matiere (docs §4.5)"),
    ("semiconductor", "composant : sa recette est la matiere (docs §4.5)"),
    ("component", "composant : sa recette est la matiere (docs §4.5)"),
    ("electronics", "composant : sa recette est la matiere (docs §4.5)"),
    ("oscillator", "composant : sa recette est la matiere (docs §4.5)"),
    ("computer", "composant : sa recette est la matiere (docs §4.5)"),
    ("motor", "composant : sa recette est la matiere (docs §4.5)"),
    ("cell", "composant : sa recette est la matiere (docs §4.5)"),
    ("matrix", "composant : sa recette est la matiere (docs §4.5)"),
    ("nanotube", "composant : sa recette est la matiere (docs §4.5)"),
    ("fiber", "composant : sa recette est la matiere (docs §4.5)"),
    ("ounce", "composant : sa recette est la matiere (docs §4.5)"),
    ("cement", "composant : sa recette est la matiere (docs §4.5)"),
    ("insulation", "composant : sa recette est la matiere (docs §4.5)"),
    ("bottle", "contenant (gaz) : hors composition"),
    ("marker", "bloc technique du moteur"),
    ("broken", "objet endommage (reparation, pas fabrication)"),
    ("coins", "monnaie"),
    ("toxicwaste", "residu, hors fabrication"),
    ("techtree", "marqueur d'arbre technologique"),
    ("chest", "decor / butin"),
)

# ------------------------------------------------- passe des COMPOSANTS
# Un composant n'a pas de composant en dessous : sa recette EST la matiere.
# Cible = OutputCount x Mass(composant) x rendement (15 des 31 sont en LOT :
# une passe produit 10 plaques, les quantites se calculent par lot).
# `parts=None` = garder la composition de l'auteur et la remettre a l'echelle
# de la masse (matieres fictives : Eden, cellules plasma, fusion).
@dataclass(frozen=True)
class CompRule:
    parts: Optional[Tuple[Tuple[str, float], ...]]
    waste: float
    src: str


COMPONENTS: Dict[str, CompRule] = {
    # metaux et plaques : coulee/laminage, rendement faible
    "SteelPlate": CompRule((("IronIngot", 98), ("Graphite", 2)),
                           1.05, "estimation"),
    "TitanPlates": CompRule((("TitanRods", 100),), 1.05, "estimation"),
    "GlassPlate": CompRule((("SILICIUM", 70), ("RockDust", 30)),
                           1.05, "estimation"),
    "AluminiumCoil": CompRule((("AluminiumPowder", 100),), 1.05, "estimation"),
    "Cement": CompRule((("RockDust", 70), ("CrushedStone", 30)),
                       1.05, "estimation"),
    "CobaltAlloy": CompRule((("CobaltIngot", 80), ("IronIngot", 20)),
                            1.05, "estimation"),
    "ZascosiumAlloy": CompRule((("ZascosiumIngot", 60),
                                ("ErestrumIngot", 40)), 1.05, "estimation"),
    "PlatinOunce": CompRule((("PlatinBar", 100),), 1.02, "estimation"),
    # machine electrique : acier 50, alu 32, cuivre 12, aimants 3 (ReFreeDrive)
    "Motor": CompRule((("ACIER", 50), ("ALU", 30), ("CUIVRE", 12),
                       ("AIMANT", 4), ("PLASTIQUE", 4)), 1.30, "source"),
    "FluxCoil": CompRule((("CUIVRE", 70), ("ACIER", 30)), 1.10,
                         "estimation"),
    "PowerCoil": CompRule((("ACIER", 50), ("CUIVRE", 40), ("ELEC", 10)),
                          1.10, "estimation"),
    "Eden_Electromagnet": CompRule((("CUIVRE", 60), ("ACIER", 40)),
                                   1.10, "extrapole"),
    # electronique : carte = cuivre 30-40 %, silice, resine
    "Electronics": CompRule((("CUIVRE", 35), ("SILICIUM", 30),
                             ("PLASTIQUE", 35)), 1.50, "estimation"),
    "Computer": CompRule((("ELEC", 50), ("ACIER", 25), ("PLASTIQUE", 25)),
                         1.30, "estimation"),
    "Oscillator": CompRule((("SILICIUM", 40), ("ELEC", 30), ("CUIVRE", 30)),
                           1.30, "estimation"),
    "Eden_ComputerT2": CompRule((("ELEC", 50), ("ACIER", 25),
                                 ("PLASTIQUE", 25)), 1.30, "extrapole"),
    "Eden_Semiconductor": CompRule((("SILICIUM", 100),), 1.20, "extrapole"),
    "Eden_PlasmaCoil": CompRule((("CUIVRE", 50), ("OR", 25), ("ALU", 25)),
                                1.10, "extrapole"),
    "OpticalFiber": CompRule((("SILICIUM", 100),), 1.20, "estimation"),
    "CapacitorComponent": CompRule((("ALU", 45), ("PLASTIQUE", 35),
                                    ("CHIMIE", 20)), 1.15, "estimation"),
    "EnergyMatrix": CompRule((("CHIMIE", 40), ("CUIVRE", 20), ("ALU", 20),
                              ("PLASTIQUE", 20)), 1.20, "estimation"),
    # mecanique fine et nano
    "MechanicalComponents": CompRule((("ACIER", 100),), 1.30, "estimation"),
    "Nanotubes": CompRule((("Graphite", 100),), 1.20, "estimation"),
    "InsulationBoost": CompRule((("PLASTIQUE", 60), ("VERRE", 40)),
                                1.20, "estimation"),
    "Eden_MagmacitePlate": CompRule((("Eden_MagmaciteIngot", 100),),
                                    1.05, "extrapole"),
    # compositions fictives : on garde celle de l'auteur, a l'echelle de masse
    "EnergyCell": CompRule(None, 1.10, "extrapole"),
    "EnergyCellLarge": CompRule(None, 1.10, "extrapole"),
    "FusionCell": CompRule(None, 1.10, "extrapole"),
    "PlasmaCellCVT1": CompRule(None, 1.10, "extrapole"),
    "PlasmaCellCVT2": CompRule(None, 1.10, "extrapole"),
    "PlasmaCellCVT3": CompRule(None, 1.10, "extrapole"),
}

# --------------------------------------------- pointe de matiere exotique
# Le gisement redevient un palier : les objets avances prennent une petite
# part de leur masse en matiere exotique. Le PALIER n'est pas `UnlockLevel`
# (un T3 peut se debloquer au niveau 1) mais la PROFONDEUR dans l'arbre
# technologique (`TechTreeParent`), plancher au suffixe du nom (`T2`, `T3`).
_TIER_SUFFIX = re.compile(r"[_ ]?T(\d)$")
EXOTIC_CLASSES = {"GENERATOR", "THRUSTER", "SHIELD", "WARP", "CONSTRUCTOR",
                  "MOTOR", "CORE", "FIREARM"}
EXOTIC_WEAPON = {"FIREARM"}
EXOTIC_MACHINE_MATERIAL = "ZascosiumAlloy"
EXOTIC_WEAPON_MATERIAL = "ErestrumIngot"
EXOTIC_BANDS = ((4, 0.06), (2, 0.03))   # tier mini -> part de la masse cible

MIN_COVERAGE = 0.80      # masse obtenue / masse cible : sous ce seuil, alerte
MAX_COVERAGE = 1.20
# Masse de VOLUME (coques, beton, bois) et non de piece usinee : mesure du
# 06/11, l'ancrage masse y multipliait la matiere par 6 (mediane) a 1400
# (beton 2x2x2), et le jeu est deliberement abstrait sur ces blocs.
# Composition d'auteur conservee, signalee dans le rapport.
NO_MASS_ANCHOR = {"STRUCTURE"}
COUNT_FACTOR_WARN = 10.0  # quantite > x10 l'ancienne : suspect (unites fines)
FINE_UNIT = 1.0           # composant "fin" en dessous de 1 kg l'unite
FINE_MASS_CAP = 0.02      # part maximale de la masse cible pour un fin
CRAFT_MIN, CRAFT_MAX = 1, 120
CRAFT_EXPONENT = 0.4      # CraftTime sous-lineaire : 625 kg et 78 t differencies


# ------------------------------------------------------------------- outils

def _num(raw) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(str(raw).strip().strip('"').split(",")[0].strip())
    except ValueError:
        return None


def _mass_of(idx: RecipeIndex, name: str) -> Optional[float]:
    obj = idx.objs.get(name)
    if obj is None:
        return None
    value = _num(obj.node.get_property("Mass"))
    return value if value and value > 0 else None


def unit_masses(idx: RecipeIndex) -> Dict[str, float]:
    """Masse unitaire de chaque composant cite par les tables (0 = inconnu)."""
    names = {c for chain in MATERIALS.values() for c in chain}
    for klass in CLASSES.values():        # composants imposes par la table
        names.update(tok for tok, _part in klass.parts
                     if tok not in MATERIALS)
    for rule in COMPONENTS.values():      # passe des composants
        for tok, _part in rule.parts or ():
            names.update(MATERIALS.get(tok, (tok,)))
    return {name: _mass_of(idx, name) or 0.0 for name in names}


def template_groups(idx: RecipeIndex) -> Dict[str, List[str]]:
    """Template -> objets qui le declarent (RecipeName/TemplateRoot)."""
    groups: Dict[str, List[str]] = {}
    for name, obj in idx.objs.items():
        for key in ("RecipeName", "TemplateRoot"):
            tpl = (obj.node.get_property(key) or "").strip()
            if tpl:
                groups.setdefault(tpl, []).append(name)
                break
    return groups


def classify(idx: RecipeIndex, template: str,
             groups: Optional[Dict[str, List[str]]] = None
             ) -> Tuple[Optional[str], str]:
    """Classe reelle du template, ou la raison de l'ecart.

    Ordre : IndexName, Category, tokens d'arme, tokens de famille, puis les
    ecarts explicites (`SKIP_TOKENS`). Un seul des deux champs est renseigne.
    """
    names = [template]
    if groups:
        names.extend(groups.get(template, ()))
    for name in names:
        obj = idx.objs.get(name)
        if obj is None:
            continue
        index_name = (obj.node.get_property("IndexName") or "").strip()
        if index_name in INDEXNAME_CLASS:
            return INDEXNAME_CLASS[index_name], ""
        category = (obj.node.get_property("Category") or "").strip()
        if category in CATEGORY_CLASS:
            return CATEGORY_CLASS[category], ""
    lowered = template.lower()
    for tokens, code in _NAME_CLASS:
        if any(tok in lowered for tok in tokens):
            return code, ""
    for token, code in TOKEN_CLASS:
        if token in lowered:
            return code, ""
    for token, reason in SKIP_TOKENS:
        if token in lowered:
            return None, reason
    obj = idx.objs.get(template)
    if obj is not None and (obj.node.get_property("Category") or "").strip():
        return "GENERIC_DEVICE", ""
    return None, "classe absente de la table"


def is_raw(recipe) -> bool:
    """Matiere premiere (BaseItem) : la composition n'a pas de sens."""
    return (recipe.node.get_property("BaseItem") or "").strip().lower() == "true"


def target_of(recipe) -> str:
    """Constructeurs cibles d'une recette. `Target: ""` (guillemets compris)
    = recette cachee ou de deconstruction : hors economie de craft."""
    return (recipe.node.get_property("Target") or "").strip().strip('"').strip()


def resolve(token: str, part_mass: float,
            masses: Dict[str, float]) -> Tuple[str, float]:
    """Composant retenu pour une part de masse (le plus grossier qui tient)."""
    chain = MATERIALS.get(token)
    if chain is None:                     # composant impose par la table
        return token, masses.get(token, 0.0)
    for name in reversed(chain):
        mass = masses.get(name, 0.0)
        if mass and mass <= part_mass:
            return name, mass
    return chain[0], masses.get(chain[0], 0.0)


# ------------------------------------------------------------------- rapport

@dataclass
class RealismProposal:
    name: str
    klass: str
    src: str
    obj_mass: float
    target_mass: float
    old_inputs: List[Tuple[str, float]]
    new_inputs: List[Tuple[str, int]]
    old_mass: float
    new_mass: float
    craft_old: float
    craft_new: int
    notes: List[str] = field(default_factory=list)
    # ecriture : le noeud et le document sont deja charges par l'index
    node: object = None
    doc: object = None
    path: object = None
    output_count: Optional[int] = None   # None = ne pas toucher

    @property
    def old_craft(self) -> float:
        """Nom attendu par l'ecriture de `recipe_balance`."""
        return self.craft_old

    @property
    def new_craft(self) -> int:
        """Nom attendu par l'ecriture de `recipe_balance`."""
        return self.craft_new

    @property
    def changed(self) -> bool:
        before = {n: int(round(q)) for n, q in self.old_inputs}
        after = dict(self.new_inputs)
        return before != after or int(self.craft_old or 0) != self.craft_new

    @property
    def coverage(self) -> float:
        return self.new_mass / self.target_mass if self.target_mass else 0.0

    @property
    def extrapolated(self) -> bool:
        return self.src == "extrapole"


@dataclass
class RealismReport:
    proposals: List[RealismProposal] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)
    masses: Dict[str, float] = field(default_factory=dict)

    def per_class(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for prop in self.proposals:
            out[prop.klass] = out.get(prop.klass, 0) + 1
        return out

    def warnings(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for prop in self.proposals:
            for note in prop.notes:
                key = note.split(" ")[0]
                out[key] = out.get(key, 0) + 1
        return out


def _target_mass(idx: RecipeIndex, template: str,
                 groups: Dict[str, List[str]]) -> Tuple[Optional[float], bool]:
    """Masse de l'objet lui-meme ; a defaut, masse MAXIMALE du groupe.

    Le max de groupe est ecarte en premier choix : mesure du 06/11,
    `ContainerLargeBlocks` pese 125 kg alors qu'une variante du meme
    template pese 20 000 kg (x160) — la recette deviendrait celle d'un
    vaisseau pour un bloc de 125 kg.
    """
    own = _mass_of(idx, template)
    if own:
        return own, False
    names = groups.get(template, ())
    values = [m for m in (_mass_of(idx, n) for n in names) if m]
    return (max(values), True) if values else (None, False)


def _unit_mass(idx: RecipeIndex, masses: Dict[str, float],
               name: str) -> float:
    """Masse unitaire, avec repli hors table (matieres fictives des recettes :
    les compter pour zero fausse la couverture et les facteurs d'echelle)."""
    value = masses.get(name)
    return value if value is not None else (_mass_of(idx, name) or 0.0)


def _old_mass(idx: RecipeIndex, recipe,
              masses: Dict[str, float]) -> float:
    """Masse des ingredients actuels (repli hors table inclus)."""
    return sum(qty * _unit_mass(idx, masses, name)
               for name, qty in recipe.inputs)


def _creates_cycle(idx: RecipeIndex, component: str,
                   ingredients: Sequence[str]) -> bool:
    """Vrai si un ingredient demande, transitivement, le composant ecrit :
    la recette se contiendrait elle-meme (vecu 04/11 : prix a 1e17)."""
    seen = set()
    stack = list(ingredients)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        recipe = idx.recipes.get(name)
        if recipe is None:
            continue
        for child, _qty in recipe.inputs:
            if child == component:
                return True
            stack.append(child)
    return False


def _component_proposal(idx: RecipeIndex, name: str, recipe, rule: CompRule,
                        masses: Dict[str, float]
                        ) -> Tuple[Optional[RealismProposal], str]:
    """Proposition pour un composant : cible = lot x masse x rendement."""
    unit_mass = _mass_of(idx, name) or 0.0
    if unit_mass <= 0:
        return None, "masse inconnue (composant)"
    if rule.parts is not None and unit_mass < FINE_UNIT:
        # Objet de quelques grammes : l'ancrage masse ne peut rien exprimer
        # (Eden_Semiconductor 0,05 kg x 10 = 0,5 kg de matiere) et le minimum
        # d'une unite fausse tout — mesure du 06/11, une recette d'auteur de
        # 486 kg (silicium, cuivre, or, argent, platine, plastique) s'etait
        # effondree en "1 SiliconIngot". Composition d'auteur conservee.
        return None, ("objet de quelques grammes : composition d'auteur "
                      "conservee")
    batch = max(1, int(recipe.output_count or 1))
    target = unit_mass * batch * rule.waste
    old_mass = _old_mass(idx, recipe, masses)
    notes = ["composant en lot" if batch > 1 else "composant"]
    if rule.parts is None:
        if old_mass <= 0:
            return None, "composition vide (composant)"
        factor = target / old_mass
        if not 0.25 <= factor <= 4.0:
            # matiere fictive ET masse d'auteur tres eloignee : remettre a
            # l'echelle produirait des milliers d'unites (vecu : 3259 gels)
            return None, (f"composition fictive incoherente en masse "
                          f"(x{factor:.2f}), conservee")
        rows = [(child, max(1, int(round(qty * factor))))
                for child, qty in recipe.inputs]
        notes.append("composition conservee, echelle de masse")
    else:
        agg: Dict[str, int] = {}
        for token, part in rule.parts:
            part_mass = target * part / 100.0
            component, unit = resolve(token, part_mass, masses)
            if not unit:
                notes.append(f"masseunité_inconnue {component}")
                continue
            agg[component] = agg.get(component, 0) + max(
                1, int(round(part_mass / unit)))
        rows = list(agg.items())
    if not rows:
        return None, "aucun ingredient resolu (composant)"
    if _creates_cycle(idx, name, [child for child, _qty in rows]):
        return None, "cycle : la nouvelle recette se contiendrait"
    new_mass = sum(q * _unit_mass(idx, masses, c) for c, q in rows)
    if target:
        coverage = new_mass / target
        if not MIN_COVERAGE <= coverage <= MAX_COVERAGE:
            notes.append(f"ecart_masse x{coverage:.2f}")
    craft = round(2 + unit_mass ** CRAFT_EXPONENT * 0.5)
    craft = max(CRAFT_MIN, min(CRAFT_MAX, craft))
    return RealismProposal(
        name=name, klass="COMPOSANT", src=rule.src, obj_mass=unit_mass,
        target_mass=target, old_inputs=list(recipe.inputs),
        new_inputs=rows, old_mass=old_mass, new_mass=new_mass,
        craft_old=recipe.craft_time, craft_new=craft, notes=notes,
        node=recipe.node, doc=recipe.doc, path=recipe.path), ""


def tier_of(idx: RecipeIndex, name: str, _seen: tuple = ()) -> int:
    """Profondeur dans l'arbre technologique, plancher au suffixe T<n>.

    `UnlockLevel` ne convient pas : mesure du 06/11, des blocs de haut niveau
    se debloquent des le niveau 1-5. La lignee (`TechTreeParent`) est
    structurelle : un T3 est le petit-fils d'un T1.
    """
    match = _TIER_SUFFIX.search(name)
    own = int(match.group(1)) if match else 0
    obj = idx.objs.get(name)
    parent = ((obj.node.get_property("TechTreeParent") or "").strip()
              .strip('"') if obj else "")
    if not parent or parent in _seen:
        return own
    return max(own, 1 + tier_of(idx, parent, _seen + (name,)))


def _exotic_contribution(idx: RecipeIndex, masses: Dict[str, float],
                         name: str, code: str, target: float
                         ) -> Tuple[Optional[Tuple[str, int]], float]:
    """(ingredient exotique, part de masse prelevee sur la cible).

    La part est PRISE sur la masse, pas ajoutee : la composition reste juste.
    Renvoie (None, 0) si la classe n'est pas concernee ou si la masse de la
    part ne tient pas une unite (une arme de 5 kg ne peut pas contenir
    4,65 kg d'Erestrum) — signale par l'appelant.
    """
    if code not in EXOTIC_CLASSES:
        return None, 0.0
    tier = tier_of(idx, name)
    share = next((part for minimum, part in EXOTIC_BANDS if tier >= minimum),
                 0.0)
    if not share:
        return None, 0.0
    material = (EXOTIC_WEAPON_MATERIAL if code in EXOTIC_WEAPON
                else EXOTIC_MACHINE_MATERIAL)
    unit = _unit_mass(idx, masses, material)
    if not unit:
        return None, 0.0
    qty = int(round(target * share / unit))
    return ((material, qty), share) if qty >= 1 else (None, 0.0)


def _device_rows(idx: RecipeIndex, masses: Dict[str, float], klass: Klass,
                 target: float) -> Tuple[List[Tuple[str, int]], List[str]]:
    """Composition d'une classe pour une masse cible : parts, plafond des
    unites fines (surplus vers la part non fine la plus lourde), resolution
    de granularite. Partage par `analyze` et par les templates de
    deconstruction generes."""
    agg: Dict[str, int] = {}          # deux tokens -> le meme composant
    notes: List[str] = []
    parts = [(token, target * part / 100.0) for token, part in klass.parts]
    # Les unites fines (PlasticMaterial 0,18 kg, MechanicalComponents
    # 0,65 kg) ne peuvent pas peser 30 % d'une machine de plusieurs
    # tonnes : 1582 plastiques pour un panneau, 18000 mecaniques pour un
    # constructeur. Le surplus repart sur la part non fine la plus lourde.
    cap = target * FINE_MASS_CAP
    deficit = 0.0
    for pos, (token, part_mass) in enumerate(parts):
        _comp, unit = resolve(token, part_mass, masses)
        if unit and unit < FINE_UNIT and part_mass > cap:
            deficit += part_mass - cap
            parts[pos] = (token, cap)
            notes.append(f"fin_cap {_comp}")
    if deficit:
        pos = max(range(len(parts)), key=lambda i: parts[i][1])
        parts[pos] = (parts[pos][0], parts[pos][1] + deficit)
    for token, part_mass in parts:
        component, unit = resolve(token, part_mass, masses)
        if not unit:
            notes.append(f"masseunité_inconnue {component}")
            continue
        agg[component] = agg.get(component, 0) + max(
            1, int(round(part_mass / unit)))
    return list(agg.items()), notes


def composition_for(idx: RecipeIndex, name: str,
                    groups: Optional[Dict[str, List[str]]] = None,
                    masses: Optional[Dict[str, float]] = None
                    ) -> Optional[Tuple[List[Tuple[str, int]], int]]:
    """Composition realiste d'un objet SANS recette : (ingredients, CraftTime).

    Sert aux templates de deconstruction generes (jamais fabricables) : la
    matiere rendue au demontage suit la meme table que les recettes. `None`
    si la classe ou la masse manque, ou si la classe est hors ancrage masse
    (structures) — l'appelant retombe alors sur le modele le plus proche.
    """
    code, _reason = classify(idx, name, groups)
    if code is None or code in NO_MASS_ANCHOR:
        return None
    if code == "GENERIC_DEVICE":
        # classe de repli : sa composition (acier/electronique) n'a aucun
        # sens pour une salade ou une ressource (vecu : AkuaFruit rendait
        # des lingots et de l'electronique). L'appelant retombe sur le
        # modele le plus proche, qui est plus juste.
        return None
    mass, _from_group = _target_mass(idx, name, groups or {})
    if not mass:
        return None
    klass = CLASSES[code]
    existing = idx.recipes.get(name)
    batch = max(1, int((existing.output_count if existing else 1) or 1))
    target = mass * klass.waste * batch   # la matiere de TOUT le lot
    local = masses if masses is not None else unit_masses(idx)
    exotic, share = _exotic_contribution(idx, local, name, code, target)
    rows, _notes = _device_rows(idx, local, klass, target * (1.0 - share))
    if exotic is not None:
        rows.append(exotic)
    if not rows:
        return None
    craft = round(2 + target ** CRAFT_EXPONENT * klass.sec_per_kg)
    return rows, max(CRAFT_MIN, min(CRAFT_MAX, craft))


def refresh_deconstruction(idx: RecipeIndex, names: Sequence[str]) -> List[
        "RealismProposal"]:
    """Recalcule des templates de deconstruction generes (`Target: ""`).

    Un objet de tier >= 2 doit rendre l'exotique que sa fabrication consomme :
    sans ce rafraichissement, demonter puis refabriquer perd de la matiere.
    Ne touche ni `Target`, ni `CraftTime` du modele voisin : seules les
    compositions deterministes (classe connue) sont reecrites.
    """
    groups = template_groups(idx)
    masses = unit_masses(idx)
    proposals: List[RealismProposal] = []
    for name in names:
        recipe = idx.recipes.get(name)
        if recipe is None:
            continue
        wanted = composition_for(idx, name, groups, masses)
        if wanted is None:
            continue
        rows, craft = wanted
        if sorted((c, int(q)) for c, q in recipe.inputs) == sorted(rows):
            continue
        proposals.append(RealismProposal(
            name=name, klass="DECONSTRUCTION", src="realisme",
            obj_mass=_mass_of(idx, name) or 0.0, target_mass=0.0,
            old_inputs=list(recipe.inputs), new_inputs=rows,
            old_mass=_old_mass(idx, recipe, masses), new_mass=0.0,
            craft_old=recipe.craft_time, craft_new=max(
                CRAFT_MIN, min(CRAFT_MAX, int(craft))),
            notes=["rafraichissement (Target vide conserve)"],
            node=recipe.node, doc=recipe.doc, path=recipe.path))
    return proposals


def sync_to_base(root, base_root: str, vanilla_root: str = ""
                 ) -> Tuple[List[RealismProposal], Dict[str, str]]:
    """Realigne les recettes fabricables du scenario sur sa base (RE2 Beta),
    SANS modification : composition, CraftTime et OutputCount de la base,
    tels quels. Doctrine finale du 06/11 — l'auteur veut la base exacte.

    Recettes cibles : fabricables dans les DEUX scenarios et differentes.
    Target reste celui du scenario (choix de constructeurs, pas de l'economie).
    """
    idx, _van = load_recipe_index(root, vanilla_root)
    idx_base, _ = load_recipe_index(base_root)
    proposals: List[RealismProposal] = []
    skipped: Dict[str, str] = {}
    for name, base in sorted(idx_base.recipes.items()):
        cur = idx.recipes.get(name)
        if cur is None or not target_of(cur) or not target_of(base):
            continue
        if is_raw(cur):
            continue
        rows = [(c, int(round(q))) for c, q in base.inputs]
        craft_new = int(base.craft_time or 1)
        out_new = int(base.output_count or 1)
        if (sorted(rows) == sorted((c, int(round(q))) for c, q in cur.inputs)
                and int(cur.craft_time or 1) == craft_new
                and int(cur.output_count or 1) == out_new):
            continue                     # deja identique a la base
        proposals.append(RealismProposal(
            name=name, klass="RE2 BETA", src="base", obj_mass=0.0,
            target_mass=0.0, old_inputs=list(cur.inputs), new_inputs=rows,
            old_mass=0.0, new_mass=0.0, craft_old=cur.craft_time,
            craft_new=craft_new,
            output_count=(out_new if out_new != int(cur.output_count or 1)
                          else None),
            notes=["recette de la base RE2 Beta, sans modification"],
            node=cur.node, doc=cur.doc, path=cur.path))
    return proposals, skipped


def analyze(root, vanilla_root: str = "", base_root: str = "") -> RealismReport:
    """Compose les recettes realistes. Ne modifie AUCUN fichier.

    `base_root` : scenario de base (RE2 Beta). Toute recette fabricable qui
    y existe est gouvernee par la base (`sync_to_base` : recette RE2 Beta verbatim)
    et sort du perimetre de la composition par classe.
    """
    idx, _van = load_recipe_index(root, vanilla_root)
    masses = unit_masses(idx)
    groups = template_groups(idx)
    idx_base = None
    if base_root:
        idx_base, _ = load_recipe_index(base_root)
    report = RealismReport(masses=masses)
    for name, recipe in sorted(idx.recipes.items()):
        if is_raw(recipe):
            report.skipped[name] = "matiere premiere (BaseItem)"
            continue
        if not target_of(recipe):
            # Target vide = recette cachee ou de deconstruction generee :
            # elle n'est dans aucun constructeur, donc hors economie de craft.
            report.skipped[name] = "non fabricable (Target vide)"
            continue
        if idx_base is not None and name in idx_base.recipes:
            # gouvernee par la base : composition/quantites de RE2 Beta
            # (recette RE2 Beta verbatim), pas par les classes
            report.skipped[name] = "gouvernee par la base RE2 (sync_to_base)"
            continue
        code, reason = classify(idx, name, groups)
        if code is None:
            report.skipped[name] = reason
            continue
        if code in NO_MASS_ANCHOR:
            report.skipped[name] = ("structure : masse de volume, composition "
                                    "d'auteur conservee")
            continue
        klass = CLASSES[code]
        obj_mass, from_group = _target_mass(idx, name, groups)
        if not obj_mass:
            report.skipped[name] = "masse inconnue (ni Mass du groupe)"
            continue
        # OutputCount > 1 = un lot (30 roquettes, 40 obus) : la matiere
        # entrante porte sur tout le lot. Mesure du 06/11 : FastRocketBAT2
        # produit 30 x 128 kg et n'en consommait que 128 kg.
        batch = max(1, int(recipe.output_count or 1))
        target = obj_mass * klass.waste * batch
        notes: List[str] = []
        if from_group:
            notes.append("masse_du_groupe")
        exotic, share = _exotic_contribution(idx, masses, name, code, target)
        if (exotic is None and code in EXOTIC_CLASSES
                and tier_of(idx, name) >= EXOTIC_BANDS[-1][0]):
            notes.append("exotique impossible (part < 1 unite)")
        rows, row_notes = _device_rows(idx, masses, klass,
                                       target * (1.0 - share))
        notes.extend(row_notes)
        achieved = sum(q * _unit_mass(idx, masses, c) for c, q in rows)
        if target and rows and not (0.25 * target <= achieved <= 4.0 * target):
            # Les unites du jeu sont trop grossieres pour exprimer cet objet
            # (pilule de 10 g, plantule de 2,4 kg) : ecrire quand meme
            # produirait une recette 46x trop lourde. Mesure du 06/11.
            report.skipped[name] = ("composition inexprimable (unites trop "
                                    "grossieres), recette d'auteur conservee")
            continue
        if exotic is not None:
            rows.append(exotic)
            notes.append(f"exotique {share:.0%}")
        for component, qty in rows:
            old_qty = dict(recipe.inputs).get(component, 0.0)
            if old_qty and qty > old_qty * COUNT_FACTOR_WARN:
                notes.append(f"comptage x{qty / old_qty:.0f} {component}")
        new_mass = sum(q * _unit_mass(idx, masses, c) for c, q in rows)
        if rows:
            coverage = new_mass / target if target else 0.0
            if not MIN_COVERAGE <= coverage <= MAX_COVERAGE:
                notes.append(f"ecart_masse x{coverage:.2f}")
            # sous-lineaire : 625 kg et 78 t ne doivent pas finir au plafond
            craft = round(2 + target ** CRAFT_EXPONENT * klass.sec_per_kg)
            # bornes ABSOLUES seulement : un plafond relatif au CraftTime
            # courant n'est pas idempotent (vecu 06/11 : 3 -> 30 plafonne,
            # puis 60, le plafond montant avec la valeur ecrite — ratchet)
            craft = max(CRAFT_MIN, min(CRAFT_MAX, craft))
        else:
            notes.append("aucun ingredient resolu")
            craft = max(CRAFT_MIN, int(recipe.craft_time or 1))
        report.proposals.append(RealismProposal(
            name=name, klass=code, src=klass.src, obj_mass=obj_mass,
            target_mass=target, old_inputs=list(recipe.inputs),
            new_inputs=rows, old_mass=_old_mass(idx, recipe, masses),
            new_mass=new_mass, craft_old=recipe.craft_time, craft_new=craft,
            notes=notes, node=recipe.node, doc=recipe.doc,
            path=recipe.path))
    # --- passe des COMPOSANTS : ceux qui n'ont pas de composant en dessous
    for name, reason in list(report.skipped.items()):
        if "composant" not in reason and "metallurgie" not in reason:
            continue
        rule = COMPONENTS.get(name)
        recipe = idx.recipes.get(name)
        if rule is None or recipe is None:
            continue
        proposal, why = _component_proposal(idx, name, recipe, rule, masses)
        if proposal is None:
            report.skipped[name] = why
            continue
        del report.skipped[name]
        report.proposals.append(proposal)
    return report


def apply_proposals(proposals: Sequence[RealismProposal]
                    ) -> Dict[Path, int]:
    """Ecrit les recettes choisies. Reutilise l'ecriture de recipe_balance :
    Child Inputs + CraftTime, backup central, ecriture atomique."""
    from core.recipe_balance import apply_proposals as _apply  # local : conftest
    return _apply([prop for prop in proposals if prop.changed])


_COLUMNS = ("template", "classe", "source", "masse_objet_kg", "masse_cible_kg",
            "ingredients_avant", "ingredients_apres", "masse_avant_kg",
            "masse_apres_kg", "ecart_masse", "craft_avant", "craft_apres",
            "notes")


def write_report_csv(report: RealismReport, path) -> Path:
    """Rapport lisible (lot 1) : aucune ecriture dans le scenario."""
    path = Path(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(_COLUMNS)
        for prop in report.proposals:
            writer.writerow((
                prop.name, prop.klass, prop.src,
                f"{prop.obj_mass:.2f}", f"{prop.target_mass:.2f}",
                ", ".join(f"{n}x{q:g}" for n, q in prop.old_inputs),
                ", ".join(f"{n}x{q}" for n, q in prop.new_inputs),
                f"{prop.old_mass:.2f}", f"{prop.new_mass:.2f}",
                f"{prop.coverage:.2f}", f"{prop.craft_old:g}",
                prop.craft_new, " ; ".join(prop.notes)))
        for name, reason in sorted(report.skipped.items()):
            # les ecartees sont dans le meme fichier : une recette non traitee
            # sans raison visible est un angle mort du controle
            writer.writerow((name, "-", "-", "", "", "", "", "", "", "", "",
                             "", reason))
    return path


def summary(report: RealismReport) -> List[str]:
    """Lignes de synthese pour la console / le dialogue."""
    lines = [f"{len(report.proposals)} recettes proposees, "
             f"{len(report.skipped)} ecartees"]
    for code, count in sorted(report.per_class().items(),
                              key=lambda kv: -kv[1]):
        lines.append(f"  {count:4d}  {code}")
    if report.skipped:
        reasons: Dict[str, int] = {}
        for reason in report.skipped.values():
            reasons[reason] = reasons.get(reason, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {count:4d}  ecartees : {reason}")
    for note, count in report.warnings().items():
        lines.append(f"  {count:4d}  alerte : {note}")
    return lines
