@echo off
REM Construit l'executable (PyInstaller) puis l'installeur Windows (Inno Setup)
REM en une seule commande. Voir BUILD.md pour la configuration initiale.
REM
REM IMPORTANT : ce script active LUI-MEME l'environnement virtuel (venv\) avant de
REM construire quoi que ce soit -- inutile (et deconseille) de l'activer a la main
REM avant de lancer ce script. Ceci evite un probleme reel deja rencontre : lancer
REM pyinstaller avec le Python GLOBAL au lieu du venv produit un .exe construit SANS
REM les dependances du projet (deep-translator, bs4...), sans erreur visible avant
REM de tester la fonction concernee une fois l'appli installee.

echo ============================================
echo  0/3 - Verification de l'environnement
echo ============================================

if not exist venv\Scripts\activate.bat (
    echo.
    echo ERREUR : environnement virtuel introuvable ^(dossier venv\^).
    echo Cree-le d'abord ^(voir BUILD.md, section 1^) :
    echo     python -m venv venv
    echo     venv\Scripts\activate
    echo     pip install -r requirements.txt
    echo     pip install -r requirements-build.txt
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Python utilise pour la construction :
where python
echo.

python -c "import deep_translator, bs4, PyQt6, PyInstaller" 2>nul
if errorlevel 1 (
    echo.
    echo ERREUR : une ou plusieurs dependances du projet sont introuvables dans cet
    echo environnement virtuel ^(deep_translator, bs4, PyQt6 ou PyInstaller^).
    echo Installe-les avant de relancer ce script :
    echo     venv\Scripts\activate
    echo     pip install -r requirements.txt
    echo     pip install -r requirements-build.txt
    pause
    exit /b 1
)
echo Dependances verifiees : OK

echo.
echo ============================================
echo  1/3 - Construction de l'executable (PyInstaller)
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
echo  2/3 - Construction de l'installeur (Inno Setup)
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
echo  3/3 - Termine ! Installeur disponible dans :
echo  installer_output\
echo ============================================
pause
