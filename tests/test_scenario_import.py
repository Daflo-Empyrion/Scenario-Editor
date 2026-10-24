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

"""Import d'un bloc ECF de A/B vers la copie de travail (demande 22/10) :
cible parseable, plan SANS ecriture (added/merged/conflict), puis un seul
bloc ecrit -- le reste du fichier de destination est intact."""
from core.scenario_import import block_plan, import_block, parse_target


def test_parse_target_accepts_scope_path_and_block():
    target = parse_target("b:Content/Configuration/BlocksConfig.ecf#500")
    assert (target.scope, target.rel, target.ident) == (
        "b", "Content/Configuration/BlocksConfig.ecf", "500")
    assert parse_target("a:Playfields/SectorA").ident == ""
    assert parse_target("b:..\\secret.ecf") is None
    assert parse_target("/etc/passwd") is None
    assert parse_target("") is None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _source(tmp_path):
    return _write(tmp_path / "b" / "Blocks.ecf",
                  "{ Block Id: 500, Name: Ship\n"
                  "  HitPoints: 9\n"
                  "}\n")


def test_plan_reports_added_without_writing(tmp_path):
    source = _source(tmp_path)
    dest = tmp_path / "working" / "Blocks.ecf"
    plan = block_plan(source, dest, "500")
    assert plan["status"] == "added"
    assert plan["block"]["name"] == "Ship"
    assert not dest.exists()


def test_plan_reports_conflict_with_another_name(tmp_path):
    source = _source(tmp_path)
    dest = _write(tmp_path / "working" / "Blocks.ecf",
                  "{ Block Id: 500, Name: Other\n  HitPoints: 1\n}\n")
    plan = block_plan(source, dest, "500")
    assert plan["status"] == "conflict"
    assert plan["conflict"]["working_name"] == "Other"
    assert "disabled" in plan["note"]


def test_import_block_adds_and_keeps_the_rest(tmp_path):
    source = _source(tmp_path)
    dest = _write(tmp_path / "working" / "Blocks.ecf",
                  "{ Block Id: 1, Name: Existing\n  HitPoints: 5\n}\n")
    ok, status, code = import_block(source, dest, "500")
    assert ok and status == "added" and code == ""
    text = dest.read_text(encoding="utf-8")
    assert "Name: Existing" in text and "Name: Ship" in text
    assert "HitPoints: 9" in text


def test_import_block_refuses_unknown_ident_and_writes_nothing(tmp_path):
    source = _source(tmp_path)
    dest = tmp_path / "working" / "Blocks.ecf"
    ok, _status, code = import_block(source, dest, "999")
    assert not ok and code == "scenario_import_failed"
    assert not dest.exists()


# ---------------------------------------------------------------------------
# Chemin connecte : applier de l'assistant (revue -> copie dans la working)
# ---------------------------------------------------------------------------

class _Tabs:
    def __init__(self, tips, widgets=None):
        self._tips = list(tips)
        self._widgets = list(widgets or [])

    def count(self):
        return len(self._tips)

    def tabToolTip(self, index):
        return self._tips[index]

    def removeTab(self, index):
        self._tips.pop(index)

    def widget(self, index):
        return self._widgets[index] if index < len(self._widgets) else None


class _Workspace:
    def __init__(self, tmp):
        self.source_a_root = tmp / "a"
        self.source_b_root = tmp / "b"
        self.working_root = tmp / "working"
        self.working_root.mkdir(parents=True)
        self.working = None
        self.rescans = 0

    def rescan_working(self):
        self.rescans += 1


def _fake_window(tmp):
    from types import SimpleNamespace

    pushed = []
    window = SimpleNamespace(
        workspace=_Workspace(tmp),
        tabs=_Tabs([]),
        tree_working=None,
        _push_workspace_undo=pushed.append,
        _populate_tree=lambda *args: None,
        statusBar=lambda: SimpleNamespace(showMessage=lambda *args: None))
    return window, pushed


def test_assistant_applier_imports_a_block_and_pushes_undo(tmp_path):
    from core.ai.assistant.changeset import Change
    from gui.main_window import MainWindow

    _write(tmp_path / "b" / "Blocks.ecf",
           "{ Block Id: 500, Name: Ship\n  HitPoints: 9\n}\n")
    window, pushed = _fake_window(tmp_path)
    ok, problem = MainWindow._apply_scenario_imports(
        window, [Change(kind="scenario_import", target="b:Blocks.ecf#500")])
    assert ok and problem == ""
    dest = window.workspace.working_root / "Blocks.ecf"
    assert "Name: Ship" in dest.read_text(encoding="utf-8")
    assert pushed and window.workspace.rescans == 1


def test_assistant_applier_rolls_back_everything_on_a_failed_target(tmp_path):
    from core.ai.assistant.changeset import Change
    from gui.main_window import MainWindow

    _write(tmp_path / "b" / "Blocks.ecf",
           "{ Block Id: 500, Name: Ship\n}\n")
    window, pushed = _fake_window(tmp_path)
    ok, problem = MainWindow._apply_scenario_imports(window, [
        Change(kind="scenario_import", target="b:Blocks.ecf#500"),
        Change(kind="scenario_import", target="b:Missing.ecf"),
    ])
    assert not ok and problem == "scenario_import_missing"
    assert not (window.workspace.working_root / "Blocks.ecf").exists()
    assert not pushed


def test_import_wrapper_delegates_editor_changes_and_imports():
    from core.ai.assistant.changeset import Change
    from core.ai.assistant.context import TabContext
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import ToolRegistry
    from gui.main_window import MainWindow

    seen = []

    class _Window:
        def _apply_scenario_imports(self, imports):
            seen.append(("imports", [c.target for c in imports]))
            return True, ""

        def _expand_imports(self, changeset):
            return changeset

    binding = SurfaceBinding(
        name="ecf", context=lambda: TabContext("x", ""),
        registry=lambda: ToolRegistry(),
        apply=lambda changes: seen.append(
            ("editor", [c.kind for c in changes])) or (True, ""))
    wrapped = MainWindow._with_scenario_import(_Window(), binding)
    ok, problem = wrapped.apply([
        Change(kind="ecf_set", target="[1] / Count", old="1", new="2"),
        Change(kind="scenario_import", target="b:Blocks.ecf#500"),
    ])
    assert ok and problem == ""
    assert seen == [("editor", ["ecf_set"]),
                    ("imports", ["b:Blocks.ecf#500"])]
    assert wrapped.registry().names("ecf") == []


def test_assistant_applier_refuses_when_the_target_tab_is_modified(tmp_path):
    from types import SimpleNamespace

    from core.ai.assistant.changeset import Change
    from gui.main_window import MainWindow

    _write(tmp_path / "b" / "Blocks.ecf", "{ Block Id: 500, Name: Ship\n}\n")
    window, pushed = _fake_window(tmp_path)
    dest = window.workspace.working_root / "Blocks.ecf"
    window.tabs = _Tabs([str(dest)], [SimpleNamespace(
        is_modified=lambda: True)])
    ok, problem = MainWindow._apply_scenario_imports(
        window, [Change(kind="scenario_import", target="b:Blocks.ecf#500")])
    assert not ok and problem == "scenario_import_unsaved"
    assert not dest.exists() and not pushed


def test_parse_target_reads_the_with_deps_flag():
    target = parse_target("b:Content/Configuration/BlocksConfig.ecf#500+deps")
    assert target.ident == "500" and target.with_deps is True
    plain = parse_target("b:Content/Configuration/BlocksConfig.ecf#500")
    assert plain.with_deps is False


def test_assistant_applier_resolves_the_dependency_graph(tmp_path):
    from core.ai.assistant.changeset import Change
    from gui.main_window import MainWindow

    cfg = tmp_path / "b" / "Content" / "Configuration"
    _write(cfg / "BlocksConfig.ecf",
           "{ +Block Name: HyperDrive\n  Ref: HyperCore\n}\n"
           "{ +Block Name: HyperCore\n}\n")
    window, pushed = _fake_window(tmp_path)
    ok, problem = MainWindow._apply_scenario_imports(window, [
        Change(kind="scenario_import",
               target="b:Content/Configuration/BlocksConfig.ecf#HyperDrive+deps")])
    assert ok and problem == ""
    blocks = (window.workspace.working_root / "Content" / "Configuration"
              / "BlocksConfig.ecf").read_text(encoding="utf-8")
    assert "Name: HyperDrive" in blocks
    assert "Name: HyperCore" in blocks
    assert pushed and window.workspace.rescans == 1


def test_applier_writes_the_unresolved_report_outside_the_scenario(tmp_path,
                                                                   monkeypatch):
    from core import settings
    from core.ai.assistant.changeset import Change
    from gui.main_window import MainWindow

    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path / "cfg")
    cfg = tmp_path / "b" / "Content" / "Configuration"
    _write(cfg / "BlocksConfig.ecf",
           "{ +Block Name: HyperDrive\n  Info: MissingKey\n}\n")
    window, _pushed = _fake_window(tmp_path)
    ok, problem = MainWindow._apply_scenario_imports(window, [
        Change(kind="scenario_import",
               target="b:Content/Configuration/BlocksConfig.ecf#HyperDrive+deps")])
    assert ok and problem == ""
    reports = list((tmp_path / "cfg" / "imports").glob("*.csv"))
    assert reports, "le rapport CSV doit etre ecrit hors du scenario"
    content = reports[0].read_text(encoding="utf-8-sig")
    assert "MissingKey" in content and "localization" in content


def test_expand_imports_turns_deps_into_one_row_per_target(tmp_path):
    from core.ai.assistant.changeset import Change, ChangeSet
    from gui.main_window import MainWindow

    cfg = tmp_path / "b" / "Content" / "Configuration"
    _write(cfg / "BlocksConfig.ecf",
           "{ +Block Name: Alpha\n"
           "  Ref: Beta\n"
           "  TechTreeParent: Gamma\n"
           "  TechTreeNames: AsgardTech\n"
           "  CustomIcon: MissingIcon\n"
           "}\n"
           "{ +Block Name: Beta\n"
           "}\n"
           "{ +Block Name: Gamma\n"
           "}\n")
    window, _pushed = _fake_window(tmp_path)
    changeset = ChangeSet(changes=[Change(
        kind="scenario_import",
        target="b:Content/Configuration/BlocksConfig.ecf#Alpha+deps")])
    expanded = MainWindow._expand_imports(window, changeset)
    targets = [change.target for change in expanded.changes]
    assert len(targets) == 2
    assert all(t.startswith("b:Content/Configuration/BlocksConfig.ecf#")
               for t in targets)
    assert not any("+deps" in target for target in targets)
    assert any(row["reference"] == "MissingIcon"
               for row in expanded.report)
    # l'arbre technologique n'est PAS suivi, mais il est signale
    assert not any(target.endswith("#Gamma") for target in targets)
    assert "Gamma" in expanded.summary and "AsgardTech" in expanded.summary


def test_import_wrapper_exposes_the_expand_hook():
    from core.ai.assistant.context import TabContext
    from core.ai.assistant.surfaces.base import SurfaceBinding
    from core.ai.assistant.tools import ToolRegistry
    from gui.main_window import MainWindow

    class _Window:
        def _apply_scenario_imports(self, imports):
            return True, ""

        def _expand_imports(self, changeset):
            return changeset

    binding = SurfaceBinding(
        name="ecf", context=lambda: TabContext("x", ""),
        registry=lambda: ToolRegistry(), apply=lambda changes: (True, ""))
    wrapped = MainWindow._with_scenario_import(_Window(), binding)
    assert callable(wrapped.expand)
