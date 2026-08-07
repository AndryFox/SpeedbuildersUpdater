import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
from dotenv import load_dotenv

# --- SEZIONE PER MANTENERE IL BOT ATTIVO SU RENDER ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot Online!"

def run():
    # Render assegna automaticamente una porta nella variabile d'ambiente PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    # Avvia il server web in un thread separato per non bloccare il bot di Discord
    t = Thread(target=run)
    t.start()

# Avvia il server web anti-sospensione
keep_alive()
# ----------------------------------------------------

# 1. Caricamento in sicurezza del Token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 2. Configurazione Intents e creazione del Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- ID REALI ---
REVIEW_CHANNEL_ID = 1535055543033532467  # ID del canale di revisione 
UPDATES_CHANNEL_ID = 1535055543033532467 # ID del canale finale 
ADMIN_ID = 715247279141027890            # ID Admin per i DM
MIO_ID = 715247279141027890              # ID per il tag

# 3. Finestra di compilazione (Modal)
class WRModal(Modal, title='Aggiornamento World Record'):
    build_name = TextInput(label='Nome build', placeholder='Es. Caveau', required=True)
    time_val = TextInput(label='Time', placeholder='Es. 6.7', required=True)
    player_name = TextInput(label='Nome Giocatore', placeholder='Es. AndryFox_14', required=True)

    def __init__(self, attachment, original_view):
        super().__init__()
        self.attachment = attachment
        self.original_view = original_view

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Spegne i tasti della View
        for child in self.original_view.children:
            child.disabled = True
            
        # 2. Disabilita i tasti a schermo in modo istantaneo e chiude la finestra
        await interaction.response.edit_message(view=self.original_view)
        
        # 3. Manda il messaggio nel canale finale con il blocco di codice scuro
        channel = bot.get_channel(UPDATES_CHANNEL_ID)
        testo_record = f'```\n{self.build_name.value} : {self.time_val.value} - {self.player_name.value}\n```'
        
        # 4. Scarica e invia il file nativo per nascondere l'URL testuale
        file_da_inviare = await self.attachment.to_file()
        await channel.send(content=testo_record, file=file_da_inviare)

# 4. Tasti sotto lo screen (View)
class ReviewView(View):
    def __init__(self, attachment, original_author):
        super().__init__(timeout=None)
        self.attachment = attachment
        self.original_author = original_author

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: Button):
        # Apre il modal passandogli l'allegato
        await interaction.response.send_modal(WRModal(self.attachment, self))

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        # Spegne subito i tasti 
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Invia l'immagine nei tuoi DM
        admin_user = await bot.fetch_user(ADMIN_ID)
        await admin_user.send(f"Hai rifiutato questo screen inviato da {self.original_author.mention}:\n{self.attachment.url}")
        
        # Conferma visibile solo a te
        await interaction.followup.send("Wr rifiutato. Lo screen è stato salvato in DM.", ephemeral=True)

# 5. Evento principale di ascolto messaggi
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    has_media = len(message.attachments) > 0
    has_tag = any(mention.id == MIO_ID for mention in message.mentions)

    if has_media and has_tag:
        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)
        
        for attachment in message.attachments:
            view = ReviewView(attachment, message.author)
            
            # Usiamo to_file() anche per il canale di revisione
            file_review = await attachment.to_file()
            
            await review_channel.send(
                content=f"New world record from {message.author.mention}:",
                file=file_review,
                view=view
            )
            
        await message.channel.send(f"{message.author.mention}, your world record has been sent for review!", delete_after=5)

    await bot.process_commands(message)

# 6. Avvio del bot
bot.run(TOKEN)
