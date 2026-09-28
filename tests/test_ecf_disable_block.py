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

"""Blocs ECF commentes (desactives) : detection des blocs NATIFS
reactivables au clic droit. Regression vecue 26/09 : la detection coupait
au premier '}' sans compter la PROFONDEUR -- un Item desactive par la
fusion (avec '{ Child ... }' imbrique) etait fragmente en 'Item [6]' +
'Child [?]' et reactiver le premier fragment produisait un bloc jamais
referme (fichier casse, tous les blocs suivants avales)."""
from core.ecf.disable_block import (find_native_commented_blocks,
                                    uncomment_native_block)
from core.ecf.model import block_identity
from core.ecf.parser import parse_ecf_text

MERGE_DISABLED = """{ +Item Id: 1, Name: DejaLa
  MarketPrice: 10
}

# CONFLIT D'ID 6 (+Item) : la copie de travail utilise deja cet Id pour
# { +Item Id: 6, Name: PulseRifle
#   Meshfile: Entities/Items/Weapons/Rifles/ScifiRifle2BlackT1Prefab
#   MarketPrice: 1705, display: true
#   { Child 0
#     Class: Ranged
#     Range: 160, display: false
#   }
#   { Child 1
#     Class: Ranged
#     Range: 180, display: false
#   }
#   HoldType: 15
# }

{ +Item Id: 9, Name: Apres
  MarketPrice: 99
}
"""


def test_nested_children_are_one_block_not_fragments():
    doc = parse_ecf_text(MERGE_DISABLED)
    blocks = find_native_commented_blocks(doc)
    # AVANT le fix : 'Item [6]' coupe au '}' du premier Child + 'Child [?]'
    assert [b.label for b in blocks] == ["Item [6]"]
    assert len(blocks[0].nodes) == 13          # jusqu'a l'accolade fermante
    last = blocks[0].nodes[-1].raw.strip()
    assert last == "# }"


def test_activate_nested_block_yields_valid_document():
    doc = parse_ecf_text(MERGE_DISABLED)
    nb = find_native_commented_blocks(doc)[0]
    uncomment_native_block(nb)
    doc2 = parse_ecf_text(doc.render())
    kinds = [block_identity(b) for b in doc2.nodes
             if type(b).__name__ == "EcfBlock"]
    # bloc reactif + voisins intacts ; l'Item 6 referme correctement
    assert kinds[:3] == ["1", "6", "9"]
    item6 = next(b for b in doc2.nodes
                 if type(b).__name__ == "EcfBlock"
                 and block_identity(b) == "6")
    child_labels = [c.kind for c in item6.children
                    if type(c).__name__ == "EcfBlock"]
    assert [k.split()[0] for k in child_labels] == ["Child", "Child"]


def test_adjacent_disabled_blocks_stay_separate():
    text = MERGE_DISABLED.replace(
        "# CONFLIT D'ID 6 (+Item) : la copie de travail utilise deja cet Id pour\n",
        "")
    doc = parse_ecf_text(text)
    blocks = find_native_commented_blocks(doc)
    # seul le groupe commente est un bloc natif ; Item [9] est ACTIF
    assert [b.label for b in blocks] == ["Item [6]"]
    # reactiver le commente ne touche pas les blocs actifs voisins
    uncomment_native_block(blocks[0])
    doc2 = parse_ecf_text(doc.render())
    active = [block_identity(b) for b in doc2.nodes
              if type(b).__name__ == "EcfBlock"]
    assert active == ["1", "6", "9"]


def test_single_line_block_detected():
    doc = parse_ecf_text("#{ +Item Id: 5, Name: Compact\n"
                         "#  MarketPrice: 5\n"
                         "#}\n")
    blocks = find_native_commented_blocks(doc)
    assert [b.label for b in blocks] == ["Item [5]"]
