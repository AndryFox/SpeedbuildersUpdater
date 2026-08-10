import discord
from discord import app_commands
import config
import aiohttp
import time
from database_utils import get_main_name

# --- CACHE GLOBALE ---
PLAYERS_CACHE = []
WR_RECORDS_CACHE = {} # Ora salva TUTTI i record, non solo i numeri!

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
    global PLAYERS_CACHE, WR_RECORDS_CACHE
    
    db_channel = bot.get_channel(config.DATABASE_CHANNEL_ID)
    wr_counts = {}
    display_names = {} 
    temp_records_cache = {} # Cache temporanea per questa lettura
    
    async for message in db_channel.history(limit=None):
        for line in message.content.split('\n'):
            if ("🥇" in line or ":first_place:" in line) and "**__" in line:
                try:
                    # 1. Trova i nomi e i tempi
                    start = line.find("**__") + 4
                    end = line.find("__**", start)
                    if end == -1: end = line.find("**", start)
                    if end == -1: end = len(line)
                        
                    content = line[start:end].strip()
                    parts = content.split()
                    
                    # L'ultimo pezzo è il tempo (es. "6.7"), il resto sono i nomi
                    if len(parts) > 1:
                        nomi_str = " ".join(parts[:-1])
                        time_str = parts[-1]
                    else:
                        nomi_str = parts[0]
                        time_str = "?"
                        
                    # 2. Estrae il NOME DELLA BUILD togliendo medaglie e formattazioni
                    raw_prefix = line[:line.find("**__")]
                    build_name = raw_prefix.replace("🥇", "").replace(":first_place:", "").lstrip("> -•").strip()
                    if not build_name:
                        build_name = "Build Sconosciuta"
                        
                    record_entry = f"**{build_name}** (⏱️ {time_str})"
                        
                    # 3. Assegna il record a tutti i giocatori che lo condividono (in caso di pareggio)
                    nomi_grezzi = [n.strip() for n in nomi_str.split('/') if n.strip()]
                    for nome_grezzo in nomi_grezzi:
                        nome_norm = get_main_name(nome_grezzo)
                        wr_counts[nome_norm] = wr_counts.get(nome_norm, 0) + 1
                        
                        if nome_norm not in temp_records_cache:
                            temp_records_cache[nome_norm] = []
                        temp_records_cache[nome_norm].append(record_entry)
                        
                        if nome_norm not in display_names:
                            if nome_grezzo.lower() != nome_norm.lower():
                                display_names[nome_norm] = nome_norm.capitalize()
                            else:
                                display_names[nome_norm] = nome_grezzo
                except Exception as e:
                    pass

    # Aggiorna la cache globale
    PLAYERS_CACHE = sorted(list(display_names.values()))
    WR_RECORDS_CACHE = temp_records_cache.copy()

    sorted_wrs = sorted(wr_counts.items(), key=lambda x: x[1], reverse=True)
    score_groups = {}
    for player_norm, count in sorted_wrs:
        if count not in score_groups:
            score_groups[count] = []
        nome_estetico = display_names.get(player_norm, player_norm.capitalize())
        score_groups[count].append(nome_estetico)
        
    testo_classifica = f"## Ranking Fear Games WRs (Updated <t:{int(time.time())}:d>)\n"
    
    posizione = 1
    for count, players in score_groups.items():
        players_str = " / ".join(players)
        role = get_role_tag(count)
        
        has_quote = "> " if (posizione <= 3) or (posizione % 2 != 0) else ""
        ordinale = get_ordinal(posizione)
        
        if posizione == 1:
            riga = f"{has_quote}# :first_place: {ordinale} **__{players_str}__** : {count}Wrs ({role})"
        elif posizione == 2:
            riga = f"{has_quote}## :second_place: {ordinale} **{players_str}** : {count}Wrs ({role})"
        elif posizione == 3:
            riga = f"{has_quote}### :third_place: {ordinale} {players_str} : {count}Wrs ({role})"
        else:
            riga = f"{has_quote}{ordinale} {players_str} : {count}Wrs ({role})"
                
        testo_classifica += riga + "\n"
        posizione += 1
        
    tag_speedbuilders = getattr(config, 'ROLE_SPEEDBUILDERS', '||@Speedbuilders||')
    testo_classifica += tag_speedbuilders
    return testo_classifica

async def trigger_ranking_update(bot):
    if not hasattr(config, 'RANKING_WR_MSG_ID') or not config.RANKING_WR_MSG_ID:
        return
    
    new_text = await generate_wr_ranking_text(bot)
    
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
        await webhook.edit_message(config.RANKING_WR_MSG_ID, content=new_text)

def setup_rankings_commands(bot):
    bot.loop.create_task(generate_wr_ranking_text(bot))

    @bot.tree.command(name="setup_rankings", description="Invia il messaggio iniziale della Classifica WR")
    async def setup_rankings(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        initial_text = await generate_wr_ranking_text(bot)
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
            msg = await webhook.send(content=initial_text, username="Rankings Updater", wait=True)
            
        await interaction.followup.send(f"✅ Classifica creata! Copia questo ID in config.py:\n**{msg.id}**")

    async def player_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        choices = [
            app_commands.Choice(name=player, value=player)
            for player in PLAYERS_CACHE if current.lower() in player.lower()
        ]
        return choices[:25] 

    @bot.tree.command(name="wrs", description="Visualizza tutti i WR e i tempi di un giocatore (visibile solo a te)")
    @app_commands.describe(player="Il nome del giocatore da cercare")
    @app_commands.autocomplete(player=player_autocomplete)
    async def check_wrs(interaction: discord.Interaction, player: str):
        if interaction.channel_id != config.SUBMISSION_CHANNEL_ID:
            return await interaction.response.send_message(
                f"⚠️ Questo comando può essere usato solo in <#{config.SUBMISSION_CHANNEL_ID}>.", 
                ephemeral=True
            )
            
        await interaction.response.defer(ephemeral=True)
        
        if not WR_RECORDS_CACHE:
            await generate_wr_ranking_text(bot)
            
        player_norm = get_main_name(player)
        records = WR_RECORDS_CACHE.get(player_norm, [])
        count = len(records)
        
        if count > 0:
            ruolo = get_role_tag(count)
            nome_estetico = player if player.lower() != player_norm else player_norm.capitalize()
            
            # --- CREAZIONE DELL'EMBED VISIVO ---
            embed = discord.Embed(
                title=f"🏆 WRs di {nome_estetico} ({count})",
                description=f"**Ruolo Attuale:** {ruolo}\n\n",
                color=discord.Color.gold()
            )
            
            # Crea una lista puntata bellissima
            lista_formattata = "\n".join([f"🔹 {r}" for r in records])
            
            # Limite di sicurezza (gli Embed di Discord reggono massimo 4096 caratteri)
            if len(lista_formattata) > 3900:
                lista_formattata = lista_formattata[:3900] + "\n... e altri (limite di testo raggiunto)!"
                
            embed.description += lista_formattata
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"📉 **{player}** non è ancora presente nella classifica o non ha WR al momento.")
