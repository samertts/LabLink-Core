#define MyAppName "LabLink Core"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "LabLink"
#define MyAppExeName "Application.exe"

[Setup]
AppId={{8C16A17A-7A5F-4DEA-B3D0-21BC2D4C8D9A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer\Output
OutputBaseFilename=ApplicationSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

[Files]
Source: "dist\Application.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "storage\*"; DestDir: "{app}\storage"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\storage\data"
Name: "{app}\storage\backups"
Name: "{app}\storage\exports"
Name: "{app}\storage\logs"
Name: "{app}\storage\temp"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
