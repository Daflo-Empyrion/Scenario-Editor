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

"""Digest de log (tools/logdigest.py) : le groupe remplace le texte.

Un log client de 1,4 Mo coute ~360 000 tokens en contexte. Le digest dit ce
qui se repete, combien de fois et a quelles lignes ; `--grep` ramene ensuite
la fenetre exacte, donc aucune information n'est perdue.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import logdigest

LOG = """\
Initialize engine version: 2022.3.62f2 (7670c08855a9)
07-17:41:24.763 18_41 -LOG- Loading POI 12 at 100,200
07-17:41:25.001 18_41 -ERR- 32 Losing data when packing (6, 267, -15) (BGI_W)
07-17:41:26.002 18_41 -ERR- 32 Losing data when packing (6, 267, -15) (BGI_W)
07-17:41:27.003 18_41 -ERR- 32 Losing data when packing (-6, 275, -15) (BGI_W)
07-17:41:28.004 18_41 -ERR- Exception: Material metalweapon not found
07-17:41:29.005 18_42 -WRN- slow frame
"""


@pytest.fixture
def log(tmp_path):
    path = tmp_path / "Client_261107.log"
    path.write_text(LOG, encoding="utf-8")
    return path


def test_signature_neutralise_les_valeurs():
    """Deux occurrences identiques a un chiffre pres tombent dans le meme groupe."""
    assert (logdigest.signature("-ERR- 32 Losing data (6, 267, -15)")
            == logdigest.signature("-ERR- 99 Losing data (7, 268, -16)"))


def test_scan_groupe_et_garde_les_numeros_de_ligne(log):
    data = logdigest.scan(log)
    assert data["lines"] == 7
    count, first, last, _sample, _tails = max(data["groups"].values(),
                                              key=lambda g: g[0])
    assert (count, first, last) == (2, 3, 4)


def test_level_ne_garde_que_le_niveau_demande(log):
    data = logdigest.scan(log, "ERR")
    assert data["lines"] == 7                      # le poids total reste exact
    assert sorted(data["groups"]) and all("-ERR-" in g[3]
                                          for g in data["groups"].values())


def test_rapport_donne_poids_et_span(log):
    texte = logdigest.report(log, logdigest.scan(log), 15)
    assert "7 lignes" in texte and "k tokens" in texte
    assert "L3..L4" in texte
    assert "Exception: Material metalweapon" in texte


def test_grep_numerote_avec_contexte(log, capsys):
    assert logdigest.grep(log, "metalweapon", 1) == 0
    out = capsys.readouterr().out
    assert ">       6" in out                      # la ligne trouvee
    assert "slow frame" in out                     # une ligne de contexte apres


def test_grep_sans_correspondance(log, capsys):
    assert logdigest.grep(log, "introuvable-xyz", 1) == 0
    assert "aucune correspondance" in capsys.readouterr().out


def test_queue_variable_signalee(tmp_path):
    """Deux messages qui ne divergent qu'apres le 110e caractere : le groupe
    reste unique (c'est voulu) mais il est signale, donc jamais lu comme un seul."""
    debut = "07-17:41:24.763 18_41 -ERR- " + "x" * 90
    path = tmp_path / "long.log"
    path.write_text(f"{debut} cas A\n{debut} cas B\n", encoding="utf-8")
    data = logdigest.scan(path)
    texte = logdigest.report(path, data, 5)
    assert len(data["groups"]) == 1
    assert "[queue variable]" in texte


def test_fichier_absent(tmp_path):
    argv = ["logdigest", str(tmp_path / "absent.log")]
    ancien = sys.argv
    sys.argv = argv
    try:
        assert logdigest.main() == 2
    finally:
        sys.argv = ancien
