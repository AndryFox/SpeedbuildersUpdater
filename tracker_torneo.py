import os
import time
import re
import platform
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# ⚙️ CONFIGURAZIONE DEL MATCH
# ==========================================
FASE_TORNEO = "Round of 8" # Sostituiscilo con Elimination Round 4, Quarter Finals, ecc.
PLAYER_1 = "mistsv"
PLAYER_2 = "vino123"

WEBHOOK_URL = os.environ.get('TOURNEY_WEBHOOK_URL')

if platform.system() == "Windows":
    LOG_FILE = r"C:\Users\liron\.lunarclient\profiles\vanilla-1.21\logs\latest.log"
else:
    LOG_FILE = r"/Users/andrea/.lunarclient/profiles/1.21/logs/latest.log"

# ==========================================
# 🔍 ESPRESSIONI REGOLARI (Regex)
# ==========================================
REGEX_PERFETTA = re.compile(r"\[CHAT\]\s+(?:\[\d{1,2}:\d{2}:\d{2}\s[AP]M\]\s+)?([a-zA-Z0-9_]+) ha fatto una costruzione perfetta in ([0-9.]+) Secondi!")
REGEX_MANUALE = re.compile(r"\[CHAT\]\s+(?:\[\d{1,2}:\d{2}:\d{2}\s[AP]M\]\s+)?([a-zA-Z0-9_]+)\s*»\s*.*?(?:!p\s*([0-9]+)|([0-9]+)\s*%)")
# Nuova Regex per capire quando finisce la partita intera
REGEX_FINE_GAME = re.compile(r"\[CHAT\]\s+(?:\[\d{1,2}:\d{2}:\d{2}\s[AP]M\]\s+)?\s*1st Posto - ([a-zA-Z0-9_]+)")

# Variabili di stato
match_data = {
    "giocatori": [PLAYER_1.lower(), PLAYER_2.lower()],
    "vittorie": {PLAYER_1.lower(): 0, PLAYER_2.lower(): 0},
    "ultima_prestazione": {}, # Ricorda solo l'ultima percentuale/tempo del giocatore
    "storia_games": [] # Salva il riepilogo di Game 1, Game 2, ecc.
}

def annuncia_vittoria_discord(vincitore, score_vincitore, perdente, score_perdente):
    if not WEBHOOK_URL:
        print("\n⚠️ Errore: TOURNEY_WEBHOOK_URL non trovato. Controlla il file .env!")
        return

    # Costruiamo il riepilogo di tutti i Game
    testo_storia = ""
    for i, game in enumerate(match_data["storia_games"]):
        testo_storia += f"\n**Game {i+1}**\n"
        testo_storia += f"🟢 **Winner:** `{game['w_name']}` {game['w_stat']}\n"
        testo_storia += f"🔴 **Loser:** `{game['l_name']}` {game['l_stat']}\n"

    p1 = match_data['giocatori'][0]
    p2 = match_data['giocatori'][1]
    
    # Formattazione esattamente come da tua richiesta
    contenuto_discord = f"""# 🏆 {FASE_TORNEO}: {p1.upper()} VS {p2.upper()}
**The winner is {vincitore} defeated his opponent {perdente} by {score_vincitore} to {score_perdente}**
━━━━━━━━━━━━━━━━━━━━━━━━━━{testo_storia}"""

    messaggio = {"content": contenuto_discord}
    data = json.dumps(messaggio).encode('utf-8')
    req = urllib.request.Request(WEBHOOK_URL, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        urllib.request.urlopen(req)
        print(f"\n✅ Risultato inviato con successo su Discord!")
    except Exception as e:
        print(f"\n⚠️ Errore invio Webhook: {e}")

def formatta_statistica(dati):
    """Formatta la frase del tempo o della percentuale."""
    if not dati:
        return "with an unknown score"
    if dati['perc'] == 100:
        return f"finishing the game completing the build with a time of {dati['tempo']}s"
    else:
        return f"finishing the game with {dati['perc']}% of the build"

def registra_fine_game(vincitore_game):
    """Viene chiamata quando in chat esce '1st Posto'."""
    perdente_game = PLAYER_1.lower() if vincitore_game == PLAYER_2.lower() else PLAYER_2.lower()
    
    # Salviamo i dati per Discord
    stat_vincitore = formatta_statistica(match_data["ultima_prestazione"].get(vincitore_game))
    stat_perdente = formatta_statistica(match_data["ultima_prestazione"].get(perdente_game))
    
    match_data["storia_games"].append({
        "w_name": vincitore_game.upper(),
        "w_stat": stat_vincitore,
        "l_name": perdente_game.upper(),
        "l_stat": stat_perdente
    })
    
    # Aggiungi il punto
    match_data["vittorie"][vincitore_game] += 1
    print(f"\n🎮 GAME CONCLUSO! Vinto da {vincitore_game.upper()}")
    print(f"Punteggio attuale Bo3: {PLAYER_1} [{match_data['vittorie'][PLAYER_1.lower()]}] - {PLAYER_2} [{match_data['vittorie'][PLAYER_2.lower()]}]")
    
    # Puliamo le prestazioni per il Game successivo
    match_data["ultima_prestazione"].clear()

    # Controllo se qualcuno ha vinto il torneo (2 vittorie)
    if match_data["vittorie"][vincitore_game] == 2:
        print(f"\n🎉 {vincitore_game.upper()} HA VINTO IL MATCH!")
        annuncia_vittoria_discord(
            vincitore_game.upper(), match_data["vittorie"][vincitore_game], 
            perdente_game.upper(), match_data["vittorie"][perdente_game]
        )

def processa_riga(riga):
    global match_data
    
    # 1. Traccia i tempi perfetti in background
    match_perfetto = REGEX_PERFETTA.search(riga)
    if match_perfetto:
        player = match_perfetto.group(1).lower()
        tempo = float(match_perfetto.group(2))
        if player in match_data["giocatori"]:
            match_data["ultima_prestazione"][player] = {"perc": 100, "tempo": tempo}
            print(f"[{player}] 100% in {tempo}s")

    # 2. Traccia le percentuali manuali in background
    match_manuale = REGEX_MANUALE.search(riga)
    if match_manuale:
        player = match_manuale.group(1).lower()
        perc = int(match_manuale.group(2) or match_manuale.group(3))
        if player in match_data["giocatori"]:
            match_data["ultima_prestazione"][player] = {"perc": perc}
            print(f"[{player}] Parziale {perc}%")

    # 3. SENSORE FINE GAME (1st Posto)
    match_vittoria = REGEX_FINE_GAME.search(riga)
    if match_vittoria:
        vincitore_game = match_vittoria.group(1).lower()
        # Se il vincitore fa parte della nostra sfida, registriamo il Game
        if vincitore_game in match_data["giocatori"]:
            registra_fine_game(vincitore_game)

def segui_log():
    if not os.path.exists(LOG_FILE):
        print(f"❌ Impossibile trovare il file di log: {LOG_FILE}")
        return

    print(f"🚀 Tracker Avviato! (Modalità Bo3)\nIn attesa dei risultati di {PLAYER_1} e {PLAYER_2}...")
    
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        f.seek(0, os.SEEK_END)
        
        while True:
            riga = f.readline()
            if not riga:
                time.sleep(0.1)
                continue
            processa_riga(riga)

if __name__ == "__main__":
    segui_log()