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

"""Conflits d'Id dans l'apercu de fusion (demande 25/09) : meme Id mais
Name different = materiel different — l'apercu doit afficher UNE LIGNE
par conflit avec les DEUX noms (avant = copie de travail, apres =
source), non cochable (le bloc conflit est de toute facon ajoute
DESACTIVE en fin de fichier)."""
import pytest

from core.ecf.parser import parse_ecf_file
from gui.merge_preview_dialog import (MergePreviewDialog,
                                      compute_merge_preview)

WORKING_ECF = """{ Block Id: 628, Name: InteriorBath
  MaxCount: 2
}

{ Block Id: 412, Name: HullTest
}

{ Block Id: 271, Name: SciencelabMS
  Model: @models/Old
}
"""

SOURCE_ECF = """{ Block Id: 628, Name: CPUExtenderLargeT5
  MaxCount: 1
}

{ Block Id: 412, Name: HullTest
  Mass: 80
}

{ +Block Id: 271, Name: SciencelabMS
  Model: @models/New
}
"""


@pytest.fixture
def docs(tmp_path):
    wp = tmp_path / "working_BlocksConfig.ecf"
    sp = tmp_path / "source_BlocksConfig.ecf"
    wp.write_text(WORKING_ECF, encoding="utf-8")
    sp.write_text(SOURCE_ECF, encoding="utf-8")
    return parse_ecf_file(wp), parse_ecf_file(sp)


def test_id_conflict_row_shows_both_names(qapp, docs):
    working_doc, source_doc = docs
    result, rows = compute_merge_preview(working_doc, source_doc, "source")
    assert len(result.id_conflicts) == 2   # 628 (nom) + 271 (Model)
    conflicts = [r for r in rows if r.row_type == "id_conflict"]
    assert len(conflicts) == 2
    by_names = {r.working_value: r for r in conflicts}
    # cas 1 : Name different -> les deux noms affiches
    row = by_names["InteriorBath"]
    assert row.merged_value == "CPUExtenderLargeT5"
    assert row.prop_key.startswith("Id 628") and "Name" in row.prop_key
    # cas 2 (vecu 25/09) : MEME Id + MEME Name mais Model different ->
    # la RAISON du conflit est affichee dans la cle
    row2 = by_names["SciencelabMS"]
    assert row2.merged_value == "SciencelabMS"
    assert "Model" in row2.prop_key
    assert "@models/Old" in row2.prop_key
    assert "@models/New" in row2.prop_key


def test_conflict_row_dialog_non_checkable_and_apply_safe(qapp, docs):
    """La ligne conflit : pas de case a cocher, colonne Apres non editable,
    apply_selected ne la touche pas (bloc conflit deja ajoute desactive)."""
    from PyQt6.QtCore import Qt
    working_doc, source_doc = docs
    result, rows = compute_merge_preview(working_doc, source_doc, "source")
    dlg = MergePreviewDialog(working_doc, source_doc, "source",
                             precomputed=(result, rows))
    conflict_r = next(r for r, row in enumerate(rows)
                      if row.row_type == "id_conflict")
    check_item = dlg.table.item(conflict_r, dlg.COL_CHECK)
    assert not (check_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert not (dlg.table.item(conflict_r, dlg.COL_AFTER).flags()
                & Qt.ItemFlag.ItemIsEditable)
    dlg._set_all_checks(True)
    dlg.apply_selected()                        # ne leve, ne modifie rien
    # le bloc conflit est present DESACTIVE (commente) dans le document
    rendered = result.document.render()
    assert "# CONFLIT D'ID 628" in rendered
    assert "CPUExtenderLargeT5" in rendered


def test_rows_display_block_name(qapp, docs):
    """Demande 25/09 : chaque ligne affiche le NOM du bloc (pas seulement
    l'Id) — valider une valeur sans savoir sur quel bloc elle porte est
    impossible."""
    working_doc, source_doc = docs
    _result, rows = compute_merge_preview(working_doc, source_doc, "source")
    assert rows
    for r in rows:
        if "[412]" in r.block_label:
            assert "HullTest" in r.block_label   # nom + Id visibles
        if "[628]" in r.block_label and r.row_type != "id_conflict":
            assert "InteriorBath" in r.block_label
