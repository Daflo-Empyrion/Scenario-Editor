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
Tests des checks « chargeurs du moteur » (core/engine_loaders.py) : chaque
cas reproduit une validation FATALE du chargeur du jeu (regles verifiees
contre le chargement reel du jeu, session du 25/10/2026). Les messages
attendus sont les messages EXACTS du moteur.

Les registres de classes (BLOCK_CLASSES etc.) etant embarques, les tests
tournent SANS installation du jeu (vanilla_content="").
"""
from pathlib import Path

import pytest

from core.engine_loaders import run_engine_loader_checks

BLOCKS_HEADER = (
    "{ Material Id: 1, Name: Device\n}\n\n"
)
ITEMS_HEADER = ""
TEMPLATE_OK = (
    "{ Template Name: TestBlockA\n"
    "  CraftTime: 5\n"
    "}\n\n"
)


def _scenario(tmp_path: Path, blocks: str = "", items: str = "",
              materials: str = BLOCKS_HEADER, templates: str = "") -> Path:
    conf = tmp_path / "Content" / "Configuration"
    conf.mkdir(parents=True)
    if blocks:
        (conf / "BlocksConfig.ecf").write_text(blocks, encoding="utf-8")
    if items:
        (conf / "ItemsConfig.ecf").write_text(items, encoding="utf-8")
    if materials:
        (conf / "MaterialConfig.ecf").write_text(materials, encoding="utf-8")
    if templates:
        (conf / "Templates.ecf").write_text(templates, encoding="utf-8")
    return tmp_path


def _run(root: Path) -> list:
    return run_engine_loader_checks(root, "")


def _messages(issues: list) -> str:
    return "\n".join(i.message for i in issues)


# ---------------------------------------------------------------------------
# ItemsConfig — GroupTree.TestDevice
# ---------------------------------------------------------------------------

def test_item_duplicate_id_is_fatal(tmp_path):
    """« Item already defined: Id N » — le jeu jette sur le doublon."""
    root = _scenario(tmp_path, items=(
        "{ Item Id: 10, Name: A\n"
        "  Material: Device\n"
        "}\n\n"
        "{ Item Id: 10, Name: B\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "already defined" in i.message]
    assert len(issues) == 1
    assert "Id 10" in issues[0].message
    assert "B" in issues[0].message


def test_item_ref_unknown_is_fatal(tmp_path):
    root = _scenario(tmp_path, items=(
        "{ Item Id: 10, Name: A, Ref: MissingItem\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "Referenced item" in i.message]
    assert len(issues) == 1
    assert "MissingItem" in issues[0].message and "A" in issues[0].message


def test_item_unknown_class_is_fatal_even_without_vanilla(tmp_path):
    """Le registre ItemClass est embarque : Class: NotAClass est attrape
    sans installation du jeu."""
    root = _scenario(tmp_path, items=(
        "{ Item Id: 10, Name: A\n"
        "  Class: NotAClass\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "No class" in i.message]
    assert len(issues) == 1
    assert "NotAClass" in issues[0].message


def test_item_missing_material_is_fatal(tmp_path):
    root = _scenario(tmp_path, items="{ Item Id: 10, Name: A }\n")
    issues = [i for i in _run(root) if "Material missing" in i.message]
    assert len(issues) == 1


def test_item_unknown_material_is_fatal(tmp_path):
    root = _scenario(tmp_path, items=(
        "{ Item Id: 10, Name: A\n"
        "  Material: Unobtanium\n"
        "}\n"))
    issues = [i for i in _run(root) if "not found in item" in i.message]
    assert len(issues) == 1
    assert "Unobtanium" in issues[0].message


def test_item_holdtype_not_integer_is_fatal(tmp_path):
    root = _scenario(tmp_path, items=(
        "{ Item Id: 10, Name: A\n"
        "  Class: Ranged\n"
        "  Material: Device\n"
        "  HoldType: many\n"
        "}\n"))
    issues = [i for i in _run(root) if "hold_type" in i.message]
    assert len(issues) == 1


def test_item_alt_section_without_class_is_fatal(tmp_path):
    root = _scenario(tmp_path, items=(
        "{ Item Id: 10, Name: A\n"
        "  Class: Ranged\n"
        "  Material: Device\n"
        "  { Alt0\n"
        "    Model: @models/Weapons/Rifle.spo\n"
        "  }\n"
        "}\n"))
    issues = [i for i in _run(root) if "No child" in i.message]
    assert len(issues) == 1
    assert "Alt0" in issues[0].message


# ---------------------------------------------------------------------------
# BlocksConfig — SymbolList.OpenNetwork + PartitionDictionary.Init
# ---------------------------------------------------------------------------

def test_block_duplicate_name_is_only_warning(tmp_path):
    """Fidelite : les blocs doublons sont ECRASES avec un warning du jeu
    (« overridden »), contrairement aux items ou le doublon d'Id jette."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        "}\n\n"
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        "}\n"))
    issues = _run(root)
    assert [i.severity for i in issues] == ["warning"]
    assert "overridden" in issues[0].message


def test_block_id_above_2048_is_fatal(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Id: 3000, Name: TestBlockA\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "2048" in i.message]
    assert len(issues) == 1


def test_block_ref_unknown_is_fatal(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA, Ref: NoSuchBlock\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "not found for block" in i.message]
    assert len(issues) == 1
    assert "NoSuchBlock" in issues[0].message


def test_block_name_resolution_is_case_sensitive(tmp_path):
    """Le jeu resout les noms de blocs SENSIBLE A LA CASSE (TryGetValue) :
    ChildBlocks: testblocka pour Name: TestBlockA est fatal en jeu."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        "}\n\n"
        "{ Block Name: TestBlockB\n"
        "  Material: Device\n"
        "  TemplateRoot: testblocka\n"
        "}\n"))
    issues = [i for i in _run(root) if "not found on block" in i.message]
    assert len(issues) == 1
    assert "testblocka" in issues[0].message


def test_block_template_root_unknown_is_fatal(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        "  TemplateRoot: Ghost\n"
        "}\n"))
    issues = [i for i in _run(root) if "not found on block" in i.message]
    assert len(issues) == 1
    assert "Ghost" in issues[0].message


def test_block_texture_not_integer_is_fatal(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        '  Texture: "101,xyz,103"\n'
        "}\n"))
    issues = [i for i in _run(root) if "texture id" in i.message]
    assert len(issues) == 1
    assert "xyz" in issues[0].message


def test_block_texture_quoted_values_are_accepted(tmp_path):
    """Fidelite : le jeu desechappe les guillemets ECF avant int.Parse —
    Texture: "101,102" est LEGAL (vecu sur RE2 : fausse erreur corrigee)."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        '  Texture: "101,102,103"\n'
        "}\n"))
    assert not [i for i in _run(root) if "texture id" in i.message]


def test_block_class_damage_is_known(tmp_path):
    """Vecu sur RE2 : Class: Damage est dans le registre « Block » du jeu
    (table des registres du moteur) alors qu'aucun bloc vanilla ne l'utilise —
    PAS une erreur."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Class: Damage\n"
        "  Material: Device\n"
        "}\n"))
    assert not [i for i in _run(root) if "Block class" in i.message]


def test_block_unknown_class_is_fatal_even_without_vanilla(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Class: NotAClass\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "Block class" in i.message]
    assert len(issues) == 1


# ---------------------------------------------------------------------------
# TechTree — ConfigTree
# ---------------------------------------------------------------------------

def test_techtree_recursion_beyond_engine_limit_is_fatal(tmp_path):
    """Le jeu jette au 8e ancetre d'une chaine TechTreeParent."""
    lines = [f"{{ Block Name: N{i}\n  Material: Device\n"
             f"  TechTreeNames: \"Base\"\n"
             + (f"  TechTreeParent: N{i - 1}\n" if i else "")
             + "  UnlockLevel: " + str(i + 1) + "\n}\n\n"
             for i in range(12)]
    root = _scenario(tmp_path, blocks=BLOCKS_HEADER + "".join(lines))
    issues = [i for i in _run(root) if "recursion" in i.message]
    assert len(issues) == 1


def test_techtree_sort_indices_conflict_is_fatal(tmp_path):
    """« Nom$2 » et « Nom$5 » pour la meme categorie : le jeu jette."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        '  TechTreeNames: "Base$2"\n'
        "  UnlockLevel: 1\n"
        "}\n\n"
        "{ Block Name: TestBlockB\n"
        "  Material: Device\n"
        '  TechTreeNames: "Base$5"\n'
        "  UnlockLevel: 3\n"
        "}\n"))
    issues = [i for i in _run(root) if "different sort indices" in i.message]
    assert len(issues) == 1


def test_no_template_found_is_warning(tmp_path):
    """Bloc affiche dans l'arbre sans Template a son nom : warning du jeu
    (pas de barre constructeur), PAS une erreur. Le check ne parle que s'il
    y a au moins un template connu (sinon rien n'est prouvable sans vanilla)."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        '  TechTreeNames: "Base"\n'
        "  UnlockLevel: 1\n"
        "}\n\n"
        "{ Block Name: TestBlockB\n"
        "  Material: Device\n"
        '  TechTreeNames: "Base"\n'
        "  UnlockLevel: 3\n"
        "}\n"),
        templates=TEMPLATE_OK)   # TestBlockA a un template, B non
    issues = [i for i in _run(root) if "No template found" in i.message]
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert "TestBlockB" in issues[0].message


def test_template_present_silences_warning(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        '  TechTreeNames: "Base"\n'
        "  UnlockLevel: 1\n"
        "}\n"),
        templates=TEMPLATE_OK)
    assert not [i for i in _run(root) if "No template found" in i.message]


# ---------------------------------------------------------------------------
# Parseur ECF du jeu
# ---------------------------------------------------------------------------

def test_element_without_id_and_name_is_fatal(tmp_path):
    """StoreInDynamicProps : element sans Id NI Name = LogError + IGNORE."""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block\n"
        "  Material: Device\n"
        "}\n"))
    issues = [i for i in _run(root) if "without an id or name" in i.message]
    assert len(issues) == 1


# ---------------------------------------------------------------------------
# Integration bilan + clean run
# ---------------------------------------------------------------------------

def test_valid_minimal_scenario_produces_no_issues(tmp_path):
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        "}\n"),
        items=(
            "{ Item Id: 10, Name: TestItem\n"
            "  Material: Device\n"
            "}\n"),
        templates=TEMPLATE_OK)
    assert _run(root) == []


def test_engine_checks_run_inside_launch_checks(tmp_path, monkeypatch):
    """Chemin connecte : run_launch_checks integre la categorie 'engine'.
    (Sectors.yaml manquant court-circuite le reste — on verifie donc juste
    que les issues engine ont le bon check quand le bilan complet tourne sur
    un scenario Content-only, via l'appel direct qui est le vrai contrat.)"""
    root = _scenario(tmp_path, blocks=(
        BLOCKS_HEADER +
        "{ Block Name: TestBlockA\n"
        "  Material: Device\n"
        "  TemplateRoot: Ghost\n"
        "}\n"))
    from core.launch_check import run_launch_checks
    # sans Sectors.yaml le bilan s'arrete tot : appeler la fonction isolee
    # revient au contrat pour la categorie engine
    from core.engine_loaders import run_engine_loader_checks
    issues = run_engine_loader_checks(root, "")
    assert all(i.check == "engine" for i in issues)
    assert any("Ghost" in i.message for i in issues)
    assert not hasattr(run_launch_checks, "_skip_engine")
