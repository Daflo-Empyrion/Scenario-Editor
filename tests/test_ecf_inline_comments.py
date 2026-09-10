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

"""Tests des commentaires /* ... */ INLINE en fin de ligne de propriete ou
d'entete de bloc. Avant le correctif du 10/09/2026, seul '#' etait reconnu
en fin de ligne : le commentaire restait dans la valeur et la moindre
virgule qu'il contenait (ex 'true,animals') declenchait un faux E004
"virgule non protegee" (signale sur RE2 EVO / FactionWarfare.ecf)."""

from pathlib import Path

from core.ecf.model import EcfBlock, EcfComment, EcfProperty
from core.ecf.parser import parse_ecf_file, parse_ecf_text
from core.ecf.validation import validate_document

# Lignes calquees sur le fichier RE2 EVO a l'origine du signalement.
RE2_SNIPPET = (
    "{ ElementUnit\n"
    "{\n"
    "   CommandPointsPerLevel: 1 /* price per level,final price = CommandPointsLv1"
    " + level * CommandPointsPerLevel */\n"
    "   SpawnInSameDirection: false /* if true,animals will spawn all in"
    " approximately_same direction */\n"
    "}\n"
)


def _all_properties(doc):
    """Toutes les proprietes, tous niveaux d'imbrication."""
    found = []

    def walk(nodes):
        for node in nodes:
            if isinstance(node, EcfBlock):
                for child in node.children:
                    if isinstance(child, EcfProperty):
                        found.append(child)
                    elif isinstance(child, EcfBlock):
                        walk([child])

    walk(doc.nodes)
    return found


def _find_property(doc, key):
    for prop in _all_properties(doc):
        if prop.get(key) is not None:
            return prop
    return None


def test_inline_comment_split_from_value():
    doc = parse_ecf_text(RE2_SNIPPET)
    points = _find_property(doc, 'CommandPointsPerLevel')
    spawn = _find_property(doc, 'SpawnInSameDirection')
    assert points.get('CommandPointsPerLevel') == '1'
    assert points.comment is not None and points.comment.startswith('/*')
    assert '*/' in points.comment
    assert spawn.get('SpawnInSameDirection') == 'false'
    assert 'animals' in spawn.comment
    # aucune paire orpheline (cle=None) dans les proprietes : le commentaire
    # n'est plus eclate en fausse valeur
    for prop in (points, spawn):
        assert all(key is not None for key, _ in prop.pairs)


def test_inline_comment_no_ghost_E004():
    doc = parse_ecf_text(RE2_SNIPPET)
    codes = [issue.code for issue in validate_document(doc)]
    assert 'E004' not in codes


def test_real_unquoted_comma_still_flagged():
    text = (
        "{ Block Test\n"
        "{\n"
        "   SizeBlocks: 4,7\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    codes = [issue.code for issue in validate_document(doc)]
    assert codes.count('E004') == 1  # le vrai cas reste detecte


def test_inline_comment_on_block_header():
    text = (
        "{ +Container Id: 5 /* groups,respawn */\n"
        "{\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    block = doc.find_block_by_identity('+Container', '5')
    assert block is not None
    assert 'groups,respawn' in (block.comment or '')


def test_unclosed_inline_comment_consumes_following_lines():
    text = (
        "{ Block Test\n"
        "{\n"
        "   Key: value /* blah multi\n"
        "   lignes, avec virgules */\n"
        "   Other: 2\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    root = next(n for n in doc.nodes if isinstance(n, EcfBlock))
    # "{ Block Test" est suivi d'une ligne "{" : les proprietes vivent dans
    # le bloc anonyme imbrique
    inner = next(n for n in root.children if isinstance(n, EcfBlock))
    children = inner.children
    # ligne 1 : propriete avec commentaire NON ferme -> ouvre un
    # commentaire multi-lignes
    key_prop = children[0]
    assert isinstance(key_prop, EcfProperty)
    assert key_prop.get('Key') == 'value'
    assert key_prop.comment == '/* blah multi'
    # ligne 2 : suite du commentaire, jamais interpretee comme structure
    assert isinstance(children[1], EcfComment)
    assert 'virgules' in children[1].raw
    # ligne 3 : le commentaire etant ferme, la lecture reprend normalement
    other = children[2]
    assert isinstance(other, EcfProperty)
    assert other.get('Other') == '2'


def test_quoted_slash_star_is_not_a_comment():
    text = (
        "{ Block Test\n"
        "{\n"
        "   Name: \"a/*pasuncommentaire*/b\"\n"
        "}\n"
    )
    doc = parse_ecf_text(text)
    prop = _find_property(doc, 'Name')
    assert prop.get('Name') == '"a/*pasuncommentaire*/b"'
    assert prop.comment is None


def test_roundtrip_byte_perfect_with_inline_comments(tmp_path):
    # CRLF + BOM + espacements irreguliers : le round-trip d'un fichier NON
    # modifie reste byte-pour-byte, commentaires inline compris.
    content = (
        "\ufeff{ ElementUnit\r\n"
        "{\r\n"
        "   CommandPointsPerLevel: 1    /* price per level,final price */\r\n"
        "   SpawnInSameDirection:false /* if true,animals spawn */\r\n"
        "}\r\n"
    )
    path = tmp_path / "faction.ecf"
    path.write_bytes(content.encode('utf-8'))
    doc = parse_ecf_file(path)
    assert doc.render().encode('utf-8') == content.encode('utf-8')


def test_edit_keeps_inline_comment(tmp_path):
    content = (
        "{ ElementUnit\r\n"
        "{\r\n"
        "   CommandPointsPerLevel: 1 /* price per level,final price */\r\n"
        "}\r\n"
    )
    path = tmp_path / "faction.ecf"
    path.write_bytes(content.encode('utf-8'))
    doc = parse_ecf_file(path)
    prop = _find_property(doc, 'CommandPointsPerLevel')
    assert prop is not None
    assert prop.set('CommandPointsPerLevel', '10') is True
    rendered = doc.render()
    # la ligne regeneree garde le commentaire (espacement normalise a deux
    # espaces, comme pour les commentaires '#')
    assert 'CommandPointsPerLevel: 10  /* price per level,final price */' in rendered
    assert prop.get('CommandPointsPerLevel') == '10'
