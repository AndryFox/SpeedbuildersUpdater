import discord
from discord.ui import Button, View, Modal, TextInput
import config
from database_utils import get_main_name, get_wr_count, get_wr_rounds_info, get_wr_from_database, get_sim_wr_link

# --- VIEW PER IL TASTO EDIT (WR NORMALI) ---
class EditWRView(View):
    def __init__(self, bot, attachment, update_message, def_b, def_t, def_p, jump_url):
        super().__init__(timeout=None)
        self.bot = bot
        self.attachment = attachment
        self.update_message = update_message
        self.def_b = def_b
        self.def_t = def_t
        self.def_p = def_p
        
        # Aggiungiamo il tasto Link al database con il nuovo nome in inglese
        if jump_url: 
            self.add_item(discord.ui.Button(label="Go to WR", url=jump_url, style=discord.ButtonStyle.link))

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_btn(self, interaction: discord.Interaction, button: Button):
        # Rimosso il jump_url che causava l'errore TypeError
        await interaction.response.send_modal(
            WRModal(self.bot, self.attachment, self, interaction.message,
                    is_edit=True, update_message=self.update_message,
                    def_b=self.def_b, def_t=self.def_t, def_p=self.def_p) 
        )

# --- VIEW PER IL TASTO EDIT (WR ROUNDS) ---
class EditRoundView(View):
    def __init__(self, bot, attachment, update_message, def_r, def_w, def_o):
        super().__init__(timeout=None)
        self.bot = bot
        self.attachment = attachment
        self.update_message = update_message
        self.def_r = def_r
        self.def_w = def_w
        self.def_o = def_o

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            WrRoundModal(self.bot, self.attachment, self, interaction.message,
                         is_edit=True, update_message=self.update_message,
                         def_r=self.def_r, def_w=self.def_w, def_o=self.def_o)
        )

# --- MODAL PER I WR ROUND ---
class WrRoundModal(Modal):
    def __init__(self, bot, attachment, original_view, original_message, is_edit=False, update_message=None, def_r="", def_w="", def_o=""):
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

        self.add_item(self.rounds_val)
        self.add_item(self.winner_name)
        self.add_item(self.opponent_name)

    async def on_submit(self, interaction: discord.Interaction):
        # Mettiamo in attesa Discord prima di fare qualsiasi calcolo
        await interaction.response.defer(ephemeral=True)
        
        try:
            new_rounds = int(self.rounds_val.value)
        except ValueError:
            new_rounds = 0

        current_team = f"{self.winner_name.value.strip()} & {self.opponent_name.value.strip()}"
        old_rounds, old_holders = await get_wr_rounds_info(self.bot)

        extra_message = ""
        if old_rounds > 0:
            if new_rounds > old_rounds:
                diff = new_rounds - old_rounds
                round_word = "round" if diff == 1 else "rounds"
                extra_message = f"\n{current_team} beat {old_holders}'s old wr by {diff} {round_word}"
            elif new_rounds == old_rounds:
                extra_message = f"\n{current_team} tied {old_holders}'s wr"

        testo_record = f'```fix\nWR Rounds (Legit): {new_rounds} Rounds - {current_team}{extra_message}\n```'

        if self.is_edit:
            await self.update_message.edit(content=testo_record)
            
            self.original_view.def_r = self.rounds_val.value
            self.original_view.def_w = self.winner_name.value
            self.original_view.def_o = self.opponent_name.value
            
            # Usiamo original_message.edit per non far arrabbiare Discord
            await self.original_message.edit(view=self.original_view)
            await interaction.followup.send("✅ Modifica salvata con successo!", ephemeral=True)
            
        else:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            file_da_inviare = await self.attachment.to_file()
            update_msg = await channel.send(content=testo_record, file=file_da_inviare)

            edit_view = EditRoundView(self.bot, self.attachment, update_msg, self.rounds_val.value, self.winner_name.value, self.opponent_name.value)
            
            new_content = f"{self.original_message.content} - **Accepted ✅**"
            await self.original_message.edit(content=new_content, view=edit_view)
            await interaction.followup.send("✅ WR Rounds inviato! (Ricorda di aggiornare manualmente la classifica)", ephemeral=True)


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
        
        for child in self.original_view.children:
            child.disabled = True
        new_content = f"{self.original_message.content} - **Sim WR 🔄**"
        await self.original_message.edit(content=new_content, view=self.original_view)
        
        build_key = self.build_name.value.lower().strip()
        jump_url = await get_sim_wr_link(self.bot, build_key)

        if jump_url:
            await interaction.followup.send(f"✅ Archiviato come Sim WR.\n🔗 **Vai ad aggiornare il database:** {jump_url}", ephemeral=True)
        else:
            await interaction.followup.send("✅ Archiviato come Sim WR.\n⚠️ *(Nessun link precedente trovato nel database per questa build)*", ephemeral=True)


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
        # Mettiamo subito in pausa Discord!
        await interaction.response.defer(ephemeral=True)
        
        build_key = self.build_name.value.lower().strip()
        current_player = self.player_name.value.strip()
        current_norm = get_main_name(current_player)
        
        try:
            new_time = float(self.time_val.value.replace(',', '.'))
        except ValueError:
            new_time = 0.0

        extra_message = ""
        stats_msg = "\n" 
        
        old_player, old_time, jump_url = await get_wr_from_database(self.bot, build_key)
        current_c = await get_wr_count(self.bot, current_norm)
        
        if old_player and old_time is not None:
            if new_time < old_time:
                diff = round(old_time - new_time, 3) 
                
                nomi_vecchi = [p.strip() for p in old_player.split('/')]
                nomi_vecchi_norm = [get_main_name(p) for p in nomi_vecchi]
                
                if current_norm in nomi_vecchi_norm:
                    if len(nomi_vecchi) > 1:
                        altri_giocatori = [p for p in nomi_vecchi if get_main_name(p) != current_norm]
                        altri_formattati = "/".join(altri_giocatori)
                        extra_message = f"\n{current_player} improved their own wr and beat {altri_formattati} by {diff}s"
                    else:
                        extra_message = f"\n{current_player} improved their own wr by {diff}s"
                        
                    stats_msg += f"{current_player} kept their wr count ({current_c})\n"
                    
                    if len(nomi_vecchi) > 1:
                        for p in altri_giocatori:
                            p_norm = get_main_name(p)
                            old_c = await get_wr_count(self.bot, p_norm)
                            stats_msg += f"{p} lost 1 wr ({old_c} -> {max(0, old_c - 1)})\n"
                            
                else:
                    extra_message = f"\n{current_player} beat {old_player}'s old wr by {diff}s"
                    stats_msg += f"{current_player} gained 1 wr ({current_c} -> {current_c + 1})\n"
                    
                    for p in nomi_vecchi:
                        p_norm = get_main_name(p)
                        old_c = await get_wr_count(self.bot, p_norm)
                        stats_msg += f"{p} lost 1 wr ({old_c} -> {max(0, old_c - 1)})\n"
                    
            elif new_time == old_time:
                nomi_vecchi = [p.strip() for p in old_player.split('/')]
                nomi_vecchi_norm = [get_main_name(p) for p in nomi_vecchi]
                
                if current_norm in nomi_vecchi_norm:
                    extra_message = f"\n{current_player} tied their own wr"
                    stats_msg += f"{current_player} kept their wr count ({current_c})\n"
                else:
                    extra_message = f"\n{current_player} tied {old_player}'s wr"
                    stats_msg += f"{current_player} gained 1 wr ({current_c} -> {current_c + 1})\n"
        else:
            stats_msg += f"{current_player} gained 1 wr ({current_c} -> {current_c + 1})\n"
        
        testo_record = f'```\n{self.build_name.value} : {self.time_val.value} - {self.player_name.value}{extra_message}\n\n{stats_msg.strip()}\n```'
        
        if self.is_edit:
            await self.update_message.edit(content=testo_record)
            
            self.original_view.def_b = self.build_name.value
            self.original_view.def_t = self.time_val.value
            self.original_view.def_p = self.player_name.value
            
            await self.original_message.edit(view=self.original_view)
            # In fondo alla WRModal, dentro la parte if self.is_edit:
            await interaction.followup.send(f"✅ Modifica salvata!\n🔗 **Ricorda, per aggiornare la list dei wr:** {jump_url}", ephemeral=True)
            
        else:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            file_da_inviare = await self.attachment.to_file()
            update_msg = await channel.send(content=testo_record, file=file_da_inviare)

            # Cerca questa riga nel WRModal (intorno alla riga 170) e modificala così:
            edit_view = EditWRView(self.bot, self.attachment, update_msg, self.build_name.value, self.time_val.value, self.player_name.value, jump_url)
            
            new_content = f"{self.original_message.content} - **Accepted ✅**"
            await self.original_message.edit(content=new_content, view=edit_view)
            
            if jump_url:
                await interaction.followup.send(f"✅ Record aggiornato con successo!\n🔗 **Clicca qui per aggiornare la lista dei wr:** {jump_url}", ephemeral=True)
            else:
                await interaction.followup.send("✅ Record aggiornato con successo!\n⚠️ *(Questa sembra una build nuova, non ho link da darti)*", ephemeral=True)
            

# --- BOTTONI SOTTO LO SCREEN ---
class ReviewView(View):
    def __init__(self, bot, attachment, original_author):
        super().__init__(timeout=None)
        self.bot = bot
        self.attachment = attachment
        self.original_author = original_author

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(WRModal(self.bot, self.attachment, self, interaction.message))

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        admin_user = await self.bot.fetch_user(config.ADMIN_ID)
        
        file_to_send = await self.attachment.to_file()
        await admin_user.send(content=f"Hai rifiutato questo screen inviato da {self.original_author.mention}:", file=file_to_send)
        
        for child in self.children:
            child.disabled = True
        new_content = f"{interaction.message.content} - **Rejected ❌**"
        await interaction.message.edit(content=new_content, view=self)
        
        await interaction.followup.send("Wr rifiutato. Lo screen è stato inviato nei tuoi DM.", ephemeral=True)

    @discord.ui.button(label="Wr Round", style=discord.ButtonStyle.primary)
    async def round_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(WrRoundModal(self.bot, self.attachment, self, interaction.message))

    @discord.ui.button(label="Sim Wr", style=discord.ButtonStyle.secondary)
    async def sim_wr_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SimWrModal(self.bot, self, interaction.message))