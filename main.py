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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
# ----------------------------------------------------

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="§", intents=intents)

# --- ID REALI ---
REVIEW_CHANNEL_ID = 1535055543033532467    
UPDATES_CHANNEL_ID = 1092204135505461349   
ADMIN_ID = 715247279141027890              
MIO_ID = 715247279141027890                
SUBMISSION_CHANNEL_ID = 1300032038165938176 # SOSTITUISCI CON L'ID DI #pb-share
DATABASE_CHANNEL_ID = 1252593722286276680  # Il canale dove tieni la classifica aggiornata a mano

# --- FUNZIONE PER LEGGERE LA CHAT DI DISCORD COME DATABASE ---
async def get_wr_from_database(build_name):
    channel = bot.get_channel(DATABASE_CHANNEL_ID)
    
    if not channel:
        print("ERRORE: Il bot non riesce a vedere il canale database!")
        return None, None
        
    build_clean = build_name.lower().strip()
    
    # Scansiona gli ultimi 500 messaggi nel canale
    async for message in channel.history(limit=500):
        if not message.content:
            continue
            
        lines = message.content.split('\n')
        for i, line in enumerate(lines):
            
            # Pulizia base per trovare la riga della build
            clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").strip()
            
            # Cerca "build:" e il nome della build
            if clean_line.startswith("build:") and build_clean in clean_line:
                
                # Guarda le prossime 3 righe, così se c'è uno spazio vuoto non si blocca
                for j in range(i + 1, min(i + 4, len(lines))):
                    
                    # Puliamo COMPLETAMENTE la riga del record dai simboli di formattazione di Discord
                    top_line = lines[j]
                    top_line = top_line.replace(">", "").replace("_", "").replace("*", "").replace("~", "").strip()
                    top_line = top_line.replace("–", "-").replace("—", "-")
                    
                    # Cerchiamo il trattino che separa l'emoji dal nome
                    if "-" in top_line:
                        # Prende tutto quello che c'è dopo il PRIMO trattino
                        data_str = top_line.split("-", 1)[1].strip() 
                        
                        if data_str != "": 
                            # Taglia partendo dall'ultimo spazio per separare nome e tempo
                            parts = data_str.rsplit(' ', 1)
                            if len(parts) == 2:
                                player = parts[0].strip()
                                
                                # Puliamo il tempo da eventuali lettere "s" rimaste
                                time_str = parts[1].lower().replace("s", "").replace("sec", "").strip()
                                
                                try:
                                    time_val = float(time_str)
                                    return player, time_val
                                except ValueError:
                                    print(f"ERRORE: Impossibile leggere il tempo {time_str}")
                                    pass
                        
                        # Trovato il primo posto (la prima riga col trattino), fermiamo il mini-ciclo
                        break
                        
    return None, None

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
        # Spegne i tasti della View a schermo
        for child in self.original_view.children:
            child.disabled = True
            
        await interaction.response.edit_message(view=self.original_view)
        
        build_key = self.build_name.value.lower().strip()
        current_player = self.player_name.value.strip()
        
        try:
            new_time = float(self.time_val.value)
        except ValueError:
            new_time = 0.0

        extra_message = ""
        
        # --- RICERCA DEL VECCHIO RECORD NELLA CHAT ---
        old_player, old_time = await get_wr_from_database(build_key)
        
        if old_player and old_time:
            if new_time < old_time:
                diff = round(old_time - new_time, 3) 
                
                nomi_vecchi = [p.strip() for p in old_player.split('/')]
                nomi_vecchi_lower = [p.lower() for p in nomi_vecchi]
                
                if current_player.lower() in nomi_vecchi_lower:
                    if len(nomi_vecchi) > 1:
                        altri_giocatori = [p for p in nomi_vecchi if p.lower() != current_player.lower()]
                        altri_formattati = "/".join(altri_giocatori)
                        extra_message = f"\n{current_player} improved their own wr and beat {altri_formattati} by {diff}s"
                    else:
                        extra_message = f"\n{current_player} improved their own wr by {diff}s"
                else:
                    extra_message = f"\n{current_player} beat {old_player}'s old wr by {diff}s"
                    
            elif new_time == old_time:
                nomi_vecchi = [p.strip().lower() for p in old_player.split('/')]
                
                if current_player.lower() in nomi_vecchi:
                    extra_message = f"\n{current_player} tied their own wr"
                else:
                    extra_message = f"\n{current_player} tied {old_player}'s wr"
        
        # --- MESSAGGIO FINALE ---
        channel = bot.get_channel(UPDATES_CHANNEL_ID)
        testo_record = f'```\n{self.build_name.value} : {self.time_val.value} - {self.player_name.value}{extra_message}\n```'
        
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

    @discord.ui.button(label="Sim Wr", style=discord.ButtonStyle.secondary)
    async def sim_wr_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Archiviato come Sim WR. Il messaggio è stato rimosso.", ephemeral=True)
        await interaction.message.delete()

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def remove_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Immagine rimossa perché non inerente.", ephemeral=True)
        await interaction.message.delete()

# 5. Evento principale di ascolto messaggi
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Filtra i messaggi che non sono nel canale corretto
    if message.channel.id != SUBMISSION_CHANNEL_ID:
        await bot.process_commands(message)
        return

    has_media = len(message.attachments) > 0
    has_tag = any(mention.id == MIO_ID for mention in message.mentions)

    if has_media and has_tag:
        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)
        
        for attachment in message.attachments:
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