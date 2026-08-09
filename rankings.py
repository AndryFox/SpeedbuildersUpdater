import discord
from discord import app_commands
import config
import aiohttp
import time
from database_utils import get_main_name

def get_role_tag(wr_count: int) -> str:
    """Restituisce il ping reale al ruolo in base al numero di WR posseduti."""
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

    # Prende l'ID da config.py e lo formatta come menzione di ruolo <@&ID>
    role_id = config.ROLE_IDS.get(role_name)
    return f"<@&{role_id}>" if role_id else f"@{role_name}"

def get_ordinal(n: int) -> str:
    """Aggiunge il suffisso ordinale corretto (1st, 2nd, 3rd, 4th...)."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

async def generate_wr_ranking_text(bot) -> str:
    """Scansiona il database e genera il testo formattato della classifica."""
    db_channel = bot.get_channel(config.DATABASE_CHANNEL_ID)
    wr_counts = {}
    
    # 1. Scansione del Database (legge gli ultimi 500 messaggi)
    async for message in db_channel.history(limit=500):
        for line in message.content.split('\n'):
            if ":first_place:" in line and "**__" in line:
                try:
                    # Estrae il testo tra **__ e __**
                    start = line.find("**__") + 4
                    end = line.find("__**")
                    content = line[start:end]
                    
                    # Rimuove il tempo alla fine (es. 3.4)
                    nomi_str = " ".join(content.split()[:-1])
                    
                    # Usa get_main_name per unire gli alias come namsarr1 -> namsar
                    nomi = [get_main_name(n.strip()) for n in nomi_str.split('/')]
                    
                    for nome in nomi:
                        if nome:
                            wr_counts[nome] = wr_counts.get(nome, 0) + 1
                except:
                    pass

    # 2. Ordinamento e Pareggi
    sorted_wrs = sorted(wr_counts.items(), key=lambda x: x[1], reverse=True)
    score_groups = {}
    for player, count in sorted_wrs:
        if count not in score_groups:
            score_groups[count] = []
        score_groups[count].append(player)
        
    # 3. Formattazione Stile
    testo_classifica = f"## Ranking Fear Games WRs (Updated <t:{int(time.time())}:d>)\n"
    
    posizione = 1
    for count, players in score_groups.items():
        players_str = " / ".join(players)
        role = get_role_tag(count)
        
        # Gestisce i > per le righe 1, 2, 3 e per le posizioni dispari successive
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
        
    # Al posto di testo_classifica += "||@Speedbuilders||"
    testo_classifica += f"||{config.ROLE_SPEEDBUILDERS}||"
    return testo_classifica

async def trigger_ranking_update(bot):
    """Viene chiamata quando accetti/editi un WR per aggiornare il Webhook."""
    if not hasattr(config, 'RANKING_WR_MSG_ID') or not config.RANKING_WR_MSG_ID:
        return
    
    new_text = await generate_wr_ranking_text(bot)
    
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
        await webhook.edit_message(config.RANKING_WR_MSG_ID, content=new_text)

def setup_rankings_commands(bot):
    @bot.tree.command(name="setup_rankings", description="Invia il messaggio iniziale della Classifica WR")
    async def setup_rankings(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        initial_text = await generate_wr_ranking_text(bot)
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
            msg = await webhook.send(
                content=initial_text, 
                username="Rankings Updater",
                wait=True
            )
            
        await interaction.followup.send(f"✅ Classifica creata! Copia questo ID e mettilo in config.py come RANKING_WR_MSG_ID:\n**{msg.id}**")