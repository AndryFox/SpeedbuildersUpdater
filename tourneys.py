import discord
from discord import app_commands
import config
import aiohttp

def setup_tourney_commands(bot):
    
    # --- 1. COMMAND TO SEND THE INITIAL MESSAGE ---
    @bot.tree.command(name="setup_tourney", description="Sends the initial Hall of Fame message via Webhook")
    async def setup_tourney(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Abbiamo rimosso 'title' e 'url' e usato il Markdown '# ' per farlo grande
        embed = discord.Embed(
            color=discord.Color.yellow(),
            description="# Hall of Fame\n\n"
                        "**SBIT** (Summer tourney)\n"
                        "**SBIL** (Winter tourney)\n\n"
                        "<!-- START LIST -->\n" 
                        "<!-- END LIST -->\n"
        )
        
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=session)
            msg = await webhook.send(
                embed=embed, 
                username="Tourneys Updater",
                wait=True
            )
            
        await interaction.followup.send(f"✅ Message sent! Now copy this ID and put it in config.py as TOURNEY_MESSAGE_ID:\n**{msg.id}**")

    # --- 2. COMMAND TO ADD A WINNER ---
    @bot.tree.command(name="addrole", description="Adds a winner to the Hall of Fame")
    @app_commands.describe(tourney="E.g. @SBIT Winner 2026", player="E.g. @Lorenz223")
    async def addrole(interaction: discord.Interaction, tourney: str, player: str):
        await interaction.response.defer(ephemeral=True)
        
        if not config.TOURNEY_MESSAGE_ID:
            return await interaction.followup.send("⚠️ Error: You must set the TOURNEY_MESSAGE_ID in config.py first!")
            
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=session)
            msg = await webhook.fetch_message(config.TOURNEY_MESSAGE_ID)
            
            old_embed = msg.embeds[0]
            description = old_embed.description
            
            new_row = f"{tourney} — {player}\n"
            
            # Sostituiamo usando i nuovi tag in inglese
            new_description = description.replace("<!-- END LIST -->\n", f"{new_row}<!-- END LIST -->\n")
            old_embed.description = new_description
            
            await webhook.edit_message(config.TOURNEY_MESSAGE_ID, embed=old_embed)
            
        await interaction.followup.send(f"✅ Added: {tourney} — {player}")

    # --- 3. COMMAND TO REMOVE A WINNER ---
    @bot.tree.command(name="remrole", description="Removes a winner from the Hall of Fame")
    @app_commands.describe(tourney="E.g. @SBIT Winner 2026", player="E.g. @Lorenz223")
    async def remrole(interaction: discord.Interaction, tourney: str, player: str):
        await interaction.response.defer(ephemeral=True)
        
        if not config.TOURNEY_MESSAGE_ID:
            return await interaction.followup.send("⚠️ Error: You must set the TOURNEY_MESSAGE_ID in config.py first!")
            
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=session)
            msg = await webhook.fetch_message(config.TOURNEY_MESSAGE_ID)
            
            old_embed = msg.embeds[0]
            description = old_embed.description
            
            row_to_remove = f"{tourney} — {player}\n"
            
            if row_to_remove in description:
                new_description = description.replace(row_to_remove, "")
                old_embed.description = new_description
                await webhook.edit_message(config.TOURNEY_MESSAGE_ID, embed=old_embed)
                await interaction.followup.send(f"✅ Removed: {tourney} — {player}")
            else:
                await interaction.followup.send("⚠️ Exact row not found in the embed. Make sure you typed it correctly!")