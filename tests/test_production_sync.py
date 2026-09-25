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

"""Synchronisation vers le scenario EN PRODUCTION (demande 24/09/2026) :
core (deduction du dossier + copie/remplace avec sauvegarde), dialogue et
proposition a la fermeture de l'application."""
import types

import pytest

from core.production_sync import (find_default_production_root,
                                  sync_to_production)


def _tree(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


@pytest.fixture
def trio(tmp_path):
    """source (originale) / working (modifiee) / scenarios de la vanille."""
    source = tmp_path / "source"
    working = tmp_path / "RE2 ATL"
    vanilla = tmp_path / "vanilla_content"
    _tree(source, {"Content/Configuration/BlocksConfig.ecf": "original",
                   "Extras/Localization.csv": "loc"})
    _tree(working, {"Content/Configuration/BlocksConfig.ecf": "MODIFIE",
                    "Extras/Localization.csv": "loc",
                    "Extras/Nouveau.csv": "ajoute"})
    _tree(vanilla, {"Scenarios/re2 atl/Content/Configuration/BlocksConfig.ecf":
                    "PRODUCTION"})
    return source, working, vanilla


def test_find_default_production_root_matches_working_name(trio):
    _source, working, vanilla = trio
    guess = find_default_production_root(str(vanilla), working)
    assert guess is not None
    assert guess.name.lower() == working.name.lower()
    assert find_default_production_root("", working) is None
    assert find_default_production_root(str(vanilla), "") is None
    assert find_default_production_root(str(tmp_missing(vanilla)),
                                        working) is None


def tmp_missing(vanilla):
    return vanilla / "inexistant"


def test_sync_replaces_added_and_backs_up(trio, tmp_path):
    _source, working, vanilla = trio
    from gui.modified_files_dialog import list_changed_files
    files = list_changed_files(working, _source)
    states = {p.name: s for p, s in files}
    assert states == {"BlocksConfig.ecf": "modified",
                      "Nouveau.csv": "added"}

    backup = tmp_path / "sauvegardes"
    copied, saved = sync_to_production(files, working,
                                       vanilla / "Scenarios" / "re2 atl",
                                       backup_dir=backup)
    prod = vanilla / "Scenarios" / "re2 atl"
    assert copied == 2
    assert saved == backup
    assert (prod / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8") == "MODIFIE"
    assert (prod / "Extras/Nouveau.csv").read_text(
        encoding="utf-8") == "ajoute"
    # l'ecrase a ete sauvegarde, le nouveau non (rien a ecraser)
    assert (backup / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8") == "PRODUCTION"
    assert not (backup / "Extras/Nouveau.csv").exists()


def test_settings_roundtrip(tmp_path, monkeypatch):
    import core.settings as settings
    monkeypatch.setattr(settings, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    assert settings.get_production_scenario_path(str(tmp_path)) == ""
    assert settings.get_propose_sync_on_close() is True
    settings.set_production_scenario_path(str(tmp_path), str(tmp_path / "prod"))
    settings.set_propose_sync_on_close(False)
    assert (settings.get_production_scenario_path(str(tmp_path))
            == str(tmp_path / "prod"))
    # un autre projet n'herite PAS du reglage (par projet, vecu 24/09)
    assert settings.get_production_scenario_path(str(tmp_path / "autre")) == "" 
    assert settings.get_propose_sync_on_close() is False


class _ListWidgetProbe:
    pass


def test_dialog_construction_lists_files_and_copy(qapp, trio, tmp_path,
                                                  monkeypatch):
    """Regle projet : construction testee (PyQt6 : exception en slot =
    crash natif). La liste est une DIFFERENCE AVEC LA PRODUCTION ; apres
    copie, une nouvelle session ne propose PLUS RIEN (vecu 24/09 : la
    difference vs la source A reproposait toujours les memes fichiers)."""
    from PyQt6.QtWidgets import QDialog
    from gui.production_sync_dialog import ProductionSyncDialog
    _source, working, vanilla = trio
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working, source_a_root=_source))
    prod_dir = vanilla / "Scenarios" / "re2 atl"
    monkeypatch.setattr("core.settings.get_production_scenario_path",
                        lambda root=None: str(prod_dir))
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(vanilla))
    monkeypatch.setattr("core.settings.set_production_scenario_path",
                        lambda root, p: None)
    seen = []
    monkeypatch.setattr("gui.msgboxes.info",
                        lambda parent, title, text: seen.append((title,
                                                                 text)))
    dlg = ProductionSyncDialog(main)
    # vs production : BlocksConfig modifie + Localization et Nouveau absents
    assert dlg.has_files() and dlg.list_files.count() == 3
    assert dlg.target_edit.text().lower().endswith("re2 atl")
    dlg.chk_backup.setChecked(False)     # n'ecrit pas dans le home
    dlg._do_copy()
    assert (prod_dir / "Content/Configuration/BlocksConfig.ecf").read_text(
        encoding="utf-8") == "MODIFIE"
    assert (prod_dir / "Extras/Nouveau.csv").read_text(
        encoding="utf-8") == "ajoute"
    assert (prod_dir / "Extras/Localization.csv").read_text(
        encoding="utf-8") == "loc"
    # confirmation affichee puis dialogue FERME (accepte)
    assert len(seen) == 1 and "3" in seen[0][1]
    assert dlg.result() == QDialog.DialogCode.Accepted
    # NOUVELLE SESSION : plus aucune difference -> plus aucune proposition
    dlg2 = ProductionSyncDialog(main)
    assert not dlg2.has_files()
    assert not dlg2.btn_copy.isEnabled()


def test_dialog_copy_failure_keeps_dialog_open(qapp, trio, monkeypatch):
    """Une erreur de copie (disque, permission) affiche l'erreur, ne ferme
    PAS le dialogue et ne plante pas nativement (PyQt 6.11 : exception en
    slot = crash)."""
    from PyQt6.QtWidgets import QDialog
    from gui.production_sync_dialog import ProductionSyncDialog
    _source, working, vanilla = trio
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working, source_a_root=_source))
    monkeypatch.setattr("core.settings.get_production_scenario_path",
                        lambda root=None: "")
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(vanilla))
    monkeypatch.setattr("core.settings.set_production_scenario_path",
                        lambda root, p: None)
    errors = []
    monkeypatch.setattr("gui.msgboxes.critical",
                        lambda parent, title, text: errors.append(text))

    def boom(*_a, **_k):
        raise PermissionError("fichier verrouille par le jeu")

    monkeypatch.setattr("core.production_sync.sync_to_production", boom)
    dlg = ProductionSyncDialog(main)
    dlg.chk_backup.setChecked(False)
    dlg._do_copy()
    assert len(errors) == 1 and "verrouille" in errors[0]
    assert dlg.result() != QDialog.DialogCode.Accepted


def test_close_proposal_respects_setting(qapp, monkeypatch):
    """La proposition a la fermeture : rien sans projet ni si l'utilisateur
    a coche « ne plus me proposer » ; sinon dialogue construit et exec()."""
    import gui.main_window as mw
    win = mw.MainWindow.__new__(mw.MainWindow)
    built = []

    class FakeDialog:
        def __init__(self, _main, **_k):
            built.append("built")

        def has_files(self):
            return True

        def exec(self):
            built.append("exec")

    monkeypatch.setattr("core.settings.get_propose_sync_on_close",
                        lambda: True)
    win.workspace = None
    mw.MainWindow._propose_production_sync(win)     # sans projet : rien
    assert built == []
    win.workspace = types.SimpleNamespace(working_root="x")
    monkeypatch.setattr("gui.production_sync_dialog.ProductionSyncDialog",
                        FakeDialog)
    monkeypatch.setattr("core.settings.get_propose_sync_on_close",
                        lambda: False)
    mw.MainWindow._propose_production_sync(win)     # opt-out : rien
    assert built == []
    monkeypatch.setattr("core.settings.get_propose_sync_on_close",
                        lambda: True)
    mw.MainWindow._propose_production_sync(win)
    assert built == ["built", "exec"]
