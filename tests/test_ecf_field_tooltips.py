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

"""Tests de core.ecf.model.find_first_inline_comment_for_key -- repli des
infobulles de colonne/propriete (voir gui/ecf_edit_widget.py::_field_tooltip)
quand le glossaire manuel (core/ecf_header_glossary.py) ne couvre pas un
champ precis : cherche un vrai commentaire dans le fichier ouvert plutot
que d'inventer une explication."""
from core.ecf.parser import parse_ecf_text
from core.ecf.model import find_first_inline_comment_for_key


def test_finds_comment_on_child_property_line():
    text = (
        "{ Block Id: 1, Name: TestBlock\n"
        "  Material: Concrete  # materiau physique du bloc\n"
        "  XpFactor: 2.0\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    assert find_first_inline_comment_for_key(doc, "Material") == "materiau physique du bloc"


def test_returns_none_when_no_comment():
    text = "{ Block Id: 1, Name: TestBlock\n  XpFactor: 2.0\n}\n"
    doc = parse_ecf_text(text)
    assert find_first_inline_comment_for_key(doc, "XpFactor") is None


def test_returns_none_for_unknown_key():
    text = "{ Block Id: 1, Name: TestBlock\n  Material: Concrete  # un commentaire\n}\n"
    doc = parse_ecf_text(text)
    assert find_first_inline_comment_for_key(doc, "CleInexistante") is None


def test_finds_comment_on_block_opening_line():
    text = "{ Block Id: 1, Name: TestBlock  # bloc de test\n  Material: Concrete\n}\n"
    doc = parse_ecf_text(text)
    assert find_first_inline_comment_for_key(doc, "Id") == "bloc de test"


def test_finds_comment_in_nested_child_block():
    text = (
        "{ Block Id: 1, Name: TestBlock\n"
        "  { Child DropOnDestroy\n"
        "    Item: IronOre  # objet largue a la destruction\n"
        "  }\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    assert find_first_inline_comment_for_key(doc, "Item") == "objet largue a la destruction"


def test_returns_first_match_when_multiple_comments_exist():
    """Doit retourner le PREMIER commentaire trouve, pas le dernier --
    coherent avec le fichier lu de haut en bas."""
    text = (
        "{ Block Id: 1, Name: A\n"
        "  Material: Concrete  # premier commentaire\n"
        "}\n"
        "{ Block Id: 2, Name: B\n"
        "  Material: Steel  # second commentaire\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    assert find_first_inline_comment_for_key(doc, "Material") == "premier commentaire"
