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

"""Equilibrage par correlations (core/correlation_balance.py) : mediane par
groupe de reference (Material, famille x tier, tier), ratio a la recette
pour Mass, whitelist design volontaire, statuts (zero, sans_valeur,
sans_groupe), application + re-analyse propre."""

from pathlib import Path

from core.correlation_balance import (OK, OUTLIER, SANS_GROUPE, SANS_VALEUR,
                                      WHITELIST, ZERO, analyze_correlations,
                                      apply_changes, make_changes)

ITEMS = """{ Item Name: CompA
  Mass: 10
  MarketPrice: 2
}
{ Item Name: CompHeavy
  Mass: 100
}
{ Item Name: GunT1
  Mass: 5
  Damage: 100
}
{ Item Name: GunT2
  Mass: 8
  Damage: 400
}
{ Item Name: GunT2Odd
  Mass: 8
  Damage: 40
}
{ Item Name: GunT2b
  Mass: 8
  Damage: 360
}
{ Item Name: RockMass
  Mass: 999
}
"""

BLOCKS = """{ Block Id: 500, Name: SteelBlockA
  TemplateRoot: SteelBlocks
  Mass: 100
  HitPoints: 500
  Material: SteelLarge
}
{ Block Id: 501, Name: SteelBlockB
  TemplateRoot: SteelBlocks
  Mass: 90
  HitPoints: 480
  Material: SteelLarge
}
{ Block Id: 502, Name: SteelBlockOdd
  TemplateRoot: SteelBlocks
  Mass: 5
  HitPoints: 5000
  Material: SteelLarge
}
{ Block Id: 503, Name: SteelNoMat
  Mass: 100
  HitPoints: 500
}
{ Block Id: 504, Name: ArtMassHeavy
  Mass: 560000
  Material: SteelLarge
}
{ Block Id: 505, Name: ZeroHP
  TemplateRoot: SteelBlocks
  Mass: 100
  HitPoints: 0
  Material: SteelLarge
}
{ Block Id: 506, Name: ShieldGenT1
  Mass: 50
  ShieldCapacity: 1000
  Material: Device
}
{ Block Id: 507, Name: ShieldGenT2
  Mass: 60
  ShieldCapacity: 2000
  Material: Device
}
{ Block Id: 508, Name: ShieldGenT2Odd
  Mass: 60
  ShieldCapacity: 90000
  Material: Device
}
{ Block Id: 510, Name: ShieldGenT2b
  Mass: 60
  ShieldCapacity: 1800
  Material: Device
}
"""

TEMPLATES = """{ Template Name: SteelBlocks
  CraftTime: 5
  OutputCount: 1
  { Child Inputs
    CompA: 2
  }
}
{ Template Name: GunT1
  CraftTime: 5
  { Child Inputs
    CompA: 1
  }
}
{ Template Name: GunT2
  CraftTime: 5
  { Child Inputs
    CompA: 1
  }
}
{ Template Name: GunT2Odd
  CraftTime: 5
  { Child Inputs
    CompA: 1
  }
}
{ Template Name: GunT2b
  CraftTime: 5
  { Child Inputs
    CompA: 1
  }
}
"""


def _scenario(tmp_path: Path):
    cdir = tmp_path / "Content" / "Configuration"
    cdir.mkdir(parents=True)
    (cdir / "ItemsConfig.ecf").write_text(ITEMS, encoding="utf-8")
    (cdir / "BlocksConfig.ecf").write_text(BLOCKS, encoding="utf-8")
    (cdir / "Templates.ecf").write_text(TEMPLATES, encoding="utf-8")
    return tmp_path


def _entries(rep):
    return {e.name: e for e in rep.entries}


def test_mass_median_per_material(tmp_path):
    _, rep = analyze_correlations(_scenario(tmp_path), "mass")
    e = _entries(rep)
    # SteelBlockA/B : masse 100/90 vs 2x CompA(10)=20 -> ratios 5.0/4.5 ;
    # SteelBlockOdd : 5/20 = 0.25 -> outlier ; mediane groupe
    # [5.0, 4.5, 0.25, 5.0] = 4.75 -> cible 4.75 x 20 = 95
    assert e["SteelBlockA"].status == OK
    assert e["SteelBlockOdd"].status == OUTLIER
    assert e["SteelBlockOdd"].target == 95.0
    # lest : whitelist jamais propose
    assert e["ArtMassHeavy"].status == WHITELIST
    assert e["ArtMassHeavy"].target is None
    # sans Material ni TemplateRoot : sans groupe
    assert e["SteelNoMat"].status == SANS_GROUPE
    # les items ne font PAS partie du perimetre masse (blocs seuls)
    assert all(e_.kind == "block" for e_ in rep.entries)


def test_hitpoints_median_per_material(tmp_path):
    _, rep = analyze_correlations(_scenario(tmp_path), "hitpoints")
    e = _entries(rep)
    # SteelLarge HP 500/480/5000 -> mediane 500 ; ZeroHP -> status zero
    assert e["SteelBlockA"].status == OK
    assert e["SteelBlockOdd"].status == OUTLIER
    assert e["SteelBlockOdd"].target == 500
    assert e["ZeroHP"].status == ZERO
    assert e["ZeroHP"].target is None


def test_damage_median_per_family_tier(tmp_path):
    _, rep = analyze_correlations(_scenario(tmp_path), "damage")
    e = _entries(rep)
    # famille gunt2 : 400/40/360 -> mediane 360 ; Odd (40) outlier -> 360
    assert e["GunT2"].status == OK
    assert e["GunT2Odd"].status == OUTLIER
    assert e["GunT2Odd"].target == 360
    assert e["GunT2b"].status == OK
    # gunt1 seul dans son groupe : sous MIN_GROUP -> pas de reference
    assert e["GunT1"].status == SANS_GROUPE


def test_shield_median_per_tier(tmp_path):
    _, rep = analyze_correlations(_scenario(tmp_path), "shield")
    e = _entries(rep)
    # t2 : 2000/90000/1800 -> mediane 2000 ; Odd (90000) outlier -> 2000
    assert e["ShieldGenT2Odd"].status == OUTLIER
    assert e["ShieldGenT2Odd"].target == 2000
    assert e["ShieldGenT2b"].status == OK
    # groupe de 2 (t1, un seul + rien) : sous MIN_GROUP -> sans groupe
    assert e["ShieldGenT1"].status == SANS_GROUPE


def test_apply_then_reanalyze_stable(tmp_path):
    root = _scenario(tmp_path)
    idx, rep = analyze_correlations(root, "hitpoints")
    names = {e.name for e in rep.entries if e.status == OUTLIER}
    assert names == {"SteelBlockOdd"}
    changes = make_changes(idx, rep, names)
    done = apply_changes(changes, fmt_int=rep.fmt_int)
    assert sum(done.values()) == 1
    _, rep2 = analyze_correlations(root, "hitpoints")
    e2 = _entries(rep2)
    assert e2["SteelBlockOdd"].status == OK
    assert e2["SteelBlockOdd"].value == 500
    # les autres proprietes du bloc et les autres blocs intacts
    text = (root / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8")
    assert "Mass: 5" in text
    assert "HitPoints: 500" in text


def test_apply_missing_prop_materializes_with_type(tmp_path):
    """Vecu 17/10 : valeur effective HERITEE d'un Ref -> set_property echoue
    et le fallback creait une ligne NUE sans 'type:' ; le jeu la lit en
    string ('Error converting property'), propulseurs sans poussee. La ligne
    creee porte desormais son attribut type."""
    from core.ecf.parser import parse_ecf_file
    from core.correlation_balance import CorrChange, apply_changes
    root = _scenario(tmp_path)
    path = root / "Content" / "Configuration" / "BlocksConfig.ecf"
    blocks_file = root / "Content" / "Configuration" / "BlocksConfig.ecf"
    blocks_file.write_text(
        blocks_file.read_text(encoding="utf-8") +
        "{ Block Id: 601, Name: RefChildThrust, Ref: SteelBlockA\n"
        "  Mass: 5\n}\n", encoding="utf-8")
    doc = parse_ecf_file(path)
    block = next(b for b in doc.iter_blocks()
                 if b.get_property("Name") == "RefChildThrust")
    assert block.set_property("HitPoints", "450") is False   # absente
    ch = CorrChange(path=path, doc=doc, node=block, name="RefChildThrust",
                    prop="HitPoints", old=None, new=450)
    apply_changes([ch], fmt_int=True)
    text = path.read_text(encoding="utf-8")
    assert "HitPoints: 450, type: int" in text


def test_sans_valeur_never_proposed(tmp_path):
    root = _scenario(tmp_path)
    # bloc avec template mais sans HitPoints : affiche, jamais ecrit
    blocks = root / "Content/Configuration/BlocksConfig.ecf"
    blocks.write_text(blocks.read_text(encoding="utf-8") +
                      "{ Block Id: 509, Name: NoHPBlock\n"
                      "  Mass: 100\n  Material: SteelLarge\n}\n",
                      encoding="utf-8")
    _, rep = analyze_correlations(root, "hitpoints")
    e = _entries(rep)
    assert e["NoHPBlock"].status == SANS_VALEUR
    assert e["NoHPBlock"].target is None


def test_size_normalized_doors_not_flagged(tmp_path):
    """Vecu 17/10 : ShutterDoor 1x1/3x3/4x4/5x5 avec des RECETTES
    IDENTIQUES et des masses qui grandissent avec la taille — le modele
    sans taille proposait le MEME 810 aux quatre. Avec normalisation par
    les dimensions du nom : tous coherents, aucune proposition. Et un
    3x3 pesant le poids d'un 1x1 reste detecte, cible re-scalee."""
    root = _scenario(tmp_path)
    blocks = root / "Content/Configuration/BlocksConfig.ecf"
    blocks.write_text(blocks.read_text(encoding="utf-8") + (
        "{ Block Id: 520, Name: DoorBig1x1\n"
        "  TemplateRoot: DoorBig\n  Mass: 210\n  Material: SteelLarge\n}\n"
        "{ Block Id: 521, Name: DoorBig3x3\n"
        "  TemplateRoot: DoorBig\n  Mass: 1530\n  Material: SteelLarge\n}\n"
        "{ Block Id: 522, Name: DoorBig5x5\n"
        "  TemplateRoot: DoorBig\n  Mass: 4050\n  Material: SteelLarge\n}\n"
        "{ Block Id: 523, Name: DoorBig4x4Wrong\n"
        "  TemplateRoot: DoorBig\n  Mass: 210\n  Material: SteelLarge\n}\n"),
        encoding="utf-8")
    templates = root / "Content/Configuration/Templates.ecf"
    templates.write_text(templates.read_text(encoding="utf-8") + (
        "{ Template Name: DoorBig\n  CraftTime: 5\n  OutputCount: 1\n"
        "  { Child Inputs\n    CompA: 2\n  }\n}\n"), encoding="utf-8")
    _, rep = analyze_correlations(root, "mass")
    e = {x.name: x for x in rep.entries}
    # tailles 1/9/25, meme cout : ratios normalises ~ proches -> ok
    assert e["DoorBig1x1"].status == OK
    assert e["DoorBig3x3"].status == OK
    assert e["DoorBig5x5"].status == OK
    # 4x4 (facteur 16) avec la masse du 1x1 : outlier, cible re-scalee
    assert e["DoorBig4x4Wrong"].status == OUTLIER
    assert e["DoorBig4x4Wrong"].target > e["DoorBig1x1"].value * 5


def test_sizeinblocks_property_wins_over_name(tmp_path):
    """Source officielle de la taille : la propriete SizeInBlocks du jeu
    ('13,7,1' -> 91). Le nom n'est qu'un repli. Ici un bloc NOMME '1x1'
    mais reellement 3x3 (SizeInBlocks) doit etre juge sur 9."""
    root = _scenario(tmp_path)
    blocks = root / "Content/Configuration/BlocksConfig.ecf"
    blocks.write_text(blocks.read_text(encoding="utf-8") + (
        "{ Block Id: 520, Name: DoorBig1x1\n"
        "  TemplateRoot: DoorBig\n  Mass: 210\n  Material: SteelLarge\n}\n"
        "{ Block Id: 521, Name: DoorBig3x3\n"
        "  TemplateRoot: DoorBig\n  Mass: 1530\n  Material: SteelLarge\n}\n"
        "{ Block Id: 522, Name: DoorBig5x5\n"
        "  TemplateRoot: DoorBig\n  Mass: 4050\n  Material: SteelLarge\n}\n"
        "{ Block Id: 530, Name: DoorMisnamed1x1\n"
        "  TemplateRoot: DoorBig\n  Mass: 1530\n"
        "  SizeInBlocks: \"3,3,1\"\n  Material: SteelLarge\n}\n"),
        encoding="utf-8")
    templates = root / "Content/Configuration/Templates.ecf"
    templates.write_text(templates.read_text(encoding="utf-8") + (
        "{ Template Name: DoorBig\n  CraftTime: 5\n  OutputCount: 1\n"
        "  { Child Inputs\n    CompA: 2\n  }\n}\n"), encoding="utf-8")
    _, rep = analyze_correlations(root, "mass")
    e = {x.name: x for x in rep.entries}
    # facteur 9 (SizeInBlocks) : 1530/9 = 170/unite ~ la densite des
    # portes DoorBig (1530/9, 4050/25=162) -> coherent, PAS outlier
    assert e["DoorMisnamed1x1"].status == OK


def test_extreme_deviation_not_proposed(tmp_path):
    """Vecu 17/10 : un propulseur geant propose x27 vers la densite de son
    groupe — au-dela de x10 ce n'est plus une derive mais un design
    different : statut sans_groupe, jamais de cible absurde."""
    root = _scenario(tmp_path)
    blocks = root / "Content/Configuration/BlocksConfig.ecf"
    blocks.write_text(blocks.read_text(encoding="utf-8") + (
        "{ Block Id: 540, Name: GiantThruster\n"
        "  TemplateRoot: SteelBlocks\n  Mass: 315000\n"
        "  Material: SteelLarge\n}\n"), encoding="utf-8")
    _, rep = analyze_correlations(root, "mass")
    e = {x.name: x for x in rep.entries}
    assert e["GiantThruster"].status == SANS_GROUPE
    assert e["GiantThruster"].target is None


def test_homogeneous_subdesign_not_flagged(tmp_path):
    """Vecu 17/10 (ecran) : TribalBarrow/Oven/Boat/Hearth ont tous QUATRE la
    meme masse (400) — un sous-design choisi par l'auteur. La mediane du
    groupe DecoTribal, tiree par un membre plus lourd, les mettait tous a
    l'amene (400 -> 800). Regle : >= 3 membres au meme ratio normalise =
    sous-design homogene -> coherent."""
    root = _scenario(tmp_path)
    blocks = root / "Content/Configuration/BlocksConfig.ecf"
    blocks.write_text(blocks.read_text(encoding="utf-8") + (
        "{ Block Id: 550, Name: TribalBig\n"
        "  TemplateRoot: DecoTribal\n  Mass: 2000\n  Material: Wood\n}\n"
        "{ Block Id: 555, Name: TribalMid1\n"
        "  TemplateRoot: DecoTribal\n  Mass: 800\n  Material: Wood\n}\n"
        "{ Block Id: 556, Name: TribalMid2\n"
        "  TemplateRoot: DecoTribal\n  Mass: 800\n  Material: Wood\n}\n"
        "{ Block Id: 557, Name: TribalMid3\n"
        "  TemplateRoot: DecoTribal\n  Mass: 800\n  Material: Wood\n}\n"
        "{ Block Id: 551, Name: TribalBarrow\n"
        "  TemplateRoot: DecoTribal\n  Mass: 400\n  Material: Wood\n}\n"
        "{ Block Id: 552, Name: TribalOven\n"
        "  TemplateRoot: DecoTribal\n  Mass: 400\n  Material: Wood\n}\n"
        "{ Block Id: 553, Name: TribalBoat\n"
        "  TemplateRoot: DecoTribal\n  Mass: 400\n  Material: Wood\n}\n"
        "{ Block Id: 554, Name: TribalHearth\n"
        "  TemplateRoot: DecoTribal\n  Mass: 400\n  Material: Wood\n}\n"),
        encoding="utf-8")
    templates = root / "Content/Configuration/Templates.ecf"
    templates.write_text(templates.read_text(encoding="utf-8") + (
        "{ Template Name: DecoTribal\n  CraftTime: 5\n  OutputCount: 1\n"
        "  { Child Inputs\n    CompA: 1\n  }\n}\n"), encoding="utf-8")
    _, rep = analyze_correlations(root, "mass")
    e = {x.name: x for x in rep.entries}
    # ratios : Big 200, Mid 80 x3, tribals 40 x4 -> mediane 60 ;
    # Big (200) outlier ; les quatre identiques (40, hors bornes) forment
    # un sous-design homogene -> coherent, PAS proposes a 60
    assert e["TribalBig"].status == OUTLIER
    assert e["TribalMid1"].status == OK
    for n in ("TribalBarrow", "TribalOven", "TribalBoat", "TribalHearth"):
        assert e[n].status == OK, n
        assert "sous-design" in e[n].detail


def test_pinned_medians_prevent_ratchet(tmp_path):
    """Vecu 17/10 (ecran utilisateur) : apres une application PARTIELLE,
    le re-scan recalcule les medianes sur les valeurs actuelles et cree de
    NOUVELLES propositions sur les membres non appliques. Epingler les
    medianes de la premiere analyse = zero proposal fantome."""
    root = _scenario(tmp_path)
    blocks = root / "Content/Configuration/BlocksConfig.ecf"
    # groupe DEDIE (RatchetBlocks, isole de la fixture de base qui partage
    # SteelBlocks) : 100/100/400/400 -> mediane 12.5 ; les 100 (ratio 5,
    # bornes [8.75-17.5]) ET les 400 (ratio 20) sont outliers
    blocks.write_text(blocks.read_text(encoding="utf-8") + (
        "{ Block Id: 560, Name: FamA\n"
        "  TemplateRoot: RatchetBlocks\n  Mass: 100\n  Material: SteelLarge\n}\n"
        "{ Block Id: 561, Name: FamB\n"
        "  TemplateRoot: RatchetBlocks\n  Mass: 100\n  Material: SteelLarge\n}\n"
        "{ Block Id: 562, Name: FamC\n"
        "  TemplateRoot: RatchetBlocks\n  Mass: 400\n  Material: SteelLarge\n}\n"
        "{ Block Id: 563, Name: FamD\n"
        "  TemplateRoot: RatchetBlocks\n  Mass: 400\n  Material: SteelLarge\n}\n"),
        encoding="utf-8")
    templates = root / "Content/Configuration/Templates.ecf"
    templates.write_text(templates.read_text(encoding="utf-8") + (
        "{ Template Name: RatchetBlocks\n  CraftTime: 5\n  OutputCount: 1\n"
        "  { Child Inputs\n    CompA: 2\n  }\n}\n"), encoding="utf-8")
    idx, rep = analyze_correlations(root, "mass")
    pinned = dict(rep.groups)                 # epinglage session
    # application partielle : seuls les 100 -> 250 (la cible epinglee)
    changes = make_changes(idx, rep, {"FamA", "FamB"})
    apply_changes(changes, fmt_int=rep.fmt_int)
    # re-scan EPINGLE : les 250 sont exactement sur la mediane -> ok ;
    # les 400 restent outliers avec la MEME cible
    _, rep2 = analyze_correlations(root, "mass", pinned_medians=pinned)
    e2 = {x.name: x for x in rep2.entries}
    assert e2["FamA"].status == OK and e2["FamB"].status == OK
    assert e2["FamC"].status == OUTLIER and e2["FamC"].target == 250
    assert e2["FamD"].status == OUTLIER and e2["FamD"].target == 250
    # contraste : re-scan FRAIS = la mediane glisse (12.5 -> 16.25) et
    # la cible de FamC derive a 325 : c'est le ratchet que l'epingle
    # empeche (la cible restait 250 avec l'epingle)
    _, rep3 = analyze_correlations(root, "mass")
    e3 = {x.name: x for x in rep3.entries}
    assert e3["FamC"].target == 325
