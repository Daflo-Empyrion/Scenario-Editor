@echo off
REM Construit l'executable (PyInstaller) puis l'installeur Windows (Inno Setup)
REM en une seule commande. A lancer depuis le dossier du projet, avec
REM l'environnement virtuel active. Voir BUILD.md pour la configuration initiale.

echo ============================================
echo  1/2 - Construction de l'executable (PyInstaller)
echo ============================================
pyinstaller empyrion_editor.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERREUR : la construction PyInstaller a echoue. Voir le message ci-dessus.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  2/2 - Construction de l'installeur (Inno Setup)
echo ============================================

REM Cherche ISCC.exe (compilateur Inno Setup) aux emplacements d'installation
REM habituels. Si Inno Setup est installe ailleurs, modifier la ligne ci-dessous.
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist %ISCC% (
    echo.
    echo ERREUR : Inno Setup introuvable. Installe-le depuis
    echo https://jrsoftware.org/isinfo.php puis relance ce script.
    echo Si deja installe ailleurs, modifie la variable ISCC dans build.bat.
    pause
    exit /b 1
)

%ISCC% installer.iss
if errorlevel 1 (
    echo.
    echo ERREUR : la construction de l'installeur a echoue. Voir le message ci-dessus.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Termine ! Installeur disponible dans :
echo  installer_output\
echo ============================================
pause
