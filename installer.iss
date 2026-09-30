#define MyAppName "Cassette"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Cassette"
#define MyAppExeName "Cassette.exe"

[Setup]
SetupIconFile=cassette.ico
AppId={{A7A1F5D4-7D54-4E4C-9E2A-CASSETTE1000}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Cassette
DefaultGroupName=Cassette
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Cassette_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Cassette.exe

[Files]
Source: "dist\Cassette.exe"; DestDir: "{app}"; Flags: ignoreversion

; Cassette image assets
Source: "logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "s1.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "s2.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "s3.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "s4.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "s5.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Cassette"; Filename: "{app}\Cassette.exe"
Name: "{autodesktop}\Cassette"; Filename: "{app}\Cassette.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\Cassette.exe"; Description: "Launch Cassette"; Flags: nowait postinstall skipifsilent