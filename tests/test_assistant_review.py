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

"""Revue des propositions et aiguillage de l'envoi : outils -> reponse
complete, sinon flux. Aucun reseau, aucun fichier."""
import pytest
from PyQt6 import sip
from PyQt6.QtCore import Qt

from core import settings
from core.ai.assistant.changeset import Change, ChangeSet
from core.ai.assistant.context import TabContext


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    from core.ai import budget
    budget.reset()


def _empty_binding(name="tab"):
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import ToolRegistry
    return SurfaceBinding(
        name=name, context=lambda: TabContext(name, ""),
        registry=lambda: ToolRegistry(),
        apply=lambda changes: (False, "unsupported"))


def _tooled_binding(name="ecf"):
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import Tool, ToolRegistry

    def registry():
        tools = ToolRegistry()
        tools.add(Tool(name="read", description="", parameters={},
                       handler=lambda args: "", surface=name))
        return tools

    return SurfaceBinding(name=name, context=lambda: TabContext(name, ""),
                          registry=registry,
                          apply=lambda changes: (True, ""))


def test_binding_needs_tools_only_with_a_registry():
    assert _empty_binding().action().needs_tools is False
    assert _tooled_binding().action().needs_tools is True


def test_review_selection_skips_unchecked_and_keeps_edits(qapp):
    from gui.assistant_review_dialog import ChangeReviewDialog
    changeset = ChangeSet(changes=[
        Change(kind="ecf_set", target="[1] / A", old="1", new="2"),
        Change(kind="ecf_set", target="[2] / B", old="3", new="4")])
    dialog = ChangeReviewDialog(changeset, lambda changes: (True, ""))
    try:
        dialog.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
        dialog.table.item(0, 3).setText("2.5")
        selected = dialog.selected_changes()
        assert len(selected) == 1
        assert selected[0].target == "[1] / A" and selected[0].new == "2.5"
    finally:
        sip.delete(dialog)


def test_send_uses_the_stream_worker_without_tools(qapp, monkeypatch):
    from gui import assistant_dialog

    class _Signal:
        def connect(self, *_args):
            pass

    class _Stub:
        started = []

        def __init__(self, *args, **kwargs):
            self.delta = _Signal()
            self.done = _Signal()
            self.failed = _Signal()
            type(self).started.append(self)

        def start(self):
            pass

    class _StreamStub(_Stub):
        started = []

    class _SurfaceStub(_Stub):
        started = []

    monkeypatch.setattr(assistant_dialog, "AssistantWorker", _StreamStub)
    monkeypatch.setattr(assistant_dialog, "SurfaceWorker", _SurfaceStub)
    monkeypatch.setattr(assistant_dialog.router, "configured", lambda: True)

    dialog = assistant_dialog.AssistantDialog(
        surface_provider=lambda: _empty_binding())
    try:
        dialog.input.setPlainText("salut")
        dialog._send()
        assert len(_StreamStub.started) == 1
        assert not _SurfaceStub.started
    finally:
        sip.delete(dialog)


def test_send_uses_the_surface_worker_with_tools(qapp, monkeypatch):
    from gui import assistant_dialog

    class _Signal:
        def connect(self, *_args):
            pass

    class _Stub:
        started = []

        def __init__(self, *args, **kwargs):
            self.delta = _Signal()
            self.done = _Signal()
            self.failed = _Signal()
            type(self).started.append(self)

        def start(self):
            pass

    class _StreamStub(_Stub):
        started = []

    class _SurfaceStub(_Stub):
        started = []

    monkeypatch.setattr(assistant_dialog, "AssistantWorker", _StreamStub)
    monkeypatch.setattr(assistant_dialog, "SurfaceWorker", _SurfaceStub)
    monkeypatch.setattr(assistant_dialog.router, "configured", lambda: True)

    dialog = assistant_dialog.AssistantDialog(
        surface_provider=lambda: _tooled_binding())
    try:
        dialog.input.setPlainText("double Count")
        dialog._send()
        assert len(_SurfaceStub.started) == 1
        assert dialog.btn_stop.isEnabled() is False
    finally:
        sip.delete(dialog)


def test_surface_answer_opens_the_review_with_the_binding(qapp, monkeypatch):
    import gui.assistant_review_dialog as review
    from core.ai.assistant import engine
    from gui.assistant_dialog import AssistantDialog

    seen = []
    monkeypatch.setattr(review, "review_changeset",
                        lambda changeset, apply, parent=None:
                        seen.append((changeset, apply)))
    binding = _tooled_binding()
    dialog = AssistantDialog()
    try:
        dialog._active_surface = binding
        changeset = ChangeSet(changes=[
            Change(kind="ecf_set", target="[399] / HitPoints", old="600",
                   new="900")])
        dialog._on_surface_done(engine.Answer(
            text="Proposition.", link="P / m", changeset=changeset))
        assert seen == [(changeset, binding.apply)]
        assert dialog._worker is None
        assert "Proposition." in dialog.view.toPlainText()
    finally:
        sip.delete(dialog)


def test_invalid_changeset_is_reported_and_not_reviewed(qapp, monkeypatch):
    import gui.assistant_review_dialog as review
    from core.ai.assistant import engine
    from gui.assistant_dialog import AssistantDialog

    seen = []
    monkeypatch.setattr(review, "review_changeset",
                        lambda *args, **kwargs: seen.append(args))
    dialog = AssistantDialog()
    try:
        dialog._active_surface = _tooled_binding()
        dialog._on_surface_done(engine.Answer(
            text="Proposition.",
            changeset=ChangeSet(changes=[
                Change(kind="ecf_set", target="[1] / A")]),
            changeset_problems=["ecf_value_changed"]))
        assert seen == []
        assert "changé" in dialog.status_label.text()
    finally:
        sip.delete(dialog)
