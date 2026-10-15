import io
import os
import random
import aiohttp
import re
from PIL import Image, ImageDraw, ImageFont

async def get_player_body(player_name: str):
    """Scarica il render 3D del corpo del giocatore da Minotar."""
    url = f"https://minotar.net/armor/body/{player_name}/300.png"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")
    # Immagine vuota di fallback
    return Image.new("RGBA", (300, 300), (0, 0, 0, 0))

def draw_rounded_rect(img, xy, radius, fill_color, outline_color, outline_width=4):
    """Disegna un rettangolo traslucido arrotondato."""
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(xy, radius=radius, fill=fill_color, outline=outline_color, width=outline_width)
    return Image.alpha_composite(img, overlay)

def pulisci_grado(grado_grezzo: str) -> str:
    """Trasforma un tag ruolo di Discord <&id> o @ruolo nel nome del grado visibile (es. Expert)."""
    # Se contiene un tag Discord del tipo <@&123456789>, rimuovilo
    match = re.search(r'<@&(\d+)>', grado_grezzo)
    if match:
        # Se è un tag ruolo di cui non sappiamo il nome, usiamo un fallback generico
        # o cerchiamo di estrarlo dalle impostazioni se presenti, altrimenti mostriamo l'estetica.
        # Fallback nel caso in cui config o il bot non trovi il nome
        return "GIOCATORE"
    return grado_grezzo.replace("@", "").replace("<", "").replace(">", "").replace("&", "").strip().upper()

def draw_text_with_shadow(draw, text, xy, font_size=24, color=(255, 255, 255), bold=False, shadow_offset=2):
    """Disegna un testo con un'ombra marcata per la massima leggibilità."""
    try:
        font = ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # Calcolo ingombro testo
    try:
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except AttributeError:
        w, h = draw.textsize(text, font=font)
        
    x = xy[0] - (w / 2)
    y = xy[1] - (h / 2) - 5
    
    # Disegna ombra scura
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 230))
    # Disegna testo in primo piano
    draw.text((x, y), text, font=font, fill=color)

async def generate_compare_gui(p1_name, p2_name, stats):
    """Genera l'immagine GUI della sfida."""
    # Cerca in automatico tutti i file "bg" disponibili
    sfondi_disponibili = [f for f in os.listdir() if f.startswith("bg") and f.lower().endswith((".jpg", ".png", ".jpeg"))]
    
    try:
        if sfondi_disponibili:
            sfondo_scelto = random.choice(sfondi_disponibili)
            base = Image.open(sfondo_scelto).convert("RGBA").resize((1100, 600))
        else:
            base = Image.new("RGBA", (1100, 600), (30, 30, 30, 255))
    except:
        base = Image.new("RGBA", (1100, 600), (30, 30, 30, 255))

    # Definizione colori più intensi e visibili
    color_p1_fill = (220, 20, 20, 100)   # Rosso vivo traslucido
    color_p1_out = (255, 60, 60, 255)    # Bordo Rosso Acceso
    
    color_p2_fill = (20, 20, 220, 100)   # Blu vivo traslucido
    color_p2_out = (60, 150, 255, 255)   # Bordo Blu/Azzurro Acceso
    
    # Box centrali molto più oscurati e contrastati
    color_mid_fill = (15, 15, 15, 210)   # Grigio fumo quasi nero
    color_mid_out = (100, 100, 100, 255) # Bordo grigio chiaro

    # 1. Disegna i box di contenimento
    base = draw_rounded_rect(base, [(30, 80), (310, 550)], 25, color_p1_fill, color_p1_out)
    base = draw_rounded_rect(base, [(790, 80), (1070, 550)], 25, color_p2_fill, color_p2_out)

    boxes = [
        {"y": 100, "title": "World Records Attivi", "v1": str(stats['p1_wr']), "v2": str(stats['p2_wr'])},
        {"y": 190, "title": "Scontri Diretti Vinti", "v1": str(stats['p1_wins']), "v2": str(stats['p2_wins'])},
        {"y": 280, "title": "Trofei Tornei", "v1": str(stats['p1_trofei']), "v2": str(stats['p2_trofei'])},
        {"y": 370, "title": "Record Pareggiati", "v1": str(stats['ties']), "v2": str(stats['ties'])},
        {"y": 460, "title": "Dominio Testa a Testa", "v1": f"{stats['p1_perc']}%", "v2": f"{stats['p2_perc']}%"}
    ]
    
    for box in boxes:
        base = draw_rounded_rect(base, [(350, box['y']), (750, box['y'] + 75)], 15, color_mid_fill, color_mid_out)

    draw = ImageDraw.Draw(base)
    
    # Titolo Principale in Giallo/Oro Acceso, enorme
    draw_text_with_shadow(draw, "STAT COMPARISON · SPEED BUILDERS", (550, 40), font_size=34, color=(255, 215, 0), bold=True)
    
    # 2. Informazioni Player Sinistro (P1)
    draw_text_with_shadow(draw, p1_name, (170, 125), font_size=32, color=(255, 100, 100), bold=True)
    grado_p1 = pulisci_grado(stats['p1_rank'])
    draw_text_with_shadow(draw, grado_p1, (170, 510), font_size=20, color=(255, 200, 50), bold=True)
    
    # 3. Informazioni Player Destro (P2)
    draw_text_with_shadow(draw, p2_name, (930, 125), font_size=32, color=(100, 180, 255), bold=True)
    grado_p2 = pulisci_grado(stats['p2_rank'])
    draw_text_with_shadow(draw, grado_p2, (930, 510), font_size=20, color=(255, 200, 50), bold=True)

    # 4. Inserimento Scritte e Numeri centrali
    for box in boxes:
        # Titolo della Statistica
        draw_text_with_shadow(draw, box['title'], (550, box['y'] + 22), font_size=18, color=(240, 240, 240), bold=True)
        # Valore Player 1 (Rosso Vivo)
        draw_text_with_shadow(draw, box['v1'], (440, box['y'] + 50), font_size=26, color=(255, 60, 60), bold=True)
        # Separatore "/"
        draw_text_with_shadow(draw, "/", (550, box['y'] + 50), font_size=24, color=(140, 140, 140))
        # Valore Player 2 (Azzurro/Blu Vivissimo)
        draw_text_with_shadow(draw, box['v2'], (660, box['y'] + 50), font_size=26, color=(60, 170, 255), bold=True)

    # 5. Gestione delle Skin Centrate
    skin1 = await get_player_body(p1_name)
    skin2 = await get_player_body(p2_name)
    
    # Ridimensionamento compatto della skin per inquadrarla nel pannello senza tagli
    largh_max = 160
    s1_w = largh_max
    s1_h = int((largh_max / skin1.width) * skin1.height)
    skin1 = skin1.resize((s1_w, s1_h))

    s2_w = largh_max
    s2_h = int((largh_max / skin2.width) * skin2.height)
    skin2 = skin2.resize((s2_w, s2_h))

    # Calcolo dei punti di incollatura al millimetro per posizionare la skin in perfetto centro d'area
    area_sinistra = (30, 150, 310, 480) # x1, y1, x2, y2
    area_destra = (790, 150, 1070, 480)

    p1_x = int(area_sinistra[0] + (area_sinistra[2] - area_sinistra[0] - s1_w) / 2)
    p1_y = int(area_sinistra[1] + (area_sinistra[3] - area_sinistra[1] - s1_h) / 2)

    p2_x = int(area_destra[0] + (area_destra[2] - area_destra[0] - s2_w) / 2)
    p2_y = int(area_destra[1] + (area_destra[3] - area_destra[1] - s2_h) / 2)

    # Incolla le skin in trasparenza
    base.paste(skin1, (p1_x, p1_y), skin1)
    base.paste(skin2, (p2_x, p2_y), skin2)

    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
