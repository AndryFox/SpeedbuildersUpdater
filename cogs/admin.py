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

    # --- FUNZIONE DI AUTOCOMPLETAMENTO PER GLI ALIAS ---
    async def alias_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        current_lower = current.lower()
        choices = []
        
        for old_name, new_name in database_utils.ALIASES_CACHE.items():
            # Saltiamo le voci "auto-riferite" create per la sicurezza delle maiuscole
            if old_name == new_name.lower():
                continue
                
            if not current_lower or current_lower in old_name.lower() or current_lower in new_name.lower():
                label = f"{old_name} ➔ {new_name}"
                choices.append(app_commands.Choice(name=label[:100], value=old_name))
                
        return sorted(choices, key=lambda x: x.name.lower())[:25]

    # --- 1. COMANDO MANUAL SUBMIT ---
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

    # --- 2. COMANDO ADD ALIAS ---
    @app_commands.command(name="add_alias", description="🔧 Unisce i record di un vecchio nome al nuovo nome (Solo Admin)")
    @app_commands.describe(vecchio_nome="Il nome vecchio (es. blaagoosb)", nuovo_nome="Il nome corretto (es. M2xD)")
    @app_commands.default_permissions(administrator=True)
    async def add_alias(self, interaction: discord.Interaction, vecchio_nome: str, nuovo_nome: str):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        v_name = vecchio_nome.lower().strip()
        nuovo_nome = nuovo_nome.strip()

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
           
        await interaction.followup.send(f"✅ Identità unite! Tutti i record passati e futuri di `{vecchio_nome}` apparterranno a **{nuovo_nome}**.", ephemeral=True)
        await database_utils.log_action(
            interaction.user.id, 
            "ADD_ALIAS", 
            f"Unito vecchio nome '{vecchio_nome}' nel nuovo nome '{nuovo_nome}'"
        )

    # --- 3. COMANDO REMOVE ALIAS ---
    @app_commands.command(name="remove_alias", description="🗑️ Scollega un vecchio nome (alias) dal database (Solo Admin)")
    @app_commands.describe(vecchio_nome="Seleziona o scrivi il vecchio nome da scollegare")
    @app_commands.autocomplete(vecchio_nome=alias_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def remove_alias(self, interaction: discord.Interaction, vecchio_nome: str):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        v_name = vecchio_nome.lower().strip()

        async with database_utils.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT new_name FROM Aliases WHERE old_name = $1", v_name)
            if not row:
                return await interaction.followup.send(f"⚠️ L'alias `{vecchio_nome}` non è presente nel database.", ephemeral=True)
            
            target_new_name = row['new_name']
            await conn.execute("DELETE FROM Aliases WHERE old_name = $1", v_name)

        await database_utils.load_aliases()
        await rankings.trigger_ranking_update(self.bot)

        await interaction.followup.send(f"✅ Alias rimosso! I record di `{vecchio_nome}` non sono più collegati a **{target_new_name}** e la classifica è stata aggiornata.", ephemeral=True)
        await database_utils.log_action(
            interaction.user.id,
            "REMOVE_ALIAS",
            f"Rimosso collegamento alias '{vecchio_nome}' (era unito a '{target_new_name}')"
        )

    # --- 4. COMANDO LIST ALIASES ---
    @app_commands.command(name="list_aliases", description="📜 Mostra tutti gli alias attualmente registrati (Solo Admin)")
    @app_commands.default_permissions(administrator=True)
    async def list_aliases(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        grouped = {}
        for old_n, new_n in database_utils.ALIASES_CACHE.items():
            if old_n == new_n.lower():
                continue # Ignoriamo le righe di sicurezza delle maiuscole per tenere la lista pulita
            grouped.setdefault(new_n, []).append(old_n)

        if not grouped:
            return await interaction.followup.send("📭 Nessun alias registrato al momento.", ephemeral=True)

        lines = []
        for main_player in sorted(grouped.keys(), key=lambda x: x.lower()):
            olds = ", ".join(f"`{o}`" for o in sorted(grouped[main_player]))
            lines.append(f"▸ **{main_player}** ⬅️ {olds}")

        testo = "\n".join(lines)
        if len(testo) > 3900:
            testo = testo[:3900] + "\n\n*... (limite caratteri raggiunto)*"

        embed = discord.Embed(
            title=f"🔄 Alias Registrati ({len(grouped)} giocatori principali)",
            description=testo,
            color=discord.Color.blurple()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
