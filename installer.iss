; Script Inno Setup -- genere un installeur Windows classique
; (Setup-EmpyrionScenarioEditor-vX.Y.Z.exe) a partir du build PyInstaller.
;
; PREREQUIS : avoir deja lance "pyinstaller empyrion_editor.spec" (voir BUILD.md)
; -- ce script attend le resultat dans dist/EmpyrionScenarioEditor/.
;
; OUTIL NECESSAIRE : Inno Setup (gratuit) -- https://jrsoftware.org/isinfo.php
; Une fois installe, ouvrir ce fichier avec "Inno Setup Compiler" et cliquer
; "Compile" (ou clic droit sur ce fichier > "Compile").
;
; A CHAQUE NOUVELLE VERSION : mettre a jour MyAppVersion ci-dessous pour qu'il
; corresponde exactement a APP_VERSION dans core/version.py.

#define MyAppName "Empyrion Scenario Editor"
#define MyAppVersion "1.2.2"
#define MyAppPublisher "Daflo"
#define MyAppExeName "EmpyrionScenarioEditor.exe"

[Setup]
; Identifiant unique de l'application (genere une fois, ne JAMAIS changer par la
; suite -- c'est ce qui permet a Windows/Inno Setup de reconnaitre une mise a
; jour de la meme application plutot qu'une nouvelle installation independante).
AppId={{8F2C9B1A-4E7D-4A3F-9C6B-2D5E8A1F3C7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Metadonnees de version Windows pour l'INSTALLEUR lui-meme (Setup-*.exe) --
; distinctes de version_info.txt, qui ne concerne que les executables de
; l'application une fois installes (voir empyrion_editor.spec). Sans ceci,
; l'installeur affiche des proprietes vides, moins rassurant pour l'utilisateur
; et pour les heuristiques antivirus (voir BUILD.md, section 7).
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Installeur de {#MyAppName}
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher} -- GNU GPLv3
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Affiche une page d'information avant l'installation, resumant les seules
; fonctionnalites qui font des requetes reseau (traduction en ligne,
; verification de version, bouton Signaler) et comment les desactiver --
; exige par la politique de confidentialite SignPath Foundation pour les
; logiciels transferant des donnees utilisateur. Detail complet dans
; PRIVACY.md a la racine du depot.
InfoBeforeFile=installer_privacy_notice.txt
; Installation par utilisateur (pas besoin de droits administrateur) -- plus
; simple pour un public non-technique, et coherent avec le fait que les donnees
; utilisateur vivent deja dans le profil (~/.empyrion_editor), jamais dans le
; dossier d'installation.
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=Setup-EmpyrionScenarioEditor-v{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Desinstalle automatiquement l'ancienne version avant d'installer la nouvelle,
; sans jamais toucher au dossier d'installation choisi par l'utilisateur ni a
; ses donnees (scenarios, reglages) qui vivent ailleurs.
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copie l'integralite du dossier construit par PyInstaller. Ne touche jamais aux
; donnees utilisateur (~/.empyrion_editor) ni aux dossiers de scenarios choisis
; par l'utilisateur -- entierement hors de ce dossier d'installation.
Source: "dist\EmpyrionScenarioEditor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Outils de diagnostic en ligne de commande (voir cli_tools.py) -- un seul .exe
; autonome, installe a cote de l'appli graphique pour un usage depuis un terminal.
; Outils de diagnostic en ligne de commande (voir cli_tools.py) -- installes dans
; un sous-dossier dedie (CLI\) plutot qu'a cote de l'exe principal, pour eviter
; toute collision entre les dossiers _internal\ respectifs des deux executables
; (chacun construit desormais en mode "dossier", pas "fichier unique" -- voir
; empyrion_editor.spec, raison detaillee dans le commentaire pres de upx=False).
Source: "dist\EmpyrionEditorCLI\*"; DestDir: "{app}\CLI"; Flags: ignoreversion recursesubdirs createallsubdirs
; La GPLv3 exige que le texte de la licence accompagne le programme distribue --
; copie explicitement ici (PyInstaller n'embarque que le code, pas ce fichier).
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "PRIVACY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Licence (GPLv3)"; Filename: "{app}\LICENSE.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
