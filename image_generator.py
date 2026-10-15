import io
import os
import random
import aiohttp
import re
import urllib.request
from PIL import Image, ImageDraw, ImageFont
import config

FONT_BOLD_PATH = "Roboto-Black.ttf"
FONT_REG_PATH = "Roboto-Bold.ttf"

def get_font(size: int, bold: bool = True):
    """Carica un font vero garantito su Linux (Render), Mac o Windows."""
    candidates = [
        FONT_BOLD_PATH if bold else FONT_REG_PATH,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf"
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

    try:
        url = "https://cdn.jsdelivr.net/gh/googlefonts/roboto@main/src/hinted/Roboto-Black.ttf"
        urllib.request.urlretrieve(url, FONT_BOLD_PATH)
        return ImageFont.truetype(FONT_BOLD_PATH, size)
    except Exception:
        return ImageFont.load_default(size=size)

async def get_player_3d_skin(player_name: str):
    """Scarica il render 3D isometrico della skin (con mantello se presente)."""
    clean_name = player_name.replace("\\", "").strip()
    urls = [
        f"https://starlightskins.lunareclipse.studio/render/ultimate/{clean_name}/full",
        f"https://vzge.me/full/512/{clean_name}.png",
        f"https://mc-heads.net/body/{clean_name}/400"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (SpeedBuildersBot/2.0)"}
    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data)).convert("RGBA")
                        bbox = img.getbbox()
                        if bbox:
                            img = img.crop(bbox)
                        return img
            except Exception:
                continue
    return Image.new("RGBA", (200, 350), (0, 0, 0, 0))

def draw_rounded_rect(img, xy, radius, fill_color, outline_color, outline_width=3):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(xy, radius=radius, fill=fill_color, outline=outline_color, width=outline_width)
    return Image.alpha_composite(img, overlay)

def pulisci_grado(grado_grezzo: str) -> str:
    match = re.search(r"<@&(\d+)>", str(grado_grezzo))
    if match:
        role_id = int(match.group(1))
        for name, rid in config.ROLE_IDS.items():
            if rid == role_id:
                return name
    return str(grado_grezzo).replace("@", "").replace("<", "").replace(">", "").replace("&", "").strip()

def draw_centered_text(draw, text, xy, size=22, color=(255, 255, 255), bold=True, shadow=True):
    font = get_font(size, bold=bold)
    text_str = str(text)
    bbox = draw.textbbox((0, 0), text_str, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = xy[0] - w / 2 - bbox[0]
    y = xy[1] - h / 2 - bbox[1]
    if shadow:
        draw.text((x + 2, y + 2), text_str, font=font, fill=(0, 0, 0, 210))
    draw.text((x, y), text_str, font=font, fill=color)

def draw_split_values(draw, v1_str, v2_str, center_xy, size=26, c1=(255, 165, 50), c2=(215, 155, 105)):
    """Disegna 'Valore1 / Valore2' perfettamente centrato sulla barra '/'."""
    font = get_font(size, bold=True)
    slash = " / "
    b1 = draw.textbbox((0, 0), v1_str, font=font)
    bs = draw.textbbox((0, 0), slash, font=font)
    b2 = draw.textbbox((0, 0), v2_str, font=font)

    w1, ws, w2 = b1[2] - b1[0], bs[2] - bs[0], b2[2] - b2[0]
    total_w = w1 + ws + w2
    h = max(b1[3] - b1[1], bs[3] - bs[1], b2[3] - b2[1])

    start_x = center_xy[0] - total_w / 2
    y = center_xy[1] - h / 2 - b1[1]

    draw.text((start_x + 2, y + 2), v1_str, font=font, fill=(0, 0, 0, 210))
    draw.text((start_x + w1 + 2, y + 2), slash, font=font, fill=(0, 0, 0, 210))
    draw.text((start_x + w1 + ws + 2, y + 2), v2_str, font=font, fill=(0, 0, 0, 210))

    draw.text((start_x, y), v1_str, font=font, fill=c1)
    draw.text((start_x + w1, y), slash, font=font, fill=(190, 190, 190))
    draw.text((start_x + w1 + ws, y), v2_str, font=font, fill=c2)

async def generate_compare_gui(p1_name, p2_name, stats):
    W, H = 1200, 640
    sfondi = [f for f in os.listdir() if f.startswith("bg") and f.lower().endswith((".jpg", ".png", ".jpeg"))]
    try:
        if sfondi:
            base = Image.open(random.choice(sfondi)).convert("RGBA").resize((W, H))
            dark_layer = Image.new("RGBA", (W, H), (12, 10, 8, 95))
            base = Image.alpha_composite(base, dark_layer)
        else:
            base = Image.new("RGBA", (W, H), (28, 22, 18, 255))
    except Exception:
        base = Image.new("RGBA", (W, H), (28, 22, 18, 255))

    # --- PALETTE ARANCIO AMBRA (P1) vs MARRONE BRONZO (P2) ---
    p1_fill = (165, 75, 15, 135)       # Arancio scuro traslucido
    p1_border = (255, 150, 40, 255)    # Bordo Arancio Ambra
    p1_text_col = (255, 165, 55)       # Testo Arancio Chiaro

    p2_fill = (95, 55, 30, 145)        # Marrone Caffè/Bronzo traslucido
    p2_border = (195, 135, 85, 255)    # Bordo Bronzo/Perla
    p2_text_col = (225, 170, 120)      # Testo Bronzo Chiaro

    tie_fill = (40, 35, 32, 175)       # Grigio-Marrone neutro per i pareggi
    tie_border = (130, 120, 110, 255)

    # 1. Pannelli Laterali Giocatori
    base = draw_rounded_rect(base, [(25, 75), (275, 605)], 20, p1_fill, p1_border, 3)
    base = draw_rounded_rect(base, [(925, 75), (1175, 605)], 20, p2_fill, p2_border, 3)

    # 2. Scarica e incolla le Skin 3D
    skin1 = await get_player_3d_skin(p1_name)
    skin2 = await get_player_3d_skin(p2_name)

    target_h = 275
    for idx, (skin, box_x1, box_x2) in enumerate([(skin1, 25, 275), (skin2, 925, 1175)]):
        if skin.height > 0:
            ratio = target_h / skin.height
            new_w = min(210, int(skin.width * ratio))
            new_h = int(skin.height * (new_w / skin.width))
            skin_resized = skin.resize((new_w, new_h), Image.Resampling.LANCZOS)
            if idx == 1:
                skin_resized = skin_resized.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            sx = box_x1 + (box_x2 - box_x1 - new_w) // 2
            sy = 180 + (305 - new_h) // 2
            base.paste(skin_resized, (sx, sy), skin_resized)

    # 3. Griglia 2 Colonne x 4 Righe (8 Box grandi, senza Top 3, Build Recorded e Barra Finale)
    grid_items = [
        {"title": "Active WRs",       "v1": stats["p1_wr"],      "v2": stats["p2_wr"],      "fmt": "int"},
        {"title": "Solo WRs",         "v1": stats["p1_solo"],    "v2": stats["p2_solo"],    "fmt": "int"},
        {"title": "Tied WRs",         "v1": stats["p1_tied_wr"], "v2": stats["p2_tied_wr"], "fmt": "int"},
        {"title": "Tourney Trophies", "v1": stats["p1_trofei"],  "v2": stats["p2_trofei"],  "fmt": "int"},
        {"title": "H2H Wins",         "v1": stats["p1_wins"],    "v2": stats["p2_wins"],    "fmt": "int"},
        {"title": "H2H Dominance",    "v1": stats["p1_perc"],    "v2": stats["p2_perc"],    "fmt": "perc"},
        {"title": "Fastest Record",   "v1": stats["p1_fast"],    "v2": stats["p2_fast"],    "fmt": "time"},
        {"title": "Avg Best Time",    "v1": stats["p1_avg"],     "v2": stats["p2_avg"],     "fmt": "time"},
    ]

    start_x, start_y = 295, 75
    box_w, box_h = 295, 121
    gap_x, gap_y = 20, 15

    box_renders = []
    for i, item in enumerate(grid_items):
        row, col = divmod(i, 2)
        x1 = start_x + col * (box_w + gap_x)
        y1 = start_y + row * (box_h + gap_y)
        x2, y2 = x1 + box_w, y1 + box_h

        v1, v2 = item["v1"], item["v2"]
        winner = 0
        diff_str = "PARI"

        if item["fmt"] == "time":
            if v1 > 0 and v2 > 0:
                if v1 < v2:
                    winner = 1
                    diff_str = f"-{round(v2 - v1, 2)}s"
                elif v2 < v1:
                    winner = 2
                    diff_str = f"-{round(v1 - v2, 2)}s"
            elif v1 > 0:
                winner = 1
                diff_str = f"{v1}s"
            elif v2 > 0:
                winner = 2
                diff_str = f"{v2}s"
            v1_str = f"{v1}s" if v1 > 0 else "N/A"
            v2_str = f"{v2}s" if v2 > 0 else "N/A"
        else:
            if v1 > v2:
                winner = 1
                diff_val = v1 - v2
                diff_str = f"+{diff_val}%" if item["fmt"] == "perc" else f"+{diff_val}"
            elif v2 > v1:
                winner = 2
                diff_val = v2 - v1
                diff_str = f"+{diff_val}%" if item["fmt"] == "perc" else f"+{diff_val}"
            v1_str = f"{v1}%" if item["fmt"] == "perc" else str(v1)
            v2_str = f"{v2}%" if item["fmt"] == "perc" else str(v2)

        if winner == 1:
            bfill, bborder, dcol = p1_fill, p1_border, p1_text_col
        elif winner == 2:
            bfill, bborder, dcol = p2_fill, p2_border, p2_text_col
        else:
            bfill, bborder, dcol = tie_fill, tie_border, (180, 180, 180)

        base = draw_rounded_rect(base, [(x1, y1), (x2, y2)], 16, bfill, bborder, 3)
        box_renders.append((x1, y1, x2, y2, item["title"], v1_str, v2_str, diff_str, dcol))

    # 4. Disegno di tutti i Testi
    draw = ImageDraw.Draw(base)

    # Titolo in alto
    draw_centered_text(draw, "Stat Comparison · Speed Builders", (W // 2, 35), size=32, color=(255, 200, 70), bold=True)

    # Nomi Player nei box laterali
    s_p1 = 26 if len(p1_name) <= 12 else 21
    s_p2 = 26 if len(p2_name) <= 12 else 21
    draw_centered_text(draw, p1_name, (150, 115), size=s_p1, color=p1_text_col, bold=True)
    draw_centered_text(draw, p2_name, (1050, 115), size=s_p2, color=p2_text_col, bold=True)

    # Ruoli / Gradi in basso sotto le skin
    rank1_clean = pulisci_grado(stats["p1_rank"])
    rank2_clean = pulisci_grado(stats["p2_rank"])
    draw_centered_text(draw, rank1_clean, (150, 530), size=22, color=(255, 215, 0), bold=True)
    draw_centered_text(draw, f"({stats['p1_wr']} WRs)", (150, 565), size=17, color=(220, 220, 220), bold=False)

    draw_centered_text(draw, rank2_clean, (1050, 530), size=22, color=(255, 215, 0), bold=True)
    draw_centered_text(draw, f"({stats['p2_wr']} WRs)", (1050, 565), size=17, color=(220, 220, 220), bold=False)

    # Testi dentro gli 8 Box Centrali
    for (x1, y1, x2, y2, title, v1_str, v2_str, diff_str, dcol) in box_renders:
        cx = (x1 + x2) // 2
        draw_centered_text(draw, title, (cx, y1 + 26), size=19, color=(235, 235, 235), bold=False)
        draw_split_values(draw, v1_str, v2_str, (cx, y1 + 63), size=27, c1=p1_text_col, c2=p2_text_col)
        draw_centered_text(draw, diff_str, (cx, y1 + 98), size=18, color=dcol, bold=True)

    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
