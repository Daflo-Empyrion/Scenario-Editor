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

"""Resolution recursive des dependances ECF (demande 22/10) : recette,
ingredients, Ref, TechTreeParent, icone, localisation, anti-cycle, et
separation import / deja present / non importable."""
from core.ecf.dependencies import resolve

BLOCKS = """{ +Block Name: HyperDrive
  Category: Devices
  TechTreeParent: HyperCore
  CustomIcon: iconHD
  Info: HyperDriveInfo
  TechTreeNames: Base,AsgardTech
}
"""

ITEMS = """{ +Item Id: 1, Name: HyperCore, Ref: BaseItem
  Info: HyperCoreInfo
}

{ +Item Id: 2, Name: BaseItem
  Mass: 1
}
"""

TEMPLATES = """{ +Template Name: HyperDrive
  OutputCount: 1
  { Child Inputs
    HyperCore: 5
  }
}

{ +Template Name: HyperCore
  { Child Inputs
    BaseItem: 2
  }
}
"""

GROUPS = """{ BlockGroup Name: HDGroup
  MaxCount: 1
  Blocks: "HyperDrive"
}
"""

LOC = "KEY,English\nHyperDriveInfo,Drive\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _source(tmp_path):
    b = tmp_path / "b"
    cfg = b / "Content" / "Configuration"
    _write(cfg / "BlocksConfig.ecf", BLOCKS)
    _write(cfg / "ItemsConfig.ecf", ITEMS)
    _write(cfg / "Templates.ecf", TEMPLATES)
    _write(cfg / "BlockGroupsConfig.ecf", GROUPS)
    _write(b / "Extras" / "Localization.csv", LOC)
    icon = b / "SharedData" / "Content" / "Bundles" / "ItemIcons" / "iconHD.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_bytes(b"\x89PNG")
    return b


def test_resolve_follows_recipe_ingredients_ref_icon_and_csv(tmp_path):
    b = _source(tmp_path)
    result = resolve(b, "Content/Configuration/BlocksConfig.ecf", "HyperDrive")
    targets = [entry["target"] for entry in result.imports]
    assert "Content/Configuration/BlocksConfig.ecf#HyperDrive" in targets
    assert "Content/Configuration/Templates.ecf#HyperDrive" in targets
    assert "Content/Configuration/Templates.ecf#HyperCore" in targets
    assert "Content/Configuration/ItemsConfig.ecf#HyperCore" in targets
    assert "Content/Configuration/ItemsConfig.ecf#BaseItem" in targets
    assert "SharedData/Content/Bundles/ItemIcons/iconHD.png" in targets
    assert "Extras/Localization.csv" in targets
    assert not result.truncated


def test_resolve_reports_what_cannot_be_imported(tmp_path):
    b = _source(tmp_path)
    result = resolve(b, "Content/Configuration/BlocksConfig.ecf", "HyperDrive")
    kinds = {(item.kind, item.ref) for item in result.unresolved}
    # cle de localisation absente du CSV du scenario source
    assert ("localization", "HyperCoreInfo") in kinds
    # l'arbre technologique n'est PAS une dependance (ni un bruit)
    assert not any(kind == "techtree" for kind, _ref in kinds)


def test_resolve_marks_already_present_entities(tmp_path):
    b = _source(tmp_path)
    working = tmp_path / "working"
    _write(working / "Content" / "Configuration" / "ItemsConfig.ecf",
           "{ +Item Id: 2, Name: BaseItem\n}\n")
    result = resolve(b, "Content/Configuration/BlocksConfig.ecf", "HyperDrive",
                     working)
    targets = [entry["target"] for entry in result.imports]
    assert "Content/Configuration/ItemsConfig.ecf#BaseItem" not in targets
    present = [entry["target"] for entry in result.present]
    assert "Content/Configuration/ItemsConfig.ecf#BaseItem" in present


def test_resolve_stops_on_cycles(tmp_path):
    b = tmp_path / "b"
    cfg = b / "Content" / "Configuration"
    _write(cfg / "BlocksConfig.ecf",
           "{ +Block Name: A\n  Ref: B\n}\n"
           "{ +Block Name: B\n  Ref: A\n}\n")
    result = resolve(b, "Content/Configuration/BlocksConfig.ecf", "A")
    targets = [entry["target"] for entry in result.imports]
    assert targets == ["Content/Configuration/BlocksConfig.ecf#B",
                       "Content/Configuration/BlocksConfig.ecf#A"] or \
        sorted(targets) == [
            "Content/Configuration/BlocksConfig.ecf#A",
            "Content/Configuration/BlocksConfig.ecf#B"]
