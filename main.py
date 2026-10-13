import discord
from discord.ext import commands
import os
from aiohttp import web

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

class SpeedBuildersBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 1. Inizializziamo il database
        await database_utils.init_pool()
        await database_utils.load_aliases()
        
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
