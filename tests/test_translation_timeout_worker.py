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

"""Tests du timeout de traduction (core/translation.py -- deep-translator ne
passe aucun timeout a requests, une connexion pendante figerait sinon l'appelant
indefiniment) et du worker de traduction en lot (gui/translation_worker.py).
Aucun reseau : GoogleTranslator / translate_text sont remplaces par des doubles."""
import time

import pytest
from PyQt6.QtCore import QEventLoop

from core import translation, translation_memory


@pytest.fixture
def offline_env(tmp_path, monkeypatch):
    """Isolation complete : memoire de traduction en temporaire, opt-out
    confidentialite force a True (autorisé), pour ne JAMAIS toucher a la vraie
    memoire de l'utilisateur ni au reseau."""
    monkeypatch.setattr(translation_memory, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(translation_memory, 'MEMORY_FILE', tmp_path / 'memory.json')
    monkeypatch.setattr(translation_memory, '_cache', None)
    monkeypatch.setattr(translation_memory, '_cache_for_path', None)
    monkeypatch.setattr('core.settings.get_online_translation_enabled', lambda: True)


class _FakeTranslator:
    """Double de GoogleTranslator : repond tout de suite, ou apres un delai, ou
    avec une erreur -- selon les attributs de classe regles par le test."""
    delay_s = 0.0
    error = None
    seen_text = None

    def __init__(self, source="auto", target="fr", **kwargs):
        pass

    def translate(self, text):
        _FakeTranslator.seen_text = text
        # Lookups via type(self) : les sous-classes de test redefinissent
        # delay_s/error, il faut voir l'ombre et non l'attribut de la base.
        if type(self).delay_s:
            time.sleep(type(self).delay_s)
        if type(self).error is not None:
            raise type(self).error
        return f"TRAD[{text}]"


def test_translate_text_returns_result(offline_env, monkeypatch):
    monkeypatch.setattr(translation, 'GoogleTranslator', _FakeTranslator)
    assert translation.translate_text("hello", timeout_seconds=5) == "TRAD[hello]"


def test_translate_text_times_out_on_hung_connection(offline_env, monkeypatch):
    """Le cas que le timeout existe pour resoudre : Google ne repond JAMAIS.
    Sans garde, l'appelant (l'interface !) restait gele indefiniment."""
    class _Hung(_FakeTranslator):
        delay_s = 5.0  # bien plus long que le timeout du test
    monkeypatch.setattr(translation, 'GoogleTranslator', _Hung)
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        translation.translate_text("hello", timeout_seconds=0.2)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0  # rend la main quasi immédiatement, pas apres 5 s


def test_translate_text_propagates_translator_error(offline_env, monkeypatch):
    class _Broken(_FakeTranslator):
        error = RuntimeError("HTTP 429")
    monkeypatch.setattr(translation, 'GoogleTranslator', _Broken)
    with pytest.raises(RuntimeError):
        translation.translate_text("hello", timeout_seconds=5)


# ---------------------------------------------------------------------------
# BatchTranslationWorker
# ---------------------------------------------------------------------------

def test_worker_translates_all_texts_and_signals(qapp, monkeypatch):
    from gui.translation_worker import BatchTranslationWorker
    monkeypatch.setattr(translation, 'translate_text',
                        lambda text, target="fr": f"TRAD:{text}")

    worker = BatchTranslationWorker(["a", "b", "c"], "fr")
    results = {}
    progress_seen = []
    loop = QEventLoop()
    worker.item_done.connect(
        lambda i, tr, err: results.__setitem__(i, (tr, err)))
    worker.progress.connect(lambda done, total: progress_seen.append((done, total)))
    worker.finished_all.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()

    assert results == {0: ("TRAD:a", ""), 1: ("TRAD:b", ""), 2: ("TRAD:c", "")}
    assert progress_seen[0] == (0, 3)


def test_worker_reports_errors_without_stopping(qapp, monkeypatch):
    """Un texte qui echoue produit un item_done avec message d'erreur, et le lot
    continue sur les suivants (l'arret anticipe est decide par l'appelant)."""
    from gui.translation_worker import BatchTranslationWorker

    def _flaky(text, target="fr"):
        if text == "boom":
            raise RuntimeError("panne")
        return f"TRAD:{text}"
    monkeypatch.setattr(translation, 'translate_text', _flaky)

    worker = BatchTranslationWorker(["ok1", "boom", "ok2"], "fr")
    results = {}
    loop = QEventLoop()
    worker.item_done.connect(
        lambda i, tr, err: results.__setitem__(i, (tr, err)))
    worker.finished_all.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()

    assert results[0] == ("TRAD:ok1", "")
    assert results[1][0] == "" and "panne" in results[1][1]
    assert results[2] == ("TRAD:ok2", "")


def test_worker_stop_takes_effect_between_items(qapp, monkeypatch):
    """stop() arrete le lot entre deux textes : les suivants ne sont pas traduits.
    Chaque traduction dort un peu pour que les signaux (mis en file entre
    threads) aient le temps d'etre delivres pendant le lot."""
    from gui.translation_worker import BatchTranslationWorker

    def _slow(text, target="fr"):
        time.sleep(0.1)
        return f"TRAD:{text}"
    monkeypatch.setattr(translation, 'translate_text', _slow)

    worker = BatchTranslationWorker(["a", "b", "c", "d"], "fr")
    done = []
    loop = QEventLoop()

    def _on_item(i, tr, err):
        done.append(i)
        if len(done) == 1:
            worker.stop()  # arret des le premier texte
    worker.item_done.connect(_on_item)
    worker.finished_all.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()

    assert done[0] == 0
    assert len(done) < 4  # arrete avant la fin (marge sur le timing de delivrance)
