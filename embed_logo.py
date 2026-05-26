"""
embed_logo.py — Embute o HCsoftware.png directamente no hc_theme.py como base64.
Corre UMA VEZ no Windows antes de compilar:
    python embed_logo.py

Depois compila normalmente com build.bat.
O logo ficará embutido no .exe sem precisar de ficheiros externos.
"""

import os
import sys
import base64

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path  = os.path.join(script_dir, "imagens", "HCsoftware.png")
    theme_path = os.path.join(script_dir, "hc_theme.py")

    # 1. Verificar que o logo existe
    if not os.path.exists(logo_path):
        print(f"ERRO: Logo não encontrado em '{logo_path}'")
        print("Coloca o ficheiro HCsoftware.png na pasta 'imagens' primeiro.")
        input("Prima Enter para sair...")
        sys.exit(1)

    # 2. Ler e codificar em base64
    with open(logo_path, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    print(f"Logo lido: {len(raw)} bytes → {len(b64)} chars base64")

    # 3. Ler hc_theme.py actual
    with open(theme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 4. Verificar se já tem base64 embutido
    MARKER_START = "# <<<LOGO_BASE64_START>>>"
    MARKER_END   = "# <<<LOGO_BASE64_END>>>"

    new_block = f"""{MARKER_START}
_LOGO_B64 = (
    "{b64}"
)
{MARKER_END}"""

    if MARKER_START in content:
        # Substituir bloco existente
        import re
        content = re.sub(
            rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
            new_block,
            content,
            flags=re.DOTALL
        )
        print("Logo base64 actualizado no hc_theme.py")
    else:
        # Inserir antes da função load_logo
        content = content.replace(
            "def _get_base_dir():",
            new_block + "\n\ndef _get_base_dir():"
        )
        print("Logo base64 inserido no hc_theme.py")

    # 5. Actualizar load_logo para usar base64 primeiro
    NEW_LOAD_LOGO = '''def load_logo(height=28):
    import sys, base64, io
    # Tentar base64 embutido primeiro (funciona sempre, incluindo no .exe)
    if "_LOGO_B64" in globals() and _LOGO_B64:
        try:
            raw   = base64.b64decode(_LOGO_B64)
            img   = Image.open(io.BytesIO(raw)).convert("RGBA")
            ratio = height / img.height
            new_w = max(1, int(img.width * ratio))
            img   = img.resize((new_w, height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            return photo
        except Exception as e:
            print(f"[logo] base64 falhou: {e}")

    # Fallback: ficheiro em disco
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "imagens", "HCsoftware.png"))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "imagens", "HCsoftware.png"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "imagens", "HCsoftware.png"))
    candidates.append(os.path.join(os.getcwd(), "imagens", "HCsoftware.png"))

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            img   = Image.open(path).convert("RGBA")
            ratio = height / img.height
            new_w = max(1, int(img.width * ratio))
            img   = img.resize((new_w, height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            return photo
        except Exception as e:
            print(f"[logo] Falhou {path}: {e}")

    print("[logo] Não foi possível carregar o logo.")
    return None'''

    # Substituir função load_logo existente
    import re
    content = re.sub(
        r"def load_logo\(height=28\):.*?(?=\ndef |\nclass )",
        NEW_LOAD_LOGO + "\n\n",
        content,
        flags=re.DOTALL
    )

    # 6. Gravar
    with open(theme_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ hc_theme.py actualizado com logo embutido!")
    print("   Podes agora correr build.bat para compilar.")
    print("   O logo aparecerá sempre, mesmo sem a pasta 'imagens'.\n")
    input("Prima Enter para sair...")

if __name__ == "__main__":
    main()
