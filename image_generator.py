import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont

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

def draw_rounded_rect(img, xy, radius, fill_color, outline_color, outline_width=3):
    """Disegna un rettangolo traslucido arrotondato."""
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(xy, radius=radius, fill=fill_color, outline=outline_color, width=outline_width)
    return Image.alpha_composite(img, overlay)

def draw_text_center(draw, text, xy, font_size=24, color=(255, 255, 255), bold=False):
    """Disegna un testo centrato rispetto alla coordinata."""
    # Usiamo il font predefinito (per renderlo compatibile ovunque) ma scalato
    try:
        font = ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # Metodo compatibile con versioni vecchie e nuove di Pillow
    try:
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except AttributeError:
        w, h = draw.textsize(text, font=font)
        
    x = xy[0] - (w / 2)
    y = xy[1] - (h / 2) - 5
    draw.text((x, y), text, font=font, fill=color)

async def generate_compare_gui(p1_name, p2_name, stats):
    """Genera l'immagine GUI della sfida."""
    # Sfondo di base grigio scuro (Puoi sostituirlo mettendo un'immagine bg.jpg nel progetto!)
    try:
        base = Image.open("bg.jpg").convert("RGBA").resize((1100, 600))
    except:
        base = Image.new("RGBA", (1100, 600), (35, 39, 42, 255))

    # Colori dei pannelli
    color_p1_fill = (255, 85, 85, 90)   # Rosso traslucido
    color_p1_out = (255, 85, 85, 255)   # Bordo Rosso
    
    color_p2_fill = (85, 85, 255, 90)   # Blu traslucido
    color_p2_out = (85, 170, 255, 255)  # Bordo Blu
    
    color_mid_fill = (50, 50, 50, 150)  # Grigio scuro traslucido
    color_mid_out = (150, 150, 150, 255)

    # 1. Pannello Player 1 (Sinistra)
    base = draw_rounded_rect(base, [(30, 80), (330, 550)], 20, color_p1_fill, color_p1_out)
    
    # 2. Pannello Player 2 (Destra)
    base = draw_rounded_rect(base, [(770, 80), (1070, 550)], 20, color_p2_fill, color_p2_out)

    # 3. Pannelli Statistiche (Centro)
    boxes = [
        {"y": 100, "title": "World Records Attivi", "v1": str(stats['p1_wr']), "v2": str(stats['p2_wr'])},
        {"y": 200, "title": "Scontri Diretti Vinti", "v1": str(stats['p1_wins']), "v2": str(stats['p2_wins'])},
        {"y": 300, "title": "Trofei Tornei", "v1": str(stats['p1_trofei']), "v2": str(stats['p2_trofei'])},
        {"y": 400, "title": "Record Pareggiati", "v1": str(stats['ties']), "v2": str(stats['ties'])},
        {"y": 500, "title": "Dominio Testa a Testa", "v1": f"{stats['p1_perc']}%", "v2": f"{stats['p2_perc']}%"}
    ]
    
    for box in boxes:
        base = draw_rounded_rect(base, [(360, box['y']), (740, box['y'] + 80)], 15, color_mid_fill, color_mid_out)

    # Disegniamo tutti i testi
    draw = ImageDraw.Draw(base)
    
    # Titolo Principale
    draw_text_center(draw, "Stat Comparison · Speed Builders", (550, 40), font_size=32, color=(255, 200, 0), bold=True)
    
    # Nomi e Gradi laterali
    draw_text_center(draw, p1_name, (180, 120), font_size=28, color=(255, 100, 100), bold=True)
    draw_text_center(draw, stats['p1_rank'].replace('@', ''), (180, 520), font_size=22, color=(255, 200, 50))
    
    draw_text_center(draw, p2_name, (920, 120), font_size=28, color=(100, 150, 255), bold=True)
    draw_text_center(draw, stats['p2_rank'].replace('@', ''), (920, 520), font_size=22, color=(255, 200, 50))

    # Testi Statistiche Centrali
    for box in boxes:
        draw_text_center(draw, box['title'], (550, box['y'] + 25), font_size=18, color=(200, 200, 200))
        # Valore P1 (Sinistra box)
        draw_text_center(draw, box['v1'], (430, box['y'] + 55), font_size=28, color=(255, 100, 100), bold=True)
        # Barra divisione
        draw_text_center(draw, "/", (550, box['y'] + 55), font_size=26, color=(100, 100, 100))
        # Valore P2 (Destra box)
        draw_text_center(draw, box['v2'], (670, box['y'] + 55), font_size=28, color=(100, 150, 255), bold=True)

    # Scarica e incolla le skin 3D
    skin1 = await get_player_body(p1_name)
    skin2 = await get_player_body(p2_name)
    
    # Incolla le skin ridimensionate al centro dei rispettivi pannelli laterali
    skin1 = skin1.resize((200, int(200 * skin1.height / skin1.width)))
    skin2 = skin2.resize((200, int(200 * skin2.height / skin2.width)))
    base.paste(skin1, (80, 160), skin1)
    base.paste(skin2, (820, 160), skin2)

    # Salva in RAM e restituisci per Discord
    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
