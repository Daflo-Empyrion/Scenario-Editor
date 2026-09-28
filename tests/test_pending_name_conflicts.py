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

"""Blocs en attente identifies par leur NOM (sans Id numerique, ex:
GalaxyConfig -- etoiles) : vecu 26/09, 'Activer avec cet Id' echouait
avec 'motif Id: introuvable' car ces blocs n'ont PAS d'Id assignable.
Desormais : detection + REMPLACEMENT du bloc actif de meme identite."""
from core.ecf.model import block_identity
from pathlib import Path

from core.ecf.parser import parse_ecf_text, parse_ecf_text
from core.ecf.pending_conflicts import (activate_pending_conflict,
                                        find_pending_conflicts,
                                        parse_pending_block,
                                        pending_has_numeric_id,
                                        replace_pending_conflict)

GALAXY_DOC = """{ GalaxyConfig Name: Neutron Star
  StarClass: N
  Probability: 0.00625
}

{ +GalaxyConfig Name: OtherStar
  Probability: 0.01
}

# CONFLIT D'ID Neutron Star (GalaxyConfig) : la copie de travail utilise
# deja cet Id pour "Neutron Star" (source: working), mais source
# l'utilise pour "Neutron Star". Bloc DESACTIVE ci-dessous.
# { +GalaxyConfig Name: Neutron Star
#   StarClass: N2
#   Probability: 0.003
#   ModelColor: "0.33,0.35,0.75"
# }
"""

ITEM_DOC = """# CONFLIT D'ID 6 (+Item) : la copie de travail utilise deja cet
# Id pour "SubmachineGunT1" (source: working), mais source l'utilise pour
# "PulseRifle". Bloc DESACTIVE ci-dessous.
# { +Item Id: 6, Name: PulseRifle
#   MarketPrice: 1705
# }
"""


def _doc_with_conflict(text):
    doc = parse_ecf_text(text)
    conflicts = find_pending_conflicts(doc)
    assert len(conflicts) == 1
    return doc, conflicts[0]


def test_numeric_id_detection():
    doc, conflict = _doc_with_conflict(ITEM_DOC)
    assert pending_has_numeric_id(conflict)
    doc2, conflict2 = _doc_with_conflict(GALAXY_DOC)
    assert not pending_has_numeric_id(conflict2)


def test_replace_name_identified_block_in_place():
    doc, conflict = _doc_with_conflict(GALAXY_DOC)
    base = [block_identity(b) for b in doc.nodes
            if type(b).__name__ == "EcfBlock"]
    assert base == ["Neutron Star", "OtherStar"]
    assert replace_pending_conflict(doc, conflict)
    blocks = [b for b in doc.nodes if type(b).__name__ == "EcfBlock"]
    # remplacement SUR PLACE : l'ordre de chargement est preserve
    assert [block_identity(b) for b in blocks] == ["Neutron Star",
                                                   "OtherStar"]
    replaced = blocks[0]
    assert replaced.get_property("StarClass") == "N2"
    assert replaced.get_property("Probability") == "0.003"
    assert replaced.get_property("ModelColor") == '"0.33,0.35,0.75"'
    # plus de commentaires de conflit dans le document
    assert not find_pending_conflicts(parse_ecf_text(doc.render()))


def test_replace_without_base_inserts_block():
    """Aucun bloc actif de meme identite (supprime depuis) : le bloc en
    attente est insere a la place des commentaires."""
    text = GALAXY_DOC.replace(
        "{ +GalaxyConfig Name: OtherStar\n  Probability: 0.01\n}\n\n", "")
    text = text.replace(
        "{ GalaxyConfig Name: Neutron Star\n  StarClass: N\n"
        "  Probability: 0.00625\n}\n\n", "")
    doc, conflict = _doc_with_conflict(text)
    assert replace_pending_conflict(doc, conflict)
    blocks = [b for b in doc.nodes if type(b).__name__ == "EcfBlock"]
    assert [block_identity(b) for b in blocks] == ["Neutron Star"]
    assert blocks[0].get_property("StarClass") == "N2"


def test_numeric_activation_still_works():
    doc, conflict = _doc_with_conflict(ITEM_DOC)
    assert activate_pending_conflict(doc, conflict, "7000")
    block = next(b for b in doc.nodes if type(b).__name__ == "EcfBlock")
    assert block_identity(block) == "7000"
    assert block.get_property("Name") == "PulseRifle"


def test_parse_pending_block_roundtrip():
    doc, conflict = _doc_with_conflict(GALAXY_DOC)
    pending = parse_pending_block(conflict)
    assert pending is not None
    assert pending.get_property("Name") == "Neutron Star"
    assert pending.get_property("StarClass") == "N2"


def test_dialog_switches_to_replace_mode(qapp):
    """Construction + bascule du bouton selon la presence d'un Id
    numerique (regle projet : tout dialogue nouveau a un test)."""
    from gui.ecf_edit_widget import PendingConflictsDialog
    doc, conflict = _doc_with_conflict(GALAXY_DOC)
    doc2, conflict2 = _doc_with_conflict(ITEM_DOC)
    pending = parse_pending_block(conflict)
    pending2 = parse_pending_block(conflict2)
    entries = [
        {'path': Path('galaxy.ecf'), 'doc': doc, 'conflict': conflict,
         'pending_block': pending, 'base_block': None},
        {'path': Path('items.ecf'), 'doc': doc2, 'conflict': conflict2,
         'pending_block': pending2, 'base_block': None},
    ]
    dlg = PendingConflictsDialog(entries, used_ids=set(), parent=None)
    # 1re selection = bloc par nom -> bouton Remplacer, champs Id caches
    assert 'Remplacer' in dlg.btn_activate.text()
    assert dlg.btn_activate.text() != "" and dlg.list_widget.count() == 2
    dlg.list_widget.setCurrentRow(0)
    dlg._on_activate()
    assert dlg.chosen_replace is True and dlg.chosen_new_id is None
    # 2e selection = bloc numerique -> champs Id affiches
    dlg2 = PendingConflictsDialog(entries, used_ids=set(), parent=None)
    dlg2.list_widget.setCurrentRow(1)
    dlg2.id_edit.setText("7000")
    dlg2._on_activate()
    assert dlg2.chosen_replace is False and dlg2.chosen_new_id == "7000"


def test_unbalanced_group_is_refused():
    """Regression vecue 26/09 : un groupe endommage (accolades non
    equilibrees, sequelle d'anciennes activations) produit un bloc jamais
    referme qui avalait tout le fichier -- refuse par le coeur."""
    doc, conflict = _doc_with_conflict(GALAXY_DOC)
    conflict.block_text = conflict.block_text.rsplit('# }', 1)[0] \
        + "  }"          # ferme le sous-bloc mais plus le bloc parent
    assert not _balanced_ok(conflict)
    assert replace_pending_conflict(doc, conflict) is False


def _balanced_ok(conflict):
    from core.ecf.pending_conflicts import _balanced
    return _balanced(conflict)


VANILLA_DISABLED_CHILD = """{ +Item Id: 111, Name: Avant
  MarketPrice: 1
}

# CONFLIT D'ID 112 (+Item) : la copie de travail utilise deja cet Id
# { +Item Id: 112, Name: PulseLaserMSWeapon
#   Meshfile: SomePrefab
#   { Child 0
#     Class: Ranged
#   }
#   # { Child 1
#   #   Class: Ranged
#   # }
#   HoldType: 15
# }

{ +Item Id: 113, Name: Apres
  MarketPrice: 3
}
"""


def test_group_with_natively_commented_child_is_complete():
    """Regression vecu 26/09 (items vanille a enfant DESACTIVE nativement) :
    la fermeture commentee du sous-bloc ('#   # }' une fois le groupe
    re-commente) tronquait le groupe au scan -- bloc jamais referme a
    l'activation, avalant tout le fichier. Desormais : les accolades des
    lignes re-commentees ne comptent pas."""
    doc, conflict = _doc_with_conflict(VANILLA_DISABLED_CHILD)
    assert conflict.block_text.count('{') == conflict.block_text.count('}')
    assert conflict.block_text.splitlines()[-1] == '}'
    assert activate_pending_conflict(doc, conflict, '7019')
    doc2 = parse_ecf_text(doc.render())
    blocks = [(block_identity(b), b) for b in doc2.nodes
              if type(b).__name__ == 'EcfBlock']
    assert [i for i, _ in blocks] == ['111', '7019', '113']
    item = blocks[1][1]
    child_kinds = [c.kind for c in item.children
                   if type(c).__name__ == 'EcfBlock']
    assert child_kinds == ['Child 0']       # l'enfant commente reste commente
    assert item.get_property('HoldType') == '15'   # fin de bloc presente


BLOCK_DOC = """# CONFLIT D'ID 628 (+Block) : la copie de travail utilise deja cet
# Id pour "InteriorBath" (source: working), mais source l'utilise pour
# "CPUExtenderLargeT5". Bloc DESACTIVE ci-dessous.
# { +Block Id: 628, Name: CPUExtenderLargeT5
#   Mass: 2
#   HitPoints: 500
# }
"""


def test_activate_block_name_only():
    """Demande 26/09 : activer un bloc SANS son Id (identification par Name
    seul, comme les 1335 blocs Id-less du RE2) -- aucun conflit d'Id
    possible, referencable par les POIs via le mapping de noms."""
    doc = parse_ecf_text(BLOCK_DOC)
    conflict = find_pending_conflicts(doc)[0]
    assert pending_has_numeric_id(conflict)          # il a un Id...
    from core.ecf.pending_conflicts import \
        activate_pending_conflict_name_only
    assert activate_pending_conflict_name_only(doc, conflict)
    doc2 = parse_ecf_text(doc.render())
    blocks = [b for b in doc2.nodes if type(b).__name__ == 'EcfBlock']
    assert len(blocks) == 1
    b = blocks[0]
    assert b.get_property('Name') == 'CPUExtenderLargeT5'
    assert b.get('Id') is None and b.get_property('Id') is None
    assert b.get_property('Mass') == '2'             # proprietes conservees
    # un deuxieme passage est refuse : le nom existe deja
    assert activate_pending_conflict_name_only(doc2, conflict) is False


def test_activate_block_name_only_refuses_existing_name():
    doc = parse_ecf_text(
        "{ +Block Name: CPUExtenderLargeT5\n  Mass: 9\n}\n" + BLOCK_DOC)
    conflict = find_pending_conflicts(doc)[0]
    from core.ecf.pending_conflicts import \
        activate_pending_conflict_name_only
    assert activate_pending_conflict_name_only(doc, conflict) is False
