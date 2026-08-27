import discord
import re
from discord.ui import Button, View, Modal, TextInput
import config
import rankings
from database_utils import get_main_name, get_wr_count, get_sim_wr_link
import time
import asyncpg
import aiohttp
import database_utils

# --- MODAL PER IL LINK IMGUR ---
class ImgurModal(Modal, title="Inserisci Link Imgur"):
    imgur_link = TextInput(label="Link Imgur", placeholder="https://imgur.com/a/...", required=True)

    def __init__(self, bot, update_message, original_message, def_r, def_w, def_o, def_t):
        super().__init__()
        self.bot = bot
        self.update_message = update_message
        self.original_message = original_message
        self.def_r = def_r
        self.def_w = def_w
        self.def_o = def_o
        self.def_t = def_t

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Saltiamo la modifica del log su #wrs-updated.
        # Andiamo diretti ad aggiornare la classifica pubblica!
        current_team = f"{self.def_w.strip()} & {self.def_o.strip()}"
        rounds_int = int(self.def_r) if str(self.def_r).isdigit() else 0
        
        await rankings.add_or_update_round_record(
            self.bot, 
            rounds_int, 
            current_team, 
            self.def_t, 
            self.imgur_link.value.strip()
        )
        
        await interaction.followup.send("✅ Link Imgur aggiunto e classifica aggiornata in automatico!", ephemeral=True)

# --- VIEW PER IL TASTO EDIT (WR ROUNDS) ---
class EditRoundView(View):
    def __init__(self, bot, attachment, update_message, def_r, def_w, def_o, def_t, original_message):
        super().__init__(timeout=None)
        self.bot = bot
        self.attachment = attachment
        self.update_message = update_message
        self.def_r = def_r
        self.def_w = def_w
        self.def_o = def_o
        self.def_t = def_t 
        self.original_message = original_message

    # INSERISCI QUESTO BUTTAFUORI:
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != config.MIO_ID:
            await interaction.response.send_message("❌ Solo l'amministratore può modificare i record.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            WrRoundModal(self.bot, self.attachment, self, self.original_message,
                         is_edit=True, update_message=self.update_message,
                         def_r=self.def_r, def_w=self.def_w, def_o=self.def_o, def_t=self.def_t)
        )

    @discord.ui.button(label="Add Imgur", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def imgur_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ImgurModal(self.bot, self.update_message, self.original_message, self.def_r, self.def_w, self.def_o, self.def_t))

    @discord.ui.button(label="Undo / Reject", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def undo_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        try: await self.update_message.delete()
        except: pass
            
        rejected_channel = self.bot.get_channel(config.REJECT_CHANNEL_ID)
        author_mention = self.original_message.mentions[0].mention if self.original_message.mentions else "l'utente"
        if rejected_channel and self.attachment:
            file_to_send = await self.attachment.to_file()
            await rejected_channel.send(content=f"Screen rifiutato (dopo annullamento) da {author_mention}:", file=file_to_send)

        for child in self.children: child.disabled = True
        new_content = self.original_message.content.replace("**Accepted ✅**", "**Rejected ❌ (Annullato)**")
        await self.original_message.edit(content=new_content, view=self)
        await self.original_message.delete(delay=20)
        await interaction.followup.send("✅ Record annullato!", ephemeral=True)

# --- MODAL PER I WR ROUND ---
class WrRoundModal(Modal):
    def __init__(self, bot, attachment, original_view, original_message, is_edit=False, update_message=None, def_r="", def_w="", def_o="", def_t=""):
        super().__init__(title='Edit WR Rounds' if is_edit else 'Aggiornamento WR Rounds')
        self.bot = bot
        self.attachment = attachment
        self.original_view = original_view
        self.original_message = original_message
        self.is_edit = is_edit
        self.update_message = update_message

        self.rounds_val = TextInput(label='Numero di Round', placeholder='Es. 42', default=def_r, required=True)
        self.winner_name = TextInput(label='Nome Vincitore', placeholder='Es. Lorenz223', default=def_w, required=True)
        self.opponent_name = TextInput(label='Nome Avversario', placeholder='Es. blaagoosb', default=def_o, required=True)
        self.timestamp_val = TextInput(label='Timestamp (es. 1780327920)', placeholder='Vuoto per usare ora attuale', default=def_t, required=False)

        self.add_item(self.rounds_val)
        self.add_item(self.winner_name)
        self.add_item(self.opponent_name)
        self.add_item(self.timestamp_val)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try: new_rounds = int(self.rounds_val.value)
        except ValueError: new_rounds = 0

        current_team = f"{self.winner_name.value.strip()} & {self.opponent_name.value.strip()}"
        
        ts_input = self.timestamp_val.value.strip()
        if not ts_input: ts_input = str(int(time.time()))
        else: ts_input = "".join([c for c in ts_input if c.isdigit()])

        # Il log rimane immacolato come hai richiesto
        testo_record = f'```fix\nWR Rounds (Legit): {new_rounds} Rounds - {current_team}\n```'

        if self.is_edit:
            await self.update_message.edit(content=testo_record)
            self.original_view.def_r = self.rounds_val.value
            self.original_view.def_w = self.winner_name.value
            self.original_view.def_o = self.opponent_name.value
            self.original_view.def_t = ts_input
            await self.original_message.edit(view=self.original_view)
            
            # Stringa vuota su link conserva quello già esistente nel webhook
            await rankings.add_or_update_round_record(self.bot, new_rounds, current_team, ts_input, "")
            await interaction.followup.send("✅ Modifica salvata e classifica aggiornata!", ephemeral=True)
            
        else:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            file_da_inviare = await self.attachment.to_file()
            update_msg = await channel.send(content=testo_record, file=file_da_inviare)

            edit_view = EditRoundView(self.bot, self.attachment, update_msg, self.rounds_val.value, self.winner_name.value, self.opponent_name.value, ts_input, self.original_message)
            new_content = f"{self.original_message.content} - **Accepted ✅**"
            await self.original_message.edit(content=new_content, view=edit_view)
            
            await rankings.add_or_update_round_record(self.bot, new_rounds, current_team, ts_input, "")
            await interaction.followup.send("✅ WR Rounds inserito in classifica! (Aggiungi link Imgur dalla chat)", ephemeral=True)


# --- VIEW PER IL TASTO EDIT (WR NORMALI) ---
class EditWRView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # timeout=None rende i bottoni immortali
        self.bot = bot

    def extract_data(self, content):
        # Il bot cerca l'inchiostro simpatico nel messaggio
        match = re.search(r'\|\|#WR#\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|\|', content)
        if match:
            return match.group(1), match.group(2), float(match.group(3)), int(match.group(4))
        return None, None, 0.0, None

    @discord.ui.button(label="Edit Record", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="persistent_edit_btn")
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        build, player, time_val, update_msg_id = self.extract_data(interaction.message.content)
        if not build:
            return await interaction.response.send_message("❌ Questo è un vecchio record. Usa /manual_submit per modificarlo.", ephemeral=True)
        
        attachment = interaction.message.attachments[0] if interaction.message.attachments else None
        self.def_b = build
        self.def_p = player
        self.def_t = str(time_val)
        self.update_msg_id = update_msg_id
        
        modal = WRModal(self.bot, attachment, original_view=self, original_message=interaction.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Undo / Reject", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="persistent_undo_btn")
    async def undo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        build_key, player, time_val, update_msg_id = self.extract_data(interaction.message.content)
        if not build_key:
            return await interaction.followup.send("❌ Dati mancanti, impossibile annullare automaticamente i vecchi record.", ephemeral=True)

        updates_channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
        if updates_channel:
            try:
                msg_to_delete = await updates_channel.fetch_message(update_msg_id)
                await msg_to_delete.delete()
            except: pass

        rejected_channel = self.bot.get_channel(config.REJECT_CHANNEL_ID)
        author_mention = interaction.message.mentions[0].mention if interaction.message.mentions else "l'utente"
        if rejected_channel and interaction.message.attachments:
            file_to_send = await interaction.message.attachments[0].to_file()
            await rejected_channel.send(content=f"Screen rifiutato (dopo annullamento) da {author_mention}:", file=file_to_send)

        msg_id = None
        import database_utils 
        async with database_utils.pool.acquire() as conn:
            await conn.execute("DELETE FROM WorldRecords WHERE LOWER(build_name) = LOWER($1) AND player_name = $2 AND time = $3", build_key, player, time_val)
            row = await conn.fetchrow("SELECT message_id FROM BuildMessages WHERE LOWER(build_name) = LOWER($1)", build_key)
            if row: msg_id = row['message_id']

        if msg_id:
            testo_formattato = await database_utils.generate_build_message(build_key)
            import aiohttp
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(config.WORLD_RECORDS_WEBHOOK_URL, session=session)
                try: await webhook.edit_message(msg_id, content=testo_formattato)
                except: pass

        for child in self.children: child.disabled = True
        new_content = interaction.message.content.replace("**Accepted ✅**", "**Rejected ❌ (Annullato)**")
        new_content = re.sub(r'\n\|\|#WR#.*\|\|', '', new_content) # Puliamo i dati nascosti
        await interaction.message.edit(content=new_content, view=self)
        await interaction.message.delete(delay=20)

        # INSERISCI QUESTO: Registriamo l'annullamento
        await database_utils.log_audit(
            admin_name=interaction.user.name,
            action_type="REJECT_WR",
            target=f"Mappa: {build_key}, Giocatore: {player}",
            details=f"Tempo annullato: {time_val}"
        )
        
        import rankings
        await rankings.trigger_ranking_update(self.bot)
        await interaction.followup.send("✅ Record annullato e database ripristinato (Persistente)!", ephemeral=True)
# --- MODAL PER SIM WR ---
class SimWrModal(Modal, title='Cerca link per Sim WR'):
    build_name = TextInput(label='Nome build', placeholder='Es. Caveau', required=True)

    def __init__(self, bot, original_view, original_message):
        super().__init__()
        self.bot = bot
        self.original_view = original_view
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        for child in self.original_view.children: child.disabled = True
        new_content = f"{self.original_message.content} - **Sim WR 🔄**"
        await self.original_message.edit(content=new_content, view=self.original_view)
        await self.original_message.delete(delay=30)
        build_key = self.build_name.value.lower().strip()
        jump_url = await get_sim_wr_link(self.bot, build_key)
        if jump_url: await interaction.followup.send(f"✅ Archiviato come Sim WR.\n🔗 **Vai ad aggiornare:** {jump_url}", ephemeral=True)
        else: await interaction.followup.send("✅ Archiviato come Sim WR.\n⚠️ *(Nessun link precedente)*", ephemeral=True)

# --- MODAL WR CLASSICI ---
class WRModal(Modal):
    def __init__(self, bot, attachment, original_view, original_message, is_edit=False, update_message=None, def_b="", def_t="", def_p=""):
        super().__init__(title='Edit World Record' if is_edit else 'Aggiornamento World Record')
        self.bot = bot
        self.attachment = attachment
        self.original_view = original_view
        self.original_message = original_message
        self.is_edit = is_edit
        self.update_message = update_message

        self.build_name = TextInput(label='Nome build', placeholder='Es. Caveau', default=def_b, required=True)
        self.time_val = TextInput(label='Time', placeholder='Es. 6.7', default=def_t, required=True)
        self.player_name = TextInput(label='Nome Giocatore', placeholder='Es. AndryFox_14', default=def_p, required=True)
        self.add_item(self.build_name)
        self.add_item(self.time_val)
        self.add_item(self.player_name)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        build_key = self.build_name.value.strip()
        current_player = self.player_name.value.strip()
        current_norm = get_main_name(current_player)
        try: new_time = float(self.time_val.value.replace(',', '.'))
        except ValueError: new_time = 0.0

        async with database_utils.pool.acquire() as conn:
            if self.is_edit:
                try: old_t = float(self.original_view.def_t)
                except ValueError: old_t = 0.0
                await conn.execute(
                    "DELETE FROM WorldRecords WHERE LOWER(build_name) = LOWER($1) AND player_name = $2 AND time = $3",
                    self.original_view.def_b.strip(), self.original_view.def_p.strip(), old_t
                )

            row = await conn.fetchrow("SELECT build_name FROM WorldRecords WHERE LOWER(build_name) = LOWER($1) LIMIT 1", build_key)
            if row: 
                build_key = row['build_name']
                    
            query_old = """
                SELECT time, player_name 
                FROM WorldRecords r1 
                WHERE LOWER(build_name) = LOWER($1) 
                AND time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
            """
            old_time = None
            old_players = []
            
            rows = await conn.fetch(query_old, build_key)
            if rows:
                old_time = rows[0]['time']
                old_players = [r['player_name'] for r in rows]

            players_to_check = set([get_main_name(p) for p in old_players] + [current_norm])
            old_counts = {}
            for p in players_to_check:
                old_counts[p] = await get_wr_count(self.bot, p)

            await conn.execute("INSERT INTO WorldRecords (build_name, player_name, time) VALUES ($1, $2, $3)", build_key, current_player, new_time)
            
            new_counts = {}
            for p in players_to_check:
                new_counts[p] = await get_wr_count(self.bot, p)

            extra_message = ""
            stats_msg = "\n"
            
            if old_time is not None:
                if new_time < old_time:
                    diff = round(old_time - new_time, 3)
                    old_players_norm = [get_main_name(p) for p in old_players]
                    if current_norm in old_players_norm:
                        if len(old_players) > 1:
                            altri = [p for p in old_players if get_main_name(p) != current_norm]
                            extra_message = f"\n{current_player} improved their own wr and beat {'/'.join(altri)} by {diff}s"
                        else: extra_message = f"\n{current_player} improved their own wr by {diff}s"
                    else: extra_message = f"\n{current_player} beat {'/'.join(old_players)}'s old wr by {diff}s"
                elif new_time == old_time:
                    old_players_norm = [get_main_name(p) for p in old_players]
                    if current_norm in old_players_norm: extra_message = f"\n{current_player} tied their own wr"
                    else: extra_message = f"\n{current_player} tied {'/'.join(old_players)}'s wr"
                        
            for p_norm in players_to_check:
                disp_name = current_player if p_norm == current_norm else next((p for p in old_players if get_main_name(p) == p_norm), p_norm)
                c_old, c_new = old_counts[p_norm], new_counts[p_norm]
                if c_new > c_old: stats_msg += f"{disp_name} gained 1 wr ({c_old} -> {c_new})\n"
                elif c_new < c_old: stats_msg += f"{disp_name} lost 1 wr ({c_old} -> {c_new})\n"
                elif p_norm == current_norm: stats_msg += f"{disp_name} kept their wr count ({c_new})\n"

            testo_record = f'```\n{build_key} : {new_time} - {current_player}{extra_message}\n\n{stats_msg.strip()}\n```'
            
            jump_url = None
            msg_row = await conn.fetchrow("SELECT message_id FROM BuildMessages WHERE LOWER(build_name) = LOWER($1)", build_key)
            msg_id = msg_row['message_id'] if msg_row else None

            if msg_id:
                testo_formattato = await database_utils.generate_build_message(build_key)
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(config.WORLD_RECORDS_WEBHOOK_URL, session=session)
                    try:
                        await webhook.edit_message(msg_id, content=testo_formattato)
                        jump_url = f"https://discord.com/channels/{interaction.guild_id}/{config.WR_CHANNEL_ID}/{msg_id}"
                    except Exception as e:
                        print(f"Errore webhook edit: {e}")
            else:
                testo_formattato = await database_utils.generate_build_message(build_key)
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(config.WORLD_RECORDS_WEBHOOK_URL, session=session)
                    new_msg = await webhook.send(content=testo_formattato, wait=True)
                    jump_url = f"https://discord.com/channels/{interaction.guild_id}/{config.WR_CHANNEL_ID}/{new_msg.id}"
                    await conn.execute("INSERT INTO BuildMessages (build_name, message_id) VALUES ($1, $2)", build_key, new_msg.id)

        # INSERISCI QUESTO: Prepariamo e inviamo il log
        action = "EDIT_WR" if self.is_edit else "ACCEPT_WR"
        dettagli = f"Nuovo tempo: {new_time}"
        if self.is_edit:
            dettagli += f" (Vecchio tempo era: {self.original_view.def_t})"
            
        await database_utils.log_audit(
            admin_name=interaction.user.name,
            action_type=action,
            target=f"Mappa: {build_key}, Giocatori: {current_player}",
            details=dettagli
        )
        
        if self.is_edit:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            try:
                msg_to_edit = await channel.fetch_message(self.original_view.update_msg_id)
                await msg_to_edit.edit(content=testo_record)
            except: pass
            
            # Nascondiamo i nuovi dati
            hidden_data = f"||#WR#|{build_key}|{current_player}|{new_time}|{self.original_view.update_msg_id}||"
            new_content_msg = re.sub(r'\n\|\|#WR#.*\|\|', '', self.original_message.content)
            new_content_msg += f"\n{hidden_data}"
            
            await self.original_message.edit(content=new_content_msg, view=self.original_view)
            await interaction.followup.send(f"✅ Modifica salvata!\n🔗 **Vai al record:** {jump_url or 'N/A'}", ephemeral=True)
        else:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            file_da_inviare = await self.attachment.to_file()
            update_msg = await channel.send(content=testo_record, file=file_da_inviare)
            
            # Stampiamo i dati invisibili alla fine del messaggio di revisione
            hidden_data = f"||#WR#|{build_key}|{current_player}|{new_time}|{update_msg.id}||"
            new_content = f"{self.original_message.content} - **Accepted ✅**\n{hidden_data}"
            
            edit_view = EditWRView(self.bot)
            await self.original_message.edit(content=new_content, view=edit_view)
            await interaction.followup.send(f"✅ Record approvato!\n🔗 **Vai al record:** {jump_url or 'N/A'}", ephemeral=True)

        import rankings
        await rankings.trigger_ranking_update(self.bot)

# --- BOTTONI SOTTO LO SCREEN (RESI IMMORTALI) ---
class ReviewView(View):
    def __init__(self):
        super().__init__(timeout=None) 

    # INSERISCI QUESTO BUTTAFUORI:
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != config.MIO_ID:
            await interaction.response.send_message("❌ Solo l'amministratore può approvare o rifiutare gli screen.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="btn_accept_review")
    async def accept_btn(self, interaction: discord.Interaction, button: Button):
        attachment = interaction.message.attachments[0] if interaction.message.attachments else None
        await interaction.response.send_modal(WRModal(interaction.client, attachment, self, interaction.message))

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="btn_reject_review")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        rejected_channel = interaction.client.get_channel(config.REJECT_CHANNEL_ID)
        attachment = interaction.message.attachments[0] if interaction.message.attachments else None
        author_mention = interaction.message.mentions[0].mention if interaction.message.mentions else "l'utente"
        if rejected_channel and attachment:
            file_to_send = await attachment.to_file()
            await rejected_channel.send(content=f"Screen rifiutato da {author_mention}:", file=file_to_send)
        for child in self.children: child.disabled = True
        new_content = f"{interaction.message.content} - **Rejected ❌**"
        await interaction.message.edit(content=new_content, view=self)
        await interaction.message.delete(delay=20)
        await interaction.followup.send(f"Screen spostato in <#{config.REJECT_CHANNEL_ID}>.", ephemeral=True)

    @discord.ui.button(label="Wr Round", style=discord.ButtonStyle.primary, custom_id="btn_round_review")
    async def round_btn(self, interaction: discord.Interaction, button: Button):
        attachment = interaction.message.attachments[0] if interaction.message.attachments else None
        await interaction.response.send_modal(WrRoundModal(interaction.client, attachment, self, interaction.message))

    @discord.ui.button(label="Sim Wr", style=discord.ButtonStyle.secondary, custom_id="btn_sim_review")
    async def sim_wr_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SimWrModal(interaction.client, self, interaction.message))
