import re
import config
import asyncpg

# --- POOL DI CONNESSIONI GLOBALE ---
pool = None

async def init_pool():
    global pool
    # Mantiene sempre aperte tra 2 e 10 connessioni al database
    pool = await asyncpg.create_pool(config.DATABASE_URL, statement_cache_size=0, min_size=2, max_size=10)

def get_main_name(name):
    n = name.lower().strip()
    return config.ALIASES.get(n, n)

async def get_wr_count(bot, player_name):
    target_name = get_main_name(player_name)
    count = 0
    
    async with pool.acquire() as conn:
        query = """
            SELECT player_name 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
        """
        rows = await conn.fetch(query)
        
        for row in rows:
            if get_main_name(row['player_name']) == target_name:
                count += 1
                    
    return count

async def get_wr_rounds_info(bot):
    channel = bot.get_channel(config.RANKINGS_CHANNEL_ID)
    if not channel: return 0, "Sconosciuto"

    async for message in channel.history(limit=50):
        if not message.content: continue
        lines = message.content.split('\n')
        for i, line in enumerate(lines):
            if ":first_place:" in line and "Rounds" in line:
                match = re.search(r'(\d+)\s*Rounds', line, re.IGNORECASE)
                old_rounds = int(match.group(1)) if match else 0
                old_holders = []
                for j in range(i+1, min(i+10, len(lines))):
                    if ":second_place:" in lines[j] or ":third_place:" in lines[j]: break
                    if "|" in lines[j] and "[" in lines[j] and "]" in lines[j]:
                        holder_match = re.search(r'\[(.*?)\]', lines[j])
                        if holder_match: old_holders.append(holder_match.group(1).replace("&amp;", "&").strip())

                holders_str = " / ".join(old_holders) if old_holders else "Sconosciuto"
                return old_rounds, holders_str
    return 0, "Sconosciuto"

async def get_sim_wr_link(bot, build_name):
    channel = bot.get_channel(config.SIM_WR_CHANNEL_ID)
    if not channel: return None
        
    build_clean = build_name.lower().strip()
    async for message in channel.history(limit=500):
        if not message.content: continue
        lines = message.content.split('\n')
        for line in lines:
            clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").strip()
            if clean_line.startswith(f"{build_clean}:") or clean_line.startswith(f"{build_clean} :"):
                return message.jump_url
    return None

async def get_top_players(limit=15):
    async with pool.acquire() as conn:
        query = """
            SELECT player_name, COUNT(*) as wr_count 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
            GROUP BY LOWER(player_name), player_name
            ORDER BY wr_count DESC
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
        return [(r['player_name'], r['wr_count']) for r in rows]

async def generate_build_message(build_name: str) -> str:
    async with pool.acquire() as conn:
        # Peschiamo TUTTI i tempi senza raggrupparli via SQL
        query = """
            SELECT player_name, time 
            FROM WorldRecords 
            WHERE LOWER(build_name) = LOWER($1)
        """
        rows = await conn.fetch(query, build_name)
        
    # 1. Trova il tempo migliore per ogni giocatore (unificando gli alias)
    best_times = {}
    for row in rows:
        p_name = row['player_name']
        t_val = row['time']
        norm_name = get_main_name(p_name)
        
        # Se non ha un tempo registrato o se questo tempo è migliore, aggiornalo
        if norm_name not in best_times or t_val < best_times[norm_name]:
            best_times[norm_name] = t_val
            
    # 2. Raggruppiamo i giocatori per tempo per gestire i pareggi
    tempi_raggruppati = {}
    for norm_name, t_val in best_times.items():
        safe_player = norm_name.replace("_", "\\_")
        if t_val not in tempi_raggruppati: 
            tempi_raggruppati[t_val] = []
        tempi_raggruppati[t_val].append(safe_player)
        
    # 3. Creiamo il testo ordinando dal tempo più basso
    tempi_ordinati = sorted(tempi_raggruppati.keys())
    testo = f"Build: {build_name}\n"
    
    if len(tempi_ordinati) > 0:
        t1 = tempi_ordinati[0]
        p1 = "/".join(tempi_raggruppati[t1])
        testo += f"> :first_place: - **__{p1} {t1}__**\n"
    else: testo += "> :first_place: - \n"
        
    if len(tempi_ordinati) > 1:
        t2 = tempi_ordinati[1]
        p2 = "/".join(tempi_raggruppati[t2])
        testo += f"> :second_place: - {p2} {t2}\n"
    else: testo += "> :second_place: - \n"
        
    if len(tempi_ordinati) > 2:
        t3 = tempi_ordinati[2]
        p3 = "/".join(tempi_raggruppati[t3])
        testo += f"> :third_place: - {p3} {t3}"
    else: testo += "> :third_place: - "
        
    return testo
