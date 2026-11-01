#ifndef NEMOVersion
#define NEMOVersion "1.0.0"
#endif

[Setup]
AppId={{872FD780-0BBA-43A9-A26B-0C71304AF725}
AppName=N.E.M.O
AppVersion={#NEMOVersion}
AppVersionInfoVersion={#NEMOVersion}
AppPublisher=N.E.M.O
DefaultDirName={localappdata}\Programs\NEMO
DefaultGroupName=N.E.M.O
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=NEMO-Setup-{#NEMOVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\NEMO.exe

[Files]
Source: "..\dist\NEMO\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\N.E.M.O"; Filename: "{app}\NEMO.exe"
Name: "{autodesktop}\N.E.M.O"; Filename: "{app}\NEMO.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\NEMO.exe"; Description: "Launch N.E.M.O"; Flags: postinstall nowait skipifsilent
