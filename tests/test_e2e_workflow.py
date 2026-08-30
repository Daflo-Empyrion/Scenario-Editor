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

"""Test bout-en-bout du flux de travail complet, identifie comme manque par
l'audit du 30/08/2026 : creer un projet (copie de travail), ouvrir un fichier
dans le vrai editeur ECF, modifier une propriete PAR LE TABLEAU (le meme
chemin signaux Qt qu'une saisie utilisateur : itemChanged -> _on_cell_changed),
enregistrer, puis relire le fichier sur disque pour verifier que la
modification est bien persistee ET que le reste du fichier est intact.

Aucun mock sur le chemin critique : vrai workspace sur disque, vrai widget,
vraie ecriture atomique, vrai re-parsing."""
from pathlib import Path

import pytest

from core.ecf.parser import parse_ecf_file
from core.workspace import load_existing_workspace, open_workspace

SOURCE_ECF = (
    "{ Block Id: 1, Name: IronOre\n"
    "  Material: resourcehard\n"
    "  Mass: 100\n"
    "}\n"
)


@pytest.fixture
def scenario_source(tmp_path):
    """Scenario source minimal, dans un dossier avec espaces et accents
    (noms reels de projets Windows)."""
    source = tmp_path / "Mon Scénario"
    (source / "Configuration").mkdir(parents=True)
    (source / "Configuration" / "BlocksConfig.ecf").write_text(
        SOURCE_ECF, encoding="utf-8")
    return source


def _find_value_row(widget, key: str):
    """Indice de la ligne du tableau de proprietes dont la colonne cle vaut
    `key` (None si absente)."""
    for i in range(widget.props_table.rowCount()):
        item_k = widget.props_table.item(i, 0)
        if item_k is not None and item_k.text() == key:
            return i
    return None


def test_full_workflow_create_modify_save_reparse(qapp, tmp_path, scenario_source):
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)

    # 1. Creation du projet : copie de travail physique depuis la source.
    working_dest = tmp_path / "Copie de travail"
    ws = open_workspace(scenario_source, working_dest)
    assert (working_dest / "Configuration" / "BlocksConfig.ecf").read_text(
        encoding="utf-8") == SOURCE_ECF

    # 2. Ouverture du fichier dans l'editeur ECF reel.
    widget = EcfEditWidget(ws.working_root / "Configuration" / "BlocksConfig.ecf")
    assert widget.is_modified() is False

    # 3. Selection du bloc par son Id (navigation reelle de l'editeur) puis
    #    modification de la valeur Mass dans le tableau : setText() declenche
    #    itemChanged -> _on_cell_changed, exactement comme une saisie clavier.
    assert widget.select_block_by_identity("1") is True
    row = _find_value_row(widget, "Mass")
    assert row is not None
    widget.props_table.item(row, 1).setText("999")

    assert widget.is_modified() is True

    # 4. Enregistrement.
    widget.save()
    assert widget.is_modified() is False

    # 5. Verification sur disque : re-parsing complet du fichier ecrit.
    path = working_dest / "Configuration" / "BlocksConfig.ecf"
    reloaded = parse_ecf_file(path)
    block = reloaded.find_block_by_identity("Block", "1")
    assert block is not None
    assert block.get_property("Mass") == "999"
    # Le reste du fichier est intact (round-trip de la modification seule).
    assert block.get_property("Name") == "IronOre"
    assert block.get_property("Material") == "resourcehard"


def test_workflow_resume_project_reopen_and_verify_persistence(
        qapp, tmp_path, scenario_source):
    """Reprise d'un projet existant (load_existing_workspace, sans nouvelle
    copie) : la modification enregistree par la session precedente doit etre
    visible dans la copie de travail rechargee."""
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)

    ws = open_workspace(scenario_source, tmp_path / "Copie de travail")
    path = ws.working_root / "Configuration" / "BlocksConfig.ecf"
    widget = EcfEditWidget(path)
    assert widget.select_block_by_identity("1") is True
    row = _find_value_row(widget, "Mass")
    widget.props_table.item(row, 1).setText("42")
    widget.save()

    # Nouvelle session : reprise du projet, sans recopie de la source.
    ws2 = load_existing_workspace(scenario_source, tmp_path / "Copie de travail")
    assert ws2.working_root == ws.working_root
    widget2 = EcfEditWidget(ws2.working_root / "Configuration" / "BlocksConfig.ecf")
    assert widget2.select_block_by_identity("1") is True
    row2 = _find_value_row(widget2, "Mass")
    assert widget2.props_table.item(row2, 1).text() == "42"
