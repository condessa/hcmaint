@echo off
REM HCCleaner - Build Script (Windows)
REM Requer: Python 3.10+, pip

echo.
echo ========================================
echo  HCCleaner Build Script v1.3.3
echo  HCsoftware
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Verificar imagem do logo...
if not exist "imagens\HCsoftware.png" (
    echo AVISO: imagens\HCsoftware.png nao encontrado!
    echo Coloca o ficheiro antes de compilar.
    pause
    exit /b 1
) else (
    echo OK - Logo encontrado.
)

echo [2/4] Instalar dependencias...
pip install Pillow pyinstaller --quiet

echo [3/4] Limpar builds anteriores...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "HCCleaner.spec" del HCCleaner.spec

echo [4/4] Compilar executavel...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "HCCleaner" ^
    --add-data "imagens;imagens" ^
    --add-data "hc_theme.py;." ^
    --add-data "modules;modules" ^
    --uac-admin ^
    main.py

echo.
if exist "dist\HCCleaner.exe" (
    echo ========================================
    echo  Build concluido com sucesso!
    echo  Executavel: dist\HCCleaner.exe
    echo ========================================
) else (
    echo ERRO: Build falhou!
)
echo.
pause
