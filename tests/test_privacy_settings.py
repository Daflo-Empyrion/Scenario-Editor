"""
Tests du reglage de confidentialite pour la traduction en ligne -- ajoute
suite a une verification de conformite aux exigences SignPath Foundation
(les logiciels transferant des donnees utilisateur doivent proposer une
option de desactivation explicite).
"""
import pytest


def test_online_translation_enabled_by_default(tmp_path, monkeypatch):
    from core import settings
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    assert settings.get_online_translation_enabled() is True


def test_online_translation_can_be_disabled_and_reenabled(tmp_path, monkeypatch):
    from core import settings
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")

    settings.set_online_translation_enabled(False)
    assert settings.get_online_translation_enabled() is False

    settings.set_online_translation_enabled(True)
    assert settings.get_online_translation_enabled() is True


def test_translate_text_refuses_when_disabled(tmp_path, monkeypatch):
    from core import settings, translation
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    settings.set_online_translation_enabled(False)

    with pytest.raises(RuntimeError, match="desactivee"):
        translation.translate_text("Hello", target="fr", source="en")


def test_translate_text_still_uses_local_cache_when_disabled(tmp_path, monkeypatch):
    """Le reglage bloque uniquement les NOUVEAUX appels reseau -- une
    traduction deja obtenue precedemment (memoire locale) doit rester
    utilisable meme desactive, puisqu'aucune donnee n'est alors envoyee."""
    from core import settings, translation, translation_memory
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(translation_memory, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(translation_memory, "MEMORY_FILE", tmp_path / "translation_memory.json")

    translation_memory.store("Bonjour", "fr", "en", "Hello")
    settings.set_online_translation_enabled(False)

    result = translation.translate_text("Bonjour", target="en", source="fr")
    assert result == "Hello"


def test_privacy_md_exists_and_mentions_google_translate():
    from pathlib import Path
    privacy_path = Path(__file__).parent.parent / "PRIVACY.md"
    assert privacy_path.exists()
    content = privacy_path.read_text(encoding="utf-8")
    assert "Google Translate" in content
    assert "api.github.com" in content


def test_installer_privacy_notice_exists():
    from pathlib import Path
    notice_path = Path(__file__).parent.parent / "installer_privacy_notice.txt"
    assert notice_path.exists()
    content = notice_path.read_text(encoding="utf-8")
    assert "Google Translate" in content


def test_installer_iss_references_privacy_notice():
    from pathlib import Path
    iss_path = Path(__file__).parent.parent / "installer.iss"
    content = iss_path.read_text(encoding="utf-8")
    assert "InfoBeforeFile=installer_privacy_notice.txt" in content


def test_readme_has_code_signing_policy_section():
    from pathlib import Path
    readme_path = Path(__file__).parent.parent / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    assert "Politique de signature de code" in content
    assert "SignPath.io" in content
    assert "PRIVACY.md" in content


def test_privacy_menu_action_present(qapp):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    apply_theme(qapp)
    window = MainWindow()
    assert hasattr(window, "action_privacy")


def test_privacy_dialog_opens_real_file(qapp, monkeypatch):
    from gui.theme import apply_theme
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QDialog
    apply_theme(qapp)
    window = MainWindow()

    captured = {}
    monkeypatch.setattr(QDialog, "exec", lambda self: (captured.setdefault("dialog", self),
                                                         QDialog.DialogCode.Accepted)[1])
    window._open_privacy_dialog()
    dialog = captured["dialog"]
    text = dialog.browser.toPlainText()
    assert "Google Translate" in text
    assert "api.github.com" in text


def test_installer_copies_privacy_md_next_to_exe():
    from pathlib import Path
    iss_path = Path(__file__).parent.parent / "installer.iss"
    content = iss_path.read_text(encoding="utf-8")
    assert 'Source: "PRIVACY.md"' in content
