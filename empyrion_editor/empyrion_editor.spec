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

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    ['run_gui.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Les wikis et autres fichiers markdown doivent etre embarques tels quels --
        # lus a l'execution via un chemin relatif au dossier du projet, pas importes
        # comme du code Python.
        (str(project_root / 'docs'), 'docs'),
    ],
    hiddenimports=[
        # PyQt6 charge certains sous-modules dynamiquement (non detectes par
        # l'analyse statique de PyInstaller) -- a completer si une erreur
        # "ModuleNotFoundError" apparait au premier lancement de l'exe construit.
        'PyQt6.sip',
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
    upx=True,
    console=False,  # Application graphique -- pas de console visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EmpyrionScenarioEditor',
)
