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

"""list_changed_files (production sync) : le chemin rapide taille+mtime
NE DOIT PAS changer la semantique — vecu 17/10 : 64 s de scan pour zero
changement parce que TOUT etait hashé des deux cotes. Les quatre cas :

  1. copie copy2 (meme mtime, meme contenu)  -> PAS signale
  2. re-ecrit a l'octet pres (mtime differe,
     contenu identique)                      -> PAS signale (docstring)
  3. modifie reellement                       -> 'modified'
  4. absent de la cible                       -> 'added'
Plus : .bak et .yaml.bin jamais proposes."""

import os
import time
from pathlib import Path

from gui.modified_files_dialog import list_changed_files


def _mk(root: Path, rel: str, content: bytes, mtime: float | None = None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def _scenario(tmp_path: Path):
    work = tmp_path / "work"
    prod = tmp_path / "prod"
    work.mkdir()
    prod.mkdir()
    now = time.time()
    base = b"Playfield: Test"
    # 1) copie fidele type copy2 : meme contenu, meme mtime
    _mk(work, "Playfields/A/playfield.yaml", base, now)
    _mk(prod, "Playfields/A/playfield.yaml", base, now)
    return work, prod, now


def test_case1_identical_mtime_and_content_not_reported(tmp_path):
    work, prod, _ = _scenario(tmp_path)
    assert list_changed_files(work, prod) == []


def test_case2_rewritten_identical_content_not_reported(tmp_path):
    work, prod, now = _scenario(tmp_path)
    # re-ecrit a l'octet pres : mtime PLUS RECENT, contenu identique
    _mk(work, "Playfields/A/playfield.yaml", b"Playfield: Test", now + 60)
    assert list_changed_files(work, prod) == []


def test_case3_really_modified_reported(tmp_path):
    work, prod, _ = _scenario(tmp_path)
    _mk(work, "Playfields/A/playfield.yaml", b"Playfield: Modifie !")
    changes = list_changed_files(work, prod)
    assert len(changes) == 1 and changes[0][1] == "modified"


def test_case3b_same_size_different_mtime_different_content(tmp_path):
    work, prod, now = _scenario(tmp_path)
    # meme taille, contenu different, mtime different (cas du hash)
    _mk(work, "Playfields/A/playfield.yaml", b"Playfield: Tesa", now + 5)
    changes = list_changed_files(work, prod)
    assert len(changes) == 1 and changes[0][1] == "modified"


def test_case4_added_and_filters(tmp_path):
    work, prod, now = _scenario(tmp_path)
    _mk(work, "Playfields/B/new.yaml", b"x", now)
    _mk(work, "Playfields/A/old.yaml.bak", b"x", now)
    _mk(work, "Playfields/A/playfield.yaml.bin", b"x", now)
    changes = list_changed_files(work, prod)
    assert [(Path(p).name, s) for p, s in changes] == [("new.yaml", "added")]


def test_sync_then_rescan_is_empty(tmp_path):
    """Le cas utilisateur : apres une copie copy2 (mtime conserve), un
    re-scan ne doit RIEN signaler."""
    work, prod, now = _scenario(tmp_path)
    # simulation d'une session de travail : 2 fichiers touches
    _mk(work, "Playfields/A/playfield.yaml", b"Playfield: V2")
    _mk(work, "Configuration/ItemsConfig.ecf", b"{ Item }", now + 3)
    changes = list_changed_files(work, prod)
    assert len(changes) == 2
    # sync (copy2 comme le fait le core) : mtime conserve
    for src, _s in changes:
        dst = prod / Path(src).relative_to(work)
        dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src, dst)
    assert list_changed_files(work, prod) == []
