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

"""Thread d'appel IA de l'assistant (jamais le thread GUI).

Flux gratuit si possible (le texte s'affiche au fur et a mesure), sinon
repli sur la reponse complete -- un maillon payant n'est jamais streame
(voir router.stream_with_link : pas d'usage en SSE, donc pas de decompte).
Arret cooperatif : le drapeau est teste entre deux fragments ; la fermeture
du generateur coupe la connexion HTTP.
"""
from PyQt6.QtCore import QThread, pyqtSignal

from core.ai import router
from core.ai.assistant import engine
from core.ai.assistant.dsml import strip as strip_dsml
from core.engine_errors import EngineError, EngineUnavailableError


class AssistantWorker(QThread):
    delta = pyqtSignal(str)
    done = pyqtSignal(str, str, bool)   # texte, maillon, streamed
    failed = pyqtSignal(str)

    def __init__(self, messages: list, *, min_class: str = "normal",
                 purpose: str = "assistant", parent=None):
        super().__init__(parent)
        self._messages = messages
        self._min_class = min_class
        self._purpose = purpose
        self._stop = False
        self._text = ""
        self._cut = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        stream = router.stream_with_link(
            self._messages, min_class=self._min_class,
            purpose=self._purpose)
        link = ""
        streamed = True
        try:
            try:
                for kind, payload in stream:
                    if self._stop:
                        break
                    if kind == "start":
                        link = payload.label
                    elif not self._cut:
                        self._text += payload
                        if "dsml" in self._text.lower():
                            # Appel d'outil ecrit en texte : on coupe le flux,
                            # la reponse propre est rendue a la fin (vecu 22/10).
                            self._cut = True
                            continue
                        self.delta.emit(payload)
            except EngineUnavailableError:
                if self._text:
                    raise
                streamed = False
                result, candidate = router.chat_with_link(
                    self._messages, min_class=self._min_class,
                    purpose=self._purpose)
                self._text = result.get("content") or ""
                link = candidate.label
            finally:
                close = getattr(stream, "close", None)
                if close is not None:
                    close()
            self.done.emit(strip_dsml(self._text), link, streamed)
        except EngineError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001 -- jamais de crash muet en thread
            self.failed.emit(f"{type(e).__name__}: {e}")


class SurfaceWorker(QThread):
    """Un echange complet avec outils et ChangeSet (reponse non streamee).

    Pas d'arret possible en cours d'appel : le bouton Arreter est desactive
    pour ce chemin plutot que de simuler une annulation qui n'arreterait rien.
    """

    done = pyqtSignal(object)   # Answer
    failed = pyqtSignal(str)

    def __init__(self, session, action, registry, parent=None):
        super().__init__(parent)
        self._session = session
        self._action = action
        self._registry = registry

    def run(self) -> None:
        try:
            self.done.emit(engine.ask(self._session, self._action,
                                      self._registry))
        except EngineError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")
