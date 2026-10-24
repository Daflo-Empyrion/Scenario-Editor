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

"""Fenetre d'assistant et palettes : chargement d'historique, badge de
contexte, payload, avertissement sans fournisseur, cout. Aucun reseau."""
import types

import pytest
from PyQt6 import sip

from core import settings
from core.ai.assistant.context import TabContext, build


def _binding(label="Blocks.ecf", text="Count: 3"):
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import ToolRegistry
    return SurfaceBinding(name="tab",
                          context=lambda: build(label, text),
                          registry=lambda: ToolRegistry(),
                          apply=lambda changes: (False, "unsupported"))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    from core.ai import budget
    budget.reset()


def test_payload_with_context_prefixes_the_question():
    from gui.assistant_dialog import payload_with_context
    context = build("Blocks.ecf", "Count: 3")
    payload = payload_with_context("Pourquoi 3 ?", context)
    assert payload.startswith("[Contexte joint : Blocks.ecf]")
    assert payload.endswith("Pourquoi 3 ?")
    assert payload_with_context("Pourquoi ?", TabContext("", "")) == \
        "Pourquoi ?"


def test_display_text_strips_native_tool_markup():
    from gui.assistant_dialog import display_text
    markup = ("Fini.\n<｜｜DSML｜｜ calls>"
              "<｜｜DSML｜｜ invoke name=\"file_read\">"
              "</｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>")
    assert display_text(markup) == "Fini."


def test_dialog_restores_history_without_the_context_block(qapp, tmp_path):
    from core.ai.assistant.session import Session
    from gui.assistant_dialog import AssistantDialog
    path = tmp_path / "history.json"
    session = Session()
    session.add_user("[Contexte joint : Blocks.ecf]\nCount: 3\n"
                     "[/Contexte joint]\n\nPourquoi 3 ?")
    session.add_assistant("Parce que.")
    session.save(path)

    dialog = AssistantDialog(history_path=path)
    try:
        assert [role for role, _text in dialog._entries] == ["user",
                                                             "assistant"]
        assert dialog._entries[0][1] == "Pourquoi 3 ?"
        assert "Blocks.ecf" not in dialog.view.toPlainText()
    finally:
        sip.delete(dialog)


def test_dialog_shows_the_context_badge(qapp):
    from gui.assistant_dialog import AssistantDialog
    dialog = AssistantDialog(surface_provider=_binding)
    try:
        dialog._refresh_context()
        text = dialog.context_label.text()
        assert "Blocks.ecf" in text and "8" in text
    finally:
        sip.delete(dialog)


def test_detached_context_shows_none(qapp):
    from gui.assistant_dialog import AssistantDialog
    dialog = AssistantDialog(surface_provider=_binding)
    try:
        dialog.join_check.setChecked(False)
        dialog._refresh_context()
        assert "Aucun contexte" in dialog.context_label.text()
        assert dialog._context().text == ""
    finally:
        sip.delete(dialog)


def test_send_without_provider_warns_and_starts_nothing(qapp, monkeypatch):
    from gui import assistant_dialog
    monkeypatch.setattr(assistant_dialog.router, "configured", lambda: False)
    dialog = assistant_dialog.AssistantDialog()
    try:
        dialog.input.setPlainText("salut")
        dialog._send()
        assert dialog._worker is None
        assert "Aucun fournisseur" in dialog.status_label.text()
    finally:
        sip.delete(dialog)


def test_cost_label_only_when_paid_is_enabled(qapp):
    from gui.assistant_dialog import AssistantDialog
    dialog = AssistantDialog()
    try:
        dialog._refresh_cost()
        assert dialog.cost_label.text() == ""
        settings.set_ai_paid_enabled(True)
        settings.set_ai_monthly_cap_usd(2.0)
        dialog._refresh_cost()
        assert "2.00" in dialog.cost_label.text()
    finally:
        sip.delete(dialog)


def test_palette_returns_the_typed_question(qapp):
    from gui.assistant_palette import AssistantPalette
    palette = AssistantPalette()
    try:
        palette.line.setText("  c'est quoi Count ?  ")
        palette._accept()
        assert palette.choice() == ("ask", "c'est quoi Count ?")
    finally:
        sip.delete(palette)


def test_worker_streams_and_reports_the_link(qapp, monkeypatch):
    from gui import assistant_worker
    link = types.SimpleNamespace(label="P / m")

    def fake_stream(messages, **kwargs):
        yield ("start", link)
        yield ("delta", "Bon")
        yield ("delta", "jour")

    monkeypatch.setattr(assistant_worker.router, "stream_with_link",
                        fake_stream)
    worker = assistant_worker.AssistantWorker([{"role": "user",
                                                "content": "x"}])
    try:
        chunks, done = [], []
        worker.delta.connect(chunks.append)
        worker.done.connect(lambda *args: done.append(args))
        worker.failed.connect(lambda message: done.append(("failed", message)))
        worker.run()
        assert chunks == ["Bon", "jour"]
        assert done == [("Bonjour", "P / m", True)]
    finally:
        sip.delete(worker)


def test_worker_never_streams_native_tool_markup(qapp, monkeypatch):
    from gui import assistant_worker
    link = types.SimpleNamespace(label="P / m")

    def fake_stream(messages, **kwargs):
        yield ("start", link)
        yield ("delta", "Je verifie.")
        yield ("delta", "\n<｜｜DSML｜｜ calls>")
        yield ("delta", "<｜｜DSML｜｜ invoke name=\"file_read\">")

    monkeypatch.setattr(assistant_worker.router, "stream_with_link",
                        fake_stream)
    worker = assistant_worker.AssistantWorker([{"role": "user",
                                                "content": "x"}])
    try:
        chunks, done = [], []
        worker.delta.connect(chunks.append)
        worker.done.connect(lambda *args: done.append(args))
        worker.run()
        assert "".join(chunks) == "Je verifie."
        assert done == [("Je verifie.", "P / m", True)]
    finally:
        sip.delete(worker)


def test_worker_falls_back_to_a_full_answer_without_free_link(qapp,
                                                              monkeypatch):
    from core.engine_errors import EngineUnavailableError
    from gui import assistant_worker
    link = types.SimpleNamespace(label="P / payant")

    def fake_stream(messages, **kwargs):
        raise EngineUnavailableError("aucun maillon gratuit")
        yield  # pragma: no cover -- rend la fonction generatrice

    monkeypatch.setattr(assistant_worker.router, "stream_with_link",
                        fake_stream)
    monkeypatch.setattr(assistant_worker.router, "chat_with_link",
                        lambda messages, **kwargs: ({"content": "complet"},
                                                    link))
    worker = assistant_worker.AssistantWorker([{"role": "user",
                                                "content": "x"}])
    try:
        done = []
        worker.done.connect(lambda *args: done.append(args))
        worker.run()
        assert done == [("complet", "P / payant", False)]
    finally:
        sip.delete(worker)


def test_worker_reports_a_failure(qapp, monkeypatch):
    from core.engine_errors import AuthError
    from gui import assistant_worker

    def fake_stream(messages, **kwargs):
        raise AuthError("cle invalide")
        yield  # pragma: no cover

    monkeypatch.setattr(assistant_worker.router, "stream_with_link",
                        fake_stream)
    monkeypatch.setattr(assistant_worker.router, "chat_with_link",
                        lambda messages, **kwargs: (_ for _ in ()).throw(
                            AuthError("cle invalide")))
    worker = assistant_worker.AssistantWorker([{"role": "user",
                                                "content": "x"}])
    try:
        failures = []
        worker.failed.connect(failures.append)
        worker.run()
        assert failures == ["cle invalide"]
    finally:
        sip.delete(worker)


def _answer(changes, text="proposition"):
    return types.SimpleNamespace(text=text, changeset=changes,
                                 problems=[], changeset_problems=[],
                                 link="", tool_log=[], rounds=1)


def _readonly_binding(kinds=("scenario_import",)):
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import ToolRegistry
    return SurfaceBinding(name="tab",
                          context=lambda: TabContext("", ""),
                          registry=lambda: ToolRegistry(),
                          apply=lambda changes: (False, "unsupported"),
                          kinds=kinds)


def test_review_drops_rows_the_surface_cannot_apply(qapp, monkeypatch):
    """Vecu 23/10 : une proposition yaml_set depuis un onglet sans ecrivain
    ouvrait une revue dont l'Apply repondait toujours « Cet onglet n'applique
    aucune modification ». Les lignes etrangeres sont retirees AVANT la revue."""
    from core.ai.assistant.changeset import Change, ChangeSet
    from gui import assistant_dialog as ad
    from gui import assistant_review_dialog

    binding = _readonly_binding()
    dialog = ad.AssistantDialog(surface_provider=lambda: binding)
    shown = []
    monkeypatch.setattr(assistant_review_dialog, "review_changeset",
                        lambda changeset, apply, parent=None:
                        shown.append(changeset))
    try:
        dialog._active_surface = binding
        dialog._on_surface_done(_answer(ChangeSet(changes=[
            Change(kind="yaml_set", target="a.B", old="1", new="2"),
            Change(kind="scenario_import", target="a:x.ecf", old="absent",
                   new="ok")])))
        assert [c.kind for c in shown[0].changes] == ["scenario_import"]
        assert "1 ligne(s)" in shown[0].summary
    finally:
        sip.delete(dialog)


def test_review_is_not_opened_when_nothing_can_apply(qapp, monkeypatch):
    from core.ai.assistant.changeset import Change, ChangeSet
    from gui import assistant_dialog as ad
    from gui import assistant_review_dialog

    binding = _readonly_binding()
    dialog = ad.AssistantDialog(surface_provider=lambda: binding)
    shown = []
    monkeypatch.setattr(assistant_review_dialog, "review_changeset",
                        lambda changeset, apply, parent=None:
                        shown.append(changeset))
    try:
        dialog._active_surface = binding
        dialog._on_surface_done(_answer(ChangeSet(changes=[
            Change(kind="yaml_set", target="a.B", old="1", new="2")])))
        assert shown == []
        assert "ne peut pas les appliquer" in dialog.status_label.text()
    finally:
        sip.delete(dialog)


def test_surface_binding_can_declare_it_produces_no_changeset():
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import ToolRegistry
    binding = SurfaceBinding(name="tab", context=lambda: TabContext("", ""),
                             registry=lambda: ToolRegistry(),
                             apply=lambda changes: (False, "unsupported"),
                             produces_changeset=False)
    assert binding.action().produces_changeset is False


def test_non_editor_tab_proposes_prose_only_without_a_workspace():
    from gui.main_window import MainWindow
    tabs = types.SimpleNamespace(currentWidget=lambda: None,
                                 currentIndex=lambda: -1,
                                 tabText=lambda index: "")
    window = types.SimpleNamespace(tabs=tabs, workspace=None)
    binding = MainWindow._assistant_surface(window)
    assert binding.action().produces_changeset is False
    assert binding.kinds == ()
    assert "Do NOT return a JSON change set" in binding.instruction


def test_non_editor_tab_allows_only_scenario_import(tmp_path):
    from gui.main_window import MainWindow
    tabs = types.SimpleNamespace(currentWidget=lambda: None,
                                 currentIndex=lambda: -1,
                                 tabText=lambda index: "")
    workspace = types.SimpleNamespace(working_root=tmp_path,
                                      source_a_root=tmp_path,
                                      source_b_root=tmp_path)
    window = types.SimpleNamespace(tabs=tabs, workspace=workspace,
                                   _expand_imports=lambda cs: cs)
    window._with_scenario_import = lambda binding: \
        MainWindow._with_scenario_import(window, binding)
    binding = MainWindow._assistant_surface(window)
    assert binding.kinds == ("scenario_import",)
    assert binding.action().produces_changeset is True
    assert "scenario_import" in binding.instruction
