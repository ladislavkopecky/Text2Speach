; Inno Setup skript pro Generator zvuku
; Pouziti: ISCC installer.iss  (po spusteni build_installer.bat)
; Vysledek: installer_output\GeneratorZvukuSetup.exe

#define AppName      "Generátor zvuků"
#define AppNameShort "GeneratorZvuku"
#define AppVersion   "1.0"
#define AppPublisher "Text2Speech"
#define AppExeName   "GeneratorZvuku.exe"
#define SourceDir    "dist\GeneratorZvuku"

[Setup]
AppId={{B7E2F4C1-3A5D-4F8E-9C2B-1D6A8E0F3B4C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppNameShort}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=GeneratorZvukuSetup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
ArchitecturesAllowed=x64compatible
WizardStyle=modern
; Barva pozadi pruvodce (fialova)
WizardSizePercent=120

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvorit zkratku na ploše"; GroupDescription: "Dalsi ikony:"; Flags: unchecked
Name: "startmenuicon"; Description: "Vytvorit zkratku v nabidce Start"; GroupDescription: "Dalsi ikony:"

[Files]
; Vsechny soubory z PyInstaller vystupu
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Odinstalovet {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Spustit {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Zobrazi hlasku po uspesne instalaci
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox('Instalace dokoncena!' + #13#10 + 
           'Aplikaci spustite pres zkratku na plose nebo v nabidce Start.',
           mbInformation, MB_OK);
  end;
end;
