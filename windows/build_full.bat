@echo off
REM ============================================================
REM HCCleaner - Script de Build Completo
REM HCsoftware © 2026
REM ============================================================

echo.
echo ============================================
echo  HCCleaner Build Script
echo  HCsoftware
echo ============================================
echo.

cd /d "%~dp0"

echo [1/4] Verificar dependencias...
python --version >nul 2>&1 || (echo ERRO: Python nao encontrado & pause & exit /b 1)
pip show Pillow >nul 2>&1 || pip install Pillow
pip show pyinstaller >nul 2>&1 || pip install pyinstaller

echo [2/4] Gerar imagens do instalador...
python make_installer_images.py
if errorlevel 1 (echo AVISO: Falha nas imagens - continuando... )

echo [3/4] Compilar HCCleaner.exe com PyInstaller...
pyinstaller --noconfirm --onefile --windowed ^
    --name "HCCleaner" ^
    --add-data "imagens;imagens" ^
    --add-data "hc_theme.py;." ^
    --add-data "modules;modules" ^
    --icon "imagens\HCsoftware.ico" ^
    --uac-admin ^
    --version-file version_info.txt ^
    main.py

if errorlevel 1 (
    echo ERRO: Falha na compilacao do .exe
    pause
    exit /b 1
)

echo [4/4] Criar instalador com Inno Setup...
REM Procurar o Inno Setup em locais comuns
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo.
    echo AVISO: Inno Setup nao encontrado.
    echo Descarrega em: https://jrsoftware.org/isdl.php
    echo Depois executa manualmente: ISCC.exe HCCleaner_Setup.iss
    echo.
    echo O ficheiro .exe esta em: dist\HCCleaner.exe
) else (
    mkdir installer_output 2>nul
    %ISCC% HCCleaner_Setup.iss
    if errorlevel 1 (
        echo ERRO: Falha na criacao do instalador
    ) else (
        echo.
        echo ============================================
        echo  BUILD CONCLUIDO COM SUCESSO!
        echo ============================================
        echo  Executavel:  dist\HCCleaner.exe
        echo  Instalador:  installer_output\HCCleaner_Setup_1.0.1.exe
        echo ============================================
    )
)

echo.
pause
