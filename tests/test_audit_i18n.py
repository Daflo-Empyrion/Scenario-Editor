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

"""Garde-fou de l'audit i18n (demande d'audit du 30/08/2026 apres constat de
boutons en anglais sous langue francaise) : AUCUNE cle t() absente du JSON,
AUCUNE cle incomplete fr/en, AUCUN litteral affiche en dur dans gui/ et
core/. Toute regression (un nouveau bouton ecrit en dur au lieu de passer
par t()) fait echouer la suite de tests -- l'audit manuel reste disponible
via `python tools/audit_i18n.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit_i18n import run_audit


def test_audit_finds_no_missing_keys(qapp):
    result = run_audit()
    assert result.missing_keys == [], \
        f"Cles t() absentes de i18n_strings.json : {[(str(f.path), f.line, f.detail) for f in result.missing_keys]}"


def test_audit_finds_no_incomplete_keys(qapp):
    result = run_audit()
    assert result.incomplete_keys == [], \
        f"Cles sans fr/en : {[f.detail for f in result.incomplete_keys]}"


def test_audit_finds_no_hardcoded_visible_strings(qapp):
    result = run_audit()
    assert result.hardcoded == [], \
        f"Litteraux affiches en dur : {[(str(f.path), f.line, f.detail) for f in result.hardcoded]}"
