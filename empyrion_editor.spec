# -*- mode: python ; coding: utf-8 -*-
"""
Spec PyInstaller pour Empyrion Scenario Editor.

UTILISATION (depuis un terminal Windows, dans le dossier du projet, environnement
virtuel active avec les dependances de requirements.txt deja installees) :

    pyinstaller empyrion_editor.spec

Le resultat apparait dans dist/EmpyrionScenarioEditor/ (dossier complet, pas un
fichier .exe unique -- plus rapide au demarrage que le mode "onefile", voir
BUILD.md pour le detail du choix).
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = Path(SPECPATH)

# Collecte robuste (code + donnees + binaires) pour les paquets connus pour poser
# probleme avec l'analyse statique de PyInstaller sur Windows -- notamment
# 'certifi' (embarque un fichier de certificats .pem comme DONNEE, pas du code,
# facilement oublie) et les imports dynamiques internes de bs4/soupsieve. Utilise
# par la fonction "Traduire" (voir core/translation.py, deep-translator).
_dt_datas, _dt_binaries, _dt_hiddenimports = collect_all('deep_translator')
_bs4_datas, _bs4_binaries, _bs4_hiddenimports = collect_all('bs4')
_requests_datas, _requests_binaries, _requests_hiddenimports = collect_all('requests')
_certifi_datas, _certifi_binaries, _certifi_hiddenimports = collect_all('certifi')
# Pilote Fluent (09/09/2026) : qfluentwidgets embarque ses qss/images comme
# DONNEES et importe des sous-modules dynamiquement -- collect_all obligatoire,
# sinon le pilote retombe en mode degrade (boutons vanilla) dans l'exe.
# qframelesswindow est la dependance fenetre sans bordure de qfluentwidgets.
_qfw_datas, _qfw_binaries, _qfw_hiddenimports = collect_all('qfluentwidgets')
_qfwl_datas, _qfwl_binaries, _qfwl_hiddenimports = collect_all('qframelesswindow')
# Traduction hors ligne Argos (v1.6.6) : pip embarque pour installer
# argostranslate DEPUIS l'exe -- en frozen, `sys.executable -m pip`
# relancerait l'application, donc le moteur s'installe via pip IN-PROCESS
# (core/argos_provider._pip_inprocess).
# IMPORTANT : pip ne doit PAS partir dans la PYZ. pip._vendor.distlib scanne
# ses propres fichiers (gabarits .exe) a l'import via importlib.resources,
# ce qui echoue depuis l'archive (DistlibException "Unable to locate finder",
# vecu en v1.6.6). Solution : pip copie en VRAIS FICHIERS dans _internal/pip
# + exclu de l'analyse (sinon la PYZ, consultee d'abord, masquerait le
# dossier) ; le dist-info reste colle pour la detection de version.
import pip as _pip
from PyInstaller.utils.hooks import copy_metadata
_pip_datas = [(str(Path(_pip.__file__).parent), 'pip')] + copy_metadata('pip')
_pip_binaries = []
# Modules stdlib que pip importe (parfois dynamiquement) : pip etant exclu de
# l'analyse PyInstaller (fichiers reels, voir ci-dessus), ses dependances
# stdlib ne sont pas vues par le graphe d'imports -- celles que l'appli
# elle-meme n'utilise pas manqueraient a l'execution (vecu v1.6.6 : "No
# module named 'logging.handlers'"). On recense donc TOUT ce que pip importe
# dans ses sources (vendored compris) et on croise avec la stdlib.
import re as _re
import sys as _sys
_seen = set()
for _p in Path(_pip.__file__).parent.rglob('*.py'):
    for _m in _re.finditer(
            r'^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_.]*)',
            _p.read_text(encoding='utf-8', errors='ignore'), _re.M):
        _seen.add(_m.group(1))
_pip_hiddenimports = sorted(
    _m for _m in _seen
    if _m.split('.')[0] in _sys.stdlib_module_names
    and _m.split('.')[0] not in _sys.builtin_module_names
    and not _m.startswith('_frozen')
    and _m != '__future__'
) + ['pydoc', 'pydoc_data', 'pydoc_data.topics']  # __import__("pydoc") dynamique
# STDLIB COMPLETE (top-level + TOUS les sous-modules des packages) :
# argostranslate et sa suite (stanza, torch...) installes a la volee dans
# argos_site ne sont pas analyses par PyInstaller -- la moindre import
# stdlib absent casserait l'execution vecu v1.6.6 : "No module named
# 'timeit'" (module top-level) PUIS "No module named 'unittest.mock'"
# (sous-module, unittest/__init__ ne chargeant PAS mock par defaut).
# Exclus : GUI lourd / outils de dev / inexistant sur la plateforme.
import importlib.util as _ilu
from PyInstaller.utils.hooks import collect_submodules
_STDLIB_EXCLUDED = {
    '__future__', 'ensurepip',  # embarquerait un DEUXIEME pip dans l'exe
    'tkinter', 'turtle', 'turtledemo', 'idlelib', 'lib2to3', 'pip',
    'pydoc_data',  # deja ajoute ci-dessus si pydoc present
    'test',  # autotests de CPython, tres gros, jamais utiles a l'execution
}
_stdlib_hiddenimports = []
for _m in sorted(_sys.stdlib_module_names):
    if _m in _STDLIB_EXCLUDED or _m in _sys.builtin_module_names \
            or _m.startswith(('_', 'xx')):
        continue
    _spec = _ilu.find_spec(_m)
    if _spec is None:
        continue  # inexistant sur cette plateforme (curses, readline...)
    if _spec.submodule_search_locations:
        try:
            _stdlib_hiddenimports += collect_submodules(_m)
        except Exception:
            _stdlib_hiddenimports.append(_m)
    else:
        _stdlib_hiddenimports.append(_m)
_pip_hiddenimports = sorted(set(_pip_hiddenimports) | set(_stdlib_hiddenimports))
# argostranslate et sa suite (torch, spacy...) ne doivent JAMAIS etre
# embarques : installes a la volee dans ~/.empyrion_editor/argos_site par le
# pip embarque (v1.6.6). Sans excludes, le simple fait d'avoir
# argostranslate dans l'environnement de construction gonflerait l'exe de
# plus d'un Go (imports fonction-level vises par l'analyse statique).
_ARGOS_EXCLUDES = ['argostranslate', 'stanza', 'spacy', 'torch', 'ctranslate2',
                   'sentencepiece', 'onnxruntime', 'sacremoses']

a = Analysis(
    ['run_gui.py'],
    pathex=[str(project_root)],
    binaries=[*_dt_binaries, *_bs4_binaries, *_requests_binaries, *_certifi_binaries,
              *_pip_binaries],
    datas=[
        # Les wikis et autres fichiers markdown doivent etre embarques tels quels --
        # lus a l'execution via un chemin relatif au dossier du projet, pas importes
        # comme du code Python.
        (str(project_root / 'docs'), 'docs'),
        # Badge GPLv3 affiche dans le dialogue "A propos" -- meme logique.
        (str(project_root / 'assets'), 'assets'),
        (str(project_root / 'data'), 'data'),
        *_dt_datas, *_bs4_datas, *_requests_datas, *_certifi_datas,
        *_qfw_datas, *_qfwl_datas, *_pip_datas,
    ],
    hiddenimports=[
        # PyQt6 charge certains sous-modules dynamiquement (non detectes par
        # l'analyse statique de PyInstaller) -- a completer si une erreur
        # "ModuleNotFoundError" apparait au premier lancement de l'exe construit.
        'PyQt6.sip',
        # Apercu PDF integre (gui/preview_widget.py) : imports fonction-level,
        # declares explicitement pour garantir l'embarquement de QtPdf dans
        # l'installeur (demande utilisateur -- QtPdf fait partie de la roue
        # PyQt6 depuis la 6.11).
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
        *_dt_hiddenimports, *_bs4_hiddenimports, *_requests_hiddenimports,
        *_certifi_hiddenimports, *_qfw_hiddenimports, *_qfwl_hiddenimports,
        *_pip_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_ARGOS_EXCLUDES + ['pip'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EmpyrionScenarioEditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX desactive volontairement : la compression UPX est un facteur connu et
    # documente de faux positifs antivirus (moteurs heuristiques/IA comme
    # DeepInstinct), car aussi tres utilisee pour obfusquer de vrais malwares.
    # La desactiver augmente legerement la taille du .exe mais reduit nettement
    # ce risque. Voir BUILD.md, section "Faux positifs antivirus" pour le detail.
    upx=False,
    console=False,  # Application graphique -- pas de console visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'icon.ico'),
    version=str(project_root / 'version_info.txt'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EmpyrionScenarioEditor',
)

# --- Deuxieme executable : outils de diagnostic en ligne de commande ---
# Construit separement (mode "onefile" -- un seul .exe autonome, pas de dossier
# _internal) car cli_tools.py ne depend d'aucun module PyQt6 (voir cli_tools.py),
# ce qui le rend beaucoup plus leger que l'appli graphique. Le onefile convient
# bien ici : un demarrage legerement plus lent est sans consequence pour un outil
# lance ponctuellement depuis un terminal, contrairement a l'appli graphique.
cli_a = Analysis(
    ['cli_tools.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # cli_tools.py importe ces modules dynamiquement (importlib.import_module
        # avec une variable, pas un "import" litteral) -- invisible pour l'analyse
        # statique de PyInstaller, donc declares ici explicitement. Toute nouvelle
        # commande ajoutee a cli_tools.py doit aussi etre ajoutee ici.
        'cli.verifier_parser_ecf', 'cli.verifier_parser_yaml', 'cli.verifier_parser_csv',
        'cli.diagnostic_bloc', 'cli.detecter_imbrication_anormale', 'cli.diff_ecf',
        'cli.edit_ecf', 'cli.merge_ecf', 'cli.transform_ecf', 'cli.pack_tech_tree_icons',
        'cli.pack_localization',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'qtawesome'] + _ARGOS_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

cli_pyz = PYZ(cli_a.pure, cli_a.zipped_data, cipher=block_cipher)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name='EmpyrionEditorCLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # meme raison que pour l'exe principal, voir plus haut
    console=True,  # Outil en ligne de commande -- console visible necessaire
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(project_root / 'version_info.txt'),
)

cli_coll = COLLECT(
    cli_exe,
    cli_a.binaries,
    cli_a.zipfiles,
    cli_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EmpyrionEditorCLI',
)
