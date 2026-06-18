[Setup]
AppName=MiMo Auto
AppVersion=2.0.0
AppPublisher=MiMo Team
AppPublisherURL=https://mimo.xiaomi.com
AppSupportURL=https://mimo.xiaomi.com/support
DefaultDirName={autopf}\MiMo Auto
DefaultGroupName=MiMo Auto
OutputDir=build
OutputBaseFilename=MiMoSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=yes
SetupIconFile=mimo.ico
UninstallDisplayIcon={app}\mimo_launch.exe
AppId={{9C12A3B4-55D1-4A88-9F11-ABC123456789}
VersionInfoVersion=2.0.0.0
VersionInfoDescription=MiMo Auto Installer
VersionInfoProductName=MiMo Auto
VersionInfoProductVersion=2.0.0
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full Installation"; Flags: iscustom
Name: "portable"; Description: "Portable Mode (no system changes)"

[Components]
Name: "main"; Description: "MiMo Auto Core"; Types: full portable; Flags: fixed
Name: "shortcuts"; Description: "Desktop && Start Menu Shortcuts"; Types: full
Name: "bootstrapper"; Description: "Dependency Manager (Node.js, Git)"; Types: full; Flags: fixed

[Files]
Source: "dist\MiMoInstaller.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\mimo_launch.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "bootstrapper\*"; DestDir: "{app}\bootstrapper"; Flags: recursesubdirs ignoreversion
Source: "preflight.cmd"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\MiMo Auto"; Filename: "{app}\mimo_launch.exe"; Comment: "Launch MiMo Auto"
Name: "{group}\Uninstall MiMo Auto"; Filename: "{uninstallexe}"
Name: "{commondesktop}\MiMo Auto"; Filename: "{app}\mimo_launch.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletevalue; Check: not IsPortableMode
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "MIMO_HOME"; ValueData: "{app}"; Flags: uninsdeletevalue; Check: not IsPortableMode

[Run]
Filename: "{app}\bootstrapper\MiMoBootstrapper.exe"; Parameters: "--first-run --install-dir ""{app}"""; StatusMsg: "Setting up MiMo Auto..."; Flags: nowait postinstall runascurrentuser skipifnotsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\install_state.json"
Type: files; Name: "{app}\portable.flag"

[Code]
var
  InstallMode: Integer;

function IsPortableMode: Boolean;
begin
  Result := (InstallMode = 1);
end;

procedure InitializeWizard;
begin
  InstallMode := 0;
end;
