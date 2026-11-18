; JARVIS Desktop - per-user, offline Windows installer.
; Compile using packaging/build_installer.ps1 on Windows.
#if GetEnv("JARVIS_VERSION") != ""
  #define JARVIS_VERSION GetEnv("JARVIS_VERSION")
#else
  #define JARVIS_VERSION "1.0.0"
#endif
#define AppName "JARVIS Desktop"
#define AppExe "JarvisDesktop.exe"

[Setup]
AppId={{A8E82F31-7163-41AA-9C9F-6A19B1ABF245}
AppName={#AppName}
AppVersion={#JARVIS_VERSION}
AppVerName={#AppName} {#JARVIS_VERSION}
AppPublisher=JARVIS Desktop
DefaultDirName={localappdata}\Programs\JARVIS Desktop
DefaultGroupName=JARVIS Desktop
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\jarvis.ico
UninstallDisplayIcon={app}\{#AppExe}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
OutputDir=..\dist
OutputBaseFilename=JARVIS-Setup-{#JARVIS_VERSION}-x64
; Trusted signing of Setup, temporary copies AND the uninstaller is needed for Smart App Control.
#if GetEnv("JARVIS_SIGNING_READY") == "1"
SignTool=jarvissign $f
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: autostart; Description: "Start JARVIS when I sign in to Windows (system tray)"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "..\dist\JarvisDesktop\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\JARVIS Desktop"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\JARVIS Desktop"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\JARVIS Desktop"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch JARVIS Desktop"; Flags: nowait postinstall skipifsilent

; User data deliberately stays in %LOCALAPPDATA%\JarvisLocal when upgrading or uninstalling.
; The application's API credentials are stored separately using Windows Credential Manager.
