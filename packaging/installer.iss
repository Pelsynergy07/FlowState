; FlowState installer. No paths here reference the dev machine specifically
; -- everything resolves through Inno's {autopf}/{userappdata}/{app}
; constants, so this installer is meant to run on any Windows 11 machine.

#define MyAppName "FlowState"
#define MyAppVersion "0.1.8"
#define MyAppPublisher "FlowState"
#define MyAppExeName "FlowState.exe"

[Setup]
AppId={{B6C9E1B2-6E6E-4A9B-9B6D-2E6C9C6D2F31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Matches the mutex name FlowState.exe itself creates for its single-
; instance guard (see _acquire_single_instance_lock in __main__.py). Lets
; Setup detect a running FlowState and close/relaunch it around a silent
; self-update (see updater.py's /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS).
AppMutex=Global\FlowStateSingleInstance
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
ExtraDiskSpaceRequired=2147483648
OutputDir=dist_installer
OutputBaseFilename=FlowStateSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app_icon.ico
WizardSmallImageFile=wizard_small.bmp
WizardImageFile=wizard_large.bmp
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
BeveledLabel=SYS.01 // FLOWSTATE SETUP // v{#MyAppVersion}
WelcomeLabel1=FlowState Setup
WelcomeLabel2=Local, offline voice dictation for Windows.%n%n• Real-time speech transcription & smart LLM cleanup%n• Spatial visual context capture with zero cloud telemetry%n• Private, on-device AI models%n%nClick Next to proceed with installation.
SelectDirLabel3=Setup will install FlowState into the following folder. At least 4.5 GB of free disk space is recommended for the application binaries and local offline AI models.


[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "launchatlogin"; Description: "Launch FlowState automatically when Windows starts"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\FlowState\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FlowState"; ValueData: """{app}\{#MyAppExeName}"" --autostart"; Tasks: launchatlogin; Flags: uninsdeletevalue

[Run]
; No skipifsilent: a silent run (VERYSILENT) is exactly what updater.py's
; self-update flow uses, and it depends on FlowState relaunching itself
; afterwards -- unlike a normal silent enterprise deployment, this is
; always user-initiated from inside the app, so auto-launch is wanted.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#MyAppName}');
    if DirExists(DataDir) then
    begin
      if not UninstallSilent then
      begin
        if MsgBox('Do you also want to delete all downloaded AI models and settings from ' + DataDir + '?' + #13#10 + #13#10 + 'This will free ~4 GB of disk space.', mbConfirmation, MB_YESNO or MB_DEFBUTTON1) = idYes then
        begin
          DelTree(DataDir, True, True, True);
        end;
      end
      else
      begin
        // In silent mode, leave data intact unless explicitly requested
      end;
    end;
  end;
end;
