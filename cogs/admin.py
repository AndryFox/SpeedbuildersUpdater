import discord
from discord import app_commands
from discord.ext import commands

import config
import database_utils
import ui_components
import rankings

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="manual_submit", description="Invia un record in revisione per conto di un altro utente (Solo Admin)")
    @app_commands.describe(player="L'utente che ha fatto il record", image="Lo screenshot del record")
    @app_commands.default_permissions(administrator=True)
    async def manual_submit(self, interaction: discord.Interaction, player: discord.Member, image: discord.Attachment):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        review_channel = self.bot.get_channel(config.REVIEW_CHANNEL_ID)
        
        if not review_channel:
            return await interaction.followup.send("❌ Errore: Canale di revisione non trovato.", ephemeral=True)

        view = ui_components.ReviewView()
        file_review = await image.to_file()

        await review_channel.send(
            content=f"New world record sent from {player.mention}",
            file=file_review,
            view=view
        )

        await interaction.followup.send(f"🥷 ✅ Operazione fantasma completata! Screenshot inviato in revisione per conto di {player.mention}.", ephemeral=True)

    @app_commands.command(name="add_alias", description="🔧 Unisce i record di un vecchio nome al nuovo nome (Solo Admin)")
    @app_commands.describe(vecchio_nome="Il nome vecchio (es. blaagoosb)", nuovo_nome="Il nome corretto (es. M2xD)")
    @app_commands.default_permissions(administrator=True)
    async def add_alias(self, interaction: discord.Interaction, vecchio_nome: str, nuovo_nome: str):
        v_name = vecchio_nome.lower()

        async with database_utils.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO Aliases (old_name, new_name) VALUES ($1, $2) ON CONFLICT (old_name) DO UPDATE SET new_name = $2", 
                v_name, nuovo_nome
            )
            n_name_lower = nuovo_nome.lower()
            if v_name != n_name_lower:
                await conn.execute(
                    "INSERT INTO Aliases (old_name, new_name) VALUES ($1, $2) ON CONFLICT (old_name) DO UPDATE SET new_name = $2", 
                    n_name_lower, nuovo_nome
                )

        await database_utils.load_aliases()
        await rankings.trigger_ranking_update(self.bot)
           
        await interaction.response.send_message(f"✅ Identità unite! Tutti i record passati e futuri di `{vecchio_nome}` apparterranno a **{nuovo_nome}**.", ephemeral=True)
        await database_utils.log_action(
            interaction.user.id, 
            "ADD_ALIAS", 
            f"Unito vecchio nome '{vecchio_nome}' nel nuovo nome '{nuovo_nome}'"
        )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))