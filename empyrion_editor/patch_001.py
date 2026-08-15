#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_001.py
============
Patch pour le projet Empyrion Scenario Editor.

Ce script :
  1. Corrige le bug CRITIQUE dans core/settings.py
     (la fonction get_backup_root avait perdu sa ligne 'def' ; son corps etait
      colle a la fin de set_merge_enabled -> NameError / AttributeError).
  2. Cree une suite de tests pytest avec fixtures embarquees
     (round-trip ECF/YAML/CSV + test du fix settings).
  3. Ajoute pytest a requirements.txt (s'il n'y est pas deja).
  4. Cree pytest.ini.

UTILISATION :
    Place ce fichier a la racine de ton projet (le dossier qui contient core/),
    puis lance :  python patch_001.py

Le script est IDEMPOTENT : tu peux le relancer sans risque.
"""
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Localisation de la racine du projet
# ---------------------------------------------------------------------------
def find_project_root() -> Path:
    root = Path(__file__).resolve().parent
    if (root / 'core' / 'settings.py').exists():
        return root
    cwd = Path.cwd()
    if (cwd / 'core' / 'settings.py').exists():
        return cwd
    print("ERREUR : impossible de trouver core/settings.py.")
    print("Place patch_001.py a la racine de ton projet (dossier contenant core/) et relance.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1. Fix de core/settings.py
# ---------------------------------------------------------------------------
SETTINGS_BUG_PATTERN = re.compile(r'''[ \t]*"""Dernier dossier de sauvegardes utilise pour ce type \(\'scenario\' ou \'savegame\'\),\r?\n[ \t]*ou chaine vide si jamais defini\."""\r?\n[ \t]*if SETTINGS_FILE\.exists\(\):\r?\n[ \t]*try:\r?\n[ \t]*data = json\.loads\(SETTINGS_FILE\.read_text\(encoding=\'utf-8\'\)\)\r?\n[ \t]*return data\.get\(f\'backup_root_\{kind\}\', \'\'\)\r?\n[ \t]*except Exception:\r?\n[ \t]*pass\r?\n[ \t]*return \'\'[ \t]*\r?\n''')


def build_get_backup_root(eol: str) -> str:
    lines = [
        'def get_backup_root(kind: str) -> str:',
        '    """Dernier dossier de sauvegardes utilise pour ce type (\'scenario\' ou \'savegame\'),',
        '    ou chaine vide si jamais defini."""',
        '    if SETTINGS_FILE.exists():',
        '        try:',
        '            data = json.loads(SETTINGS_FILE.read_text(encoding=\'utf-8\'))',
        '            return data.get(f\'backup_root_{kind}\', \'\')',
        '        except Exception:',
        '            pass',
        '    return \'\'',
    ]
    return eol.join(lines) + eol


def fix_settings(root: Path) -> str:
    path = root / 'core' / 'settings.py'
    content = path.read_bytes().decode('utf-8')

    if 'def get_backup_root' in content:
        return 'DEJA CORRIGE (get_backup_root existe deja)'

    def repl(m):
        eol = '\r\n' if '\r\n' in m.group(0) else '\n'
        return build_get_backup_root(eol)

    new_content, n = SETTINGS_BUG_PATTERN.subn(repl, content, count=1)
    if n == 0:
        return ('ECHEC : motif du bug introuvable. Ton core/settings.py est '
                'peut-etre different de la version attendue -- envoie-le moi.')

    path.write_bytes(new_content.encode('utf-8'))
    return 'CORRIGE (get_backup_root restaure, code mort retire de set_merge_enabled)'


# ---------------------------------------------------------------------------
# 2. Suite de tests
# ---------------------------------------------------------------------------
FIXTURE_ECF = [
    '# ==================================================',
    '# Fichier de test ECF - fixture pour les tests pytest',
    '# ==================================================',
    '',
    '## ContainerPrincipal',
    '{ +Container Id: 5',
    '  Count: "3,4"',
    '  Size: "8,1"',
    '  Name: TestContainer',
    '',
    '  { Child Items',
    '    Name_0: IronOre, param1: 0.5',
    '    Name_1: CopperOre, param1: 0.3, param2: "1,2"',
    '  }',
    '}',
    '',
    '{ Block Id: 399, Name: ConcreteBlocks',
    '  Material: concrete',
    '  BlockColor: "170,170,170"',
    '  HitPoints: 600',
    '  Mass: 1100',
    '}',
    '',
    '{ Block Name: LegacyForcefield',
    '  Material: metal',
    '  HitPoints: 9999',
    '}',
]

FIXTURE_YAML = [
    '# Playfield de test - fixture pour les tests pytest',
    'PlayfieldType: Planet',
    'PlayfieldName: TestPlanet',
    '',
    'Atmosphere:',
    '  Enabled: True',
    '  Density: 1.0',
    '  Color: "0.5,0.6,0.8"',
    '',
    'POIs:',
    '  Random:',
    '    - GroupName: JunkT1',
    '      CountMinMax: [4, 5]',
    '      DroneProb: 0',
]

FIXTURE_CSV = [
    'Key,English,Fran\u00e7ais,Deutsch',
    'Greeting,Hello World,Bonjour le monde,Hallo Welt',
    'Item_IronOre_Name,Iron Ore,Minerai de fer,Eisenerz',
    'Item_CopperOre_Name,Copper Ore,Minerai de cuivre,Kupfererz',
]

CONFTEST = """import sys
from pathlib import Path

# Ajoute la racine du projet (parent de tests/) au sys.path pour importer core
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
"""

TEST_SETTINGS = """# Tests du module core.settings -- valide en particulier le fix du bug critique
# (get_backup_root manquant / code mort dans set_merge_enabled).
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
    settings.set_backup_root('scenario', 'C:\\\\Backups\\\\scenarios')
    settings.set_backup_root('savegame', 'C:\\\\Backups\\\\saves')
    assert settings.get_backup_root('scenario') == 'C:\\\\Backups\\\\scenarios'
    assert settings.get_backup_root('savegame') == 'C:\\\\Backups\\\\saves'


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
"""

TEST_ECF = """# Tests de round-trip et de structure pour le parser ECF.
from pathlib import Path

from core.ecf.parser import parse_ecf_file
from core.ecf.model import EcfBlock

FIXTURES = Path(__file__).parent / 'fixtures'


def test_ecf_roundtrip_byte_perfect():
    path = FIXTURES / 'sample.ecf'
    original = path.read_bytes()
    doc = parse_ecf_file(path)
    rendered = doc.render()
    assert rendered.encode('utf-8') == original


def test_ecf_block_count():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    blocks = [n for n in doc.nodes if isinstance(n, EcfBlock)]
    assert len(blocks) == 3


def test_ecf_container_identity():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    container = doc.find_block_by_identity('+Container', '5')
    assert container is not None
    assert container.get_property('Name') == 'TestContainer'
    assert container.get_property('Count') == '"3,4"'


def test_ecf_child_items():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    container = doc.find_block_by_identity('+Container', '5')
    children = container.child_blocks('Child Items')
    assert len(children) == 1


def test_ecf_block_without_id():
    doc = parse_ecf_file(FIXTURES / 'sample.ecf')
    block = doc.find_block_by_identity('Block', 'LegacyForcefield')
    assert block is not None
    assert block.get('Id') is None
"""

TEST_YAML = """# Tests de round-trip et de structure pour le parser yamllite.
from pathlib import Path

from core.yamllite.parser import parse_yaml_file

FIXTURES = Path(__file__).parent / 'fixtures'


def test_yaml_roundtrip_byte_perfect():
    path = FIXTURES / 'playfield.yaml'
    original = path.read_bytes()
    doc = parse_yaml_file(path)
    rendered = doc.render()
    assert rendered.encode('utf-8') == original


def test_yaml_get_path():
    doc = parse_yaml_file(FIXTURES / 'playfield.yaml')
    assert doc.get_path('PlayfieldType') == 'Planet'
    assert doc.get_path('PlayfieldName') == 'TestPlanet'
    assert doc.get_path('Atmosphere', 'Enabled') == 'True'
    assert doc.get_path('Atmosphere', 'Color') is not None
"""

TEST_CSV = """# Tests de round-trip et de structure pour le handler CSV.
from pathlib import Path

from core.csv_handler import CsvHandler

FIXTURES = Path(__file__).parent / 'fixtures'


def test_csv_roundtrip_byte_perfect():
    path = FIXTURES / 'localization.csv'
    handler = CsvHandler()
    original = path.read_bytes()
    doc = handler.parse(handler.load(path))
    rendered = handler.serialize(doc)
    assert rendered.encode('utf-8') == original


def test_csv_header_and_rows():
    handler = CsvHandler()
    doc = handler.parse(handler.load(FIXTURES / 'localization.csv'))
    assert doc.header is not None
    assert doc.header[0] == 'Key'
    assert len(doc.rows) == 3


def test_csv_delimiter_detected():
    handler = CsvHandler()
    doc = handler.parse(handler.load(FIXTURES / 'localization.csv'))
    assert doc.delimiter == ','
"""


def _write_crlf(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(('\r\n'.join(lines) + '\r\n').encode('utf-8'))


def _write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.replace('\r\n', '\n').replace('\n', '\r\n')
    path.write_bytes(data.encode('utf-8'))


def create_tests(root: Path) -> str:
    tests_dir = root / 'tests'
    fixtures = tests_dir / 'fixtures'
    _write_crlf(fixtures / 'sample.ecf', FIXTURE_ECF)
    _write_crlf(fixtures / 'playfield.yaml', FIXTURE_YAML)
    _write_crlf(fixtures / 'localization.csv', FIXTURE_CSV)
    _write_text(tests_dir / 'conftest.py', CONFTEST)
    _write_text(tests_dir / 'test_settings.py', TEST_SETTINGS)
    _write_text(tests_dir / 'test_ecf_roundtrip.py', TEST_ECF)
    _write_text(tests_dir / 'test_yaml_roundtrip.py', TEST_YAML)
    _write_text(tests_dir / 'test_csv_roundtrip.py', TEST_CSV)
    return 'CREE (3 fixtures + 4 fichiers de tests + conftest.py)'


# ---------------------------------------------------------------------------
# 3. requirements.txt
# ---------------------------------------------------------------------------
def update_requirements(root: Path) -> str:
    path = root / 'requirements.txt'
    if not path.exists():
        path.write_bytes(b'pytest\r\n')
        return 'CREE (pytest)'
    content = path.read_text(encoding='utf-8')
    if any(l.strip().lower().startswith('pytest') for l in content.splitlines() if l.strip()):
        return 'DEJA PRESENT (pytest)'
    eol = '\r\n' if '\r\n' in content else '\n'
    new_content = content
    if not new_content.endswith(('\n', '\r')):
        new_content += eol
    new_content += 'pytest' + eol
    path.write_text(new_content, encoding='utf-8')
    return 'AJOUTE (pytest)'


# ---------------------------------------------------------------------------
# 4. pytest.ini
# ---------------------------------------------------------------------------
def create_pytest_ini(root: Path) -> str:
    path = root / 'pytest.ini'
    if path.exists():
        return 'DEJA PRESENT (pytest.ini non modifie)'
    path.write_text('[pytest]\ntestpaths = tests\npython_files = test_*.py\naddopts = -v\n', encoding='utf-8')
    return 'CREE (pytest.ini)'


# ---------------------------------------------------------------------------
def main():
    print('=' * 60)
    print('patch_001.py -- Empyrion Scenario Editor')
    print('=' * 60)
    root = find_project_root()
    print(f'Racine du projet : {root}\n')

    results = []
    print('[1/4] Correction de core/settings.py ...')
    results.append(('core/settings.py', fix_settings(root)))
    print('[2/4] Creation de la suite de tests ...')
    results.append(('tests/', create_tests(root)))
    print('[3/4] Mise a jour de requirements.txt ...')
    results.append(('requirements.txt', update_requirements(root)))
    print('[4/4] Creation de pytest.ini ...')
    results.append(('pytest.ini', create_pytest_ini(root)))

    print('\n' + '=' * 60)
    print('RESUME')
    print('=' * 60)
    for name, status in results:
        print(f'  {name:25} : {status}')

    print('\nPour lancer les tests :')
    print('    python -m pytest')
    print('\nSi pytest n\'est pas encore installe :')
    print('    pip install -r requirements.txt')


if __name__ == '__main__':
    main()