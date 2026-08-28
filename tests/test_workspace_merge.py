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

"""
Tests de core.workspace.merge_file_into_working / merge_folder_into_working --
aucun test dedie n'existait pour ces fonctions avant cette session (trou de
couverture identifie lors du refactor en pattern Strategy, voir
_merge_csv_strategy/_copy_strategy/_merge_ecf_strategy dans core/workspace.py).
Verifie a la fois le comportement public (tuple de retour) et que chaque
strategie produit exactement le meme resultat qu'avant le refactor.
"""
from pathlib import Path

import pytest

from core.scanner import scan_scenario
from core.workspace import Workspace, merge_file_into_working, merge_folder_into_working


def _make_workspace(tmp_path: Path, working_content: dict, source_content: dict) -> Workspace:
    """Cree une copie de travail et une source B minimales sur disque a partir de
    dicts {chemin_relatif: contenu texte}, et un Workspace pret a l'emploi."""
    working_root = tmp_path / "working"
    source_root = tmp_path / "source"
    for rel, content in working_content.items():
        p = working_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8', newline='')
    for rel, content in source_content.items():
        p = source_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8', newline='')

    working_scenario = scan_scenario(working_root)
    return Workspace(source_a=working_scenario, source_a_root=working_root,
                      working=working_scenario, working_root=working_root), source_root


ECF_WORKING = "{ Block Id: 1, Name: IronOre\n  Material: resourcehard\n}\n"
ECF_SOURCE_NEW_PROP = "{ Block Id: 1, Name: IronOre\n  Material: resourcehard\n  XpFactor: 3.0\n}\n"
ECF_SOURCE_NEW_BLOCK = "{ Block Id: 2, Name: CopperOre\n  Material: resourcesoft\n}\n"


def test_merge_new_file_uses_copy_strategy(tmp_path):
    """Fichier absent de la copie de travail -> simple copie (pas de fusion)."""
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={},
        source_content={"Configuration/BlocksConfig.ecf": ECF_SOURCE_NEW_BLOCK},
    )
    source_file = source_root / "Configuration" / "BlocksConfig.ecf"

    dest, highlight, id_conflicts, csv_report = merge_file_into_working(
        ws, source_file, source_root, "Source B")

    assert dest == ws.working_root / "Configuration" / "BlocksConfig.ecf"
    assert dest.read_text(encoding='utf-8') == ECF_SOURCE_NEW_BLOCK
    assert highlight is None
    assert id_conflicts == []
    assert csv_report is None


def test_merge_existing_ecf_file_merges_properties_and_reports_highlight(tmp_path):
    """.ecf deja present -> fusion 'properties' : la copie de travail garde ses
    valeurs, seules les proprietes ABSENTES sont completees depuis la source ;
    le highlight retourne doit lister XpFactor comme propriete completee sur le
    bloc Id=1 (identite = Name=IronOre)."""
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={"Configuration/BlocksConfig.ecf": ECF_WORKING},
        source_content={"Configuration/BlocksConfig.ecf": ECF_SOURCE_NEW_PROP},
    )
    source_file = source_root / "Configuration" / "BlocksConfig.ecf"
    dest = ws.working_root / "Configuration" / "BlocksConfig.ecf"

    result_dest, highlight, id_conflicts, csv_report = merge_file_into_working(
        ws, source_file, source_root, "Source B")

    assert result_dest == dest
    assert id_conflicts == []
    assert csv_report is None
    assert highlight is not None
    assert "XpFactor: 3.0" in dest.read_text(encoding='utf-8')
    # Le bloc existant est complete, pas remplace -- pas un "nouveau" bloc.
    assert highlight.new_blocks == set()
    assert len(highlight.changed_blocks) == 1


def test_merge_existing_ecf_file_new_block_is_reported_as_new(tmp_path):
    """.ecf deja present, mais le bloc de la source n'existe PAS dans la copie de
    travail -> ajoute integralement, liste dans new_blocks (pas changed_blocks)."""
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={"Configuration/BlocksConfig.ecf": ECF_WORKING},
        source_content={"Configuration/BlocksConfig.ecf": ECF_SOURCE_NEW_BLOCK},
    )
    source_file = source_root / "Configuration" / "BlocksConfig.ecf"
    dest = ws.working_root / "Configuration" / "BlocksConfig.ecf"

    _, highlight, id_conflicts, _ = merge_file_into_working(ws, source_file, source_root, "Source B")

    assert id_conflicts == []
    assert len(highlight.new_blocks) == 1
    assert highlight.changed_blocks == {}
    assert "CopperOre" in dest.read_text(encoding='utf-8')


def test_merge_ecf_id_collision_different_name_reports_conflict(tmp_path):
    """Garde-fou anti-collision : meme Id, Name different -> jamais fusionne a
    l'aveugle, remonte dans id_conflicts (voir docstring de
    merge_file_into_working)."""
    conflicting_source = "{ Block Id: 1, Name: SomethingElse\n  Material: resourcehard\n}\n"
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={"Configuration/BlocksConfig.ecf": ECF_WORKING},
        source_content={"Configuration/BlocksConfig.ecf": conflicting_source},
    )
    source_file = source_root / "Configuration" / "BlocksConfig.ecf"

    _, highlight, id_conflicts, _ = merge_file_into_working(ws, source_file, source_root, "Source B")

    assert len(id_conflicts) == 1


def test_merge_existing_csv_file_fills_empty_cells_and_reports(tmp_path):
    """.csv deja present -> fusion par cle : cellule vide completee depuis la
    source, ligne de cle absente ajoutee, rapport texte retourne (pas de
    MergeHighlight pour le CSV, c'est le 4e element du tuple)."""
    working_csv = "Key,Text,Comment\r\nA,HelloA,\r\n"
    source_csv = "Key,Text,Comment\r\nA,HelloA,CommentFromSource\r\nB,HelloB,\r\n"
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={"Content/PDA.csv": working_csv},
        source_content={"Content/PDA.csv": source_csv},
    )
    source_file = source_root / "Content" / "PDA.csv"
    dest = ws.working_root / "Content" / "PDA.csv"

    result_dest, highlight, id_conflicts, csv_report = merge_file_into_working(
        ws, source_file, source_root, "Source B")

    assert result_dest == dest
    assert highlight is None
    assert id_conflicts == []
    assert csv_report is not None
    merged_text = dest.read_text(encoding='utf-8')
    assert "CommentFromSource" in merged_text  # cellule vide completee
    assert "HelloB" in merged_text             # nouvelle ligne ajoutee
    assert any("nouvelle ligne" in line for line in csv_report)
    assert any("complete" in line for line in csv_report)


def test_merge_existing_non_ecf_non_csv_file_is_overwritten_by_copy(tmp_path):
    """Format sans moteur de fusion dedie (ex: .yaml) deja present -> simple
    copie, la source ecrase integralement la copie de travail."""
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={"Content/Playfields/x/playfield.yaml": "PlayfieldType: Planet\n"},
        source_content={"Content/Playfields/x/playfield.yaml": "PlayfieldType: Moon\n"},
    )
    source_file = source_root / "Content" / "Playfields" / "x" / "playfield.yaml"
    dest = ws.working_root / "Content" / "Playfields" / "x" / "playfield.yaml"

    result_dest, highlight, id_conflicts, csv_report = merge_file_into_working(
        ws, source_file, source_root, "Source B")

    assert result_dest == dest
    assert dest.read_text(encoding='utf-8') == "PlayfieldType: Moon\n"
    assert highlight is None
    assert id_conflicts == []
    assert csv_report is None


def test_merge_folder_into_working_aggregates_all_file_results(tmp_path):
    """merge_folder_into_working parcourt recursivement et applique la meme
    logique que merge_file_into_working a chaque fichier, en agregeant les 3
    resultats (highlights/conflicts/csv_reports) par chemin."""
    ws, source_root = _make_workspace(
        tmp_path,
        working_content={
            "Configuration/BlocksConfig.ecf": ECF_WORKING,
            "Content/PDA.csv": "Key,Text\r\nA,HelloA\r\n",
        },
        source_content={
            "Configuration/BlocksConfig.ecf": ECF_SOURCE_NEW_PROP,
            "Content/PDA.csv": "Key,Text\r\nB,HelloB\r\n",
            "Content/NewFile.txt": "contenu tout neuf\n",
        },
    )

    highlights, all_conflicts, csv_reports = merge_folder_into_working(ws, source_root, source_root, "Source B")

    assert len(highlights) == 1  # seul le .ecf produit un MergeHighlight
    assert len(csv_reports) == 1  # seul le .csv produit un rapport
    assert all_conflicts == []
    ecf_dest = ws.working_root / "Configuration" / "BlocksConfig.ecf"
    assert ecf_dest in highlights
    txt_dest = ws.working_root / "Content" / "NewFile.txt"
    assert txt_dest.read_text(encoding='utf-8') == "contenu tout neuf\n"
