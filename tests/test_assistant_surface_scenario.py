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

"""Outils de lecture du scenario : inventaire, recherche litterale, lecture
de lignes, bloc ECF d'un autre fichier. Confinement a la racine et bornes."""
import pytest

from core.ai.assistant.surfaces import scenario
from core.ai.assistant.tools import ToolRegistry

BLOCK_GROUP = """{ BlockGroup Name: LightWeaponsSmall
  MaxCount: 16
  Blocks: WeaponSV01,WeaponSV02
}
"""

USER_ECF = """{ Entity Id: 500, Name: TestShip
  BlockGroups: LightWeaponsSmall
}
"""

PLAYFIELD = """Version: 1
BlockGroup: LightWeaponsSmall
"""


@pytest.fixture()
def root(tmp_path):
    (tmp_path / "Content" / "Configuration").mkdir(parents=True)
    (tmp_path / "Playfields" / "SectorA").mkdir(parents=True)
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "Sectors").mkdir()
    (tmp_path / "Sectors" / "Sectors.yaml").write_text(
        'Sectors:\n'
        '  HomeSystem:\n'
        '    Name: Home\n'
        '    Coordinates: "0,0,0"\n',
        encoding="utf-8")
    (tmp_path / "Content" / "Configuration" / "ItemsConfig.ecf").write_text(
        '{ Item Id: 100, Name: IronOre\n'
        '  Category: Raw Materials\n'
        '  MarketPrice: 12\n'
        '}\n', encoding="utf-8")
    (tmp_path / "Content" / "Configuration" / "BlocksConfig.ecf").write_text(
        '{ Block Id: 200, Name: ConcreteBlocks\n'
        '  Category: Building\n'
        '  MarketPrice: 5\n'
        '}\n', encoding="utf-8")
    (tmp_path / "Content" / "Configuration" / "BlockGroupsConfig.ecf"
     ).write_text(BLOCK_GROUP, encoding="utf-8")
    (tmp_path / "Content" / "Configuration" / "EntityConfig.ecf"
     ).write_text(USER_ECF, encoding="utf-8")
    (tmp_path / "Playfields" / "SectorA" / "SectorA.yaml"
     ).write_text(PLAYFIELD, encoding="utf-8")
    (tmp_path / ".hidden" / "secret.txt").write_text(
        "LightWeaponsSmall", encoding="utf-8")
    return tmp_path


def _tools(root, surface="ecf"):
    tools = ToolRegistry()
    scenario.add_tools(tools, root, surface)
    return tools


def _json(result):
    return result["content"]


def test_tools_are_registered_under_the_active_surface(root):
    tools = _tools(root)
    assert tools.names() == ["catalog_search", "file_read",
                             "scenario_balance_report", "scenario_find",
                             "scenario_list_files", "scenario_read_block",
                             "yaml_list_entries", "yaml_read_entry"]
    assert tools.schemas("csv") == []


def test_list_files_skips_hidden_folders_and_filters(root):
    tools = _tools(root)
    listing = _json(tools.call("scenario_list_files", {}))
    assert "Content/Configuration/EntityConfig.ecf" in listing
    assert "secret.txt" not in listing
    filtered = _json(tools.call("scenario_list_files", {"pattern": "yaml"}))
    assert "SectorA.yaml" in filtered and "EntityConfig.ecf" not in filtered
    assert "no file matching" in _json(
        tools.call("scenario_list_files", {"pattern": "zzz"}))


def test_find_reports_path_line_and_text(root):
    tools = _tools(root)
    found = _json(tools.call("scenario_find", {"text": "lightweaponssmall"}))
    assert "EntityConfig.ecf" in found and "SectorA.yaml" in found
    assert "BlockGroupsConfig.ecf" in found
    assert '"line": 2' in found
    only_yaml = _json(tools.call("scenario_find",
                                 {"text": "LightWeaponsSmall",
                                  "extension": "yaml"}))
    assert "SectorA.yaml" in only_yaml
    assert "EntityConfig.ecf" not in only_yaml


def test_find_reports_absence_and_missing_parameter(root):
    tools = _tools(root)
    assert "missing parameter 'text'" in _json(
        tools.call("scenario_find", {}))
    assert "no occurrence" in _json(
        tools.call("scenario_find", {"text": "Introuvable"}))


def test_file_read_returns_a_numbered_window(root):
    tools = _tools(root)
    window = _json(tools.call("file_read", {
        "path": "Playfields/SectorA/SectorA.yaml", "start": 2, "count": 1}))
    assert '"n": 2' in window and "BlockGroup: LightWeaponsSmall" in window
    assert "Version" not in window


def test_file_read_refuses_paths_outside_the_scenario(root, tmp_path):
    tools = _tools(root)
    assert "outside the scenario" in _json(
        tools.call("file_read", {"path": "../outside.txt"}))
    assert "outside the scenario" in _json(
        tools.call("file_read", {"path": str(tmp_path.parent / "x.txt")}))
    assert "file not found" in _json(
        tools.call("file_read", {"path": "Content/Nope.ecf"}))


def test_read_block_reaches_another_ecf_file(root):
    tools = _tools(root)
    block = _json(tools.call("scenario_read_block", {
        "path": "Content/Configuration/BlockGroupsConfig.ecf",
        "ident": "LightWeaponsSmall"}))
    assert "MaxCount: 16" in block and "WeaponSV01" in block
    assert "not an ECF file" in _json(tools.call("scenario_read_block", {
        "path": "Playfields/SectorA/SectorA.yaml", "ident": "X"}))
    assert "no block with ident" in _json(tools.call(
        "scenario_read_block", {
            "path": "Content/Configuration/BlockGroupsConfig.ecf",
            "ident": "Nope"}))


def test_catalog_search_finds_items_and_blocks(root):
    tools = _tools(root)
    found = _json(tools.call("catalog_search", {"text": "iron"}))
    assert '"name": "IronOre"' in found and '"source": "item"' in found
    blocks = _json(tools.call("catalog_search", {"query": "building"}))
    assert "ConcreteBlocks" in blocks and '"source": "block"' in blocks
    assert "no catalog entry" in _json(
        tools.call("catalog_search", {"text": "zzz"}))


def test_yaml_entries_and_read_by_path(root):
    tools = _tools(root)
    listing = _json(tools.call("yaml_list_entries", {
        "path": "Sectors/Sectors.yaml"}))
    assert "Sectors.HomeSystem.Name" in listing
    entry = _json(tools.call("yaml_read_entry", {
        "path": "Sectors/Sectors.yaml", "keys": "Sectors.HomeSystem.Name"}))
    assert '"value": "Home"' in entry
    parent = _json(tools.call("yaml_read_entry", {
        "path": "Sectors/Sectors.yaml", "keys": "Sectors.HomeSystem"}))
    assert '"key": "Coordinates"' in parent
    assert "not found" in _json(tools.call("yaml_read_entry", {
        "path": "Sectors/Sectors.yaml", "keys": "Sectors.Nope"}))
    assert "missing parameter 'keys'" in _json(tools.call(
        "yaml_read_entry", {"path": "Sectors/Sectors.yaml"}))


def test_with_scenario_tools_extends_a_binding(root):
    from core.ai.assistant.context import TabContext
    from core.ai.assistant.surfaces.base import (SurfaceBinding,
                                                 with_scenario_tools)

    def empty():
        return ToolRegistry()

    binding = SurfaceBinding(name="ecf", context=lambda: TabContext("x", ""),
                             registry=empty, apply=lambda changes: (True, ""))
    merged = with_scenario_tools(binding, root)
    names = merged.registry().names("ecf")
    assert "scenario_find" in names and "scenario_read_block" in names
    assert "catalog_search" in names and "yaml_read_entry" in names
    assert "scenario_find" in merged.instruction
    assert merged.context().label == "x"
    assert merged.apply([]) == (True, "")
    assert merged.action().needs_tools is True


def _source_b(tmp_path):
    """Scenario B minimal : un bloc absent de la copie de travail, reference
    par un autre fichier (candidat de dependance)."""
    b = tmp_path / "b"
    (b / "Content" / "Configuration").mkdir(parents=True)
    (b / "Content" / "Configuration" / "BlocksConfig.ecf").write_text(
        '{ Block Id: 900, Name: HyperDrive\n'
        '  HitPoints: 42\n'
        '}\n', encoding="utf-8")
    (b / "Content" / "Configuration" / "Templates.ecf").write_text(
        '{ Template Name: ShipOnlyInB\n'
        '  BlockGroups: HyperDrive\n'
        '}\n\n'
        '{ +Template Name: HyperDrive\n'
        '  { Child Inputs\n'
        '    HyperCore: 5\n'
        '  }\n'
        '}\n', encoding="utf-8")
    (b / "Content" / "Configuration" / "ItemsConfig.ecf").write_text(
        '{ +Item Id: 1, Name: HyperCore\n'
        '  Mass: 1\n'
        '}\n', encoding="utf-8")
    return b


def test_scope_b_lists_and_reads_the_source_scenario(root, tmp_path):
    b = _source_b(tmp_path)
    tools = ToolRegistry()
    scenario.add_tools(tools, root, "ecf", {"b": b})
    listing = _json(tools.call("scenario_list_files", {"scope": "b"}))
    assert "BlocksConfig.ecf" in listing and "Templates.ecf" in listing
    block = _json(tools.call("scenario_read_block", {
        "scope": "b", "path": "Content/Configuration/BlocksConfig.ecf",
        "ident": "900"}))
    assert "HyperDrive" in block and "HitPoints: 42" in block
    working = _json(tools.call("scenario_read_block", {
        "path": "Content/Configuration/BlocksConfig.ecf", "ident": "900"}))
    assert "no block with ident" in working
    assert "unknown scope" in _json(tools.call(
        "scenario_list_files", {"scope": "zzz"}))


def test_merge_plan_reports_block_status_and_suggested_changes(root,
                                                              tmp_path):
    b = _source_b(tmp_path)
    tools = ToolRegistry()
    scenario.add_tools(tools, root, "ecf", {"b": b})
    plan = _json(tools.call("scenario_merge_plan", {
        "source": "b", "path": "Content/Configuration/BlocksConfig.ecf",
        "ident": "900"}))
    assert '"status": "added"' in plan
    assert '"kind": "scenario_import"' in plan
    # UNE ligne a recopier : l'apply resout le graphe
    assert ('"target": "b:Content/Configuration/BlocksConfig.ecf#900+deps"'
            in plan)
    # recette et ingredient suivis recursivement (affichage du plan)
    assert "Templates.ecf#HyperDrive" in plan
    assert "ItemsConfig.ecf#HyperCore" in plan
    assert '"unresolved"' in plan


def test_merge_plan_for_a_folder_lists_files_and_dependencies(root,
                                                              tmp_path):
    b = _source_b(tmp_path)
    (b / "Playfields" / "SectorB").mkdir(parents=True)
    (b / "Playfields" / "SectorB" / "Playfield.yaml").write_text(
        "Version: 1\n", encoding="utf-8")
    (b / "Sectors").mkdir()
    (b / "Sectors" / "Sectors.yaml").write_text(
        "Sectors:\n"
        "  NewSystem:\n"
        '    - ["0,0,0", NewPF, SectorB]\n',
        encoding="utf-8")
    tools = ToolRegistry()
    scenario.add_tools(tools, root, "ecf", {"b": b})
    plan = _json(tools.call("scenario_merge_plan", {
        "source": "b", "path": "Sectors"}))
    assert '"action": "merge_folder"' in plan
    assert "Sectors.yaml" in plan
    assert "Playfields/SectorB/Playfield.yaml" in plan


def test_import_instruction_only_appears_with_a_source_scenario(root,
                                                                tmp_path):
    from core.ai.assistant.context import TabContext
    from core.ai.assistant.surfaces.base import (SurfaceBinding,
                                                 with_scenario_tools)

    binding = SurfaceBinding(name="ecf", context=lambda: TabContext("x", ""),
                             registry=ToolRegistry,
                             apply=lambda changes: (True, ""))
    assert "scenario_merge_plan" not in with_scenario_tools(
        binding, root).instruction
    merged = with_scenario_tools(binding, root, {"b": _source_b(tmp_path)})
    assert "scenario_merge_plan" in merged.instruction
    assert "scenario_import" in merged.instruction


def test_with_scenario_tools_keeps_the_expand_hook(root):
    from core.ai.assistant.context import TabContext
    from core.ai.assistant.surfaces.base import (SurfaceBinding,
                                                 with_scenario_tools)

    expand = lambda changeset: changeset
    binding = SurfaceBinding(name="ecf", context=lambda: TabContext("x", ""),
                             registry=ToolRegistry,
                             apply=lambda changes: (True, ""), expand=expand)
    merged = with_scenario_tools(binding, root)
    assert merged.expand is expand
