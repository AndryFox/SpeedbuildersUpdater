import discord
from discord import app_commands
import config
import aiohttp

def setup_tourney_commands(bot):
    
    # --- 1. COMANDO PER INVIARE IL MESSAGGIO INIZIALE ---
    @bot.tree.command(name="setup_tourney", description="Invia il messaggio iniziale della Hall of Fame tramite Webhook")
    async def setup_tourney(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="Hall of Fame",
            url="https://il-tuo-link-qui.com", # Inserisci qui il link della Hall of Fame
            color=discord.Color.yellow(),
            description="**SBIT** (Summer tourney)\n**SBIL** (Winter tourney)\n\n"
                        "<!-- LISTA -->\n" # Questo commento invisibile ci aiuta a capire dove inserire i nomi
                        "<!-- FINE LISTA -->\n\n"
                        "Clicca su \"Hall of Fame\" e apri il link"
        )
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=session)
            msg = await webhook.send(
                embed=embed, 
                username="Tourneys Updater", # Puoi forzare il nome qui!
                avatar_url="https://i.imgur.com/tuo-link-immagine.png", # Opzionale: link diretto a un'icona
                wait=True
            )
            
        await interaction.followup.send(f"✅ Messaggio inviato! Ora copia questo ID e mettilo in config.py alla voce TOURNEY_MESSAGE_ID:\n**{msg.id}**")

    # --- 2. COMANDO PER AGGIUNGERE UN VINCITORE ---
    @bot.tree.command(name="addrole", description="Aggiunge un vincitore alla Hall of Fame")
    @app_commands.describe(torneo="Es. @SBIT Winner 2026", giocatore="Es. @Lorenz223")
    async def addrole(interaction: discord.Interaction, torneo: str, giocatore: str):
        await interaction.response.defer(ephemeral=True)
        
        if not config.TOURNEY_MESSAGE_ID:
            return await interaction.followup.send("⚠️ Errore: Devi prima impostare il TOURNEY_MESSAGE_ID in config.py!")
            
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=session)
            msg = await webhook.fetch_message(config.TOURNEY_MESSAGE_ID)
            
            vecchio_embed = msg.embeds[0]
            descrizione = vecchio_embed.description
            
            nuova_riga = f"{torneo} — {giocatore}\n"
            
            # Inseriamo la nuova riga subito prima del marcatore di fine lista
            nuova_descrizione = descrizione.replace("<!-- FINE LISTA -->\n", f"{nuova_riga}<!-- FINE LISTA -->\n")
            vecchio_embed.description = nuova_descrizione
            
            await webhook.edit_message(config.TOURNEY_MESSAGE_ID, embed=vecchio_embed)
            
        await interaction.followup.send(f"✅ Aggiunto: {torneo} — {giocatore}")

    # --- 3. COMANDO PER RIMUOVERE UN VINCITORE ---
    @bot.tree.command(name="remrole", description="Rimuove un vincitore dalla Hall of Fame")
    @app_commands.describe(torneo="Es. @SBIT Winner 2026", giocatore="Es. @Lorenz223")
    async def remrole(interaction: discord.Interaction, torneo: str, giocatore: str):
        await interaction.response.defer(ephemeral=True)
        
        if not config.TOURNEY_MESSAGE_ID:
            return await interaction.followup.send("⚠️ Errore: Devi prima impostare il TOURNEY_MESSAGE_ID in config.py!")
            
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=session)
            msg = await webhook.fetch_message(config.TOURNEY_MESSAGE_ID)
            
            vecchio_embed = msg.embeds[0]
            descrizione = vecchio_embed.description
            
            riga_da_rimuovere = f"{torneo} — {giocatore}\n"
            
            if riga_da_rimuovere in descrizione:
                nuova_descrizione = descrizione.replace(riga_da_rimuovere, "")
                vecchio_embed.description = nuova_descrizione
                await webhook.edit_message(config.TOURNEY_MESSAGE_ID, embed=vecchio_embed)
                await interaction.followup.send(f"✅ Rimosso: {torneo} — {giocatore}")
            else:
                await interaction.followup.send("⚠️ Non ho trovato questa riga esatta nell'embed. Assicurati di scriverla identica!")