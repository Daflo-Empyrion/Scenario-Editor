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

"""Tests des deux garde-fous de robustesse ajoutes a la fenetre principale :

- MainWindow.closeEvent : propose d'enregistrer (ou abandonner) les onglets
  modifies avant de fermer l'application, et refuse de fermer si un
  enregistrement echoue -- sinon quitter perdait silencieusement le travail.
- _handle_uncaught_exception : excepthook global installe par main(), qui
  empeche PyQt6 d'achever l'application par qFatal() quand un slot laisse
  filer une exception (voir la note dans gui/main_window.py).

Les tests utilisent la meme technique que le reste de la suite : instance
construite SANS passer par __init__ (object.__new__) pour ne construire que
l'etat requis, et stubs duck-typed a la place des widgets d'edition.
"""
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

import gui.main_window as mw
from gui.main_window import MainWindow, _handle_uncaught_exception


class _StubEditor(QWidget):
    """Pseudo-editeur exposant l'interface duck-typed des onglets
    (is_modified / save) avec trace des appels a save()."""

    def __init__(self, modified=False, fail_save=False):
        super().__init__()
        self._modified = modified
        self.fail_save = fail_save
        self.save_calls = 0

    def is_modified(self):
        return self._modified

    def save(self):
        self.save_calls += 1
        if not self.fail_save:
            self._modified = False


class _FakeStatusBar:
    """Remplace QMainWindow.statusBar(), indisponible sur une instance
    construite sans __init__ (le wrapper sip exige que le super-init ait tourne)."""
    def showMessage(self, message, *args):
        pass


def _make_window(*tab_widgets) -> MainWindow:
    """MainWindow minimal (sans __init__) : uniquement le QTabWidget reel
    utilise par closeEvent et _modified_tab_widgets."""
    win = MainWindow.__new__(MainWindow)
    win.tabs = QTabWidget()
    win.statusBar = lambda: _FakeStatusBar()
    for w in tab_widgets:
        win.tabs.addTab(w, "✎ test.ecf")
    return win


def _answer(answer):
    return lambda *args, **kwargs: answer


def test_close_accepted_when_no_modified_tabs(qapp, monkeypatch):
    win = _make_window(_StubEditor(modified=False))
    monkeypatch.setattr(mw, "ask_save_discard_cancel", _answer("save"))
    event = QCloseEvent()
    event.ignore()
    win.closeEvent(event)
    assert event.isAccepted()


def test_close_cancelled_keeps_window_open(qapp, monkeypatch):
    stub = _StubEditor(modified=True)
    win = _make_window(stub)
    monkeypatch.setattr(mw, "ask_save_discard_cancel", _answer("cancel"))
    event = QCloseEvent()
    win.closeEvent(event)
    assert not event.isAccepted()
    assert stub.save_calls == 0


def test_close_discards_without_saving(qapp, monkeypatch):
    stub = _StubEditor(modified=True)
    win = _make_window(stub)
    monkeypatch.setattr(mw, "ask_save_discard_cancel", _answer("discard"))
    event = QCloseEvent()
    win.closeEvent(event)
    assert event.isAccepted()
    assert stub.save_calls == 0


def test_close_saves_modified_tabs_and_closes(qapp, monkeypatch):
    stub1 = _StubEditor(modified=True)
    stub2 = _StubEditor(modified=True)
    unmodified = _StubEditor(modified=False)
    win = _make_window(stub1, unmodified, stub2)
    monkeypatch.setattr(mw, "ask_save_discard_cancel", _answer("save"))
    event = QCloseEvent()
    win.closeEvent(event)
    assert event.isAccepted()
    # Seuls les onglets modifies sont enregistres, pas les autres.
    assert stub1.save_calls == 1
    assert stub2.save_calls == 1
    assert unmodified.save_calls == 0


def test_close_refused_when_save_fails(qapp, monkeypatch):
    """Un save() en echec laisse le widget modifie (le dialogue d'erreur est
    deja affiche par le widget lui-meme) -- la fermeture doit etre annulee
    pour ne pas perdre le travail en croyant avoir sauvegarde."""
    broken = _StubEditor(modified=True, fail_save=True)
    healthy = _StubEditor(modified=True)
    win = _make_window(broken, healthy)
    monkeypatch.setattr(mw, "ask_save_discard_cancel", _answer("save"))
    event = QCloseEvent()
    win.closeEvent(event)
    assert not event.isAccepted()
    assert broken.save_calls == 1
    assert healthy.save_calls == 1


# ---------------------------------------------------------------------------
# Excepthook global
# ---------------------------------------------------------------------------

def test_keyboardinterrupt_delegates_to_default_hook(qapp, monkeypatch):
    """Ctrl+C reste un signal d'interruption standard : transmis au hook par
    defaut, jamais transforme en rapport de bug."""
    received = {}
    monkeypatch.setattr(mw.sys, "__excepthook__",
                        lambda t, v, tb: received.update(type=t))
    called_dialog = []
    monkeypatch.setattr(mw, "_show_crash_message_box", lambda *a: called_dialog.append(1))
    _handle_uncaught_exception(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert received.get("type") is KeyboardInterrupt
    assert called_dialog == []


def test_hook_shows_dialog_without_raising(qapp, monkeypatch):
    """Cas nominal : une exception quelconque produit un dialogue (visible via
    le monkeypatch), ne sort JAMAIS en exception et ne releve pas l'erreur."""
    dialog_args = []
    monkeypatch.setattr(mw, "_show_crash_message_box",
                        lambda text, value: dialog_args.append(text) or False)
    try:
        raise ValueError("boom")
    except ValueError:
        _handle_uncaught_exception(*mw.sys.exc_info())
    assert len(dialog_args) == 1
    assert "boom" in dialog_args[0]


def test_hook_report_choice_opens_report_dialog(qapp, monkeypatch):
    """Si la personne clique 'Signaler le probleme', le formulaire pre-rempli
    s'ouvre avec la meme pile d'erreur."""
    opened = {}
    monkeypatch.setattr(mw, "_show_crash_message_box", lambda text, value: True)
    monkeypatch.setattr(mw, "_open_crash_report_dialog",
                        lambda text, value: opened.update(text=text))
    try:
        raise RuntimeError("pile de test")
    except RuntimeError:
        _handle_uncaught_exception(*mw.sys.exc_info())
    assert "pile de test" in opened.get("text", "")


def test_hook_never_raises_even_if_dialog_crashes(qapp, monkeypatch):
    """Si le dialogue lui-meme plante, le hook avale l'erreur (sinon PyQt6
    retomberait sur qFatal -- voir gui/main_window.py)."""
    def _boom(text, value):
        raise RuntimeError("dialogue casse")
    monkeypatch.setattr(mw, "_show_crash_message_box", _boom)
    try:
        raise ValueError("erreur initiale")
    except ValueError:
        _handle_uncaught_exception(*mw.sys.exc_info())  # ne doit rien lever


def test_hook_guard_prevents_reentrant_dialog(qapp, monkeypatch):
    """Exception PENDANT l'affichage du dialogue (le dialogue fait tourner une
    boucle evenementielle dans laquelle d'autres slots peuvent planter) : le
    hook est rappele, la garde doit bloquer le second dialogue imbrique.
    Deux crashs SUCCESSIFS (dialogue ferme entre les deux) montrent au
    contraire chacun leur boite -- comportement voulu."""
    events = []
    def _dialog(text, value):
        events.append(text)
        try:
            raise ValueError("seconde")
        except ValueError:
            _handle_uncaught_exception(*mw.sys.exc_info())
        return False
    monkeypatch.setattr(mw, "_show_crash_message_box", _dialog)
    try:
        raise ValueError("premiere")
    except ValueError:
        _handle_uncaught_exception(*mw.sys.exc_info())
    assert len(events) == 1 and "premiere" in events[0]  # jamais de boite imbriquee
