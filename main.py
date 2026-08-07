import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
from dotenv import load_dotenv
import io
from PIL import Image
import pytesseract
import sys

# --- CONFIGURAZIONE OCR MULTI-PIATTAFORMA ---
if sys.platform == 'win32':
    # Se il bot rileva che è su Windows (il tuo PC), usa questo percorso:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    # Su Linux (Render), il sistema sa già dove si trova una volta installato
    pass

# --- SEZIONE PER MANTENERE IL BOT ATTIVO SU RENDER ---
from flask import Flask
from threading import Thread

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

# 1. Caricamento in sicurezza del Token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 2. Configurazione Intents e creazione del Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- ID REALI ---
REVIEW_CHANNEL_ID = 1535055543033532467    
UPDATES_CHANNEL_ID = 1535055543033532467   
ADMIN_ID = 715247279141027890              
MIO_ID = 715247279141027890                
SUBMISSION_CHANNEL_ID = 123456789012345678 # ID di #pb-share

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
        for child in self.original_view.children:
            child.disabled = True
            
        await interaction.response.edit_message(view=self.original_view)
        
        channel = bot.get_channel(UPDATES_CHANNEL_ID)
        testo_record = f'```\n{self.build_name.value} : {self.time_val.value} - {self.player_name.value}\n```'
        
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
        await interaction.response.send_modal(WRModal(self.attachment, self))

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        admin_user = await bot.fetch_user(ADMIN_ID)
        await admin_user.send(f"Hai rifiutato questo screen inviato da {self.original_author.mention}:\n{self.attachment.url}")
        
        await interaction.followup.send("Wr rifiutato. Lo screen è stato salvato in DM.", ephemeral=True)

# 5. Evento principale di ascolto messaggi
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != SUBMISSION_CHANNEL_ID:
        await bot.process_commands(message)
        return

    has_media = len(message.attachments) > 0
    has_tag = any(mention.id == MIO_ID for mention in message.mentions)

    if has_media and has_tag:
        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)
        
        for attachment in message.attachments:
            is_valid_submission = False
            
            # Controlla se è un'immagine
            if attachment.content_type and attachment.content_type.startswith('image/'):
                # Scarica l'immagine in memoria (senza salvarla sul disco)
                image_bytes = await attachment.read()
                img = Image.open(io.BytesIO(image_bytes))
                
                # Applica l'OCR per estrarre il testo e convertilo in minuscolo
                testo_estratto = pytesseract.image_to_string(img).lower()
                
                # Controlla le parole chiave della scoreboard di Fear Games
                if "speedbuilders" in testo_estratto or "costruzione" in testo_estratto:
                    is_valid_submission = True
            
            # Se è un video, lo accettiamo a prescindere per la revisione manuale
            elif attachment.content_type and attachment.content_type.startswith('video/'):
                is_valid_submission = True
                
            # Se è valido, crea i tasti e manda in revisione
            if is_valid_submission:
                view = ReviewView(attachment, message.author)
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