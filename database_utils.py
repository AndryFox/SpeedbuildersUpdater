import re
import config
import aiosqlite

def get_main_name(name):
    n = name.lower().strip()
    return config.ALIASES.get(n, n)

async def get_wr_count(bot, player_name):
    """
    Interroga il database per contare quanti primi posti (WR) possiede un giocatore.
    Manteniamo 'bot' come parametro per non rompere il codice esistente in altri file,
    anche se ora usiamo direttamente aiosqlite.
    """
    async with aiosqlite.connect("speedbuilders.db") as db:
        query = """
            SELECT COUNT(*) 
            FROM WorldRecords r1
            WHERE player_name = ? COLLATE NOCASE
            AND time = (SELECT MIN(time) FROM WorldRecords r2 WHERE r1.build_name = r2.build_name)
        """
        async with db.execute(query, (player_name,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0
    channel = bot.get_channel(config.RANKINGS_CHANNEL_ID)
    if not channel:
        return 0
        
    p_lower = player_name.lower().strip()
    
    async for message in channel.history(limit=50):
        if not message.content:
            continue
            
        lines = message.content.split('\n')
        for line in lines:
            line_lower = line.lower()
            
            if ":" in line_lower and "wr" in line_lower:
                # Usa rsplit per dividere la frase all'ULTIMO due punti (ignora le emoji :first_place:)
                parts = line_lower.rsplit(":", 1)
                
                if len(parts) < 2:
                    continue
                    
                left_part = parts[0]
                right_part = parts[1]
                
                left_clean = left_part.replace("*", "").replace("_", "").replace("~", "").replace("#", "")
                words = left_clean.replace("/", " ").split()
                
                if p_lower in words:
                    import re
                    match = re.search(r'(\d+)\s*wr', right_part)
                    if match:
                        return int(match.group(1))
    return 0

async def get_wr_rounds_info(bot):
    channel = bot.get_channel(config.RANKINGS_CHANNEL_ID)
    if not channel:
        return 0, "Sconosciuto"

    async for message in channel.history(limit=50):
        if not message.content:
            continue

        lines = message.content.split('\n')
        for i, line in enumerate(lines):
            if ":first_place:" in line and "Rounds" in line:
                match = re.search(r'(\d+)\s*Rounds', line, re.IGNORECASE)
                old_rounds = int(match.group(1)) if match else 0

                old_holders = []
                for j in range(i+1, min(i+10, len(lines))):
                    if ":second_place:" in lines[j] or ":third_place:" in lines[j]:
                        break
                    if "|" in lines[j] and "[" in lines[j] and "]" in lines[j]:
                        holder_match = re.search(r'\[(.*?)\]', lines[j])
                        if holder_match:
                            old_holders.append(holder_match.group(1).replace("&amp;", "&").strip())

                holders_str = " / ".join(old_holders) if old_holders else "Sconosciuto"
                return old_rounds, holders_str
    return 0, "Sconosciuto"

async def get_sim_wr_link(bot, build_name):
    channel = bot.get_channel(config.SIM_WR_CHANNEL_ID)
    if not channel:
        return None
        
    build_clean = build_name.lower().strip()
    
    async for message in channel.history(limit=500):
        if not message.content:
            continue
            
        lines = message.content.split('\n')
        for line in lines:
            clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").strip()
            
            if clean_line.startswith(f"{build_clean}:") or clean_line.startswith(f"{build_clean} :"):
                return message.jump_url
                
    return None

async def get_top_players(limit=15):
    """
    Calcola la classifica generale leggendo direttamente chi detiene i primi posti.
    Restituisce una lista di tuple: [('Giocatore1', 10), ('Giocatore2', 8), ...]
    """
    async with aiosqlite.connect("speedbuilders.db") as db:
        query = """
            SELECT player_name, COUNT(*) as wr_count 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE r1.build_name = r2.build_name)
            GROUP BY player_name COLLATE NOCASE
            ORDER BY wr_count DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cursor:
            # fetchall() restituisce tutti i risultati in un colpo solo
            return await cursor.fetchall()

async def generate_build_message(build_name: str) -> str:
    """
    Genera il testo formattato per il canale dei record (1°, 2° e 3° posto) 
    leggendo dal database SQLite, mantenendo i decimali ed effettuando
    l'escaping del Markdown di Discord per nomi speciali (es. _Ilusion_).
    """
    import aiosqlite # Assicurati che l'import sia globale o nel file
    
    async with aiosqlite.connect("speedbuilders.db") as db:
        query = """
            SELECT player_name, MIN(time) as time 
            FROM WorldRecords 
            WHERE build_name = ? COLLATE NOCASE 
            GROUP BY player_name COLLATE NOCASE 
            ORDER BY time ASC
        """
        async with db.execute(query, (build_name,)) as cursor:
            rows = await cursor.fetchall()
            
    tempi_raggruppati = {}
    for player, time_val in rows:
        # FASE DI SANIFICAZIONE: Inserisce un backslash prima di ogni underscore
        # per forzare Discord a trattarlo come testo normale e non come corsivo.
        safe_player = player.replace("_", "\\_")
        
        if time_val not in tempi_raggruppati:
            tempi_raggruppati[time_val] = []
        tempi_raggruppati[time_val].append(safe_player)
        
    tempi_ordinati = sorted(tempi_raggruppati.keys())
    
    testo = f"Build: {build_name}\n"
    
    # --- PRIMO POSTO ---
    if len(tempi_ordinati) > 0:
        t1 = tempi_ordinati[0]
        p1 = "/".join(tempi_raggruppati[t1])
        testo += f"> :first_place: - **__{p1} {t1}__**\n"
    else:
        testo += "> :first_place: - \n"
        
    # --- SECONDO POSTO ---
    if len(tempi_ordinati) > 1:
        t2 = tempi_ordinati[1]
        p2 = "/".join(tempi_raggruppati[t2])
        testo += f"> :second_place: - {p2} {t2}\n"
    else:
        testo += "> :second_place: - \n"
        
    # --- TERZO POSTO ---
    if len(tempi_ordinati) > 2:
        t3 = tempi_ordinati[2]
        p3 = "/".join(tempi_raggruppati[t3])
        testo += f"> :third_place: - {p3} {t3}"
    else:
        testo += "> :third_place: - "
        
    return testo
