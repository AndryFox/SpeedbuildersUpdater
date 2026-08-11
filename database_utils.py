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

async def get_wr_from_database(bot, build_name, channel_id=None):
    if channel_id is None:
        channel_id = config.WR_CHANNEL_ID
        
    channel = bot.get_channel(channel_id)
    
    if not channel:
        print("ERRORE: Il bot non riesce a vedere il canale database!")
        return None, None, None
        
    build_clean = build_name.lower().strip()
    
    async for message in channel.history(limit=500):
        if not message.content:
            continue
            
        lines = message.content.split('\n')
        for i, line in enumerate(lines):
            clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").strip()
            
            if clean_line.startswith("build:") and build_clean in clean_line:
                for j in range(i + 1, min(i + 4, len(lines))):
                    top_line = lines[j]
                    top_line = top_line.replace(">", "").replace("_", "").replace("*", "").replace("~", "").strip()
                    top_line = top_line.replace("–", "-").replace("—", "-")
                    
                    if "-" in top_line:
                        data_str = top_line.split("-", 1)[1].strip() 
                        
                        if data_str != "": 
                            parts = data_str.rsplit(' ', 1)
                            if len(parts) == 2:
                                player = parts[0].strip()
                                time_str = parts[1].lower().replace("s", "").replace("sec", "").strip()
                                
                                try:
                                    time_val = float(time_str)
                                    return player, time_val, message.jump_url
                                except ValueError:
                                    pass
                        break
    return None, None, None

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
