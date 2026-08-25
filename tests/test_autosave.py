"""
Tests du module de gestion des fichiers de recuperation (core/autosave.py).
Isole completement RECOVERY_ROOT vers un dossier temporaire pour chaque test
-- jamais touche au vrai dossier ~/.empyrion_editor/recovery de la machine.
"""
import pytest

from pathlib import Path
from core import autosave


@pytest.fixture(autouse=True)
def isolated_recovery_root(tmp_path, monkeypatch):
    monkeypatch.setattr(autosave, "RECOVERY_ROOT", tmp_path / "recovery")
    yield


def test_write_and_read_recovery_snapshot(tmp_path):
    working_root = tmp_path / "scenario"
    file_path = working_root / "Content" / "Configuration" / "BlocksConfig.ecf"
    autosave.write_recovery_snapshot(working_root, file_path, "contenu test")

    files = autosave.list_recovery_files(working_root)
    assert len(files) == 1
    content = autosave.read_recovery_content(working_root, files[0])
    assert content == "contenu test"


def test_decode_relative_name_reconstructs_real_path(tmp_path):
    working_root = tmp_path / "scenario"
    file_path = working_root / "Content" / "Configuration" / "BlocksConfig.ecf"
    autosave.write_recovery_snapshot(working_root, file_path, "x")
    encoded = autosave.list_recovery_files(working_root)[0]
    assert autosave.decode_relative_name(encoded) == Path("Content/Configuration/BlocksConfig.ecf")


def test_clear_recovery_file_removes_only_that_file(tmp_path):
    working_root = tmp_path / "scenario"
    file1 = working_root / "Content" / "Configuration" / "A.ecf"
    file2 = working_root / "Content" / "Configuration" / "B.ecf"
    autosave.write_recovery_snapshot(working_root, file1, "a")
    autosave.write_recovery_snapshot(working_root, file2, "b")

    autosave.clear_recovery_file(working_root, file1)

    files = autosave.list_recovery_files(working_root)
    assert len(files) == 1
    assert autosave.read_recovery_content(working_root, files[0]) == "b"


def test_clear_recovery_file_cleans_up_empty_scenario_dir(tmp_path):
    working_root = tmp_path / "scenario"
    file1 = working_root / "Content" / "Configuration" / "A.ecf"
    autosave.write_recovery_snapshot(working_root, file1, "a")

    autosave.clear_recovery_file(working_root, file1)

    assert autosave.list_recoverable_scenarios() == []


def test_clear_recovery_for_scenario_removes_everything(tmp_path):
    working_root = tmp_path / "scenario"
    file1 = working_root / "Content" / "Configuration" / "A.ecf"
    file2 = working_root / "Content" / "Configuration" / "B.ecf"
    autosave.write_recovery_snapshot(working_root, file1, "a")
    autosave.write_recovery_snapshot(working_root, file2, "b")

    autosave.clear_recovery_for_scenario(working_root)

    assert autosave.list_recovery_files(working_root) == []
    assert autosave.list_recoverable_scenarios() == []


def test_list_recoverable_scenarios_distinguishes_different_scenarios(tmp_path):
    root_a = tmp_path / "scenario_a"
    root_b = tmp_path / "scenario_b"
    autosave.write_recovery_snapshot(root_a, root_a / "X.ecf", "a")
    autosave.write_recovery_snapshot(root_b, root_b / "Y.ecf", "b")

    scenarios = autosave.list_recoverable_scenarios()
    assert len(scenarios) == 2
    roots = {s["working_root"] for s in scenarios}
    assert roots == {root_a.resolve(), root_b.resolve()}


def test_write_recovery_snapshot_overwrites_previous_version(tmp_path):
    working_root = tmp_path / "scenario"
    file_path = working_root / "A.ecf"
    autosave.write_recovery_snapshot(working_root, file_path, "version 1")
    autosave.write_recovery_snapshot(working_root, file_path, "version 2")

    files = autosave.list_recovery_files(working_root)
    assert len(files) == 1
    assert autosave.read_recovery_content(working_root, files[0]) == "version 2"


def test_no_recovery_files_returns_empty_list(tmp_path):
    assert autosave.list_recoverable_scenarios() == []
    assert autosave.list_recovery_files(tmp_path / "nonexistent") == []


def test_read_recovery_content_returns_none_for_missing_file(tmp_path):
    working_root = tmp_path / "scenario"
    assert autosave.read_recovery_content(working_root, "nonexistent.ecf") is None


# ============================================================================
# Methode _get_content_for_autosave() sur chaque type de widget -- ne doit
# JAMAIS ecrire sur le disque, seulement retourner le contenu actuel.
# ============================================================================

def test_ecf_widget_autosave_content_never_touches_disk(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.ecf_edit_widget import EcfEditWidget
    apply_theme(qapp)

    path = tmp_path / "BlocksConfig.ecf"
    path.write_text("{ Block Id: 1, Name: Test\r\n}\r\n", encoding="utf-8", newline="")
    original = path.read_bytes()

    widget = EcfEditWidget(path)
    content = widget._get_content_for_autosave()
    assert "Test" in content
    assert path.read_bytes() == original


def test_yaml_widget_autosave_content_never_touches_disk(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.yaml_edit_widget import YamlEditWidget
    apply_theme(qapp)

    path = tmp_path / "test.yaml"
    path.write_text("Key: Value\r\n", encoding="utf-8", newline="")
    original = path.read_bytes()

    widget = YamlEditWidget(path)
    content = widget._get_content_for_autosave()
    assert "Key" in content
    assert path.read_bytes() == original


def test_csv_widget_autosave_content_never_touches_disk(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.csv_edit_widget import CsvEditWidget
    apply_theme(qapp)

    path = tmp_path / "test.csv"
    path.write_text("Key,en,fr\r\nGreeting,Hello,Bonjour\r\n", encoding="utf-8", newline="")
    original = path.read_bytes()

    widget = CsvEditWidget(path, editable=True)
    content = widget._get_content_for_autosave()
    assert "Greeting" in content
    assert path.read_bytes() == original


# ============================================================================
# Cycle complet dans MainWindow : minuteur d'ecriture + nettoyage a la
# sauvegarde -- verifie que le dossier de recuperation reste toujours
# coherent avec l'etat reel des onglets.
# ============================================================================

def test_autosave_tick_writes_snapshot_only_when_modified(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    (config_dir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 1, Name: Test\r\n}\r\n", encoding="utf-8", newline="")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    widget = window.open_working_file_tab(config_dir / "BlocksConfig.ecf")
    inner = getattr(widget, "edit_widget", widget)

    window._run_autosave_tick()
    assert autosave.list_recovery_files(tmp_path) == []

    inner._set_modified(True)
    window._run_autosave_tick()
    assert len(autosave.list_recovery_files(tmp_path)) == 1


def test_saving_clears_the_recovery_snapshot(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    (config_dir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 1, Name: Test\r\n}\r\n", encoding="utf-8", newline="")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    widget = window.open_working_file_tab(config_dir / "BlocksConfig.ecf")
    inner = getattr(widget, "edit_widget", widget)

    inner._set_modified(True)
    window._run_autosave_tick()
    assert len(autosave.list_recovery_files(tmp_path)) == 1

    widget.saved.emit()
    assert autosave.list_recovery_files(tmp_path) == []


def test_autosave_tick_does_nothing_without_workspace(qapp):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp)
    window = MainWindow()
    window.workspace = None
    window._run_autosave_tick()  # ne doit pas lever d'exception


def test_autosave_tick_respects_disabled_setting(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from core import settings
    apply_theme(qapp)

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    (config_dir / "BlocksConfig.ecf").write_text(
        "{ Block Id: 1, Name: Test\r\n}\r\n", encoding="utf-8", newline="")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)
    widget = window.open_working_file_tab(config_dir / "BlocksConfig.ecf")
    inner = getattr(widget, "edit_widget", widget)
    inner._set_modified(True)

    monkeypatch.setattr(settings, "get_autosave_enabled", lambda: False)
    window._run_autosave_tick()
    assert autosave.list_recovery_files(tmp_path) == []


# ============================================================================
# Dialogue de recuperation (gui/recovery_dialog.py) + declenchement au
# demarrage (MainWindow._check_for_recovery)
# ============================================================================

def test_recovery_dialog_restore_writes_to_real_working_copy(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.recovery_dialog import RecoveryDialog
    apply_theme(qapp)

    working_root = tmp_path / "scenario"
    real_file = working_root / "Content" / "Configuration" / "BlocksConfig.ecf"
    real_file.parent.mkdir(parents=True)
    real_file.write_text("original", encoding="utf-8")

    autosave.write_recovery_snapshot(working_root, real_file, "recovered content")
    files = autosave.list_recovery_files(working_root)

    dialog = RecoveryDialog(working_root, files, parent=None)
    dialog._on_restore()

    assert real_file.read_text(encoding="utf-8") == "recovered content"
    assert autosave.list_recovery_files(working_root) == []


def test_recovery_dialog_discard_never_touches_real_file(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.recovery_dialog import RecoveryDialog
    apply_theme(qapp)

    working_root = tmp_path / "scenario"
    real_file = working_root / "Content" / "Configuration" / "BlocksConfig.ecf"
    real_file.parent.mkdir(parents=True)
    real_file.write_text("original", encoding="utf-8")

    autosave.write_recovery_snapshot(working_root, real_file, "should never appear")
    files = autosave.list_recovery_files(working_root)

    dialog = RecoveryDialog(working_root, files, parent=None)
    dialog._on_discard()

    assert real_file.read_text(encoding="utf-8") == "original"
    assert autosave.list_recovery_files(working_root) == []


def test_check_for_recovery_does_nothing_when_no_snapshots(qapp, tmp_path):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    apply_theme(qapp)

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    window._check_for_recovery()  # ne doit pas lever d'exception, aucun dialogue attendu


def test_check_for_recovery_opens_dialog_when_snapshot_exists(qapp, tmp_path, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from core.scanner import scan_scenario
    from core.workspace import Workspace
    from PyQt6.QtWidgets import QDialog
    apply_theme(qapp)

    config_dir = tmp_path / "Content" / "Configuration"
    config_dir.mkdir(parents=True)
    real_file = config_dir / "BlocksConfig.ecf"
    real_file.write_text("original", encoding="utf-8")
    autosave.write_recovery_snapshot(tmp_path, real_file, "recovered")

    scenario = scan_scenario(tmp_path)
    window = MainWindow()
    window.workspace = Workspace(source_a=scenario, source_a_root=tmp_path,
                                  working=scenario, working_root=tmp_path)

    captured = {}
    monkeypatch.setattr(QDialog, "exec", lambda self: (captured.setdefault("dialog", self),
                                                         QDialog.DialogCode.Rejected)[-1])
    window._check_for_recovery()
    assert "dialog" in captured
    assert captured["dialog"].files_list.count() == 1
