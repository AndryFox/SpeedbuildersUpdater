import discord
from discord import app_commands
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
import sqlite3
import re
import asyncio
import aiohttp
import aiosqlite
import database_utils
import shutil
from datetime import datetime
from discord.ext import tasks

# Importiamo i nostri moduli
import config
import rankings
from ui_components import ReviewView
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

@tasks.loop(hours=24)
async def backup_database():
    try:
        # Ora il bot va a pescare l'ID direttamente dal tuo config!
        canale_backup = bot.get_channel(config.CANALE_BACKUP_ID)
        
        if canale_backup:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M")
            nome_file = f"speedbuilders_backup_{now}.db"
            
            # Crea un oggetto File di Discord prendendo il tuo database attuale
            file_db = discord.File("speedbuilders.db", filename=nome_file)
            
            # Invia il file nel canale privato
            await canale_backup.send(content=f"📦 **Backup automatico del {now}**", file=file_db)
            print("✅ Backup inviato su Discord con successo!")
        else:
            print("❌ Errore: Canale di backup non trovato. Controlla l'ID nel config!")
            
    except Exception as e:
        print(f"❌ Errore durante il backup automatico: {e}")

'''
@bot.tree.command(name="setup_all_builds", description="Invia i messaggi delle build e salva gli ID nel DB")
@app_commands.default_permissions(administrator=True)
async def setup_all_builds(interaction: discord.Interaction):
    if interaction.user.id != config.MIO_ID:
        return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)
        
    await interaction.response.defer(ephemeral=True)
    
    async with aiosqlite.connect("speedbuilders.db") as db:
        # 1. Crea la rubrica per gli ID se non esiste già
        await db.execute("""
            CREATE TABLE IF NOT EXISTS BuildMessages (
                build_name TEXT PRIMARY KEY,
                message_id INTEGER
            )
        """)
        await db.commit()
        
        # Svuota la vecchia rubrica nel caso lo stessimo rilanciando
        await db.execute("DELETE FROM BuildMessages")
        await db.commit()

        # 2. Estrae le mappe in ordine alfabetico perfetto (ignora maiuscole/minuscole)
        async with db.execute("SELECT DISTINCT build_name FROM WorldRecords ORDER BY build_name COLLATE NOCASE ASC") as cursor:
            rows = await cursor.fetchall()
            mappe = [row[0] for row in rows]
            
    if not mappe:
        return await interaction.followup.send("⚠️ Il database è vuoto!")

    await interaction.followup.send(f"⏳ Inizio a inviare **{len(mappe)}** messaggi e a salvare gli ID...\n*Potrebbe volerci qualche minuto.*")

    # 3. Invia i messaggi e cattura gli ID
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.WORLD_RECORDS_WEBHOOK_URL, session=session)
        avatar_url = bot.user.avatar.url if bot.user.avatar else None
        
        async with aiosqlite.connect("speedbuilders.db") as db:
            for nome_mappa in mappe:
                testo_formattato = await database_utils.generate_build_message(nome_mappa)
                
                # wait=True è la magia: dice a Discord "aspetta di averlo inviato e restituiscimi i dati del messaggio"
                messaggio_inviato = await webhook.send(
                    content=testo_formattato, 
                    username="FearGames Records", 
                    avatar_url=avatar_url,
                    wait=True 
                )
                
                # Salva il nome della mappa e il suo ID univoco nel database
                await db.execute(
                    "INSERT INTO BuildMessages (build_name, message_id) VALUES (?, ?)", 
                    (nome_mappa, messaggio_inviato.id)
                )
                await db.commit()
                
                # Pausa per i limiti di Discord
                await asyncio.sleep(1.5)
            
    try:
        await interaction.user.send(f"✅ Finito! Ho inviato tutti i messaggi e ho salvato i loro ID in cassaforte.")
    except discord.Forbidden:
        pass
'''

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} avviato con successo e file modulari collegati!")

    # --- AVVIA IL CICLO DI BACKUP ---
    if not backup_database.is_running():
        backup_database.start()

    # --- REGISTRA I BOTTONI IMMORTALI QUI ---
    bot.add_view(ReviewView())

    setup_tourney_commands(bot)
    setup_rankings_commands(bot)

    # 1. Puliamo i comandi doppi specifici del server
    IL_MIO_SERVER = discord.Object(id=935816490039533621) 
    
    bot.tree.clear_commands(guild=IL_MIO_SERVER) 
    bot.tree.copy_global_to(guild=IL_MIO_SERVER) 
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
            view = ReviewView()
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
