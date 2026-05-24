#!/bin/bash
# HCMaint - Instalação e Arranque (Debian/Ubuntu)
# HCsoftware

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   HCMaint — Manutenção Linux         ║"
echo "║   HCsoftware                         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Verificar tkinter
python3 -c "import tkinter" 2>/dev/null || {
    echo "[!] tkinter não encontrado. A instalar..."
    sudo apt-get install -y python3-tk
}

# Instalar Pillow com uv (preferencial) ou pip
if command -v uv &>/dev/null; then
    echo "[*] A instalar dependências com uv..."
    uv pip install Pillow --system 2>/dev/null || \
    uv pip install Pillow 2>/dev/null || \
    pip3 install Pillow --break-system-packages -q
else
    echo "[*] A instalar dependências com pip..."
    pip3 install Pillow --break-system-packages -q
fi

echo "[*] A iniciar HCMaint..."
echo ""

# Correr com sudo se solicitado
if [ "$1" = "--sudo" ]; then
    sudo python3 "$SCRIPT_DIR/main.py"
else
    python3 "$SCRIPT_DIR/main.py"
fi
