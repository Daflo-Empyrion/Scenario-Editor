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

"""Tests des infobulles de l'editeur YAML (gui/yaml_edit_widget.py) --
basees sur les VRAIS commentaires de fin de ligne presents dans le fichier
ouvert (YamlEntry.comment), jamais une explication inventee."""
import pytest


@pytest.fixture
def yaml_widget_with_comments(qapp, tmp_path):
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "playfield_test.yaml"
    path.write_text(
        "PlanetClass: Temperate\n"
        "Difficulty: 2  # 1=facile, 2=normal, 3=difficile, 4=tres difficile, 5=extreme\n"
        "PlayfieldType: Planet\n",
        encoding="utf-8",
    )
    return YamlEditWidget(path)


def test_entry_with_comment_gets_tooltip(yaml_widget_with_comments):
    widget = yaml_widget_with_comments
    root_count = widget.tree.topLevelItemCount()
    found = False
    for i in range(root_count):
        item = widget.tree.topLevelItem(i)
        if item.text(0) == "Difficulty":
            found = True
            assert item.toolTip(0) != ""
            assert "extreme" in item.toolTip(0)
    assert found


def test_entry_without_comment_has_no_tooltip(yaml_widget_with_comments):
    widget = yaml_widget_with_comments
    root_count = widget.tree.topLevelItemCount()
    found = False
    for i in range(root_count):
        item = widget.tree.topLevelItem(i)
        if item.text(0) == "PlanetClass":
            found = True
            assert item.toolTip(0) == ""
    assert found
