# Tests du module core.settings -- valide en particulier le fix du bug critique
# (get_backup_root manquant / code mort dans set_merge_enabled, corrige le 15/08/2026).
import json

from core import settings


def test_get_backup_root_exists():
    assert hasattr(settings, 'get_backup_root'), 'get_backup_root manque dans core/settings.py'
    assert callable(settings.get_backup_root)


def test_get_backup_root_default_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'SETTINGS_FILE', tmp_path / 'settings.json')
    assert settings.get_backup_root('scenario') == ''
    assert settings.get_backup_root('savegame') == ''


def test_set_get_backup_root_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(settings, 'SETTINGS_FILE', tmp_path / 'settings.json')
    settings.set_backup_root('scenario', 'C:\\Backups\\scenarios')
    settings.set_backup_root('savegame', 'C:\\Backups\\saves')
    assert settings.get_backup_root('scenario') == 'C:\\Backups\\scenarios'
    assert settings.get_backup_root('savegame') == 'C:\\Backups\\saves'


def test_set_merge_enabled_does_not_crash(tmp_path, monkeypatch):
    # Avant le fix, le deuxieme appel levait NameError: name 'kind' is not defined
    monkeypatch.setattr(settings, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(settings, 'SETTINGS_FILE', tmp_path / 'settings.json')
    settings.set_merge_enabled(True)
    assert settings.get_merge_enabled() is True
    settings.set_merge_enabled(False)
    assert settings.get_merge_enabled() is False


def test_settings_file_is_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'CONFIG_DIR', tmp_path)
    settings_file = tmp_path / 'settings.json'
    monkeypatch.setattr(settings, 'SETTINGS_FILE', settings_file)
    settings.set_author('Testeur')
    data = json.loads(settings_file.read_text(encoding='utf-8'))
    assert data.get('author') == 'Testeur'
