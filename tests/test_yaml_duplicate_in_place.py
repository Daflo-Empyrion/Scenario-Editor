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

"""Duplication SUR PLACE d'une entree YAML dans l'onglet copie de travail
(menu contextuel de l'arbre, avant resserve aux panneaux sources) -- ex:
decliner un POI 'Random' d'un playfield (demande utilisateur 18/10/2026).
Recherche par IDENTITE (is) : deux entrees au contenu identique ne sont
jamais confondues (YamlEntry = dataclass a egalite par valeur)."""
import pytest

from core import settings

PLAYFIELD_TEXT = (
    "POIs:\n"
    "  Random:\n"
    "    - Group: SpacePort\n"
    "      CountMinMax: 1\n"
    "      Pos: [ 100, 200, 300 ]\n"
    "    - Group: Defense\n"
    "      CountMinMax: 2\n"
)


def _make_widget(qapp, tmp_path, name, text):
    from gui.theme import apply_theme
    from gui.yaml_edit_widget import YamlEditWidget
    apply_theme(qapp)
    path = tmp_path / "Content" / "Playfields" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return YamlEditWidget(path)


def _random_children(widget):
    rnd = next(c for c in widget.doc.nodes[0].children if c.key == "Random")
    return rnd.children


def test_duplicate_poi_in_place(qapp, tmp_path):
    widget = _make_widget(qapp, tmp_path, "Playfield Static.yaml", PLAYFIELD_TEXT)
    rnd_children = _random_children(widget)
    spaceport = rnd_children[0]
    widget._duplicate_entry_in_place(spaceport)
    assert len(rnd_children) == 3
    clone = rnd_children[1]
    assert clone is not spaceport
    # l'identite du POI est la paire cle/valeur PROPRE de l'item de sequence
    # ('- Group: SpacePort'), CountMinMax/Pos sont des enfants
    assert clone.key == "Group"
    assert clone.value == "SpacePort"
    assert clone.get("CountMinMax") == "1"
    assert clone.get("Pos") == "[ 100, 200, 300 ]"
    # l'original garde sa place, Defense reste apres le clone
    assert rnd_children[0] is spaceport
    assert rnd_children[2].value == "Defense"
    out = widget.doc.render()
    assert out.count("Group: SpacePort") == 2
    assert widget._modified is True


def test_duplicate_identical_entries_never_confused(qapp, tmp_path):
    text = (
        "POIs:\n"
        "  Random:\n"
        "    - Group: Twin\n"
        "      CountMinMax: 1\n"
        "    - Group: Twin\n"
        "      CountMinMax: 1\n"
    )
    widget = _make_widget(qapp, tmp_path, "Playfield Static.yaml", text)
    rnd_children = _random_children(widget)
    original, twin = rnd_children[0], rnd_children[1]
    widget._duplicate_entry_in_place(original)
    # egalite PAR VALEUR : le clone doit s' inserer apres l'ORIGINAL (is),
    # pas apres le jumeau -- sinon la duplication pointerait le mauvais POI.
    assert rnd_children[0] is original
    assert rnd_children[1] is not original
    assert rnd_children[1] is not twin
    assert rnd_children[2] is twin


def test_duplicate_no_annotation_on_playfield(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "get_annotations_enabled", lambda: True)
    monkeypatch.setattr(settings, "get_author", lambda: "Daflo")
    widget = _make_widget(qapp, tmp_path, "Playfield Static.yaml", PLAYFIELD_TEXT)
    widget._duplicate_entry_in_place(_random_children(widget)[0])
    # le jeu affiche les commentaires des playfields : jamais d'annotation
    assert "Duplique par" not in widget.doc.render()


def test_duplicate_elsewhere_annotated_and_undo(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "get_annotations_enabled", lambda: True)
    monkeypatch.setattr(settings, "get_author", lambda: "Daflo")
    # HORS d'un dossier Playfields : la tracabilite standard s'applique
    from gui.theme import apply_theme
    from gui.yaml_edit_widget import YamlEditWidget
    apply_theme(qapp)
    path = tmp_path / "Other.yaml"
    path.write_text(PLAYFIELD_TEXT, encoding="utf-8")
    widget = YamlEditWidget(path)
    widget._duplicate_entry_in_place(_random_children(widget)[0])
    assert "Duplique par Daflo" in widget.doc.render()
    widget.undo()
    assert "Duplique par" not in widget.doc.render()
    assert len(_random_children(widget)) == 2
