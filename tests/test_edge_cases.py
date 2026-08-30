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

"""Tests des cas limites de format et d'environnement, identifies par l'audit
du 30/08/2026. Les cas deja couverts ailleurs ne sont pas retraites ici :
guillemets imbriques du CSV (tests/test_csv_handler.py, fixture reelle a
guillemets embarques), commentaires YAML a indentation zero
(tests/test_playfield_editor.py), BOM traite dans le modele ECF
(core/ecf/model.py retire le BOM residuel de la premiere ligne).

Ce qui manquait et que ce fichier épingle :
- BOM en tete d'ECF et de YAML (de vrais fichiers du jeu en ont) : le
  round-trip doit rester byte-perfect ET le premier bloc/entry ne doit pas
  etre corrompu par le caractere U+FEFF ;
- fins de ligne CRLF (fichiers Windows du jeu) : round-trip byte-perfect ;
- chemins avec espaces ET caracteres accentues (courants sur Windows) :
  parse + ecriture + relecture sans erreur.
"""
from pathlib import Path

from core.ecf.model import EcfBlock, EcfComment
from core.ecf.parser import parse_ecf_file
from core.yamllite.parser import parse_yaml_file

ECF_BODY = (
    "{ Block Id: 399, Name: ConcreteBlocks\n"
    "  Material: concrete\n"
    "  HitPoints: 600\n"
    "}\n"
)
YAML_BODY = (
    "Terrain:\n"
    "  Temp: 24\n"
)


def _write_and_parse_ecf(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return parse_ecf_file(path)


def test_ecf_with_bom_round_trip_byte_perfect(tmp_path):
    """Un vrai BlocksConfig.ecf commence par un BOM : le parser le garde dans
    le texte (utf-8, PAS utf-8-sig -- voir core/ecf/parser.py) et le render()
    doit le reproduire a l'identique."""
    path = tmp_path / "BlocksConfig.ecf"
    original = b"\xef\xbb\xbf" + ECF_BODY.encode("utf-8")
    doc = _write_and_parse_ecf(path, original)
    assert doc.render().encode("utf-8") == original


def test_ecf_with_bom_first_block_not_corrupted(tmp_path):
    """Le BOM ne doit pas polluer l'identite du premier bloc (le modele retire
    le U+FEFF residuel de la premiere ligne -- core/ecf/model.py)."""
    path = tmp_path / "BlocksConfig.ecf"
    doc = _write_and_parse_ecf(path, b"\xef\xbb\xbf" + ECF_BODY.encode("utf-8"))
    block = doc.find_block_by_identity("Block", "399")
    assert block is not None
    assert block.get_property("Name") == "ConcreteBlocks"
    assert block.get_property("HitPoints") == "600"


def test_yaml_with_bom_round_trip_byte_perfect(tmp_path):
    """Meme contrat pour le YAML : le BOM (lu comme premier caractere du
    texte) doit survivre au round-trip ET ne pas corrompre la cle de la
    premiere entree (core/yamllite/parser.py retire le BOM du contenu parse,
    le garde dans raw)."""
    path = tmp_path / "playfield_static.yaml"
    original = b"\xef\xbb\xbf" + YAML_BODY.encode("utf-8")
    path.write_bytes(original)
    doc = parse_yaml_file(path)
    assert doc.render().encode("utf-8") == original
    assert doc.nodes[0].key == "Terrain"
    assert doc.nodes[0].get("Temp") == "24"


def test_ecf_with_bom_and_header_comment_like_real_game_files(tmp_path):
    """Forme des vrais fichiers du jeu : BOM suivi d'un commentaire d'en-tete
    AVANT le premier bloc. La premiere ligne doit etre un commentaire propre,
    et le bloc doit rester trouvable."""
    path = tmp_path / "BlocksConfig.ecf"
    original = b"\xef\xbb\xbf# En-tete technique du fichier\n\n" + ECF_BODY.encode("utf-8")
    doc = _write_and_parse_ecf(path, original)
    assert doc.render().encode("utf-8") == original
    assert isinstance(doc.nodes[0], EcfComment)
    assert doc.nodes[0].raw.lstrip("\ufeff").startswith("#")
    assert doc.find_block_by_identity("Block", "399") is not None


def test_ecf_with_crlf_round_trip_byte_perfect(tmp_path):
    """Les fichiers du jeu sont edites sous Windows : le eol de chaque ligne
    est conserve par ligne (core/ecf/parser.py _split_line), le render doit
    restituer du CRLF a l'identique."""
    path = tmp_path / "BlocksConfig.ecf"
    original = ECF_BODY.replace("\n", "\r\n").encode("utf-8")
    doc = _write_and_parse_ecf(path, original)
    assert doc.render().encode("utf-8") == original


def test_yaml_with_crlf_round_trip_byte_perfect(tmp_path):
    path = tmp_path / "playfield_static.yaml"
    original = YAML_BODY.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(original)
    doc = parse_yaml_file(path)
    assert doc.render().encode("utf-8") == original


def test_ecf_in_path_with_spaces_and_accents(tmp_path):
    """Chemin typique Windows avec espaces et accents : parse + relecture
    doivent fonctionner sans traitement special du chemin."""
    path = tmp_path / "Scénario Reforged (copie)" / "Configuration" / "BlocksConfig.ecf"
    original = ECF_BODY.encode("utf-8")
    doc = _write_and_parse_ecf(path, original)
    assert path.exists()
    assert doc.find_block_by_identity("Block", "399") is not None
    # Relecture independante depuis le disque
    reparsed = parse_ecf_file(path)
    assert reparsed.render().encode("utf-8") == original


def test_yaml_in_path_with_spaces_and_accents(tmp_path):
    path = tmp_path / "Scénario Reforged (copie)" / "Playfields" / "playfield_static.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(YAML_BODY.encode("utf-8"))
    doc = parse_yaml_file(path)
    assert doc.render().encode("utf-8") == YAML_BODY.encode("utf-8")
