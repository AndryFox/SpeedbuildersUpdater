import discord
from discord import app_commands
from discord.ext import commands
import config
import aiohttp

class Tournaments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_tourney", description="Send the initial Tourney message")
    @app_commands.default_permissions(administrator=True)
    async def setup_tourney(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Questo comando è riservato allo sviluppatore.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            color=discord.Color.yellow(),
            description="# Hall of Fame\n\n**SBIT** (Summer tourney)\n**SBIL** (Winter tourney)"
        )
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.TOURNEY_WEBHOOK_URL, session=session)
            msg = await webhook.send(embed=embed, username="Tourneys Updater", wait=True)
            
        await interaction.followup.send(f"✅ Message sent! ID per config.py:\n**{msg.id}**")

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
