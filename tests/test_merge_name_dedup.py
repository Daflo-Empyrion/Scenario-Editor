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

"""Dedoublonnage de la fusion ECF par NAME (vecu 26/09) : la garde
anti-collision ne comparait que l'Id -- un bloc importe puis reactiver
avec un Id LIBRE etait re-propose a chaque refusion (107 doublons sur
ItemsConfig). Desormais, si un bloc de meme Name existe deja dans la
copie de travail, la source ne cree pas de conflit."""
from core.ecf.merge import merge_documents
from core.ecf.model import block_identity
from core.ecf.parser import parse_ecf_text

WORKING = """{ +Item Id: 112, Name: LaserCVT1Weapon
  MarketPrice: 79
}

{ +Item Id: 7019, Name: PulseLaserMSWeapon
  MarketPrice: 1705
}
"""

SOURCE_SAME_NAME = """{ +Item Id: 112, Name: PulseLaserMSWeapon
  MarketPrice: 1705
}
"""

SOURCE_OTHER_NAME = """{ +Item Id: 112, Name: AutreArme
  MarketPrice: 5
}
"""


def _merge(source_text):
    working = parse_ecf_text(WORKING)
    source = parse_ecf_text(source_text)
    return merge_documents([("Copie de travail", working),
                            ("source", source)], mode='properties')


def test_same_name_different_id_is_not_reproposed():
    result = _merge(SOURCE_SAME_NAME)
    assert result.id_conflicts == []          # deja importe : pas de conflit
    rendered = result.document.render()
    assert rendered.count("PulseLaserMSWeapon") == 1   # pas de doublon
    blocks = [block_identity(b) for b in result.document.nodes
              if type(b).__name__ == "EcfBlock"]
    assert blocks == ["112", "7019"]


def test_different_name_still_conflicts():
    result = _merge(SOURCE_OTHER_NAME)
    assert len(result.id_conflicts) == 1      # vrai conflit : garde conservée
    assert result.id_conflicts[0].conflicting_name == "AutreArme"


def test_duplicate_identity_base_refuses_merge():
    """Vecu 26/09 (GalaxyConfig corrompu) : un fichier a noms REPETES
    (GalaxyConfig : instances d'etoiles) etait silencieusement deduplique
    par la fusion -- des definitions entieres disparaissaient. La fusion
    refuse desormais tout document de base a identites dupliquees."""
    import pytest
    working = parse_ecf_text(
        "{ GalaxyConfig, Name: Neutron Star\n  StarClass: N\n}\n"
        "{ GalaxyConfig, Name: Neutron Star\n  StarClass: N2\n}\n")
    source = parse_ecf_text("{ GalaxyConfig, Name: Neutron Star\n}\n")
    with pytest.raises(ValueError, match="doublon"):
        merge_documents([("Copie de travail", working),
                         ("source", source)], mode='properties')


def test_merge_still_works_without_duplicates():
    working = parse_ecf_text("{ +Item Id: 1, Name: A\n  MarketPrice: 1\n}\n")
    source = parse_ecf_text("{ +Item Id: 2, Name: B\n  MarketPrice: 2\n}\n")
    result = merge_documents([("Copie de travail", working),
                              ("source", source)], mode='properties')
    blocks = [block_identity(b) for b in result.document.nodes
              if type(b).__name__ == "EcfBlock"]
    assert blocks == ["1", "2"]
