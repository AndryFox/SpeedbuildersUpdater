import re
import config
import asyncpg

# --- POOL DI CONNESSIONI GLOBALE ---
pool = None

async def init_pool():
    global pool
    # Mantiene sempre aperte tra 2 e 10 connessioni al database
    pool = await asyncpg.create_pool(config.DATABASE_URL, statement_cache_size=0, min_size=2, max_size=10)

# Questa è la nuova memoria RAM per gli alias
ALIASES_CACHE = {}

async def load_aliases():
    """Carica tutti gli alias dal database alla RAM quando il bot si accende."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT old_name, new_name FROM Aliases")
        ALIASES_CACHE.clear()
        for row in rows:
            ALIASES_CACHE[row['old_name']] = row['new_name']
    print(f"🔄 Caricati {len(ALIASES_CACHE)} alias dal database.")

def get_main_name(player_name: str) -> str:
    """Controlla se il giocatore ha un alias nella cache."""
    lower_name = player_name.lower()
    return ALIASES_CACHE.get(lower_name, player_name)

async def get_wr_count(bot, player_name):
    target_name = get_main_name(player_name)
    count = 0
    
    async with pool.acquire() as conn:
        query = """
            SELECT player_name 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
        """
        rows = await conn.fetch(query)
        
        for row in rows:
            if get_main_name(row['player_name']) == target_name:
                count += 1
                    
    return count

async def get_wr_rounds_info(bot):
    channel = bot.get_channel(config.RANKINGS_CHANNEL_ID)
    if not channel: return 0, "Sconosciuto"

    async for message in channel.history(limit=50):
        if not message.content: continue
        lines = message.content.split('\n')
        for i, line in enumerate(lines):
            if ":first_place:" in line and "Rounds" in line:
                match = re.search(r'(\d+)\s*Rounds', line, re.IGNORECASE)
                old_rounds = int(match.group(1)) if match else 0
                old_holders = []
                for j in range(i+1, min(i+10, len(lines))):
                    if ":second_place:" in lines[j] or ":third_place:" in lines[j]: break
                    if "|" in lines[j] and "[" in lines[j] and "]" in lines[j]:
                        holder_match = re.search(r'\[(.*?)\]', lines[j])
                        if holder_match: old_holders.append(holder_match.group(1).replace("&amp;", "&").strip())

                holders_str = " / ".join(old_holders) if old_holders else "Sconosciuto"
                return old_rounds, holders_str
    return 0, "Sconosciuto"

async def get_sim_wr_link(bot, build_name):
    channel = bot.get_channel(config.SIM_WR_CHANNEL_ID)
    if not channel: return None
        
    build_clean = build_name.lower().strip()
    async for message in channel.history(limit=500):
        if not message.content: continue
        lines = message.content.split('\n')
        for line in lines:
            clean_line = line.lower().replace("*", "").replace("_", "").replace(">", "").strip()
            if clean_line.startswith(f"{build_clean}:") or clean_line.startswith(f"{build_clean} :"):
                return message.jump_url
    return None

async def get_top_players(limit=15):
    async with pool.acquire() as conn:
        query = """
            SELECT player_name, COUNT(*) as wr_count 
            FROM WorldRecords r1
            WHERE time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
            GROUP BY LOWER(player_name), player_name
            ORDER BY wr_count DESC
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
        return [(r['player_name'], r['wr_count']) for r in rows]

async def generate_build_message(build_name: str) -> str:
    async with pool.acquire() as conn:
        query = """
            SELECT player_name, time 
            FROM WorldRecords 
            WHERE LOWER(build_name) = LOWER($1)
        """
        rows = await conn.fetch(query, build_name)
        
    best_times = {}
    display_names = {}
    
    for row in rows:
        p_name = row['player_name']
        t_val = row['time']
        norm_name = get_main_name(p_name)
        
        if norm_name not in best_times or t_val < best_times[norm_name]:
            best_times[norm_name] = t_val
            # Salviamo il nome con le maiuscole corrette per l'estetica
            if p_name.lower() != norm_name.lower():
                display_names[norm_name] = norm_name 
            else:
                display_names[norm_name] = p_name
            
    tempi_raggruppati = {}
    for norm_name, t_val in best_times.items():
        nome_estetico = display_names.get(norm_name, norm_name)
        safe_player = nome_estetico.replace("_", "\\_")
        if t_val not in tempi_raggruppati: 
            tempi_raggruppati[t_val] = []
        tempi_raggruppati[t_val].append(safe_player)
        
    tempi_ordinati = sorted(tempi_raggruppati.keys())
    testo = f"Build: {build_name}\n"
    
    if len(tempi_ordinati) > 0:
        t1 = tempi_ordinati[0]
        p1 = "/".join(tempi_raggruppati[t1])
        testo += f"> :first_place: - **__{p1} {t1}__**\n"
    else: testo += "> :first_place: - \n"
        
    if len(tempi_ordinati) > 1:
        t2 = tempi_ordinati[1]
        p2 = "/".join(tempi_raggruppati[t2])
        testo += f"> :second_place: - {p2} {t2}\n"
    else: testo += "> :second_place: - \n"
        
    if len(tempi_ordinati) > 2:
        t3 = tempi_ordinati[2]
        p3 = "/".join(tempi_raggruppati[t3])
        testo += f"> :third_place: - {p3} {t3}"
    else: testo += "> :third_place: - "
        
    return testo

async def log_action(admin_id: int, azione: str, dettagli: str):
    """Salva un log interno delle azioni dello staff su Supabase."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO changelogs (admin_id, azione, dettagli) VALUES ($1, $2, $3)",
                admin_id, azione, dettagli
            )
    except Exception as e:
        print(f"⚠️ Errore salvataggio log: {e}")

async def save_button_memory(message_id: int, build_name: str, player_name: str, time_val: str, tipo: str, update_msg_id: int = None):
    """Salva i dati del bottone nel database per sopravvivere ai riavvii."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO buttonmemory (message_id, build_name, player_name, time_val, tipo, update_msg_id) 
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (message_id) 
                DO UPDATE SET build_name = EXCLUDED.build_name, player_name = EXCLUDED.player_name, time_val = EXCLUDED.time_val, update_msg_id = COALESCE(EXCLUDED.update_msg_id, buttonmemory.update_msg_id)
            """, message_id, build_name, player_name, str(time_val), tipo, update_msg_id)
    except Exception as e:
        print(f"⚠️ Errore salvataggio buttonmemory: {e}")

async def get_button_memory(message_id: int):
    """Recupera i dati di un bottone usando l'ID del messaggio discord."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT build_name, player_name, time_val, tipo, update_msg_id FROM buttonmemory WHERE message_id = $1",
                message_id
            )
    except Exception as e:
        print(f"⚠️ Errore lettura buttonmemory: {e}")
        return None

async def delete_button_memory(message_id: int):
    """Cancella i dati del bottone dal database (es. quando si usa Undo)."""
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM buttonmemory WHERE message_id = $1", message_id)
    except Exception as e:
        print(f"⚠️ Errore cancellazione buttonmemory: {e}")

import discord
import re
from discord.ui import Button, View, Modal, TextInput
import config
import rankings
from database_utils import get_main_name, get_wr_count, get_sim_wr_link
import time
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
    def __init__(self, jump_url=None):
        super().__init__(timeout=None)
        
        if jump_url:
            # Crea il tasto (Metti la tua scritta e la tua emoji)
            tasto_link = discord.ui.Button(label="Go to WR", url=jump_url)
            self.add_item(tasto_link)
            
            # TRUCCO: Prendiamo il tasto appena aggiunto e lo forziamo al PRIMO POSTO (a sinistra)
            ultimo_tasto = self.children.pop()
            self.children.insert(0, ultimo_tasto)

    # Rimetti la tua emoji al posto di ✏️ e il tuo label originale
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.blurple, emoji="✏️", custom_id="edit_wr_btn")
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await database_utils.get_button_memory(interaction.message.id)
        
        if not data:
            return await interaction.response.send_message("❌ Dati non trovati. Questo record è antecedente all'aggiornamento.", ephemeral=True)
        
        # 1. Iniettiamo i dati nella View
        self.def_b = data['build_name']
        self.def_p = data['player_name']
        self.def_t = data['time_val']
        self.update_msg_id = data.get('update_msg_id')
        
        # 2. Creiamo il modale
        modal = WRModal(
            bot=interaction.client, 
            attachment=None, 
            original_view=self, 
            original_message=interaction.message, 
            is_edit=True
        )
        
        # 3. PRECOMPILIAMO I CAMPI DI TESTO!
        modal.build_name.default = self.def_b
        modal.player_name.default = self.def_p
        modal.time_val.default = self.def_t
        
        # 4. Inviamo il modale
        await interaction.response.send_modal(modal)

    # Rimetti la tua emoji al posto di 🗑️ e il tuo label originale
    @discord.ui.button(label="Undo / Reject", style=discord.ButtonStyle.red, emoji="🗑️", custom_id="undo_wr_btn")
    async def undo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        data = await database_utils.get_button_memory(interaction.message.id)
        if not data:
            return await interaction.followup.send("❌ Impossibile annullare: dati non trovati.", ephemeral=True)
            
        build_key = data['build_name']
        player = data['player_name']
        time_val = data['time_val']
        tipo = data['tipo']
        
        # 1. Cancelliamo il record dal database E aggiorniamo il Webhook
        async with database_utils.pool.acquire() as conn:
            try:
                time_float = float(time_val)
                # Elimina da Supabase
                await conn.execute(
                    "DELETE FROM WorldRecords WHERE LOWER(build_name) = LOWER($1) AND player_name = $2 AND time = $3",
                    build_key, player, time_float
                )
                
                # AGGIORNAMENTO MESSAGGIO WEBHOOK SULLA BUILD
                msg_row = await conn.fetchrow("SELECT message_id FROM BuildMessages WHERE LOWER(build_name) = LOWER($1)", build_key)
                if msg_row:
                    msg_id = msg_row['message_id']
                    testo_formattato = await database_utils.generate_build_message(build_key)
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.from_url(config.WORLD_RECORDS_WEBHOOK_URL, session=session)
                        try:
                            await webhook.edit_message(msg_id, content=testo_formattato)
                        except Exception as e:
                            print(f"Errore webhook edit in undo: {e}")
                            
            except Exception as e:
                print(f"Errore cancellazione DB: {e}")
        
        # 2. Log e pulizia messaggi
        await database_utils.log_action(
            interaction.user.id, 
            "UNDO_WR", 
            f"Annullato {tipo} di {player} su {build_key} ({time_val}s)"
        )
        
        if data.get('update_msg_id'):
            channel = interaction.client.get_channel(config.UPDATES_CHANNEL_ID)
            if channel:
                try:
                    pub_msg = await channel.fetch_message(data['update_msg_id'])
                    await pub_msg.delete()
                except Exception:
                    pass

        await database_utils.delete_button_memory(interaction.message.id)
        await interaction.message.delete()

        # 3. Aggiorniamo la classifica generale (Leaderboard)
        import rankings
        await rankings.trigger_ranking_update(interaction.client)
        
        await interaction.followup.send("✅ Record annullato e messaggio Webhook aggiornato.", ephemeral=True)

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
            # 1. Se stiamo modificando, eliminiamo prima il record VECCHIO
            if self.is_edit:
                try: old_t = float(self.original_view.def_t)
                except ValueError: old_t = 0.0
                await conn.execute(
                    "DELETE FROM WorldRecords WHERE LOWER(build_name) = LOWER($1) AND player_name = $2 AND time = $3",
                    self.original_view.def_b.strip(), self.original_view.def_p.strip(), old_t
                )

            # 2. Ora prepariamo l'inserimento del record (sia se è nuovo, sia se sostituisce il precedente)
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

            # Inseriamo il record (aggiornato o nuovo)
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

        # 3. INTERFACCIA E LOG FINALI
        if self.is_edit:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            try:
                msg_to_edit = await channel.fetch_message(self.original_view.update_msg_id)
                await msg_to_edit.edit(content=testo_record)
            except: pass
            
            await database_utils.save_button_memory(
                message_id=self.original_message.id,
                build_name=build_key,
                player_name=current_player,
                time_val=str(new_time),
                tipo="WR",
                update_msg_id=self.original_view.update_msg_id
            )
            
            new_content_msg = re.sub(r'\n\|\|#WR#.*\|\|', '', self.original_message.content)
            await self.original_message.edit(content=new_content_msg, view=EditWRView(jump_url=jump_url)) 
            await interaction.followup.send("✅ Modifica salvata con successo e database aggiornato!", ephemeral=True)
            await database_utils.log_action(interaction.user.id, "EDIT_WR", f"Modificato WR: {build_key} di {current_player} a {new_time}s")
            
        else:
            channel = self.bot.get_channel(config.UPDATES_CHANNEL_ID)
            file_da_inviare = await self.attachment.to_file()
            update_msg = await channel.send(content=testo_record, file=file_da_inviare)
            
            new_content = f"{self.original_message.content} - **Accepted ✅**"
            
            # Qui usiamo la View corretta e new_content (non new_content_msg)
            await self.original_message.edit(content=new_content, view=EditWRView(jump_url=jump_url))
            
            await database_utils.save_button_memory(
                message_id=self.original_message.id,
                build_name=build_key,
                player_name=current_player,
                time_val=str(new_time),
                tipo="WR",
                update_msg_id=update_msg.id
            )
            
            await interaction.followup.send("✅ Record approvato!", ephemeral=True)
            await database_utils.log_action(interaction.user.id, "APPROVE_WR", f"Approvato nuovo WR: {build_key} di {current_player} a {new_time}s")
        
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

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="review_accept")
    async def accept_btn(self, interaction: discord.Interaction, button: Button):
        attachment = interaction.message.attachments[0] if interaction.message.attachments else None
        await interaction.response.send_modal(WRModal(interaction.client, attachment, self, interaction.message))

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="review_reject")
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

    @discord.ui.button(label="Wr Round", style=discord.ButtonStyle.primary, custom_id="review_round")
    async def round_btn(self, interaction: discord.Interaction, button: Button):
        attachment = interaction.message.attachments[0] if interaction.message.attachments else None
        await interaction.response.send_modal(WrRoundModal(interaction.client, attachment, self, interaction.message))

    @discord.ui.button(label="Sim Wr", style=discord.ButtonStyle.secondary, custom_id="review_sim")
    async def sim_wr_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SimWrModal(interaction.client, self, interaction.message))

async def save_round_button_memory(message_id: int, def_r: str, def_w: str, def_o: str, def_t: str, update_msg_id: int = None):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO roundbuttonmemory (message_id, def_r, def_w, def_o, def_t, update_msg_id) 
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (message_id) 
                DO UPDATE SET def_r = EXCLUDED.def_r, def_w = EXCLUDED.def_w, def_o = EXCLUDED.def_o, def_t = EXCLUDED.def_t, update_msg_id = COALESCE(EXCLUDED.update_msg_id, roundbuttonmemory.update_msg_id)
            """, message_id, str(def_r), str(def_w), str(def_o), str(def_t), update_msg_id)
    except Exception as e:
        print(f"⚠️ Errore salvataggio roundbuttonmemory: {e}")

async def get_round_button_memory(message_id: int):
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT def_r, def_w, def_o, def_t, update_msg_id FROM roundbuttonmemory WHERE message_id = $1",
                message_id
            )
    except Exception as e:
        print(f"⚠️ Errore lettura roundbuttonmemory: {e}")
        return None

async def delete_round_button_memory(message_id: int):
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM roundbuttonmemory WHERE message_id = $1", message_id)
    except Exception as e:
        print(f"⚠️ Errore cancellazione roundbuttonmemory: {e}")

async def upsert_tourney_hof(sigla: str, edizione: str, primo: str, secondo: str, terzo: str, note: str = ""):
    """Salva o aggiorna un'edizione del torneo su Supabase."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO tourney_hof (sigla, edizione, primo, secondo, terzo, note)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (sigla, edizione) 
            DO UPDATE SET primo = EXCLUDED.primo, secondo = EXCLUDED.secondo, terzo = EXCLUDED.terzo, note = EXCLUDED.note
        """, sigla.upper().strip(), edizione.strip(), primo.strip(), secondo.strip(), terzo.strip(), note.strip())

async def delete_tourney_hof(sigla: str, edizione: str) -> bool:
    """Elimina un'edizione del torneo da Supabase."""
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM tourney_hof WHERE UPPER(sigla) = UPPER($1) AND LOWER(edizione) = LOWER($2)",
            sigla.strip(), edizione.strip()
        )
        return res != "DELETE 0"

async def generate_hof_embed_text() -> str:
    """Genera il testo della Hall of Fame leggendo direttamente da Supabase."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT sigla, edizione, primo, secondo, terzo, note FROM tourney_hof ORDER BY id ASC")

    sbit_list = []
    sbil_list = []

    for r in rows:
        # Evitiamo che gli underscore nei nomi attivino il corsivo di Discord
        p1 = get_main_name(r['primo']).replace("_", "\\_")
        p2 = get_main_name(r['secondo']).replace("_", "\\_")
        p3 = get_main_name(r['terzo']).replace("_", "\\_")
        note_str = f" *({r['note']})*" if r['note'] else ""

        blocco = (
            f"🏆 **{r['sigla']} {r['edizione']}**{note_str}\n"
            f"> :first_place: **__{p1}__**\n"
            f"> :second_place: **{p2}**\n"
            f"> :third_place: {p3}"
        )
        
        if r['sigla'].upper() == "SBIT":
            sbit_list.append(blocco)
        else:
            sbil_list.append(blocco)

    testo = "# Hall of Fame\n\n"
    
    testo += "## ☀️ **SBIT** (Summer Tourney)\n"
    testo += "\n\n".join(sbit_list) if sbit_list else "*Nessuna edizione registrata.*"
    
    testo += "\n\n## ❄️ **SBIL** (Winter Tourney)\n"
    testo += "\n\n".join(sbil_list) if sbil_list else "*Nessuna edizione registrata.*"

    return testo
