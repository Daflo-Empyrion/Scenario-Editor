# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# Licence GPL-3 ou superieure (voir la tete de fichier des autres tests).

"""Cache de documents ECF parses (core/ecf/doc_cache.py) -- reponse au retour
utilisateur du 31/08/2026 : chaque clic dans l'arbre technologique
re-parsait BlocksConfig/ItemsConfig 2 a 3 fois (plusieurs secondes sur de
vrais fichiers). Le cache ne sert que des LECTURES ; invalidation par
(mtime_ns, taille)."""

import shutil
from pathlib import Path

from core.ecf.doc_cache import get_parsed_doc, invalidate
from core.ecf.parser import parse_ecf_file

FIXTURE = Path(__file__).parent / "fixtures" / "tech_tree_scenario" / "BlocksConfig.ecf"


def _copy(tmp_path: Path) -> Path:
    path = tmp_path / "BlocksConfig.ecf"
    shutil.copy(FIXTURE, path)
    invalidate(str(path))
    return path


def test_same_doc_returned_while_file_unchanged(tmp_path):
    path = _copy(tmp_path)
    doc1 = get_parsed_doc(path)
    doc2 = get_parsed_doc(path)
    assert doc1 is doc2  # pas de re-parse (identite objet)


def test_fresh_doc_after_external_rewrite(tmp_path):
    """Apres reecriture du fichier (atomic write ou edition externe), le
    (mtime, taille) change : la lecture suivante voit le NOUVEAU contenu."""
    path = _copy(tmp_path)
    old = get_parsed_doc(path)
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace("OxygenTankSmallMS", "OxygenTankSmallXX"),
                    encoding='utf-8', newline='')
    fresh = get_parsed_doc(path)
    assert fresh is not old
    assert fresh is get_parsed_doc(path)
    assert any(b.get('Name') == "OxygenTankSmallXX" for b in fresh.iter_blocks())


def test_invalidate_forces_reparse(tmp_path):
    path = _copy(tmp_path)
    doc1 = get_parsed_doc(path)
    invalidate(str(path))
    doc2 = get_parsed_doc(path)
    assert doc2 is not doc1


def test_missing_file_still_raises(tmp_path):
    import pytest
    with pytest.raises(OSError):
        get_parsed_doc(tmp_path / "Inexistant.ecf")


def test_real_write_workflow_refreshes_read_views(tmp_path):
    """Scenario complet : lecture fiche -> ecriture via la fonction d'ecriture
    (qui parse ses PROPres documents, jamais le cache) -> la lecture suivante
    reflete la nouvelle valeur."""
    from core.tech_tree import set_block_property, find_block_by_name
    blocks = tmp_path / "BlocksConfig.ecf"
    shutil.copy(FIXTURE, blocks)
    invalidate(str(blocks))

    assert find_block_by_name(blocks, "OxygenTankSmallMS").get_property("UnlockCost") is not None
    assert set_block_property(blocks, "OxygenTankSmallMS", "UnlockCost", "77") is True
    assert find_block_by_name(blocks, "OxygenTankSmallMS").get_property("UnlockCost") == "77"
