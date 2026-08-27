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
    view = ReviewView()
    file_review = await image.to_file()

    # Invia il messaggio fasullo nel canale di revisione
    await review_channel.send(
        content=f"New world record sent from {player.mention}",
        file=file_review,
        view=view
    )

    # Ti conferma che è andato tutto a buon fine senza che nessuno lo legga
    await interaction.followup.send(f"🥷 ✅ Operazione fantasma completata! Screenshot inviato in revisione per conto di {player.mention}.", ephemeral=True)

async def setup_hook():
    await database_utils.init_pool()
    bot.add_view(ui_components.EditWRView(bot)) # <-- Questa è la magia!
    print("🗄️ Database e Viste Persistenti inizializzati!")

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} avviato con successo e collegato al Cloud!")

    # --- REGISTRA I BOTTONI IMMORTALI QUI ---
    bot.add_view(ReviewView())

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
