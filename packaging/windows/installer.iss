; Установщик File Converter Pro для Windows (Inno Setup 6).
; Ставится для текущего пользователя в %LOCALAPPDATA%\Programs — без прав администратора и UAC.
; Сборка (из корня проекта, после python build.py):
;   iscc /DAppVersion=1.1.0 packaging\windows\installer.iss
; Результат: dist\FileConverterPro_Windows_Setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
; AppId не менять: по нему Windows узнаёт обновление уже установленной программы
AppId={{E5D32313-80E2-4CD2-830B-5FBDEFA1DF77}
AppName=File Converter Pro
AppVersion={#AppVersion}
AppVerName=File Converter Pro {#AppVersion}
AppPublisher=File Converter Pro
DefaultDirName={autopf}\File Converter Pro
DefaultGroupName=File Converter Pro
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=FileConverterPro_Windows_Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\FileConverterPro.exe
UninstallDisplayName=File Converter Pro
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\FileConverterPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\File Converter Pro"; Filename: "{app}\FileConverterPro.exe"
Name: "{autodesktop}\File Converter Pro"; Filename: "{app}\FileConverterPro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FileConverterPro.exe"; Description: "{cm:LaunchProgram,File Converter Pro}"; Flags: nowait postinstall skipifsilent
