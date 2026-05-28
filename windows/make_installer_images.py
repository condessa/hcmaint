"""
Gera as imagens necessárias para o instalador Inno Setup:
- installer_banner.bmp  (164x314 px) — painel esquerdo do wizard
- installer_icon.bmp    (55x55 px)   — ícone pequeno do wizard
- HCsoftware.ico        — ícone da aplicação
"""

import os
from PIL import Image, ImageDraw, ImageFont

IMG_DIR = os.path.join(os.path.dirname(__file__), "imagens")
os.makedirs(IMG_DIR, exist_ok=True)

# ─── Cores HCsoftware ─────────────────────────────────────────────────────────
BG_DARK  = (26,  35,  50)   # #1a2332
ACCENT   = (74, 144, 217)   # #4a90d9
GOLD     = (255, 215,   0)  # #FFD700
TEXT_PRI = (232, 232, 232)  # #e8e8e8
TEXT_MUT = (110, 110, 110)  # #6e6e6e


def make_banner():
    """Banner esquerdo do Inno Setup Wizard (164x314)."""
    w, h = 164, 314
    img = Image.new("RGB", (w, h), BG_DARK)
    d   = ImageDraw.Draw(img)

    # Gradiente simulado — faixas horizontais
    for y in range(h):
        ratio = y / h
        r = int(BG_DARK[0] + (30 - BG_DARK[0]) * ratio)
        g = int(BG_DARK[1] + (45 - BG_DARK[1]) * ratio)
        b = int(BG_DARK[2] + (70 - BG_DARK[2]) * ratio)
        d.line([(0, y), (w, y)], fill=(r, g, b))

    # Linha accent no topo
    d.rectangle([0, 0, w, 4], fill=ACCENT)

    # Ícone central — escudo estilizado
    cx, cy = w // 2, 100
    # Escudo
    shield_pts = [
        (cx, cy - 40),
        (cx + 30, cy - 20),
        (cx + 30, cy + 10),
        (cx, cy + 40),
        (cx - 30, cy + 10),
        (cx - 30, cy - 20),
    ]
    d.polygon(shield_pts, fill=ACCENT, outline=GOLD)
    # Visto no escudo
    d.line([(cx - 12, cy + 5), (cx - 2, cy + 18), (cx + 15, cy - 10)],
           fill=GOLD, width=4)

    # Texto
    try:
        font_title = ImageFont.truetype("arial.ttf", 14)
        font_sub   = ImageFont.truetype("arial.ttf", 9)
        font_ver   = ImageFont.truetype("arial.ttf", 8)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub   = font_title
        font_ver   = font_title

    # HCCleaner
    d.text((cx, cy + 60), "HCCleaner", fill=TEXT_PRI,
           font=font_title, anchor="mm")
    # Subtítulo
    d.text((cx, cy + 80), "Manutenção Windows", fill=ACCENT,
           font=font_sub, anchor="mm")

    # Separador
    d.line([(20, h - 80), (w - 20, h - 80)], fill=TEXT_MUT, width=1)

    # HCsoftware na base
    d.text((cx, h - 60), "HCsoftware", fill=TEXT_MUT,
           font=font_sub, anchor="mm")
    d.text((cx, h - 45), "Silves, Algarve", fill=TEXT_MUT,
           font=font_ver, anchor="mm")
    d.text((cx, h - 30), "© 2026", fill=TEXT_MUT,
           font=font_ver, anchor="mm")

    path = os.path.join(IMG_DIR, "installer_banner.bmp")
    img.save(path, "BMP")
    print(f"Criado: {path}")


def make_icon_bmp():
    """Ícone pequeno do wizard (55x55)."""
    size = 55
    img = Image.new("RGB", (size, size), BG_DARK)
    d   = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    # Escudo pequeno
    pts = [
        (cx, cy - 18),
        (cx + 14, cy - 8),
        (cx + 14, cy + 5),
        (cx, cy + 18),
        (cx - 14, cy + 5),
        (cx - 14, cy - 8),
    ]
    d.polygon(pts, fill=ACCENT, outline=GOLD)
    d.line([(cx - 6, cy + 2), (cx - 1, cy + 9), (cx + 8, cy - 5)],
           fill=GOLD, width=2)

    path = os.path.join(IMG_DIR, "installer_icon.bmp")
    img.save(path, "BMP")
    print(f"Criado: {path}")


def make_ico():
    """Ícone .ico da aplicação (múltiplos tamanhos)."""
    sizes = [16, 32, 48, 64, 128, 256]
    frames = []

    for sz in sizes:
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)

        # Fundo arredondado
        margin = sz // 8
        d.rounded_rectangle(
            [margin, margin, sz - margin, sz - margin],
            radius=sz // 6,
            fill=BG_DARK
        )

        # Escudo
        cx, cy = sz // 2, sz // 2
        scale  = sz / 64
        hw = int(18 * scale)
        hh = int(22 * scale)
        pts = [
            (cx, cy - hh),
            (cx + hw, cy - int(hh * 0.5)),
            (cx + hw, cy + int(hh * 0.3)),
            (cx, cy + hh),
            (cx - hw, cy + int(hh * 0.3)),
            (cx - hw, cy - int(hh * 0.5)),
        ]
        d.polygon(pts, fill=ACCENT)

        # Visto
        lw = max(1, int(2 * scale))
        d.line([
            (cx - int(7 * scale), cy + int(2 * scale)),
            (cx - int(1 * scale), cy + int(9 * scale)),
            (cx + int(9 * scale), cy - int(5 * scale)),
        ], fill=GOLD, width=lw)

        frames.append(img)

    ico_path = os.path.join(IMG_DIR, "HCsoftware.ico")
    frames[0].save(ico_path, format="ICO",
                   sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])
    print(f"Criado: {ico_path}")


if __name__ == "__main__":
    make_banner()
    make_icon_bmp()
    make_ico()
    print("\nTodas as imagens do instalador criadas em ./imagens/")
    print("Agora podes compilar o HCCleaner_Setup.iss com o Inno Setup.")
