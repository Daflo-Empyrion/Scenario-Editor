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

a = Analysis(
    ['run_gui.py'],
    pathex=[str(project_root)],
    binaries=[*_dt_binaries, *_bs4_binaries, *_requests_binaries, *_certifi_binaries],
    datas=[
        # Les wikis et autres fichiers markdown doivent etre embarques tels quels --
        # lus a l'execution via un chemin relatif au dossier du projet, pas importes
        # comme du code Python.
        (str(project_root / 'docs'), 'docs'),
        # Badge GPLv3 affiche dans le dialogue "A propos" -- meme logique.
        (str(project_root / 'assets'), 'assets'),
        *_dt_datas, *_bs4_datas, *_requests_datas, *_certifi_datas,
    ],
    hiddenimports=[
        # PyQt6 charge certains sous-modules dynamiquement (non detectes par
        # l'analyse statique de PyInstaller) -- a completer si une erreur
        # "ModuleNotFoundError" apparait au premier lancement de l'exe construit.
        'PyQt6.sip',
        *_dt_hiddenimports, *_bs4_hiddenimports, *_requests_hiddenimports,
        *_certifi_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
        'verifier_parser_ecf', 'verifier_parser_yaml', 'verifier_parser_csv',
        'diagnostic_bloc', 'detecter_imbrication_anormale', 'diff_ecf',
        'edit_ecf', 'merge_ecf', 'transform_ecf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'qtawesome'],
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
