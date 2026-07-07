; KeyHub Inno Setup Installer
; Produces KeyHub-Setup.exe — lets user choose install directory.
; Data (config, logs, keys) stays within the chosen directory.

#define MyAppName "KeyHub"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "KeyHub"
#define MyAppURL "https://github.com/Townrain/API-Key-Manager"
#define MyAppExeName "KeyHub.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Let user choose directory
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=no
; No Program Files subfolder pollution
UsePreviousAppDir=yes
; Portable-style: all data in app dir
DirExistsWarning=no
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Installer metadata
OutputDir=dist
OutputBaseFilename=KeyHub-Setup
; Windows version req
MinVersion=10.0
; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Note: config.yaml.example NOT installed — exe auto-creates config.yaml on first run
; so the user's config survives uninstall/reinstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
