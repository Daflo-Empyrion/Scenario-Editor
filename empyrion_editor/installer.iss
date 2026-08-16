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
#define MyAppVersion "1.0.0"
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
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
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

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
