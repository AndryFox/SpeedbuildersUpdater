import discord
from discord.ext import commands
import traceback

import config
import rankings
import ui_components
from tourneys import setup_tourney_commands
from rankings import setup_rankings_commands

class BotEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Leghiamo la gestione globale degli errori per i comandi Slash
        self.bot.tree.on_error = self.on_app_command_error

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ Bot {self.bot.user} avviato con successo e collegato al Cloud!")

        setup_tourney_commands(self.bot)
        setup_rankings_commands(self.bot)  

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Sensore per aggiornamento manuale su WR Channel
        if message.channel.id == config.WR_CHANNEL_ID:
            await rankings.trigger_ranking_update(self.bot)

        if message.channel.id != config.SUBMISSION_CHANNEL_ID:
            return

        # Gestione record inseriti dai player
        has_media = len(message.attachments) > 0
        has_tag = any(mention.id == config.MIO_ID for mention in message.mentions)

        if has_media and has_tag:
            review_channel = self.bot.get_channel(config.REVIEW_CHANNEL_ID)
            
            for attachment in message.attachments:
                view = ui_components.ReviewView()
                file_review = await attachment.to_file()
                
                await review_channel.send(
                    content=f"New world record sent from {message.author.mention}",
                    file=file_review,
                    view=view
                )
                
            await message.channel.send(f"{message.author.mention}, your world record has been sent for review!", delete_after=5)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if payload.channel_id == config.WR_CHANNEL_ID:
            await rankings.trigger_ranking_update(self.bot)
            await rankings.trigger_rounds_update(self.bot)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.channel_id == config.WR_CHANNEL_ID:
            await rankings.trigger_ranking_update(self.bot)
            await rankings.trigger_rounds_update(self.bot)

    @commands.Cog.listener()
    async def on_error(self, event_method, *args, **kwargs):
        log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            error_msg = traceback.format_exc()
            if len(error_msg) > 1900:
                error_msg = error_msg[-1900:]
            await log_channel.send(f"⚠️ **Errore Critico (Evento: {event_method})**\n```py\n{error_msg}\n```")

    # Questo non ha @commands.Cog.listener() perché viene agganciato nel __init__!
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"⚠️ **Errore nel comando `/{interaction.command.name}` usato da {interaction.user.name}**\n```py\n{error}\n```")
        
        if interaction.response.is_done():
            await interaction.followup.send("❌ Ops! Si è verificato un errore interno. L'amministratore è stato avvisato.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ops! Si è verificato un errore interno. L'amministratore è stato avvisato.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotEvents(bot))
