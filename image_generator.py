import io
import os
import random
import aiohttp
import re
import urllib.request
from PIL import Image, ImageDraw, ImageFont
import config

# --- SCARICA UN FONT PROFESSIONALE SE MANCA SUL SERVER (RENDER) ---
FONT_PATH = "Montserrat-Black.ttf"
def ensure_font():
    if not os.path.exists(FONT_PATH):
        try:
            # Scarica un font spesso, moderno e leggibilissimo
            url = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Black.ttf"
            urllib.request.urlretrieve(url, FONT_PATH)
        except Exception as e:
            print(f"Errore download font: {e}")

async def get_player_body(player_name: str):
    """Scarica il render 3D del corpo del giocatore da Minotar."""
    url = f"https://minotar.net/armor/body/{player_name}/300.png"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")
    # Immagine vuota se non trova la skin
    return Image.new("RGBA", (300, 300), (0, 0, 0, 0))

def draw_rounded_rect(img, xy, radius, fill_color, outline_color, outline_width=4):
    """Disegna un rettangolo traslucido arrotondato."""
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(xy, radius=radius, fill=fill_color, outline=outline_color, width=outline_width)
    return Image.alpha_composite(img, overlay)

def pulisci_grado(grado_grezzo: str) -> str:
    """Traduce l'ID del ruolo Discord nel nome reale leggendo il config."""
    match = re.search(r'<@&(\d+)>', grado_grezzo)
    if match:
        role_id = int(match.group(1))
        for name, rid in config.ROLE_IDS.items():
            if rid == role_id:
                return name.upper()
    return grado_grezzo.replace("@", "").replace("<", "").replace(">", "").replace("&", "").strip().upper()

def draw_text_with_shadow(draw, text, xy, font_size=24, color=(255, 255, 255), outline_color=(0, 0, 0)):
    """Disegna un testo spesso con un contorno/ombra scura spessa per far risaltare tutto."""
    ensure_font()
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        font = ImageFont.load_default()
    
    try:
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except AttributeError:
        w, h = draw.textsize(text, font=font)
        
    x = xy[0] - (w / 2)
    y = xy[1] - (h / 2) - (font_size / 4)
    
    # Bordo spesso (Outline)
    o = 2
    draw.text((x-o, y-o), text, font=font, fill=outline_color)
    draw.text((x+o, y-o), text, font=font, fill=outline_color)
    draw.text((x-o, y+o), text, font=font, fill=outline_color)
    draw.text((x+o, y+o), text, font=font, fill=outline_color)
    # Ombra inferiore
    draw.text((x, y+o+1), text, font=font, fill=outline_color)
    
    # Testo centrale colorato
    draw.text((x, y), text, font=font, fill=color)

async def generate_compare_gui(p1_name, p2_name, stats):
    """Genera l'immagine GUI della sfida con lo stile del mockup."""
    sfondi_disponibili = [f for f in os.listdir() if f.startswith("bg") and f.lower().endswith((".jpg", ".png", ".jpeg"))]
    try:
        if sfondi_disponibili:
            sfondo_scelto = random.choice(sfondi_disponibili)
            base = Image.open(sfondo_scelto).convert("RGBA").resize((1100, 600))
        else:
            base = Image.new("RGBA", (1100, 600), (40, 40, 40, 255))
    except:
        base = Image.new("RGBA", (1100, 600), (40, 40, 40, 255))

    # --- COLORI FEDELI AL TUO MOCKUP ---
    color_p1_fill = (180, 0, 0, 110)     # Rosso Traslucido
    color_p1_out = (255, 60, 60, 255)    # Bordo Rosso Vivo
    
    color_p2_fill = (0, 70, 180, 110)    # Blu Traslucido
    color_p2_out = (80, 180, 255, 255)   # Bordo Azzurro
    
    color_mid_fill = (25, 27, 30, 220)   # Grigio scurissimo
    color_mid_out = (120, 130, 140, 255) # Bordo grigio

    # 1. Box laterali dei Player
    base = draw_rounded_rect(base, [(30, 90), (310, 570)], 20, color_p1_fill, color_p1_out, outline_width=4)
    base = draw_rounded_rect(base, [(790, 90), (1070, 570)], 20, color_p2_fill, color_p2_out, outline_width=4)

    # 2. Box Centrali
    boxes = [
        {"y": 100, "title": "World Records Attivi", "v1": str(stats['p1_wr']), "v2": str(stats['p2_wr'])},
        {"y": 190, "title": "Scontri Diretti Vinti", "v1": str(stats['p1_wins']), "v2": str(stats['p2_wins'])},
        {"y": 280, "title": "Trofei Tornei", "v1": str(stats['p1_trofei']), "v2": str(stats['p2_trofei'])},
        {"y": 370, "title": "Record Pareggiati", "v1": str(stats['ties']), "v2": str(stats['ties'])},
        {"y": 460, "title": "Dominio Testa a Testa", "v1": f"{stats['p1_perc']}%", "v2": f"{stats['p2_perc']}%"}
    ]
    
    for box in boxes:
        base = draw_rounded_rect(base, [(340, box['y']), (760, box['y'] + 80)], 20, color_mid_fill, color_mid_out, outline_width=3)

    draw = ImageDraw.Draw(base)
    
    # Titolo Principale in Giallo/Oro Acceso
    draw_text_with_shadow(draw, "STAT COMPARISON • SPEED BUILDERS", (550, 45), font_size=38, color=(255, 220, 50))
    
    # --- TESTI PLAYER 1 (SINISTRA) ---
    draw_text_with_shadow(draw, p1_name, (170, 130), font_size=38, color=(255, 60, 60))
    grado_p1 = pulisci_grado(stats['p1_rank'])
    draw_text_with_shadow(draw, f"RANK: {grado_p1}", (170, 175), font_size=20, color=(240, 240, 240))
    
    # --- TESTI PLAYER 2 (DESTRA) ---
    draw_text_with_shadow(draw, p2_name, (930, 130), font_size=38, color=(80, 180, 255))
    grado_p2 = pulisci_grado(stats['p2_rank'])
    draw_text_with_shadow(draw, f"RANK: {grado_p2}", (930, 175), font_size=20, color=(240, 240, 240))

    # --- TESTI CENTRALI ---
    for box in boxes:
        draw_text_with_shadow(draw, box['title'], (550, box['y'] + 22), font_size=24, color=(255, 255, 255))
        draw_text_with_shadow(draw, box['v1'], (420, box['y'] + 56), font_size=34, color=(255, 60, 60))
        draw_text_with_shadow(draw, "/", (550, box['y'] + 56), font_size=28, color=(200, 200, 200))
        draw_text_with_shadow(draw, box['v2'], (680, box['y'] + 56), font_size=34, color=(80, 180, 255))

    # --- INSERIMENTO SKIN 3D ---
    skin1 = await get_player_body(p1_name)
    skin2 = await get_player_body(p2_name)
    
    largh_max = 200
    s1_w = largh_max
    s1_h = int((largh_max / skin1.width) * skin1.height)
    skin1 = skin1.resize((s1_w, s1_h))

    s2_w = largh_max
    s2_h = int((largh_max / skin2.width) * skin2.height)
    skin2 = skin2.resize((s2_w, s2_h))

    # Ancoriamo le skin esattamente in basso nei loro box
    p1_x = int(30 + (280 - s1_w) / 2)
    p1_y = 560 - s1_h  

    p2_x = int(790 + (280 - s2_w) / 2)
    p2_y = 560 - s2_h

    # Applica un'ombra dietro le skin per farle risaltare
    ombra1 = Image.new("RGBA", skin1.size, (0, 0, 0, 150))
    ombra2 = Image.new("RGBA", skin2.size, (0, 0, 0, 150))
    base.paste(ombra1, (p1_x + 5, p1_y + 5), skin1)
    base.paste(ombra2, (p2_x + 5, p2_y + 5), skin2)

    # Incolla le skin reali
    base.paste(skin1, (p1_x, p1_y), skin1)
    base.paste(skin2, (p2_x, p2_y), skin2)

    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
