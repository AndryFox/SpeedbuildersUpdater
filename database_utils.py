import re
import config
import asyncpg

def get_main_name(name):
    n = name.lower().strip()
    return config.ALIASES.get(n, n)

async def get_wr_count(bot, player_name):
    """
    Interroga il database in cloud per contare quanti primi posti (WR) possiede un giocatore.
    """
    target_name = get_main_name(player_name)
    count = 0
    
    # 1. Apriamo la connessione con Supabase
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        query = """
            SELECT player_name 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
        """
        # 2. asyncpg usa 'fetch' invece di 'execute' + 'fetchall'
        rows = await conn.fetch(query)
        
        for row in rows:
            # In asyncpg i risultati funzionano come i dizionari
            if get_main_name(row['player_name']) == target_name:
                count += 1
    finally:
        # 3. Chiudiamo sempre la connessione alla fine!
        await conn.close()
                    
    return count

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
    """
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        # Il limit ora usa $1
        query = """
            SELECT player_name, COUNT(*) as wr_count 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
            GROUP BY LOWER(player_name), player_name
            ORDER BY wr_count DESC
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
        # Convertiamo i risultati nel formato originale per non rompere il resto del codice
        return [(r['player_name'], r['wr_count']) for r in rows]
    finally:
        await conn.close()

async def generate_build_message(build_name: str) -> str:
    """
    Genera il testo formattato per il canale dei record leggendo da Supabase.
    """
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        query = """
            SELECT player_name, MIN(time) as time 
            FROM WorldRecords 
            WHERE LOWER(build_name) = LOWER($1)
            GROUP BY LOWER(player_name), player_name 
            ORDER BY time ASC
        """
        rows = await conn.fetch(query, build_name)
    finally:
        await conn.close()
        
    tempi_raggruppati = {}
    for row in rows:
        player = row['player_name']
        time_val = row['time']
        safe_player = player.replace("_", "\\_")
        
        if time_val not in tempi_raggruppati:
            tempi_raggruppati[time_val] = []
        tempi_raggruppati[time_val].append(safe_player)
        
    tempi_ordinati = sorted(tempi_raggruppati.keys())
    
    testo = f"Build: {build_name}\n"
    
    if len(tempi_ordinati) > 0:
        t1 = tempi_ordinati[0]
        p1 = "/".join(tempi_raggruppati[t1])
        testo += f"> :first_place: - **__{p1} {t1}__**\n"
    else:
        testo += "> :first_place: - \n"
        
    if len(tempi_ordinati) > 1:
        t2 = tempi_ordinati[1]
        p2 = "/".join(tempi_raggruppati[t2])
        testo += f"> :second_place: - {p2} {t2}\n"
    else:
        testo += "> :second_place: - \n"
        
    if len(tempi_ordinati) > 2:
        t3 = tempi_ordinati[2]
        p3 = "/".join(tempi_raggruppati[t3])
        testo += f"> :third_place: - {p3} {t3}"
    else:
        testo += "> :third_place: - "
        
    return testo
