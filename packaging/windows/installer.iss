; Inno Setup recipe for SysadminCareer-Setup.exe. Run it through build.py,
; which passes /DGameVersion=... and builds dist\SysadminCareer first.
;
; Installs for the current user only (no admin prompt) into
; %LOCALAPPDATA%\Programs\Sysadmin Career, with a Start-menu entry.

#ifndef GameVersion
  #define GameVersion "dev"
#endif

[Setup]
; The AppId identifies the game to Windows across versions: never change it,
; or upgrades would install side by side instead of replacing the old one.
AppId={{23ACF181-AB50-454E-8392-F8D6F616071B}
AppName=Sysadmin Career
AppVersion={#GameVersion}
AppPublisher=Banele
AppPublisherURL=https://github.com/banele-za/sysadmin-career
PrivilegesRequired=lowest
DefaultDirName={autopf}\Sysadmin Career
DefaultGroupName=Sysadmin Career
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\SysadminCareer.exe
SetupIconFile=..\icons\icon.ico
OutputDir=..\..\dist
OutputBaseFilename=SysadminCareer-Setup-{#GameVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; The game needs 64-bit Windows 10 or newer (WHPX, WebView2).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\SysadminCareer\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Sysadmin Career"; Filename: "{app}\SysadminCareer.exe"
Name: "{userdesktop}\Sysadmin Career"; Filename: "{app}\SysadminCareer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SysadminCareer.exe"; Description: "Start Sysadmin Career now"; Flags: nowait postinstall skipifsilent

[Code]
// The game keeps its save, the downloaded Linux image and the VM's disks in
// %LOCALAPPDATA%\SysadminGame (see client/host.py). Uninstalling the program
// leaves them by default, so reinstalling keeps your progress; ask first.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\SysadminGame');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox('Also delete your saved progress and the downloaded Linux image?' + #13#10 +
                '(Keep them if you plan to reinstall the game.)',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
