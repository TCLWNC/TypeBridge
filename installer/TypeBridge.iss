; TypeBridge（跨屏输入）安装程序脚本
;
; 编译（需要 Inno Setup 6）：
;   "C:\Users\<你的用户名>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer\TypeBridge.iss
; 产物在 installer\output\TypeBridge-<版本>-Setup.exe
;
; 行为：装到当前用户目录（{localappdata}\TypeBridge），不需要管理员权限；
;       可选桌面图标、开机托盘常驻、安装后下载语音模型；
;       卸载时会问一句要不要连设置和语音模型一起删（默认"否"，不会悄悄删数据）。

#define AppName "TypeBridge 跨屏输入"
#define AppVersion "1.1.0"
#define AppExe "TypeBridge-PC.exe"
; 源码根目录：本文件在 <仓库>\installer\ 下，所以往上一层
#define SrcDir ".."

[Setup]
AppId={{8E31C4B7-5A6D-4E9F-9C21-7B4F2A6D1E33}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=TCLWNC
AppPublisherURL=https://github.com/TCLWNC/TypeBridge
AppSupportURL=https://github.com/TCLWNC/TypeBridge
DefaultDirName={localappdata}\TypeBridge
DefaultGroupName=TypeBridge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=TypeBridge-{#AppVersion}-Setup
SetupIconFile={#SrcDir}\crosslink\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "cn"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："
Name: "autostart"; Description: "开机自动启动（在托盘常驻）"; GroupDescription: "附加任务："; Flags: unchecked
Name: "getmodel"; Description: "安装后下载语音模型（约 228MB，语音输入要用）"; GroupDescription: "附加任务："

[Files]
; 整个程序目录（PyInstaller onedir，含 _internal 依赖）
Source: "{#SrcDir}\pc\TypeBridge-PC-win64\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
; 脚本和说明
Source: "{#SrcDir}\Start-TypeBridge.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Start-TypeBridge-Tray.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Allow-Firewall-AsAdmin.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Remove-Firewall-Rules.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Get-Voice-Model.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\FILES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\crosslink\assets\icon.ico"; DestDir: "{app}\icon"; Flags: ignoreversion

[Icons]
Name: "{group}\TypeBridge（跨屏输入）"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\icon\icon.ico"
Name: "{group}\TypeBridge（托盘常驻）"; Filename: "{app}\{#AppExe}"; Parameters: "--tray"; IconFilename: "{app}\icon\icon.ico"
Name: "{group}\放行防火墙（需要管理员）"; Filename: "{app}\Allow-Firewall-AsAdmin.bat"; IconFilename: "{app}\icon\icon.ico"
Name: "{group}\下载语音模型（约 228MB）"; Filename: "{app}\Get-Voice-Model.bat"; IconFilename: "{app}\icon\icon.ico"
Name: "{group}\使用说明"; Filename: "{app}\README.md"
Name: "{autodesktop}\TypeBridge（跨屏输入）"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\icon\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\TypeBridge 托盘常驻"; Filename: "{app}\{#AppExe}"; Parameters: "--tray"; Tasks: autostart

[Run]
Filename: "{app}\Get-Voice-Model.bat"; Description: "下载语音模型（约 228MB）"; \
  Flags: shellexec nowait postinstall; Tasks: getmodel
Filename: "{app}\{#AppExe}"; Description: "立即启动 TypeBridge"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
{ 卸载时问一句要不要连配置和语音模型一起删掉（在 %APPDATA%\CrossLink）；默认"否" }
function InitializeUninstall(): Boolean;
var
  Answer: Integer;
  DataDir: String;
begin
  DataDir := ExpandConstant('{userappdata}\CrossLink');
  if DirExists(DataDir) then
  begin
    Answer := MsgBox('是否同时删除设置和语音模型？' + #13#10 + #13#10 +
                     DataDir + #13#10 +
                     '（语音模型约 228MB，删掉后下次要重新下载）',
                     mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
    if Answer = IDYES then
      DelTree(DataDir, True, True, True);
  end;
  Result := True;
end;
