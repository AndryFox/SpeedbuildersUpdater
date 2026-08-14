import discord
from discord import app_commands
import config
import aiohttp

def setup_tourney_commands(bot):
    
    # --- 1. COMMAND TO SEND THE INITIAL MESSAGE ---
    @bot.tree.command(name="setup_tourney", description="Send the initial Tourney message")
    @app_commands.default_permissions(administrator=True) # Nasconde il comando dal menu agli utenti normali
    async def setup_tourney(interaction: discord.Interaction):
        # Blocco di sicurezza: se l'ID non è il tuo, blocca l'esecuzione
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Questo comando è riservato allo sviluppatore.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            color=discord.Color.yellow(),
            description="# Hall of Fame\n\n"
                        "**SBIT** (Summer tourney)\n"
                        "**SBIL** (Winter tourney)"
        )
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.TOURNEY_WEBHOOK_URL, session=session)
            msg = await webhook.send(
                embed=embed, 
                username="Tourneys Updater",
                wait=True
            )
            
        await interaction.followup.send(f"✅ Message sent! Now copy this ID and put it in config.py as TOURNEY_MESSAGE_ID:\n**{msg.id}**")

    # --- 2. COMMAND TO ADD A ROLE ---
    @bot.tree.command(name="addrole", description="Aggiunge un ruolo a un utente")
    @app_commands.default_permissions(administrator=True)
    async def addrole(interaction: discord.Interaction, ruolo: discord.Role, player: discord.Member):
        # Blocco di sicurezza
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Questo comando è riservato allo sviluppatore.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            await player.add_roles(ruolo)
            await interaction.followup.send(f"✅ Ruolo {ruolo.mention} aggiunto a {player.mention} con successo!")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Errore: Il bot non ha i permessi per assegnare questo ruolo (assicurati che il ruolo del bot sia più in alto nella gerarchia).")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Si è verificato un errore imprevisto: {e}")

    # --- 3. COMMAND TO REMOVE A ROLE ---
    @bot.tree.command(name="removerole", description="Rimuove un ruolo a un utente")
    @app_commands.default_permissions(administrator=True)
    async def removerole(interaction: discord.Interaction, ruolo: discord.Role, player: discord.Member):
        # Blocco di sicurezza
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Questo comando è riservato allo sviluppatore.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            await player.remove_roles(ruolo)
            await interaction.followup.send(f"✅ Ruolo {ruolo.mention} rimosso da {player.mention} con successo!")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Errore: Il bot non ha i permessi per rimuovere questo ruolo.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Si è verificato un errore imprevisto: {e}")
