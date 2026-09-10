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

"""Tests du journal persistant PDA (core/pda/history.py) et du suivi des
lignes CSV touchees (PdaModel.touched_csv_tokens) -- ajouts du retour
utilisateur du 31/08/2026 (surlignage + rappel a la reprise)."""
import pytest

from core.csv_handler import parse_csv_text
from core.pda import history
from core.pda.model import PdaModel
from core.yamllite.parser import parse_yaml_text

# Import direct du module voisin (pas `tests.test_pda_model`) :
# la roue argostranslate installe un package `tests` TOP-LEVEL en
# site-packages qui masquerait le dossier tests/ du projet.
from test_pda_model import MINI_CSV, MINI_YAML


@pytest.fixture
def hist_file(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "pda_history.json")
    return history


def test_history_append_and_read_order(hist_file):
    history.append_history("C:/scen/A", ["modif 1", "modif 2"])
    history.append_history("C:/scen/A", ["modif 3"])
    history.append_history("C:/scen/B", ["autre projet"])
    entries = history.read_history("C:/scen/A")
    # les PLUS RECENTES d'abord
    assert [e["label"] for e in entries] == ["modif 3", "modif 2", "modif 1"]
    assert history.read_history("C:/scen/B")[0]["label"] == "autre projet"
    assert history.read_history("C:/scen/inconnu") == []


def test_history_limit_and_empty_labels(hist_file):
    for i in range(history.MAX_PER_PROJECT + 20):
        history.append_history("C:/scen/A", [f"n{i}"])
    entries = history.read_history("C:/scen/A", limit=10**6)
    assert len(entries) == history.MAX_PER_PROJECT
    assert entries[0]["label"] == f"n{history.MAX_PER_PROJECT + 19}"
    # libelle vide : no-op, aucun fichier cree
    history.append_history("C:/scen/vide", ["", None])
    assert history.read_history("C:/scen/vide") == []


def test_model_tracks_touched_csv_tokens():
    model = PdaModel(parse_yaml_text(MINI_YAML), parse_csv_text(MINI_CSV))
    model.set_csv_text("pda_NEW1", "bonjour", "English")
    model.set_csv_text("pda_Aa1Bb2C", "coucou", "English")
    assert model.take_touched_csv_tokens() == {"pda_NEW1", "pda_Aa1Bb2C"}
    # pris puis remis a zero
    assert model.take_touched_csv_tokens() == set()


def test_model_snapshot_restore_roundtrip():
    model = PdaModel(parse_yaml_text(MINI_YAML), parse_csv_text(MINI_CSV))
    snap = model.snapshot()
    ch = model.chapters()[0]
    model.set_scalar(ch, "PlayerLevel", "42")
    model.set_csv_text("pda_NEWX", "texte", "English")
    assert len(model.chapters()) == 1
    model.restore_snapshot(snap)
    assert model.scalar(model.chapters()[0], "PlayerLevel") == "5"
    assert model.csv_text("pda_NEWX", "English") == ""
    # les objets YamlDocument/CsvDocument sont CONSERVES (partages avec les
    # onglets) : seuls nodes/rows sont remplaces
    assert model.yaml_doc.render() == MINI_YAML
