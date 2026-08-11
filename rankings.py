import discord
from discord import app_commands
import config
import aiohttp
import time
from database_utils import get_main_name

# --- GLOBAL CACHE ---
PLAYERS_CACHE = []
WR_RECORDS_CACHE = {}
DISPLAY_NAMES_CACHE = {}

def get_role_tag(wr_count: int) -> str:
    role_name = ""
    if wr_count >= 100: role_name = "Greatest of All Time"
    elif wr_count >= 90: role_name = "Legend"
    elif wr_count >= 80: role_name = "Grandmaster"
    elif wr_count >= 70: role_name = "Master"
    elif wr_count >= 60: role_name = "Expert"
    elif wr_count >= 50: role_name = "Imperial"
    elif wr_count >= 45: role_name = "Professional"
    elif wr_count >= 40: role_name = "Talented"
    elif wr_count >= 35: role_name = "Skilled"
    elif wr_count >= 30: role_name = "Seasoned"
    elif wr_count >= 25: role_name = "Experienced"
    elif wr_count >= 20: role_name = "Trained"
    elif wr_count >= 15: role_name = "Apprentice"
    elif wr_count >= 10: role_name = "Amateur"
    elif wr_count >= 6: role_name = "Rookie"
    elif wr_count >= 3: role_name = "Novice"
    elif wr_count >= 1: role_name = "Prospect"
    else: role_name = "Newbie"

    if hasattr(config, 'ROLE_IDS') and role_name in config.ROLE_IDS:
        return f"<@&{config.ROLE_IDS[role_name]}>"
    return f"@{role_name}"

def get_ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

async def generate_wr_ranking_text(bot) -> str:
    global PLAYERS_CACHE, WR_RECORDS_CACHE, DISPLAY_NAMES_CACHE
    db_channel = bot.get_channel(config.DATABASE_CHANNEL_ID)
    wr_counts = {}
    display_names = {} 
    temp_records_cache = {}
    current_build_name = "Unknown Build"
    
    async for message in db_channel.history(limit=None, oldest_first=True):
        for line in message.content.split('\n'):
            line_str = line.strip()
            if not line_str: continue
            if ("🥇" in line or ":first_place:" in line) and "**__" in line:
                try:
                    start = line.find("**__") + 4
                    end = line.find("__**", start)
                    if end == -1: end = line.find("**", start)
                    if end == -1: end = len(line)
                    content = line[start:end].strip()
                    parts = content.split()
                    if len(parts) > 1:
                        nomi_str = " ".join(parts[:-1])
                        time_str = parts[-1]
                    else:
                        nomi_str = parts[0]
                        time_str = "?"
                    idx = line.find("🥇") if "🥇" in line else line.find(":first_place:")
                    raw_prefix = line[:idx]
                    build_inline = raw_prefix.replace("**", "").replace(">", "").replace("-", "").replace("•", "").strip()
                    final_build = build_inline if build_inline else current_build_name
                    record_entry = f"▸ Build: **{final_build}** ⸻ `{time_str}s`"
                    nomi_grezzi = [n.strip() for n in nomi_str.split('/') if n.strip()]
                    
                    for nome_grezzo in nomi_grezzi:
                        nome_pulito = nome_grezzo.replace("\\", "")
                        nome_norm = get_main_name(nome_pulito)
                        wr_counts[nome_norm] = wr_counts.get(nome_norm, 0) + 1
                        if nome_norm not in temp_records_cache: temp_records_cache[nome_norm] = []
                        temp_records_cache[nome_norm].append(record_entry)
                        if nome_norm not in display_names:
                            if nome_pulito.lower() != nome_norm.lower(): display_names[nome_norm] = nome_norm
                            else: display_names[nome_norm] = nome_grezzo
                except Exception as e: pass
            elif "🥈" not in line and "🥉" not in line and ":second_place:" not in line and ":third_place:" not in line:
                cleaned = line_str.replace("**", "").replace("__", "").replace(">", "").strip()
                if cleaned and len(cleaned) < 40: current_build_name = cleaned

    PLAYERS_CACHE = sorted(list({v.replace("\\", "") for v in display_names.values()}))
    DISPLAY_NAMES_CACHE = display_names.copy()
    WR_RECORDS_CACHE = temp_records_cache.copy()

    sorted_wrs = sorted(wr_counts.items(), key=lambda x: x[1], reverse=True)
    score_groups = {}
    for player_norm, count in sorted_wrs:
        if count not in score_groups: score_groups[count] = []
        nome_estetico = display_names.get(player_norm, player_norm)
        score_groups[count].append(nome_estetico)
        
    testo_classifica = f"## Ranking Fear Games WRs (Updated <t:{int(time.time())}:d>)\n"
    posizione = 1
    for count, players in score_groups.items():
        players_str = " / ".join(players)
        role = get_role_tag(count)
        has_quote = "> " if (posizione <= 3) or (posizione % 2 != 0) else ""
        ordinale = get_ordinal(posizione)
        
        if posizione == 1: riga = f"{has_quote}# :first_place: {ordinale} **__{players_str}__** : {count}Wrs ({role})"
        elif posizione == 2: riga = f"{has_quote}## :second_place: {ordinale} **{players_str}** : {count}Wrs ({role})"
        elif posizione == 3: riga = f"{has_quote}### :third_place: {ordinale} {players_str} : {count}Wrs ({role})"
        else: riga = f"{has_quote}{ordinale} {players_str} : {count}Wrs ({role})"
                
        testo_classifica += riga + "\n"
        posizione += 1
        
    tag_speedbuilders = getattr(config, 'ROLE_SPEEDBUILDERS', '|| @Speedbuilders ||')
    testo_classifica += tag_speedbuilders
    return testo_classifica

async def trigger_ranking_update(bot):
    if not hasattr(config, 'RANKING_WR_MSG_ID') or not config.RANKING_WR_MSG_ID: return
    new_text = await generate_wr_ranking_text(bot)
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
        await webhook.edit_message(config.RANKING_WR_MSG_ID, content=new_text)

# --- SISTEMA DI AUTOMAZIONE RANKING ROUNDS ---

async def generate_rounds_ranking_text(bot) -> str:
    # Per sicurezza: se qualcuno invoca un aggiornamento di massa, legge lo stato attuale e lo mantiene
    channel = bot.get_channel(config.RANKINGS_CHANNEL_ID)
    try:
        msg = await channel.fetch_message(config.RANKING_ROUNDS_MSG_ID)
        return msg.content
    except:
        return "## In total Fear Games have: __140 Builds__\n\nThe Wr rounds **(Legit)** on Fear Games is:\n\n||@Speedbuilders||"

async def trigger_rounds_update(bot):
    if not hasattr(config, 'RANKING_ROUNDS_MSG_ID') or not config.RANKING_ROUNDS_MSG_ID: return
    new_text = await generate_rounds_ranking_text(bot)
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
        await webhook.edit_message(config.RANKING_ROUNDS_MSG_ID, content=new_text)

async def add_or_update_round_record(bot, rounds: int, team: str, timestamp: str, link: str):
    channel = bot.get_channel(config.RANKINGS_CHANNEL_ID)
    if not channel: return
    try:
        msg = await channel.fetch_message(config.RANKING_ROUNDS_MSG_ID)
        content = msg.content
    except: return
        
    import re
    records = []
    current_rounds = 0
    
    # 1. Legge la classifica attuale per preservarla
    for line in content.split('\n'):
        r_match = re.search(r'\*\*_*(.*?)\s*Rounds_*\*\*', line, re.IGNORECASE)
        if r_match:
            try: current_rounds = int(r_match.group(1).replace("_", "").strip())
            except: pass
            
        if "<t:" in line and "|" in line and current_rounds > 0:
            ts_match = re.search(r'<t:(\d+):F>', line)
            team_match = re.search(r'\*\*\[(.*?)\]', line)
            link_match = re.search(r'\]\(<(.*?)>\)\*\*', line)
            
            if ts_match and team_match:
                ts = ts_match.group(1)
                t_name = team_match.group(1).replace("&amp;", "&")
                l = link_match.group(1) if link_match else ""
                if "in-attesa-di-link" in l: l = ""
                records.append({"rounds": current_rounds, "team": t_name, "timestamp": ts, "link": l})
                
    # 2. Aggiunge o aggiorna il nuovo record
    updated = False
    for r in records:
        if r["rounds"] == rounds and r["team"].lower() == team.lower():
            r["timestamp"] = timestamp
            if link: r["link"] = link
            updated = True
            break
            
    if not updated:
        records.append({"rounds": rounds, "team": team, "timestamp": timestamp, "link": link})
        
    # 3. Riordina e Raggruppa
    records = sorted(records, key=lambda x: x["rounds"], reverse=True)
    grouped = {}
    for r in records:
        if r["rounds"] not in grouped: grouped[r["rounds"]] = []
        grouped[r["rounds"]].append(r)
        
    # 4. Recupera l'intestazione esatta intatta
    header = "## In total Fear Games have: __140 Builds__\n\nThe Wr rounds **(Legit)** on Fear Games is:\n"
    header_match = re.match(r'(.*?The Wr rounds.*?:)', content, re.DOTALL | re.IGNORECASE)
    if header_match: header = header_match.group(1).strip() + "\n"
        
    # 5. Formattazione di precisione
    final_text = header + " \n"
    pos_map = [":first_place:", ":second_place:", ":third_place:"]
    idx = 0
    
    for r_val, team_records in grouped.items():
        pos_emoji = pos_map[idx] if idx < 3 else f"{idx+1}th"
        final_text += f"{pos_emoji} **__{r_val} Rounds__**\n"
        
        for i, tr in enumerate(team_records):
            prefix = "> " if i == 0 else ""
            link_str = f"(<{tr['link']}>)" if tr['link'] else "(<https://in-attesa-di-link>)"
            final_text += f"{prefix}<t:{tr['timestamp']}:F> | **[{tr['team']}]{link_str}**\n"
            
        final_text += "\n"
        idx += 1
        
    tag_speedbuilders = getattr(config, 'ROLE_SPEEDBUILDERS', '||@Speedbuilders||')
    final_text += tag_speedbuilders
    
    # 6. Salva tramite Webhook
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
        await webhook.edit_message(config.RANKING_ROUNDS_MSG_ID, content=final_text)

def setup_rankings_commands(bot):
    bot.loop.create_task(generate_wr_ranking_text(bot))

    @bot.tree.command(name="setup_rankings", description="Send the initial WR Ranking message")
    async def setup_rankings(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        initial_text = await generate_wr_ranking_text(bot)
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
            msg = await webhook.send(content=initial_text, username="Rankings Updater", wait=True)
        await interaction.followup.send(f"✅ Ranking created! Copy this ID into config.py:\n**{msg.id}**")

    async def player_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = [
            app_commands.Choice(name=player, value=player)
            for player in PLAYERS_CACHE if current.lower() in player.lower()
        ]
        return choices[:25] 

    @bot.tree.command(name="setup_rounds", description="Send the initial WR Rounds message")
    async def setup_rounds(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        initial_text = "## In total Fear Games have: __140 Builds__\n\nThe Wr rounds **(Legit)** on Fear Games is:\n\n||@Speedbuilders||"
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
            msg = await webhook.send(content=initial_text, username="Rankings Updater", wait=True)
        await interaction.followup.send(f"✅ Ranking Rounds created! Copy this ID into config.py:\n**{msg.id}**")

    @bot.tree.command(name="wrs", description="Check all WRs and times of a player (visible only to you)")
    @app_commands.describe(player="The name of the player to search")
    @app_commands.autocomplete(player=player_autocomplete)
    async def check_wrs(interaction: discord.Interaction, player: str):
        if interaction.channel_id != config.SUBMISSION_CHANNEL_ID:
            return await interaction.response.send_message(f"⚠️ This command can only be used in <#{config.SUBMISSION_CHANNEL_ID}>.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        if not WR_RECORDS_CACHE: await generate_wr_ranking_text(bot)
            
        player_norm = get_main_name(player.replace("\\", ""))
        records = WR_RECORDS_CACHE.get(player_norm, [])
        count = len(records)
        
        if count > 0:
            ruolo = get_role_tag(count)
            nome_estetico = DISPLAY_NAMES_CACHE.get(player_norm, player)
            avatar_url = f"https://minotar.net/helm/{player_norm}/256.png"
            
            embed = discord.Embed(description=f"**Current Rank:** {ruolo}\n\n", color=discord.Color.gold())
            embed.set_author(name=f"{nome_estetico}'s World Records ({count})", icon_url=avatar_url)
            embed.set_thumbnail(url=avatar_url)
            
            lista_formattata = "\n".join(records)
            if len(lista_formattata) > 3900: lista_formattata = lista_formattata[:3900] + "\n\n*... and more (text limit reached)!*"
            embed.description += lista_formattata
            
            icon_url = bot.user.avatar.url if bot.user.avatar else None
            embed.set_footer(text="FearGames Speedbuilders", icon_url=icon_url)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"📉 **{player}** is not in the rankings yet or has no WRs at the moment.")
