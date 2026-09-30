import discord
from discord import app_commands 
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import re
import asyncio
import aiohttp
import shutil
from datetime import datetime

# Importiamo i nostri moduli
import database_utils
import config
import rankings
import ui_components
from tourneys import setup_tourney_commands
from rankings import setup_rankings_commands

# --- SEZIONE PER MANTENERE IL BOT ATTIVO SU RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
# ----------------------------------------------------

# Inizializza il bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

'''
@bot.tree.command(name="setup_all_builds", description="Invia i messaggi delle build e salva gli ID nel DB")
@app_commands.default_permissions(administrator=True)
async def setup_all_builds(interaction: discord.Interaction):
    # [Comando disabilitato e conservato per backup]
    pass
'''

@bot.tree.command(name="manual_submit", description="Invia un record in revisione per conto di un altro utente (Solo Admin)")
@app_commands.describe(player="L'utente che ha fatto il record", image="Lo screenshot del record")
@app_commands.default_permissions(administrator=True)
async def manual_submit(interaction: discord.Interaction, player: discord.Member, image: discord.Attachment):
    # Buttafuori: Solo tu puoi usare questo comando
    if interaction.user.id != config.MIO_ID:
        return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

    # defer(ephemeral=True) fa sì che il comando carichi in modo "invisibile" per gli altri
    await interaction.response.defer(ephemeral=True)

    review_channel = bot.get_channel(config.REVIEW_CHANNEL_ID)
    
    if not review_channel:
        return await interaction.followup.send("❌ Errore: Canale di revisione non trovato.", ephemeral=True)

    # Prepara il file e i bottoni
    view = ui_components.ReviewView()
    file_review = await image.to_file()

    # Invia il messaggio fasullo nel canale di revisione
    await review_channel.send(
        content=f"New world record sent from {player.mention}",
        file=file_review,
        view=view
    )

    # Ti conferma che è andato tutto a buon fine senza che nessuno lo legga
    await interaction.followup.send(f"🥷 ✅ Operazione fantasma completata! Screenshot inviato in revisione per conto di {player.mention}.", ephemeral=True)

@bot.tree.command(name="add_alias", description="🔧 Unisce i record di un vecchio nome al nuovo nome (Solo Admin)")
@app_commands.describe(vecchio_nome="Il nome vecchio (es. blaagoosb)", nuovo_nome="Il nome corretto (es. M2xD)")
@app_commands.default_permissions(administrator=True) # Solo gli admin possono usarlo
async def add_alias(interaction: discord.Interaction, vecchio_nome: str, nuovo_nome: str):
    v_name = vecchio_nome.lower()

    import database_utils
    async with database_utils.pool.acquire() as conn:
        # Salviamo nel database
        await conn.execute(
            "INSERT INTO Aliases (old_name, new_name) VALUES ($1, $2) ON CONFLICT (old_name) DO UPDATE SET new_name = $2", 
            v_name, nuovo_nome
        )
        # Aggiungiamo anche la doppia sicurezza per le maiuscole (come facevamo su config.py)
        n_name_lower = nuovo_nome.lower()
        if v_name != n_name_lower:
            await conn.execute(
                "INSERT INTO Aliases (old_name, new_name) VALUES ($1, $2) ON CONFLICT (old_name) DO UPDATE SET new_name = $2", 
                n_name_lower, nuovo_nome
            )

    # Aggiorniamo la RAM in tempo reale e ricalcoliamo le classifiche
    await database_utils.load_aliases()
    import rankings
    await rankings.trigger_ranking_update(bot)
       
    await interaction.response.send_message(f"✅ Identità unite! Tutti i record passati e futuri di `{vecchio_nome}` apparterranno a **{nuovo_nome}**.", ephemeral=True)

async def setup_hook():
    await database_utils.init_pool()
    await database_utils.load_aliases() # AGGIUNGI QUESTA RIGA
    print("🗄️ Database e Viste Persistenti inizializzati!")

bot.setup_hook = setup_hook

import traceback

# 1. Cattura gli errori degli eventi e dei pulsanti
@bot.event
async def on_error(event_method, *args, **kwargs):
    log_channel = bot.get_channel(config.LOG_CHANNEL_ID)
    if log_channel:
        error_msg = traceback.format_exc()
        # Tagliamo il messaggio se è troppo lungo per Discord
        if len(error_msg) > 1900:
            error_msg = error_msg[-1900:]
        await log_channel.send(f"⚠️ **Errore Critico (Evento: {event_method})**\n```py\n{error_msg}\n```")

# 2. Cattura gli errori dei comandi Slash (come /add_alias)
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    log_channel = bot.get_channel(config.LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"⚠️ **Errore nel comando `/{interaction.command.name}` usato da {interaction.user.name}**\n```py\n{error}\n```")
    
    # Avvisiamo l'utente che qualcosa è andato storto senza mostrargli codici strani
    if interaction.response.is_done():
        await interaction.followup.send("❌ Ops! Si è verificato un errore interno. L'amministratore è stato avvisato.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Ops! Si è verificato un errore interno. L'amministratore è stato avvisato.", ephemeral=True)

from discord import app_commands
import discord
import database_utils

# --- FUNZIONI DI AUTOCOMPLETAMENTO ---
async def build_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    # Suggerisce i nomi delle build presi dal database
    async with database_utils.pool.acquire() as conn:
        if not current:
            # Se la casella è vuota, mostra le prime 25 build in ordine alfabetico
            rows = await conn.fetch("SELECT DISTINCT build_name FROM WorldRecords ORDER BY build_name LIMIT 25")
        else:
            # Cerca le build che contengono le lettere digitate (ILIKE non è case-sensitive)
            rows = await conn.fetch("SELECT DISTINCT build_name FROM WorldRecords WHERE build_name ILIKE $1 ORDER BY build_name LIMIT 25", f"%{current}%")
        
        return [app_commands.Choice(name=row['build_name'], value=row['build_name']) for row in rows]

async def player_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    # Suggerisce i nomi dei giocatori presi dal database
    async with database_utils.pool.acquire() as conn:
        if not current:
            rows = await conn.fetch("SELECT DISTINCT player_name FROM WorldRecords ORDER BY player_name LIMIT 25")
        else:
            rows = await conn.fetch("SELECT DISTINCT player_name FROM WorldRecords WHERE player_name ILIKE $1 ORDER BY player_name LIMIT 25", f"%{current}%")
            
        return [app_commands.Choice(name=row['player_name'], value=row['player_name']) for row in rows]


# --- COMANDO: /buildtimes ---
@bot.tree.command(name="buildtimes", description="Mostra la Top 3 e il Sim WR di una build (visibile solo a te)")
@app_commands.describe(build="Nome della build da cercare")
@app_commands.autocomplete(build=build_autocomplete) # <--- AGGIUNTO L'AUTOCOMPLETE
async def buildtimes_cmd(interaction: discord.Interaction, build: str):
    await interaction.response.defer(ephemeral=True)
    
    # 1. Trova la Top 3 dal Database (WR Ufficiali)
    top3_text = ""
    async with database_utils.pool.acquire() as conn:
        query = """
            SELECT player_name, time 
            FROM WorldRecords 
            WHERE LOWER(build_name) = LOWER($1)
            ORDER BY time ASC
        """
        rows = await conn.fetch(query, build.strip())
        
    if not rows:
        top3_text = "Nessun record ufficiale trovato."
    else:
        best_times = {}
        for row in rows:
            p_name = row['player_name']
            t_val = row['time']
            norm_name = database_utils.get_main_name(p_name)
            if norm_name not in best_times or t_val < best_times[norm_name]:
                best_times[norm_name] = t_val
        
        time_groups = {}
        for p, t in best_times.items():
            if t not in time_groups: time_groups[t] = []
            time_groups[t].append(p)
            
        sorted_times = sorted(time_groups.keys())
        
        medals = ["🥇 1st", "🥈 2nd", "🥉 3rd"]
        for i in range(min(3, len(sorted_times))):
            t = sorted_times[i]
            players = " / ".join([p.title() for p in time_groups[t]])
            top3_text += f"{medals[i]}: **{players}** ({t}s)\n"

    # 2. Cerca il Sim WR leggendo il canale dedicato
    sim_channel = bot.get_channel(config.SIM_WR_CHANNEL_ID)
    sim_text = "Nessun Sim WR trovato per questa build."
    build_clean = build.lower().strip()
    
    if sim_channel:
        found = False
        async for message in sim_channel.history(limit=500):
            if not message.content: continue
            for line in message.content.split('\n'):
                clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").replace("`", "").strip()
                if clean_line.startswith(f"{build_clean}:") or clean_line.startswith(f"{build_clean} :"):
                    original_line = line.replace("*", "").replace("_", "").replace(">", "").replace("`", "").strip()
                    sim_text = f"**{original_line}**\n[🔗 Vai al messaggio originale]({message.jump_url})"
                    found = True
                    break
            if found: break

    # 3. Crea l'Embed e lo invia
    embed = discord.Embed(title=f"⏱️ Statistiche Build: {build.title()}", color=discord.Color.blue())
    embed.add_field(name="🏆 Top 3 Ufficiale", value=top3_text, inline=False)
    embed.add_field(name="🔄 Sim WR", value=sim_text, inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)


# --- COMANDO: /wrssim ---
@bot.tree.command(name="wrssim", description="Mostra tutti i Sim WR di un giocatore (visibile solo a te)")
@app_commands.describe(player="Nome del giocatore")
@app_commands.autocomplete(player=player_autocomplete) # <--- AGGIUNTO L'AUTOCOMPLETE
async def wrssim_cmd(interaction: discord.Interaction, player: str):
    await interaction.response.defer(ephemeral=True)
    
    target_norm = database_utils.get_main_name(player.strip())
    sim_channel = bot.get_channel(config.SIM_WR_CHANNEL_ID)
    
    wrs_found = []
    
    if sim_channel:
        async for message in sim_channel.history(limit=500):
            if not message.content: continue
            for line in message.content.split('\n'):
                clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").replace("`", "").strip()
                
                if "-" in clean_line and ":" in clean_line:
                    parts = clean_line.split('-')
                    player_part = parts[-1].strip()
                    
                    sim_players = [p.strip() for p in player_part.split('/')]
                    sim_players_norm = []
                    
                    import re
                    for p in sim_players:
                        clean_p = re.sub(r'\(.*?\)', '', p)
                        clean_p = re.sub(r'\[.*?\]', '', clean_p).strip()
                        sim_players_norm.append(database_utils.get_main_name(clean_p))
                    
                    if target_norm in sim_players_norm:
                        original_line = line.replace("*", "").replace("_", "").replace(">", "").replace("`", "").strip()
                        wrs_found.append(f"• {original_line} - [🔗 Link]({message.jump_url})")

    if not wrs_found:
        await interaction.followup.send(f"❌ Nessun Sim WR trovato per **{player.title()}**.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title=f"🔄 Sim WR di {player.title()} ({len(wrs_found)})", 
        color=discord.Color.green()
    )
    
    description = "\n".join(wrs_found)
    if len(description) > 4000:
        description = description[:3900] + "\n... *(troppi risultati per un solo messaggio)*"
        
    embed.description = description
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} avviato con successo e collegato al Cloud!")

    setup_tourney_commands(bot)
    setup_rankings_commands(bot)

    # 1. Puliamo i comandi doppi specifici del server
    IL_MIO_SERVER = discord.Object(id=935816490039533621) 
    
    bot.tree.clear_commands(guild=IL_MIO_SERVER) 
    await bot.tree.sync(guild=IL_MIO_SERVER)     
    
    # 2. Manteniamo solo la sincronizzazione globale pulita
    await bot.tree.sync()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # --- SENSORE: Se scrivi un NUOVO messaggio a mano nel database ---
    if message.channel.id == config.WR_CHANNEL_ID:
        await rankings.trigger_ranking_update(bot)

    if message.channel.id != config.SUBMISSION_CHANNEL_ID:
        await bot.process_commands(message)
        return

    has_media = len(message.attachments) > 0
    has_tag = any(mention.id == config.MIO_ID for mention in message.mentions)

    if has_media and has_tag:
        review_channel = bot.get_channel(config.REVIEW_CHANNEL_ID)
        
        for attachment in message.attachments:
            view = ui_components.ReviewView()
            file_review = await attachment.to_file()
            
            await review_channel.send(
                content=f"New world record sent from {message.author.mention}",
                file=file_review,
                view=view
            )
            
        await message.channel.send(f"{message.author.mention}, your world record has been sent for review!", delete_after=5)

    await bot.process_commands(message)

@bot.event
async def on_raw_message_edit(payload):
    """Sensore: si accorge se modifichi un testo esistente nel database"""
    if payload.channel_id == config.WR_CHANNEL_ID:
        await rankings.trigger_ranking_update(bot)
        await rankings.trigger_rounds_update(bot)

@bot.event
async def on_raw_message_delete(payload):
    """Sensore: si accorge se elimini un record dal database"""
    if payload.channel_id == config.WR_CHANNEL_ID:
        await rankings.trigger_ranking_update(bot)
        await rankings.trigger_rounds_update(bot)

# Avvio del bot
if __name__ == "__main__":
    bot.run(config.TOKEN)
