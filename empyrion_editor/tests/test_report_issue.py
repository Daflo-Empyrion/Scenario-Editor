from gui.report_issue_dialog import _collect_diagnostic_info, _save_screenshot


def test_collect_diagnostic_info_contains_expected_fields():
    info = _collect_diagnostic_info()
    assert "Version de l'application" in info
    assert "Systeme" in info
    assert "Python" in info
    assert "Mode" in info


def test_save_screenshot_creates_file(tmp_path, monkeypatch):
    import gui.report_issue_dialog as rid
    monkeypatch.setattr(rid.Path, "home", staticmethod(lambda: tmp_path))

    class FakePixmap:
        def save(self, path, fmt):
            with open(path, "wb") as f:
                f.write(b"fake png content")
            return True

    saved_path = _save_screenshot(FakePixmap())
    assert saved_path.exists()
    assert saved_path.parent.name == "bug_reports"
    assert saved_path.suffix == ".png"
