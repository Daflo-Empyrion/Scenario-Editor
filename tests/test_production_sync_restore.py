"""Restauration des sauvegardes de synchro (core/production_sync.py +
bouton du dialogue) : cumul horodate, archive de l'etat actuel avant
remontee, caches .bin invalides, chemin connecte du dialogue."""

import types

from core.production_sync import (list_sync_backups,
                                  restore_production_backup,
                                  sync_backup_root)


def _tree(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_restore_prod_avec_archive_et_invalidation(tmp_path):
    prod = tmp_path / "prod"
    _tree(prod, {
        "Playfields/ATL_Earth/playfield_static.yaml": "NOUVEAU",
        "Playfields/ATL_Earth/playfield_static.yaml.bin": "cache",
        "Content/Configuration/BlocksConfig.ecf": "MODIFIE",
    })
    backup = tmp_path / "sync_root" / "20261029_090000"
    _tree(backup, {
        "Playfields/ATL_Earth/playfield_static.yaml": "ANCIEN",
        "Content/Configuration/BlocksConfig.ecf": "ORIGINE",
    })

    restored, archived, bins, safety = restore_production_backup(prod, backup)
    assert restored == 2 and bins == 1
    assert (prod / "Playfields/ATL_Earth/playfield_static.yaml"
            ).read_text(encoding="utf-8") == "ANCIEN"
    assert not (prod / "Playfields/ATL_Earth/playfield_static.yaml.bin"
                ).exists()
    # l'etat AVANT restauration est archive (cumul)
    assert (safety / "Playfields/ATL_Earth/playfield_static.yaml"
            ).read_text(encoding="utf-8") == "NOUVEAU"
    assert (safety / "Content/Configuration/BlocksConfig.ecf"
            ).read_text(encoding="utf-8") == "MODIFIE"
    assert archived == 2
    assert "avant_restauration_" in safety.name


def test_restore_prod_vide_ou_inconnu(tmp_path):
    prod = tmp_path / "prod"
    restored, archived, bins, safety = restore_production_backup(
        prod, tmp_path / "nulle-part")
    assert (restored, archived, bins, safety) == (0, 0, 0, None)


def test_list_backups_trie_et_filtre(tmp_path, monkeypatch):
    root = tmp_path / "production_sync"
    (root / "20261029_090000").mkdir(parents=True)
    (root / "20261030_100000").mkdir()
    (root / "fichier.txt").write_text("pas un dossier", encoding="utf-8")
    monkeypatch.setattr("core.production_sync.sync_backup_root",
                        lambda: root)
    names = [b.name for b in list_sync_backups()]
    assert names == ["20261029_090000", "20261030_100000"]
    assert sync_backup_root() != root           # defaut = home, intact


def test_dialog_bouton_restaure(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from gui.production_sync_dialog import ProductionSyncDialog

    prod = tmp_path / "prod"
    _tree(prod, {"Playfields/P1/playfield_static.yaml": "NOUVEAU"})
    backup_root = tmp_path / "production_sync"
    backup = backup_root / "20261029_090000"
    _tree(backup, {"Playfields/P1/playfield_static.yaml": "ANCIEN"})
    monkeypatch.setattr("core.production_sync.sync_backup_root",
                        lambda: backup_root)

    working = tmp_path / "working"
    working.mkdir()
    main = types.SimpleNamespace(workspace=types.SimpleNamespace(
        working_root=working, source_a_root=working))
    monkeypatch.setattr("core.settings.get_production_scenario_path",
                        lambda root=None: str(prod))
    monkeypatch.setattr("core.settings.get_vanilla_content_path",
                        lambda: str(tmp_path / "vanilla"))
    monkeypatch.setattr("core.settings.set_production_scenario_path",
                        lambda root, p: None)
    messages = []
    monkeypatch.setattr("gui.msgboxes.info",
                        lambda parent, title, text: messages.append(text))
    monkeypatch.setattr(
        "gui.msgboxes.ask_yes_no",
        lambda parent, title, text: text.endswith("archivé avant."))

    dlg = ProductionSyncDialog(main)
    assert dlg.combo_backups.count() == 1
    dlg.combo_backups.setCurrentIndex(0)
    dlg.btn_restore.click()
    assert (prod / "Playfields/P1/playfield_static.yaml"
            ).read_text(encoding="utf-8") == "ANCIEN"
    assert messages and "1 fichiers restaurés" in messages[0]

    # refus de la confirmation : rien ne change
    monkeypatch.setattr("gui.msgboxes.ask_yes_no",
                        lambda parent, title, text: False)
    messages.clear()
    dlg.btn_restore.click()
    assert messages == []
