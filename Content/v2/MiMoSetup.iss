[Setup]
AppName=MiMo Auto
AppVersion=2.2.0
AppPublisher=Sassi
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
UninstallDisplayIcon={app}\mimo.ico
AppId={{9C12A3B4-55D1-4A88-9F11-ABC123456789}
VersionInfoVersion=2.2.0.0
VersionInfoDescription=MiMo Auto Installer
VersionInfoProductName=MiMo Auto
VersionInfoProductVersion=2.2.0
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
Source: "launch_mimo.cmd"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "mimo.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\MiMo Web"; Filename: "{app}\launch_mimo.cmd"; Comment: "Open MiMo Web UI"; IconFilename: "{app}\mimo.ico"
Name: "{group}\Uninstall MiMo Auto"; Filename: "{uninstallexe}"
Name: "{commondesktop}\MiMo Web"; Filename: "{app}\launch_mimo.cmd"; Tasks: desktopicon; IconFilename: "{app}\mimo.ico"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletevalue; Check: not IsPortableMode
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "MIMO_HOME"; ValueData: "{app}"; Flags: uninsdeletevalue; Check: not IsPortableMode

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\install_state.json"
Type: files; Name: "{app}\portable.flag"
Type: files; Name: "{app}\install_progress.txt"

[Run]
Filename: "{app}\bootstrapper\MiMoBootstrapper.exe"; Parameters: "--first-run --install-dir ""{app}"""; StatusMsg: "Installing Node.js, MiMo CLI..."; Flags: postinstall runminimized waituntilterminated; AfterInstall: CheckBootstrapResult

[Code]
var
  InstallMode: Integer;
  BootstrapOK: Boolean;

function IsPortableMode: Boolean;
begin
  Result := (InstallMode = 1);
end;

procedure InitializeWizard;
begin
  InstallMode := 0;
  BootstrapOK := True;
end;

procedure CheckBootstrapResult;
var
  StateFile: String;
  Content: AnsiString;
begin
  StateFile := ExpandConstant('{app}\install_state.json');
  if not FileExists(StateFile) then
  begin
    BootstrapOK := False;
    MsgBox('Installation may be incomplete.' + #13#10 + 'Check: ' + ExpandConstant('{app}') + '\logs\bootstrapper.log', mbError, MB_OK);
    Exit;
  end;
  if not LoadStringFromFile(StateFile, Content) then
  begin
    BootstrapOK := False;
    MsgBox('Failed to read install state.', mbError, MB_OK);
    Exit;
  end;
  if Pos('"install_result": "partial"', Content) > 0 then
  begin
    BootstrapOK := False;
    MsgBox('Some dependencies failed to install.' + #13#10 + 'Check: ' + ExpandConstant('{app}') + '\logs\bootstrapper.log' + #13#10 + #13#10 + 'Run Repair from the Start Menu to retry.', mbInformation, MB_OK);
  end
  else if Pos('"install_result": "failed"', Content) > 0 then
  begin
    BootstrapOK := False;
    MsgBox('Installation failed.' + #13#10 + 'Check: ' + ExpandConstant('{app}') + '\logs\bootstrapper.log', mbError, MB_OK);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
end;
