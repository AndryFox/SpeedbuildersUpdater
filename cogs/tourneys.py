import discord
from discord import app_commands
from discord.ext import commands
import config
import aiohttp
import database_utils

class Tournaments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_hof_webhook(self):
        """Rigenera l'Embed dai dati di Supabase e aggiorna il messaggio Webhook."""
        testo = await database_utils.generate_hof_embed_text()
        embed = discord.Embed(color=discord.Color.yellow(), description=testo)
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.TOURNEY_WEBHOOK_URL, session=session)
            await webhook.edit_message(config.TOURNEY_MESSAGE_ID, embed=embed)

    # --- 1. COMANDO SETUP INIZIALE (Ora legge già da Supabase!) ---
    @app_commands.command(name="setup_tourney", description="Invia il messaggio iniziale della Hall of Fame (Solo Admin)")
    @app_commands.default_permissions(administrator=True)
    async def setup_tourney(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Questo comando è riservato allo sviluppatore.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        testo = await database_utils.generate_hof_embed_text()
        embed = discord.Embed(color=discord.Color.yellow(), description=testo)
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.TOURNEY_WEBHOOK_URL, session=session)
            msg = await webhook.send(embed=embed, username="Tourneys Updater", wait=True)
            
        await interaction.followup.send(f"✅ Messaggio inviato con i dati di Supabase! ID per config.py:\n**{msg.id}**", ephemeral=True)

    # --- 2. AGGIUNGI O MODIFICA UN TORNEO SU SUPABASE ---
    @app_commands.command(name="set_hof", description="🏆 Salva il podio di un torneo su Supabase e aggiorna la Hall of Fame")
    @app_commands.describe(
        torneo="Scegli tra SBIT (Summer) e SBIL (Winter)",
        edizione="Anno o nome dell'edizione (es. 2026)",
        primo="Vincitore (1° Posto)",
        secondo="Finalista (2° Posto)",
        terzo="Terzo classificato (3° Posto)",
        note="Opzionale: dettagli extra (es. punteggio finale)"
    )
    @app_commands.choices(torneo=[
        app_commands.Choice(name="☀️ SBIT (Summer Tourney)", value="SBIT"),
        app_commands.Choice(name="❄️ SBIL (Winter Tourney)", value="SBIL")
    ])
    @app_commands.default_permissions(administrator=True)
    async def set_hof(self, interaction: discord.Interaction, torneo: str, edizione: str, primo: str, secondo: str, terzo: str, note: str = ""):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        await database_utils.upsert_tourney_hof(torneo, edizione, primo, secondo, terzo, note)
        await self.update_hof_webhook()

        await database_utils.log_action(
            interaction.user.id,
            "SET_HOF",
            f"Salvato podio {torneo} {edizione}: 1° {primo}, 2° {secondo}, 3° {terzo}"
        )
        await interaction.followup.send(f"✅ Podio di **{torneo} {edizione}** salvato su Supabase e Hall of Fame aggiornata!", ephemeral=True)

    # --- 3. RIMUOVI UN TORNEO DA SUPABASE ---
    @app_commands.command(name="remove_hof", description="🗑️ Rimuove un'edizione del torneo da Supabase e aggiorna la Hall of Fame")
    @app_commands.choices(torneo=[
        app_commands.Choice(name="☀️ SBIT (Summer Tourney)", value="SBIT"),
        app_commands.Choice(name="❄️ SBIL (Winter Tourney)", value="SBIL")
    ])
    @app_commands.default_permissions(administrator=True)
    async def remove_hof(self, interaction: discord.Interaction, torneo: str, edizione: str):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        eliminato = await database_utils.delete_tourney_hof(torneo, edizione)
        if not eliminato:
            return await interaction.followup.send(f"⚠️ Nessun torneo **{torneo} {edizione}** trovato nel database.", ephemeral=True)

        await self.update_hof_webhook()
        await database_utils.log_action(interaction.user.id, "REMOVE_HOF", f"Rimosso torneo {torneo} {edizione}")
        await interaction.followup.send(f"✅ Torneo **{torneo} {edizione}** rimosso da Supabase e Hall of Fame aggiornata!", ephemeral=True)

    # --- 4. COMANDI GESTIONE RUOLI ---
    @app_commands.command(name="addrole", description="Aggiunge un ruolo a un utente")
    @app_commands.default_permissions(administrator=True)
    async def addrole(self, interaction: discord.Interaction, ruolo: discord.Role, player: discord.Member):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            await player.add_roles(ruolo)
            await interaction.followup.send(f"✅ Ruolo {ruolo.mention} aggiunto a {player.mention}!")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Errore imprevisto: {e}")

    @app_commands.command(name="removerole", description="Rimuove un ruolo a un utente")
    @app_commands.default_permissions(administrator=True)
    async def removerole(self, interaction: discord.Interaction, ruolo: discord.Role, player: discord.Member):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            await player.remove_roles(ruolo)
            await interaction.followup.send(f"✅ Ruolo {ruolo.mention} rimosso da {player.mention}!")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Errore imprevisto: {e}")

async def setup(bot):
    await bot.add_cog(Tournaments(bot))
