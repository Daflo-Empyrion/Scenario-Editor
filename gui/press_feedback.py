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

"""
Animation de pression des boutons -- look Relief phase 2 (12/09/2026).

Un eventFilter GLOBAL sur QApplication decale les QAbstractButton de 2px
vers le bas au clic (QPropertyAnimation sur "geometry", ~70 ms) puis les
ramene au relachement : enfoncement subtil, sans sous-classer les boutons
ni retoucher les layouts. Disponible UNIQUEMENT sur un theme Relief (le
retour visuel QSS "biseau inverse" des autres themes reste inchangé) et
desactivable dans Options (core.settings.press_anim_enabled).

PERFORMANCE : le filtre voit TOUS les evenements de l'application -- il ne
fait donc JAMAIS d'E/S disque (settings._get relit settings.json a chaque
appel !). L'option est mise en memoire a l'installation, rafraichie par
refresh_enabled() au toggle utilisateur et au changement de theme. Toute
exception est avalée : PyQt6 6.11 + exception dans un slot/filtre = crash
natif silencieux (piege connu du projet).
"""
import logging

from PyQt6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton

from core import settings

logger = logging.getLogger(__name__)

_SINK_MS, _RISE_MS, _OFFSET = 70, 90, 2

# Boutons animes : vrais boutons uniquement -- QCheckBox/QRadioButton
# (aussi des QAbstractButton) n'ont pas a "s'enfoncer" de 2px. Les widgets
# Fluent du pilote derivent de QPushButton : couverts.
_BUTTON_TYPES = (QPushButton, QToolButton)

# Etat memoire -- None = relire settings UNE fois au premier besoin.
_enabled_memo = None
_instance = None


def refresh_enabled() -> None:
    """Relit l'option utilisateur en memoire. A appeler au toggle Options et
    apres apply_theme() (changement de theme -> Relief ou non)."""
    global _enabled_memo
    try:
        from gui.theme import is_relief_theme
        _enabled_memo = is_relief_theme() and settings.get_press_anim_enabled()
    except Exception:
        _enabled_memo = False


def enabled() -> bool:
    if _enabled_memo is None:
        refresh_enabled()
    return bool(_enabled_memo)


class _PressFeedback(QObject):
    """Filtre global : press = enfoncement anime, release = retour."""

    def __init__(self):
        super().__init__()
        # id(bouton) -> (reference forte, geometry d'origine). La reference
        # est tenue seulement PENDANT l'appui ; purge sur destroyed.
        self._pressed = {}
        self._anims = {}

    def eventFilter(self, obj, event):
        try:
            if not enabled() or not isinstance(obj, _BUTTON_TYPES):
                return False
            etype = event.type()
            if etype == QEvent.Type.MouseButtonPress:
                # isDown() est encore False ici : le filtre voit l'evenement
                # AVANT le traitement de QAbstractButton (qui pose l'etat
                # down) -- on teste donc explicitement le bouton gauche.
                if obj.isEnabled() and event.button() == Qt.MouseButton.LeftButton \
                        and id(obj) not in self._pressed:
                    self._sink(obj)
            elif etype == QEvent.Type.MouseButtonRelease:
                self._rise(obj)
            elif etype == QEvent.Type.Destroyed:
                self._pressed.pop(id(obj), None)
                self._anims.pop(id(obj), None)
        except Exception:
            logger.debug("press_feedback: filtre ignore", exc_info=True)
        return False

    def _sink(self, btn):
        geo = btn.geometry()
        self._pressed[id(btn)] = (btn, geo)
        anim = QPropertyAnimation(btn, b"geometry", btn)
        anim.setDuration(_SINK_MS)
        anim.setStartValue(geo)
        anim.setEndValue(geo.translated(0, _OFFSET))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self._on_sink_done)
        anim.start()
        self._anims[id(btn)] = anim

    def _on_sink_done(self):
        # Filet de securite : si le release n'est jamais arrive sur le bouton
        # (popup modal ouvert au pressed qui capture la souris), on retablit
        # la geometry -- aucune fiche ne doit rester enfoncee.
        anim = self.sender()
        if anim is None:
            return
        for bid, entry in list(self._pressed.items()):
            if self._anims.get(bid) is anim:
                btn, geo = entry
                if not btn.isDown():
                    self._rise(btn)
                break

    def _rise(self, btn):
        entry = self._pressed.pop(id(btn), None)
        if entry is None:
            return
        old = entry[1]
        anim = QPropertyAnimation(btn, b"geometry", btn)
        anim.setDuration(_RISE_MS)
        anim.setStartValue(btn.geometry())
        anim.setEndValue(old)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda bid=id(btn): self._anims.pop(bid, None))
        anim.start()
        self._anims[id(btn)] = anim


def install(app: QApplication = None) -> None:
    """A appeler UNE fois au demarrage, apres apply_theme(). Idempotent."""
    global _instance
    refresh_enabled()
    if _instance is None:
        _instance = _PressFeedback()
        (app or QApplication.instance()).installEventFilter(_instance)
