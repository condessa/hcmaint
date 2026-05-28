; ============================================================
; HCCleaner - Script de Instalação Inno Setup
; HCsoftware © 2026 - Silves, Algarve, Portugal
; ============================================================

#define AppName "HCCleaner"
#define AppVersion "1.0.1"
#define AppPublisher "HCsoftware"
#define AppURL "https://github.com/condessa/hcmaint"
#define AppExeName "HCCleaner.exe"
#define AppDescription "Ferramenta de Manutenção e Limpeza do Windows"

[Setup]
AppId={{B7C4E2A1-9F3D-4E8B-A2C5-1D6F8E3B7A09}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppPublisher}\{#AppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=installer_output
OutputBaseFilename=HCCleaner_Setup_{#AppVersion}
SetupIconFile=imagens\HCsoftware.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppDescription}
VersionInfoCopyright=© 2026 {#AppPublisher}
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible

; Cores do tema HCsoftware
WizardImageFile=imagens\installer_banner.bmp
WizardSmallImageFile=imagens\installer_icon.bmp

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho no &Ambiente de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "startmenuicon"; Description: "Criar atalho no Menu &Início"; GroupDescription: "Atalhos:"; Flags: checkedonce
Name: "quicklaunch"; Description: "Criar atalho na Barra de &Tarefas"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
; Executável principal
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Licença e documentação
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Menu Início
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "{#AppDescription}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

; Ambiente de trabalho (opcional)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Comment: "{#AppDescription}"

; Barra de tarefas (opcional)
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunch

[Run]
; Opção de executar após instalação
Filename: "{app}\{#AppExeName}"; Description: "Executar {#AppName} agora"; Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallDelete]
; Limpar ficheiros gerados pelo programa
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp"

[Code]
// Verificar se o Windows 10 ou superior
function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  if Version.Major < 10 then
  begin
    MsgBox('O HCCleaner requer Windows 10 ou superior.', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

// Mensagem de boas-vindas personalizada
procedure InitializeWizard();
begin
  WizardForm.WelcomeLabel2.Caption :=
    'Este assistente vai instalar o ' + ExpandConstant('{#AppName}') + ' ' +
    ExpandConstant('{#AppVersion}') + ' no seu computador.' + #13#10 + #13#10 +
    'O HCCleaner é uma ferramenta gratuita de limpeza e manutenção ' +
    'do Windows, desenvolvida pela HCsoftware.' + #13#10 + #13#10 +
    'Clique em Seguinte para continuar ou Cancelar para sair.';
end;

// Aviso SmartScreen antes de terminar
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox(
      'Instalação concluída!' + #13#10 + #13#10 +
      'NOTA SOBRE O WINDOWS SMARTSCREEN:' + #13#10 +
      'Na primeira execução, o Windows pode mostrar um aviso ' +
      '"O Windows protegeu o seu PC".' + #13#10 + #13#10 +
      'Isto é normal — o HCCleaner não tem assinatura digital ' +
      'comercial (os certificados custam centenas de euros/ano).' + #13#10 + #13#10 +
      'Para executar: clique em "Mais informações" e depois ' +
      '"Executar mesmo assim".' + #13#10 + #13#10 +
      'Todo o código fonte está disponível em:' + #13#10 +
      'https://github.com/condessa/hcmaint',
      mbInformation, MB_OK);
  end;
end;
