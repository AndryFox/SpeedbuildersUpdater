import re
import config

def get_main_name(name):
    n = name.lower().strip()
    return config.ALIASES.get(n, n)

async def get_wr_count(bot, player_name):
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
                parts = line_lower.split(":", 1)
                left_part = parts[0]
                right_part = parts[1]
                
                left_clean = left_part.replace("*", "").replace("_", "").replace("~", "").replace("#", "")
                words = left_clean.replace("/", " ").split()
                
                if p_lower in words:
                    match = re.search(r'(\d+)\s*wr', right_part)
                    if match:
                        return int(match.group(1))
    return 0

# 1. AGGIORNATA: Ora il bot legge i round dal canale privato
async def get_wr_rounds_info(bot):
    channel = bot.get_channel(config.ROUNDS_DB_CHANNEL_ID)
    if not channel:
        return 0, "Sconosciuto"

    try:
        msg = await channel.fetch_message(config.ROUNDS_DB_MSG_ID)
        lines = msg.content.split('\n')
        for line in lines:
            # Trova la riga con il primo posto (il WR attuale)
            match = re.search(r'(\d+)\s*Rounds.*?\[(.*?)\]', line, re.IGNORECASE)
            if match:
                old_rounds = int(match.group(1))
                old_holders = match.group(2).replace("&amp;", "&").strip()
                return old_rounds, old_holders
    except:
        pass
    return 0, "Sconosciuto"

# 2. NUOVA: Funzione che riordina e aggiorna i record automaticamente
async def update_wr_rounds_database(bot, new_rounds, new_team, image_url):
    channel = bot.get_channel(config.ROUNDS_DB_CHANNEL_ID)
    try:
        msg = await channel.fetch_message(config.ROUNDS_DB_MSG_ID)
    except:
        return
        
    lines = msg.content.split('\n')
    records = []
    
    # Estrae tutti i vecchi record dal testo
    for line in lines:
        match = re.search(r'(\d+)\s*Rounds.*?\[(.*?)\]\((.*?)\)', line, re.IGNORECASE)
        if match:
            r = int(match.group(1))
            t = match.group(2).replace("&amp;", "&").strip()
            l = match.group(3).strip()
            records.append({"rounds": r, "team": t, "link": l})

    # Aggiunge il nuovo record
    records.append({"rounds": new_rounds, "team": new_team, "link": image_url})
    
    # Riordina dal più grande al più piccolo
    records = sorted(records, key=lambda x: x["rounds"], reverse=True)
    
    # Filtra eventuali duplicati identici e mantiene la Top 5
    unique_records = []
    seen = set()
    for rec in records:
        id_team = f"{rec['rounds']}-{rec['team']}"
        if id_team not in seen:
            seen.add(id_team)
            unique_records.append(rec)
            
    records = unique_records[:5]

    # Rigenera il testo estetico
    new_text = "**WR Rounds (Legit)**\n\n"
    for i, rec in enumerate(records):
        pos = i + 1
        if pos == 1:
            prefix = f"# :first_place: 1st **__{rec['rounds']} Rounds__**"
        elif pos == 2:
            prefix = f"## :second_place: 2nd **{rec['rounds']} Rounds**"
        elif pos == 3:
            prefix = f"### :third_place: 3rd {rec['rounds']} Rounds"
        elif pos == 4:
            prefix = f"4th {rec['rounds']} Rounds"
        else:
            prefix = f"5th {rec['rounds']} Rounds"
            
        new_text += f"{prefix} | [{rec['team']}]({rec['link']})\n"

    # Salva il nuovo testo nel messaggio database
    await msg.edit(content=new_text)

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

# --- NUOVA FUNZIONE DEDICATA SOLO AI SIM WR ---
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
            # Pulizia per togliere grassetti e corsivi
            clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").strip()
            
            # Cerca se la riga inizia con il nome della build e i due punti (es. "alveare:" o "alveare :")
            if clean_line.startswith(f"{build_clean}:") or clean_line.startswith(f"{build_clean} :"):
                return message.jump_url
                
    return None