; Inno-Setup-Skript für den Installer, aufgerufen von build.ps1 (ISCC /DVersion=<version> /DQuelle=<ordner>).
; Installiert ohne Adminrechte nach %LOCALAPPDATA%\Programs\dxf2qet (im Dialog auf „für alle Benutzer“ umstellbar).

#ifndef Version
  #error Version fehlt (ISCC /DVersion=...)
#endif

[Setup]
AppId={{8E380D0F-564A-423C-B198-B60C39400BC3}
AppName=DXF zu QElectroTech
AppVersion={#Version}
AppVerName=DXF zu QElectroTech {#Version}
AppPublisher=Christian Nagel
AppCopyright=© 2026 Christian Nagel
AppPublisherURL=https://github.com/christianngl/dxf2qet
VersionInfoVersion={#Version}
VersionInfoProductName=DXF zu QElectroTech
VersionInfoDescription=Installer für DXF zu QElectroTech
DefaultDirName={autopf}\dxf2qet
DefaultGroupName=DXF zu QElectroTech
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\dxf2qet.exe
OutputDir=..\dist
OutputBaseFilename=dxf2qet-Setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Quelle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DXF zu QElectroTech"; Filename: "{app}\dxf2qet.exe"
Name: "{autodesktop}\DXF zu QElectroTech"; Filename: "{app}\dxf2qet.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\dxf2qet.exe"; Description: "{cm:LaunchProgram,DXF zu QElectroTech}"; Flags: nowait postinstall skipifsilent
