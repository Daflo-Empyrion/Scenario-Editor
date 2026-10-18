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

"""Pas d'annotation '# original: ... -- Mod par' ni '# Ajoute par' sur les
yamls de PLAYFIELD : le jeu relit ces fichiers sans retirer les commentaires
et leur texte se retrouve AFFICHE en jeu, en surimpression sur la valeur
(vecu sur la Description modifiee ; demande utilisateur 18/10/2026).
Les autres yaml gardent la tracabilite."""
import pytest

from core import settings


@pytest.fixture
def annotate_on(monkeypatch):
    monkeypatch.setattr(settings, "get_annotations_enabled", lambda: True)
    monkeypatch.setattr(settings, "get_author", lambda: "Daflo")


def _make_widget(qapp, tmp_path, rel):
    from gui.theme import apply_theme
    from gui.yaml_edit_widget import YamlEditWidget
    apply_theme(qapp)
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "Description: Texte original\n"
        "PlanetClass: Temperate\n",
        encoding="utf-8")
    return YamlEditWidget(path)


def _select_first(widget):
    item = widget.tree.topLevelItem(0)
    widget.tree.setCurrentItem(item)
    widget._on_entry_selected(item, 0)


def test_playfield_yaml_edited_value_has_no_annotation(qapp, tmp_path, annotate_on):
    widget = _make_widget(qapp, tmp_path, "Content/Playfields/Akua/Playfield.yaml")
    assert widget._annotations_enabled_for_file() is False
    _select_first(widget)
    widget.value_edit.setPlainText("Nouveau texte")
    widget._apply_value()
    out = widget.doc.render()
    assert "Nouveau texte" in out
    assert "Mod par" not in out
    assert widget._modified is True


def test_other_yaml_keeps_annotation(qapp, tmp_path, annotate_on):
    widget = _make_widget(qapp, tmp_path, "Content/Configuration/GalaxyConfig.yaml")
    assert widget._annotations_enabled_for_file() is True
    _select_first(widget)
    widget.value_edit.setPlainText("Nouveau texte")
    widget._apply_value()
    assert "Mod par" in widget.doc.render()


def test_playfield_yaml_added_entry_has_no_annotation(qapp, tmp_path, annotate_on, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog
    widget = _make_widget(qapp, tmp_path, "Content/Playfields/Akua/Playfield.yaml")
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("NewKey", True)))
    widget._add_entry_dialog()
    out = widget.doc.render()
    assert "NewKey" in out
    assert "Ajoute par" not in out
