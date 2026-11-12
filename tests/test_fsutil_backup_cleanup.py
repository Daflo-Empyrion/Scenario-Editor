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

"""Menage des sauvegardes de `central_backup` (12/11/2026) : garder les plus
recentes, supprimer les vieilles, ne JAMAIS toucher aux dossiers de
sauvegarde de scenario."""
import os
import time
from pathlib import Path

from core.fsutil import apply_backup_cleanup, plan_backup_cleanup

DAY = 86400


def _bak(folder: Path, name: str, age_days: float, size: int = 100) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"x" * size)
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def test_keeps_the_newest_and_drops_the_old_ones(tmp_path):
    folder = tmp_path / "difficulty"
    for i in range(4):                       # 4 recentes
        _bak(folder, f"Desert-{i}.yaml.bak", age_days=1 + i)
    vieille = _bak(folder, "Desert-vieille.yaml.bak", age_days=200)
    plan = plan_backup_cleanup(tmp_path, keep=4, max_age_days=60)
    assert plan == {vieille: 100}


def test_recent_files_beyond_the_floor_are_kept(tmp_path):
    """Au-dela des `keep`, une sauvegarde recente reste : on ne supprime que
    ce qui est a la fois au-dela du quota ET trop vieux."""
    folder = tmp_path / "blocks"
    for i in range(6):
        _bak(folder, f"Hull-{i}.ecf.bak", age_days=1)
    assert plan_backup_cleanup(tmp_path, keep=2, max_age_days=60) == {}


def test_never_empty_a_folder(tmp_path):
    folder = tmp_path / "corpus"
    seule = _bak(folder, "Localization-1.csv.bak", age_days=999)
    assert seule.is_file()
    assert plan_backup_cleanup(tmp_path, keep=0, max_age_days=1) == {}


def test_sub_folders_and_foreign_files_are_untouched(tmp_path):
    """Une sauvegarde de scenario est un DOSSIER (backup_dialog) ; un fichier
    qui n'est pas un .bak n'est pas de notre ressort."""
    record = tmp_path / "ATL" / "20260930-152417"
    record.mkdir(parents=True)
    (record / "_backup_info.json").write_text("{}", encoding="utf-8")
    old_txt = tmp_path / "cjk_cleanup" / "rapport.txt"
    old_txt.parent.mkdir()
    old_txt.write_text("vieux", encoding="utf-8")
    stamp = time.time() - 400 * DAY
    os.utime(old_txt, (stamp, stamp))
    assert plan_backup_cleanup(tmp_path, keep=1, max_age_days=1) == {}
    assert record.is_dir() and old_txt.is_file()


def test_apply_deletes_only_the_plan(tmp_path):
    folder = tmp_path / "regen"
    garde = _bak(folder, "Desert-recent.yaml.bak", age_days=1)
    parti = _bak(folder, "Desert-vieux.yaml.bak", age_days=200, size=4096)
    count, freed = apply_backup_cleanup(plan_backup_cleanup(
        tmp_path, keep=1, max_age_days=60))
    assert (count, freed) == (1, 4096)
    assert garde.is_file() and not parti.exists()


def test_missing_root_is_not_an_error(tmp_path):
    assert plan_backup_cleanup(tmp_path / "absent") == {}


# ---------------------------------------- lister / restaurer (12/11)

def test_original_name_reconstitue_le_nom_dorigine():
    from core.fsutil import original_name
    assert original_name("Localization-20261112-121530.csv.bak") == \
        "Localization.csv"
    assert original_name("Desert-20261112-121530-1.yaml.bak") == "Desert.yaml"
    assert original_name("sanshorodatage.bak") == "sanshorodatage"


def test_list_backup_files_ignore_les_sous_dossiers(tmp_path):
    from core.fsutil import list_backup_files
    folder = tmp_path / "difficulty"
    recent = _bak(folder, "Desert-20261112-121530.yaml.bak", age_days=1, size=10)
    _bak(folder, "Desert-20260901-101010.yaml.bak", age_days=40, size=20)
    record = tmp_path / "ATL" / "20260930-152417"
    record.mkdir(parents=True)
    (record / "_backup_info.json").write_text("{}", encoding="utf-8")
    rows = list_backup_files(tmp_path)
    assert [r[0] for r in rows] == [recent, folder / "Desert-20260901-101010.yaml.bak"]
    assert {r[1] for r in rows} == {"difficulty"}
    assert rows[0][3] == 10


def test_restore_backup_file_copie_et_sauvegarde_lactuel(tmp_path, monkeypatch):
    from core.fsutil import restore_backup_file
    backup = _bak(tmp_path / "corpus", "Localization-20261112-121530.csv.bak",
                  age_days=1)
    backup.write_text("ancienne version", encoding="utf-8")
    target = tmp_path / "scenario" / "Localization.csv"
    target.parent.mkdir()
    target.write_text("version actuelle", encoding="utf-8")
    appels = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind="sectors": appels.append((path, kind))
                        or tmp_path / "secours.csv.bak")
    safety = restore_backup_file(backup, target)
    assert target.read_text(encoding="utf-8") == "ancienne version"
    assert appels == [(target, "restauration")]
    assert safety == tmp_path / "secours.csv.bak"


def test_restore_sans_fichier_existant_ne_sauvegarde_rien(tmp_path, monkeypatch):
    from core.fsutil import restore_backup_file
    backup = _bak(tmp_path / "corpus", "PDA-20261112-121530.csv.bak", age_days=1)
    appels = []
    monkeypatch.setattr("core.fsutil.central_backup",
                        lambda path, kind="sectors": appels.append(kind))
    target = tmp_path / "PDA.csv"
    assert restore_backup_file(backup, target) is None
    assert appels == []
