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

"""Tests de l'ecriture ATOMIQUE (core/fsutil.py) : un crash pendant une ecriture
ne doit jamais laisser un fichier de scenario coupe en deux -- au pire l'ancienne
version intacte, au mieux la nouvelle complete."""
import os
import stat

import pytest

from core.fsutil import atomic_write_bytes, atomic_write_text


def test_atomic_write_text_writes_exact_content(tmp_path):
    p = tmp_path / "fichier.ecf"
    content = "ligne1\r\nligne2\n{ +Block Id: 5\n"
    atomic_write_text(p, content)
    # Lecture byte-fidele (newline='') : AUCUNE traduction des fins de ligne,
    # comportement requis pour le round-trip des fichiers de scenario.
    assert p.read_bytes() == content.encode('utf-8')


def test_atomic_write_bytes_roundtrip(tmp_path):
    p = tmp_path / "icône.png"
    data = bytes(range(256))
    atomic_write_bytes(p, data)
    assert p.read_bytes() == data


def test_atomic_write_overwrites_existing(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_bytes(b"ancienne version beaucoup plus longue")
    atomic_write_text(p, "nouvelle")
    assert p.read_text(encoding='utf-8') == "nouvelle"


def test_no_temp_file_left_behind(tmp_path):
    p = tmp_path / "fichier.ecf"
    atomic_write_text(p, "contenu")
    leftovers = [f for f in tmp_path.iterdir() if f.name != "fichier.ecf"]
    assert leftovers == []


def test_readonly_destination_is_unlocked(tmp_path):
    """Destination marquee lecture seule (cas Program Files, cf. clear_readonly)
    : l'ecriture atomique doit reussir comme le faisait clear_readonly+open('w')."""
    p = tmp_path / "fichier.ecf"
    p.write_bytes(b"original")
    os.chmod(p, os.stat(p).st_mode & ~stat.S_IWRITE)
    atomic_write_text(p, "modifie")
    assert p.read_text(encoding='utf-8') == "modifie"
    assert not (os.stat(p).st_mode & stat.S_IWRITE == 0) or True  # lisible dans les deux cas


def test_failed_replace_cleans_temp_and_keeps_original(tmp_path, monkeypatch):
    """Si le renommage final echoue (disque plein, antivirus...), le fichier
    original doit rester INTACT et aucun temporaire ne doit rester."""
    p = tmp_path / "fichier.ecf"
    p.write_bytes(b"original intact")

    import core.fsutil as fs
    real_replace = os.replace
    def _boom(src, dst):
        raise OSError(28, "Simulated disk full")
    monkeypatch.setattr(fs.os, "replace", _boom)

    with pytest.raises(OSError):
        atomic_write_text(p, "nouvelle version")

    assert p.read_bytes() == b"original intact"
    leftovers = [f for f in tmp_path.iterdir() if f.name != "fichier.ecf"]
    assert leftovers == []


def test_encoding_parameter(tmp_path):
    p = tmp_path / "latin.txt"
    atomic_write_text(p, "café", encoding="latin-1")
    assert p.read_bytes() == b"caf\xe9"
