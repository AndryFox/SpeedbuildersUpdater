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

        # Recupera l'UUID del secondo account da Mojang
        uuid = await database_utils.get_mojang_uuid(vecchio_nome.strip())

        async with database_utils.pool.acquire() as conn:
            # 1. Inserisce gli alias testuali classici
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
                
            # 2. Lega l'UUID del secondo account al nome principale in modo permanente!
            if uuid:
                await conn.execute(
                    "INSERT INTO player_uuids (uuid, main_name) VALUES ($1, $2) ON CONFLICT (uuid) DO UPDATE SET main_name = $2",
                    uuid, nuovo_nome
                )

        await database_utils.load_aliases()
        await rankings.trigger_ranking_update(self.bot)
           
        await interaction.followup.send(f"✅ Identità unite! L'account/UUID `{vecchio_nome}` ora apparterrà per sempre a **{nuovo_nome}**.", ephemeral=True)
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

    # --- 4. COMANDO LIST ALIASES (CON PAGINAZIONE) ---
    @app_commands.command(name="list_aliases", description="📜 Mostra tutti gli alias attualmente registrati (Solo Admin)")
    @app_commands.default_permissions(administrator=True)
    async def list_aliases(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        grouped = {}
        for old_n, new_n in database_utils.ALIASES_CACHE.items():
            if old_n == new_n.lower():
                continue
            grouped.setdefault(new_n, []).append(old_n)

        if not grouped:
            return await interaction.followup.send("📭 Nessun alias registrato al momento.", ephemeral=True)

        lines = []
        for main_player in sorted(grouped.keys(), key=lambda x: x.lower()):
            olds = ", ".join(f"`{o}`" for o in sorted(grouped[main_player]))
            lines.append(f"▸ **{main_player}** ⬅️ {olds}")

        per_page = 20
        chunks = [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
        
        pages = []
        for chunk in chunks:
            embed = discord.Embed(
                title=f"🔄 Alias Registrati ({len(grouped)} giocatori principali)",
                description="\n".join(chunk),
                color=discord.Color.blurple()
            )
            pages.append(embed)

        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0], ephemeral=True)
        else:
            await interaction.followup.send(embed=pages[0], view=ui_components.PaginationView(pages), ephemeral=True)

    # --- 5. COMANDO RELOAD ALIASES ---
    @app_commands.command(name="reload_aliases", description="🔄 Ricarica la cache degli alias da Supabase (Solo Admin)")
    @app_commands.default_permissions(administrator=True)
    async def reload_aliases(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        # Svuota la RAM e ricarica i dati freschi da Supabase
        await database_utils.load_aliases()
        # Aggiorna le classifiche pubbliche per applicare i nuovi nomi
        await rankings.trigger_ranking_update(self.bot)
        
        await interaction.followup.send(f"✅ Sincronizzazione completata! Caricati {len(database_utils.ALIASES_CACHE)} alias nella memoria.", ephemeral=True)

    # --- 6. COMANDO SCAN UUID MANUALE ---
    @app_commands.command(name="scan_uuids", description="🔍 Forza la scansione immediata degli UUID da Mojang (Solo Admin)")
    @app_commands.default_permissions(administrator=True)
    async def scan_uuids(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID:
            return await interaction.response.send_message("❌ Accesso negato.", ephemeral=True)

        # Rispondiamo subito per evitare che Discord dia "L'applicazione non risponde"
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("⏳ Avvio scansione UUID su Mojang in corso... (potrebbe richiedere qualche minuto a seconda di quanti UUID ci sono, ti avviso io quando ho finito!)", ephemeral=True)

        async with database_utils.pool.acquire() as conn:
            rows = await conn.fetch("SELECT uuid, main_name FROM player_uuids")
        
        changes_made = False
        cambi_rilevati = []
        
        for row in rows:
            uuid = row['uuid']
            old_main_name = row['main_name']
            
            # Interroga Mojang
            current_name = await database_utils.get_name_from_uuid(uuid)
            
            if current_name and current_name.lower() != old_main_name.lower():
                async with database_utils.pool.acquire() as conn:
                    # 1. Aggiorna UUID
                    await conn.execute("UPDATE player_uuids SET main_name = $1 WHERE uuid = $2", current_name, uuid)
                    # 2. Crea Alias automatico
                    await conn.execute(
                        "INSERT INTO Aliases (old_name, new_name) VALUES ($1, $2) ON CONFLICT (old_name) DO UPDATE SET new_name = $2",
                        old_main_name.lower(), current_name
                    )
                changes_made = True
                cambi_rilevati.append(f"`{old_main_name}` ➔ **{current_name}**")
            
            # Pausa fondamentale per non farsi bloccare da Mojang
            await asyncio.sleep(1.5)
            
        if changes_made:
            await database_utils.load_aliases()
            await rankings.trigger_ranking_update(self.bot)
            report = "\n".join(cambi_rilevati)
            await interaction.followup.send(f"✅ **Scansione completata!** Trovati {len(cambi_rilevati)} cambi nome:\n{report}", ephemeral=True)
        else:
            await interaction.followup.send("✅ **Scansione completata!** Nessun giocatore nel database ha cambiato nome.", ephemeral=True)
    
async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
