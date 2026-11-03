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

"""Tests de gui/dialog_policy.py -- politique commune des fenetres
(31/10/2026) : bouton Agrandir partout, exec() qui ne verrouille plus les
autres fenetres et garde son code de retour, QMessageBox toujours modale."""
import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QMessageBox


@pytest.fixture
def policy(qapp):
    from gui import dialog_policy
    dialog_policy.install()
    yield dialog_policy
    dialog_policy.uninstall()


def test_install_is_idempotent(policy):
    before = QDialog.exec
    policy.install()
    assert QDialog.exec is before


def test_every_dialog_gets_the_maximize_button(policy):
    dialog = QDialog()
    assert dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint


def test_exec_returns_the_dialog_result_without_locking_the_app(policy):
    """Le code appelant attend toujours la fermeture (meme valeur de
    retour), mais les autres fenetres restent utilisables : c'est la
    demande utilisateur du 31/10/2026 (bilan F5, rapports...)."""
    dialog = QDialog()
    seen = {}

    def probe():
        seen["modal"] = dialog.isModal()
        seen["modality"] = dialog.windowModality()
        dialog.accept()

    QTimer.singleShot(0, probe)
    result = dialog.exec()
    assert result == int(QDialog.DialogCode.Accepted)
    assert seen["modal"] is False
    assert seen["modality"] == Qt.WindowModality.NonModal


def test_exec_reports_rejection(policy):
    dialog = QDialog()
    QTimer.singleShot(0, dialog.reject)
    assert dialog.exec() == int(QDialog.DialogCode.Rejected)


def test_message_boxes_stay_blocking(policy, monkeypatch):
    """Une confirmation ne doit jamais laisser modifier l'objet de la
    question pendant qu'elle est ouverte."""
    calls = []
    monkeypatch.setattr(policy, "_original_exec",
                        lambda self: calls.append(self) or 7)
    box = QMessageBox()
    assert policy._policy_exec(box) == 7
    assert calls == [box]


class _SingleDialog(QDialog):
    pass


class _MultiDialog(QDialog):
    allow_multiple = True


def test_second_instance_is_refused_and_first_raised(policy):
    """Une fenetre du meme type deja ouverte : la seconde n'apparait pas,
    la premiere revient au premier plan et l'appelant recoit Rejected."""
    first = _SingleDialog()
    results = []

    def open_second():
        second = _SingleDialog()
        results.append(second.exec())
        results.append(second.isVisible())

    QTimer.singleShot(0, open_second)
    QTimer.singleShot(60, first.accept)
    assert first.exec() == int(QDialog.DialogCode.Accepted)
    assert results == [int(QDialog.DialogCode.Rejected), False]


def test_allow_multiple_opens_two_windows(policy):
    first = _MultiDialog()
    seen = []

    def open_second():
        second = _MultiDialog()
        QTimer.singleShot(0, second.accept)
        seen.append(second.exec())

    QTimer.singleShot(0, open_second)
    QTimer.singleShot(120, first.accept)
    assert first.exec() == int(QDialog.DialogCode.Accepted)
    assert seen == [int(QDialog.DialogCode.Accepted)]


def test_same_window_can_reopen_after_close(policy):
    first = _SingleDialog()
    QTimer.singleShot(0, first.accept)
    assert first.exec() == int(QDialog.DialogCode.Accepted)
    second = _SingleDialog()
    QTimer.singleShot(0, second.accept)
    assert second.exec() == int(QDialog.DialogCode.Accepted)


def test_progress_dialogs_get_no_maximize_buttons(policy):
    """Vecu 03/11/2026 : creer un projet fermait l'application SANS message
    (access violation native dans setWindowFlags, pile enable_maximize) --
    la QProgressDialog de la copie du scenario passait par ce patch. Une
    barre de progression ne doit JAMAIS recevoir de boutons de fenetre."""
    from PyQt6.QtWidgets import QProgressDialog
    progress = QProgressDialog("copie", None, 0, 0)
    flags = progress.windowFlags()
    assert not (flags & Qt.WindowType.WindowMaximizeButtonHint)
    assert not (flags & Qt.WindowType.WindowMinimizeButtonHint)


def test_exec_survives_a_dialog_with_its_own_result_attribute(policy):
    """Vecu 03/11/2026 : MergePreviewDialog stocke son resultat dans
    self.result (objet MergeResult), ce qui masquait la methode
    QDialog.result() -- 'MergeResult object is not callable', la fusion du
    premier fichier echouait. exec() doit rester insensible a cet attribut."""
    class _OwnResultDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.result = "mon propre resultat"

    dialog = _OwnResultDialog()
    QTimer.singleShot(0, dialog.accept)
    assert dialog.exec() == int(QDialog.DialogCode.Accepted)

    dialog2 = _OwnResultDialog()
    QTimer.singleShot(0, dialog2.reject)
    assert dialog2.exec() == int(QDialog.DialogCode.Rejected)
