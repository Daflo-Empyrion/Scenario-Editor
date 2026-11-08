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


def test_entry_without_comment_gets_glossary_tooltip(yaml_widget_with_comments):
    """Cle sans commentaire mais connue du glossaire general : l'infobulle
    vient du glossaire (extension du contrat 'jamais invente' : le glossaire
    est une donnee verifiee, pas une invention)."""
    widget = yaml_widget_with_comments
    root_count = widget.tree.topLevelItemCount()
    found = False
    for i in range(root_count):
        item = widget.tree.topLevelItem(i)
        if item.text(0) == "PlanetClass":
            found = True
            assert "PlanetClass" in item.toolTip(0)
    assert found


def test_entry_unknown_to_glossary_and_comment_has_no_tooltip(qapp, tmp_path):
    """Cle inconnue du glossaire ET sans commentaire : aucune infobulle
    (mieux vaut rien qu'une explication inventee)."""
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "playfield_unknown_key.yaml"
    lines = ["PlayfieldType: Planet", "ZzzCleYamlInconnue: 42"]
    path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    widget = YamlEditWidget(path)
    found = False
    for i in range(widget.tree.topLevelItemCount()):
        item = widget.tree.topLevelItem(i)
        if item.text(0) == "ZzzCleYamlInconnue":
            found = True
            assert item.toolTip(0) == ""
    assert found


def test_fallback_to_general_glossary_without_comment(qapp, tmp_path):
    """Cle sans commentaire dans le fichier mais connue du glossaire general
    (scope YAML par nom de fichier playfield*) : infobulle posee quand meme."""
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "playfield_glossary_test.yaml"
    lines = ["PlanetClass: Temperate", "SeaLevel: 45"]
    path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    widget = YamlEditWidget(path)
    found = False
    for i in range(widget.tree.topLevelItemCount()):
        item = widget.tree.topLevelItem(i)
        if item.text(0) == "SeaLevel":
            found = True
            tip = item.toolTip(0)
            assert "SeaLevel" in tip
            assert "mer" in tip.lower() or "sea" in tip.lower()
    assert found, "entree SeaLevel non trouvee"


def test_file_explanation_label_for_known_yaml(qapp, tmp_path):
    """Les YAML connus du glossaire (playfield*) affichent la ligne
    d'explication de fichier."""
    from gui.yaml_edit_widget import YamlEditWidget
    path = tmp_path / "playfield_desc_test.yaml"
    path.write_text("PlayfieldType: Planet" + chr(10), encoding="utf-8")
    widget = YamlEditWidget(path)
    labels = [l.text() for l in widget.findChildren(type(widget.search_status))
              if "glossaire" in l.text().lower() or "This file" in l.text()
              or "Ce fichier" in l.text()]
    assert labels, "ligne d'explication de fichier absente"
