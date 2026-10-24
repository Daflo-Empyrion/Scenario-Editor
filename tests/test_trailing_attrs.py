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

"""Attributs ECF de format (display/type/formatter) : ils vivent SUR LA LIGNE
de leur propriete parente ('UnlockCost: 30, display: true', 'Mass: 56000,
type: float, display: true, formatter: Kilogram' -- convention du corpus
BlocksConfig). Le dialogue '+ Propriete' doit les ATTACHER a la derniere
ligne du bloc, jamais les poser sur leur propre ligne (vecu 18/10/2026)."""
from core.ecf.block_creation import TRAILING_ATTR_KEYS, append_trailing_attrs
from core.ecf.model import EcfBlock, EcfProperty
from core.ecf.parser import parse_ecf_text

BLOCK_TEXT = (
    "{ Block Id: 1, Name: TestBlock\n"
    "  Mass: 56000, type: float, display: true, formatter: Kilogram\n"
    "  UnlockCost: 30\n"
    "}\n"
)


def _block_with(text):
    doc = parse_ecf_text(text)
    return next(n for n in doc.nodes if isinstance(n, EcfBlock))


def test_trailing_attr_keys_content():
    # Garde-fou : l'inventaire du corpus reel, rien de plus (Name/Ref traillants
    # sont des identites de ligne d'ouverture, JAMAIS des attributs de corps).
    assert TRAILING_ATTR_KEYS == {"display", "type", "formatter"}


def test_display_attaches_to_last_line():
    block = _block_with(BLOCK_TEXT)
    attached = append_trailing_attrs(block, "display", [("display", "true")])
    assert attached is not None
    assert "UnlockCost: 30, display: true" in block.render()
    # aucune nouvelle ligne creee : les enfants sont inchanges
    assert len([c for c in block.children if isinstance(c, EcfProperty)]) == 2


def test_formatter_and_type_bundle_attaches_too():
    block = _block_with(BLOCK_TEXT)
    assert append_trailing_attrs(
        block, "type", [("type", "int"), ("display", "true")]) is not None
    assert "UnlockCost: 30, type: int, display: true" in block.render()


def test_non_attr_key_and_empty_block_return_none():
    block = _block_with(BLOCK_TEXT)
    assert append_trailing_attrs(block, "CustomProp", [("CustomProp", "1")]) is None
    empty = _block_with("{ Block Id: 2, Name: Vide\n}\n")
    assert append_trailing_attrs(empty, "display", [("display", "true")]) is None


def test_widget_property_add_wiring(qapp, tmp_path):
    """Chemin connecte du dialogue '+ Propriete' (_apply_property_pairs) :
    display rejoint la ligne UnlockCost, une cle normale reste sur sa ligne."""
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)
    path = tmp_path / "BlocksConfig.ecf"
    path.write_text(BLOCK_TEXT, encoding="utf-8")
    widget = EcfEditWidget(path)
    widget._current_block = widget.doc.nodes[0]
    widget._apply_property_pairs("display", [("display", "true")])
    widget._apply_property_pairs("CustomProp", [("CustomProp", "1")])
    out = widget.doc.render()
    assert "UnlockCost: 30, display: true" in out
    assert "\n  CustomProp: 1" in out          # sa propre ligne
    assert widget._modified is True


def test_insert_property_after_core():
    from core.ecf.model import insert_property_after
    block = _block_with(BLOCK_TEXT)
    anchor = next(c for c in block.children
                  if isinstance(c, EcfProperty) and c.pairs[0][0] == "UnlockCost")
    insert_property_after(block, anchor, [("UnlockLevel", "25")])
    keys = [c.pairs[0][0] for c in block.children if isinstance(c, EcfProperty)]
    assert keys == ["Mass", "UnlockCost", "UnlockLevel"]
    assert "UnlockCost: 30\n  UnlockLevel: 25" in block.render()


def test_move_property_up_down_core():
    from core.ecf.model import move_property
    block = _block_with(BLOCK_TEXT)
    unlock = next(c for c in block.children
                  if isinstance(c, EcfProperty) and c.pairs[0][0] == "UnlockCost")
    assert move_property(block, unlock, -1) is True
    keys = [c.pairs[0][0] for c in block.children if isinstance(c, EcfProperty)]
    assert keys == ["UnlockCost", "Mass"]
    assert move_property(block, unlock, -1) is False      # deja en tete
    assert move_property(block, unlock, +1) is True       # retour
    keys = [c.pairs[0][0] for c in block.children if isinstance(c, EcfProperty)]
    assert keys == ["Mass", "UnlockCost"]


def test_move_keeps_comments_in_place():
    from core.ecf.model import move_property
    block = _block_with(
        "{ Block Id: 1\n"
        "  A: 1\n"
        "  # note\n"
        "  B: 2\n"
        "}\n")
    prop_b = next(c for c in block.children
                  if isinstance(c, EcfProperty) and c.pairs[0][0] == "B")
    assert move_property(block, prop_b, -1) is True
    kinds = [(type(c).__name__, c.pairs[0][0] if isinstance(c, EcfProperty) else None)
             for c in block.children]
    assert kinds == [("EcfProperty", "B"), ("EcfComment", None), ("EcfProperty", "A")]


def test_widget_menu_helpers_add_below_attribute_move(qapp, tmp_path):
    """Chemins connectes du menu contextuel : 'Ajouter une propriete en
    dessous' (ancre), 'Ajouter un attribut' (ligne cliquee, sans jamais
    dupliquer une cle deja presente) et 'Monter cette ligne'."""
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)
    path = tmp_path / "BlocksConfig.ecf"
    path.write_text(BLOCK_TEXT, encoding="utf-8")
    widget = EcfEditWidget(path)
    widget._current_block = widget.doc.nodes[0]

    def _props():
        return [c for c in widget._current_block.children if isinstance(c, EcfProperty)]

    # ajouter EN DESSOUS de Mass (ancre du menu contextuel)
    mass = _props()[0]
    widget._pending_anchor = mass
    widget._apply_property_pairs("UnlockLevel", [("UnlockLevel", "25")])
    assert [c.pairs[0][0] for c in _props()] == ["Mass", "UnlockLevel", "UnlockCost"]
    assert widget._pending_anchor is None                 # ancre consommee
    # attribut sur la ligne CLIQUEE : cle absente -> ajoutee en fin de ligne ;
    # cle deja presente -> REMPLACEE (bascule display true<->false), jamais
    # dupliquee
    widget._apply_attribute_pairs(mass, [("display", "false")])
    assert "Mass: 56000, type: float, display: false, formatter: Kilogram" \
        in widget.doc.render()
    widget._apply_attribute_pairs(mass, [("display", "true")])
    assert [k for k, _v in mass.pairs] == ["Mass", "type", "display", "formatter"]
    assert "Mass: 56000, type: float, display: true, formatter: Kilogram" \
        in widget.doc.render()
    # deplacer UnlockLevel vers le haut
    unlock_level = _props()[1]
    widget._move_property_action(unlock_level, -1)
    assert [c.pairs[0][0] for c in _props()] == ["UnlockLevel", "Mass", "UnlockCost"]
    # sous-menu 'Ajouter un attribut' : presets + valeurs observees du fichier
    entries = widget._observed_trailing_attrs()
    assert ("display", "true") in entries
    assert ("formatter", "Kilogram") in entries


def test_add_property_button_click_never_passes_checked(qapp, tmp_path, monkeypatch):
    """Vecu 20/10 : clicked() de QPushButton passe l'etat coche (bool), avale
    par le parametre anchor_prop -> _pending_anchor=False -> AttributeError
    'bool' object has no attribute 'indent'. Le clic du bouton (chemin reel
    du signal) et l'appel direct simulant l'ancien cablage doivent laisser
    l'ancre a None, sans lever."""
    from PyQt6.QtWidgets import QDialog
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)
    path = tmp_path / "BlocksConfig.ecf"
    path.write_text(BLOCK_TEXT, encoding="utf-8")
    widget = EcfEditWidget(path)
    widget._current_block = widget.doc.nodes[0]
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    widget.btn_add_prop.click()            # signal reel (lambda sans argument)
    assert widget._pending_anchor is None
    widget._add_property_dialog(False)     # simulation signal non filtre
    assert widget._pending_anchor is None
    widget._add_property_dialog(True)
    assert widget._pending_anchor is None
