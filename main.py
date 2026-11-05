import discord
from discord.ext import commands
import os
from aiohttp import web
import asyncio
from discord.ext import tasks
import rankings

# Importiamo i nostri moduli necessari per l'avvio
import config
import database_utils
from ui_components import EditWRView, ReviewView, EditRoundView

async def start_dummy_server():
    """Crea un server web fittizio per accontentare Render."""
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is alive and running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Server web fittizio avviato sulla porta {port} per Render")

# --- SCANSIONE AUTOMATICA CAMBI NOME (OGNI 24 ORE) ---
@tasks.loop(hours=24)
async def auto_update_uuids():
    print("🔄 Avvio scansione automatica UUID per cambi nome...")
    async with database_utils.pool.acquire() as conn:
        rows = await conn.fetch("SELECT uuid, main_name FROM player_uuids")
    
    changes_made = False
    for row in rows:
        uuid = row['uuid']
        old_main_name = row['main_name']
        
        # Chiediamo a Mojang come si chiama OGGI questo UUID
        current_name = await database_utils.get_name_from_uuid(uuid)
        
        if current_name and current_name.lower() != old_main_name.lower():
            print(f"✨ Cambio nome rilevato da Mojang: {old_main_name} -> {current_name}")
            
            async with database_utils.pool.acquire() as conn:
                # 1. Aggiorna il nome definitivo nella tabella UUID
                await conn.execute("UPDATE player_uuids SET main_name = $1 WHERE uuid = $2", current_name, uuid)
                
                # 2. Registra in automatico il vecchio nome come Alias
                await conn.execute(
                    "INSERT INTO Aliases (old_name, new_name) VALUES ($1, $2) ON CONFLICT (old_name) DO UPDATE SET new_name = $2",
                    old_main_name.lower(), current_name
                )
            changes_made = True
        
        # Pausa vitale di 1.5 secondi per non farsi bloccare l'IP da Mojang (Rate Limit)
        await asyncio.sleep(1.5)
        
    if changes_made:
        await database_utils.load_aliases()
        await rankings.trigger_ranking_update(bot) # Assicurati che "bot" sia il nome della tua variabile bot
        print("✅ Scansione UUID completata: Database e Classifiche aggiornati da soli!")
    else:
        print("✅ Scansione UUID completata: Nessun giocatore ha cambiato nome oggi.")

@auto_update_uuids.before_loop
async def before_auto_update():
    await bot.wait_until_ready()

class SpeedBuildersBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 1. Inizializziamo il database
        await database_utils.init_pool()
        await database_utils.load_aliases()
        
        # Fai partire la scansione silenziosa
        auto_update_uuids.start()
        
        # 2. Carichiamo automaticamente tutti i moduli (Cogs) dalla cartella 'cogs'
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"⚙️ Modulo (Cog) caricato: {filename}")
        
        # 3. Avviamo le Viste Persistenti per renderle immortali
        self.add_view(EditWRView())
        self.add_view(ReviewView()) 
        self.add_view(EditRoundView())
        
        # 4. Sincronizzazione Comandi Slash (Unica e Sicura)
        IL_MIO_SERVER = discord.Object(id=935816490039533621) 
        self.tree.clear_commands(guild=IL_MIO_SERVER) 
        await self.tree.sync(guild=IL_MIO_SERVER)
        await self.tree.sync() # Sincronizzazione globale
        
        # 5. Avviamo il server fittizio per Render in background
        self.loop.create_task(start_dummy_server())
        
        print("🗄️ Database, Viste e Comandi inizializzati!")

# Avvio del bot
bot = SpeedBuildersBot()

if __name__ == "__main__":
    bot.run(config.TOKEN)
