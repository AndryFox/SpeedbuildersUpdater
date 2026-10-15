import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import re
import config
import database_utils
import image_generator

# Importiamo la tua libreria principale!
import rankings 

class RankingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Riavvia il loop asincrono per pre-generare la classifica
        self.bot.loop.create_task(rankings.generate_wr_ranking_text(self.bot))

    # --- FUNZIONI DI AUTOCOMPLETAMENTO ---
    async def build_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        async with database_utils.pool.acquire() as conn:
            if not current:
                rows = await conn.fetch("SELECT DISTINCT build_name FROM WorldRecords ORDER BY build_name LIMIT 25")
            else:
                rows = await conn.fetch("SELECT DISTINCT build_name FROM WorldRecords WHERE build_name ILIKE $1 ORDER BY build_name LIMIT 25", f"%{current}%")
            return [app_commands.Choice(name=row['build_name'], value=row['build_name']) for row in rows]

    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        current_lower = current.lower()
        async with database_utils.pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT player_name FROM WorldRecords")
            hof_rows = await conn.fetch("SELECT primo, secondo, terzo FROM tourney_hof")
        
        main_names = {database_utils.get_main_name(row['player_name']) for row in rows}
        main_names.update(database_utils.ALIASES_CACHE.values())
        
        # Aggiungiamo anche i vincitori dei tornei ai suggerimenti!
        for r in hof_rows:
            main_names.add(database_utils.get_main_name(r['primo']))
            main_names.add(database_utils.get_main_name(r['secondo']))
            main_names.add(database_utils.get_main_name(r['terzo']))
            
        choices = [app_commands.Choice(name=name, value=name) for name in main_names if not current_lower or current_lower in name.lower()]
        return sorted(choices, key=lambda x: x.name.lower())[:25]

    # --- COMANDI ADMIN SETUP ---
    @app_commands.command(name="setup_rankings", description="Send the initial WR Ranking message")
    @app_commands.default_permissions(administrator=True)
    async def setup_rankings(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID: return await interaction.response.send_message("❌ Riservato.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        initial_text = await rankings.generate_wr_ranking_text(self.bot)
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
            msg = await webhook.send(content=initial_text, username="Rankings Updater", wait=True)
        await interaction.followup.send(f"✅ Ranking created! Copy ID to config.py:\n**{msg.id}**")

    @app_commands.command(name="setup_rounds", description="Send the initial WR Rounds message")
    @app_commands.default_permissions(administrator=True)
    async def setup_rounds(self, interaction: discord.Interaction):
        if interaction.user.id != config.MIO_ID: return await interaction.response.send_message("❌ Riservato.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        initial_text = "## In total Fear Games have: __140 Builds__\n\nThe Wr rounds **(Legit)** on Fear Games is:\n\n||@Speedbuilders||"
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(config.RANKINGS_WEBHOOK_URL, session=session)
            msg = await webhook.send(content=initial_text, username="Rankings Updater", wait=True)
        await interaction.followup.send(f"✅ Rounds created! Copy ID to config.py:\n**{msg.id}**")

    # --- COMANDI STATISTICHE UTENTI ---
    @app_commands.command(name="wrs", description="Check all WRs and times of a player")
    @app_commands.describe(player="The name of the player")
    @app_commands.autocomplete(player=player_autocomplete)
    async def check_wrs(self, interaction: discord.Interaction, player: str):
        if interaction.channel_id != config.SUBMISSION_CHANNEL_ID:
            return await interaction.response.send_message(f"⚠ Can only be used in <#{config.SUBMISSION_CHANNEL_ID}>.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        
        player_norm = database_utils.get_main_name(player.replace("\\", ""))
        records = []
        async with database_utils.pool.acquire() as conn:
            query = """
                SELECT r1.build_name, r1.time, r1.player_name FROM WorldRecords r1
                WHERE r1.time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
                ORDER BY LOWER(r1.build_name) ASC
            """
            for row in await conn.fetch(query):
                if database_utils.get_main_name(row['player_name']) == player_norm:
                    records.append(f"▸ Build: **{row['build_name']}** ⸻ `{row['time']}s`")
                        
        count = len(records)
        # Recuperiamo le medaglie dalla tabella tourney_hof!
        trophies = await database_utils.get_player_trophies(player_norm)
        
        if count > 0 or trophies:
            ruolo = rankings.get_role_tag(count)
            nome_estetico = rankings.DISPLAY_NAMES_CACHE.get(player_norm, player_norm)
            avatar_url = f"https://minotar.net/helm/{player_norm}/256.png"
            
            desc = f"**Current Rank:** {ruolo}\n"
            if trophies:
                desc += f"🏆 **Tourney Trophies:** {' • '.join(trophies)}\n"
            desc += "\n"
            
            embed = discord.Embed(description=desc, color=discord.Color.gold())
            embed.set_author(name=f"{nome_estetico}'s World Records ({count})", icon_url=avatar_url)
            embed.set_thumbnail(url=avatar_url)
            
            if count > 0:
                lista_formattata = "\n".join(records)
                if len(lista_formattata) > 3800: 
                    lista_formattata = lista_formattata[:3800] + "\n\n*... and more!*"
                embed.description += lista_formattata
            else:
                embed.description += "*No active Build WRs at the moment.*"
                
            embed.set_footer(text="FearGames Speedbuilders", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"📉 **{player}** has no WRs or Tourney Trophies at the moment.")
    @app_commands.command(name="wrssim", description="Check all Sim WRs of a player")
    @app_commands.describe(player="The name of the player")
    @app_commands.autocomplete(player=player_autocomplete)
    async def wrssim_cmd(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer(ephemeral=True)
        target_norm = database_utils.get_main_name(player.strip()) 
        target_cmp = target_norm.lower().replace("_", "").replace("\\", "").strip()
        sim_channel = interaction.client.get_channel(config.SIM_WR_CHANNEL_ID)
        records = []
        
        if sim_channel:
            async for message in sim_channel.history(limit=500):
                if not message.content: continue
                for line in message.content.split('\n'):
                    raw_line = line.replace("*", "").replace(">", "").strip()
                    if ":" in raw_line:
                        try:
                            build_name, rest_of_line = map(str.strip, raw_line.split(':', 1))
                            if not rest_of_line: continue
                            
                            time_val = ""
                            player_part = rest_of_line
                            if "-" in rest_of_line:
                                time_part, player_part = rest_of_line.split('-', 1)
                                time_val = time_part.strip().lower().replace("s", "")
                            
                            for p in [p.strip() for p in player_part.split('/')]:
                                clean_p = re.sub(r'`?\(.*?\)`?', '', p)
                                clean_p = re.sub(r'\[.*?\]', '', clean_p).replace("\\", "").replace("`", "").strip()
                                
                                if target_cmp == database_utils.get_main_name(clean_p).lower().replace("_", "").replace("\\", "").strip():
                                    retime_match = re.search(r'\((retime.*?)\)', p, re.IGNORECASE)
                                    retime_str = f" - **`{retime_match.group(0)}`**" if retime_match else ""
                                    
                                    display_time = time_val or (re.search(r'[\d\.]+', retime_match.group(1)).group(0) if retime_match and re.search(r'[\d\.]+', retime_match.group(1)) else "?")
                                    records.append(f"▸ Build: **{build_name}** ⸻ `{display_time}s`{retime_str}")
                                    break
                        except: continue
                                
        count = len(records)
        if count > 0:
            avatar_url = f"https://minotar.net/helm/{target_norm}/256.png"
            embed = discord.Embed(color=discord.Color.green())
            embed.set_author(name=f"{rankings.DISPLAY_NAMES_CACHE.get(target_norm, target_norm)}'s Sim WRs ({count})", icon_url=avatar_url)
            embed.set_thumbnail(url=avatar_url)
            
            lista_formattata = "\n".join(records)
            embed.description = lista_formattata[:3900] + "\n\n*... and more!*" if len(lista_formattata) > 3900 else lista_formattata
            embed.set_footer(text="FearGames Speedbuilders", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"📉 **{player.title().replace('_', '\\_')}** has no Sim WRs at the moment.", ephemeral=True)

    @app_commands.command(name="buildtimes", description="Check the Top 3 and Sim WR of a build")
    @app_commands.describe(build="The name of the build")
    @app_commands.autocomplete(build=build_autocomplete)
    async def buildtimes_cmd(self, interaction: discord.Interaction, build: str):
        await interaction.response.defer(ephemeral=True)
        top3_text = ""
        top1_norm_name = None
        
        async with database_utils.pool.acquire() as conn:
            rows = await conn.fetch("SELECT player_name, time FROM WorldRecords WHERE LOWER(build_name) = LOWER($1) ORDER BY time ASC", build.strip())
            
        if not rows:
            top3_text = "No official records found."
        else:
            top1_norm_name = database_utils.get_main_name(rows[0]['player_name'])
            best_times, display_names = {}, {}
            
            for row in rows:
                p_name, t_val = row['player_name'], row['time']
                norm_name = database_utils.get_main_name(p_name)
                if norm_name not in best_times or t_val < best_times[norm_name]:
                    best_times[norm_name] = t_val
                    display_names[norm_name] = p_name 
            
            time_groups = {}
            for p_norm, t in best_times.items():
                time_groups.setdefault(t, []).append(display_names[p_norm].replace("_", "\\_"))
                
            sorted_times = sorted(time_groups.keys())
            medals = ["🥇 1st", "🥈 2nd", "🥉 3rd"]
            for i in range(min(3, len(sorted_times))):
                t = sorted_times[i]
                top3_text += f"{medals[i]}: **{' / '.join(time_groups[t])}** ({t}s)\n"

        sim_channel = interaction.client.get_channel(config.SIM_WR_CHANNEL_ID)
        sim_text = "No Sim WRs found for this build."
        build_clean = build.lower().strip()
        
        if sim_channel:
            async for message in sim_channel.history(limit=500):
                if not message.content: continue
                for line in message.content.split('\n'):
                    raw_line = line.replace("*", "").replace(">", "").replace("`", "").strip()
                    if raw_line.lower().replace("_", "").startswith((f"{build_clean}:", f"{build_clean} :")):
                        rest = raw_line.split(":", 1)[1].strip() if ":" in raw_line else raw_line
                        time_str, players_part = (f"{rest.split('-', 1)[0].strip()}s - ", rest.split("-", 1)[1]) if "-" in rest else ("", rest)
                            
                        formatted_players = []
                        for p in players_part.split("/"):
                            p = p.strip()
                            retime_match = re.search(r'(\(retime.*?\))', p, re.IGNORECASE)
                            retime_text = f"`{retime_match.group(1)}`" if retime_match else ""
                            p_name = p.replace(retime_match.group(1), "").strip() if retime_match else p.strip()
                            formatted_players.append(f"**{p_name.replace('_', '\\_')}**{retime_text}")
                            
                        sim_text = time_str + " / ".join(formatted_players)
                        break

        embed = discord.Embed(title=f"⏱️ Build Stats: {build.title()}", color=discord.Color.blue())
        if top1_norm_name: embed.set_thumbnail(url=f"https://minotar.net/helm/{top1_norm_name}/256.png")
        embed.add_field(name="🏆 Official Top 3", value=top3_text, inline=False)
        embed.add_field(name="🔄 Sim WR", value=sim_text, inline=False)
        embed.set_footer(text="FearGames Speedbuilders", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        await interaction.followup.send(embed=embed, ephemeral=True)

# --- COMANDO 4: /compare (TESTA A TESTA) ---
    @app_commands.command(name="compare", description="⚔️ Confronta le statistiche e i tempi di due giocatori")
    @app_commands.describe(player1="Il primo giocatore", player2="Il secondo giocatore")
    @app_commands.autocomplete(player1=player_autocomplete, player2=player_autocomplete)
    async def compare_cmd(self, interaction: discord.Interaction, player1: str, player2: str):
        if interaction.channel_id != config.SUBMISSION_CHANNEL_ID:
            return await interaction.response.send_message(f"⚠ Can only be used in <#{config.SUBMISSION_CHANNEL_ID}>.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
            
        p1_norm = database_utils.get_main_name(player1.replace("\\", ""))
        p2_norm = database_utils.get_main_name(player2.replace("\\", ""))
        
        if p1_norm.lower() == p2_norm.lower():
            return await interaction.followup.send("❌ Devi selezionare due giocatori diversi!", ephemeral=True)
            
        p1_wr_count = 0
        p2_wr_count = 0
        p1_best = {}
        p2_best = {}
        
        async with database_utils.pool.acquire() as conn:
            # 1. Conta i WR attivi di entrambi
            wr_query = """
                SELECT r1.build_name, r1.time, r1.player_name FROM WorldRecords r1
                WHERE r1.time = (SELECT MIN(time) FROM WorldRecords r2 WHERE LOWER(r1.build_name) = LOWER(r2.build_name))
            """
            for row in await conn.fetch(wr_query):
                main_p = database_utils.get_main_name(row['player_name']).lower()
                if main_p == p1_norm.lower(): p1_wr_count += 1
                if main_p == p2_norm.lower(): p2_wr_count += 1
                
            # 2. Raccoglie i record personali assoluti su OGNI build per calcolare il Testa a Testa
            all_rows = await conn.fetch("SELECT build_name, player_name, time FROM WorldRecords")
            for row in all_rows:
                b_name = row['build_name'].lower().strip()
                m_name = database_utils.get_main_name(row['player_name']).lower()
                t_val = row['time']
                
                if m_name == p1_norm.lower():
                    if b_name not in p1_best or t_val < p1_best[b_name]:
                        p1_best[b_name] = t_val
                elif m_name == p2_norm.lower():
                    if b_name not in p2_best or t_val < p2_best[b_name]:
                        p2_best[b_name] = t_val

        # --- LOGICA TESTA A TESTA ---
        common_builds = set(p1_best.keys()).intersection(set(p2_best.keys()))
        p1_wins = 0
        p2_wins = 0
        ties = 0
        
        for b in common_builds:
            if p1_best[b] < p2_best[b]: p1_wins += 1
            elif p2_best[b] < p1_best[b]: p2_wins += 1
            else: ties += 1
            
        # --- TROFEI ---
        p1_trophies = await database_utils.get_player_trophies(p1_norm)
        p2_trophies = await database_utils.get_player_trophies(p2_norm)
        
        # --- CALCOLO PERCENTUALE DOMINIO ---
        tot_scontri = p1_wins + p2_wins
        p1_perc = round((p1_wins / tot_scontri) * 100) if tot_scontri > 0 else 0
        p2_perc = round((p2_wins / tot_scontri) * 100) if tot_scontri > 0 else 0

        # --- PREPARIAMO I DATI PER L'IMMAGINE ---
        stats_data = {
            'p1_wr': p1_wr_count,
            'p2_wr': p2_wr_count,
            'p1_wins': p1_wins,
            'p2_wins': p2_wins,
            'ties': ties,
            'p1_trofei': len(p1_trophies),
            'p2_trofei': len(p2_trophies),
            'p1_rank': rankings.get_role_tag(p1_wr_count),
            'p2_rank': rankings.get_role_tag(p2_wr_count),
            'p1_perc': p1_perc,
            'p2_perc': p2_perc
        }
        
        # --- GENERIAMO L'IMMAGINE GUI ---
        p1_estetico = rankings.DISPLAY_NAMES_CACHE.get(p1_norm, p1_norm)
        p2_estetico = rankings.DISPLAY_NAMES_CACHE.get(p2_norm, p2_norm)
        
        image_buffer = await image_generator.generate_compare_gui(p1_estetico, p2_estetico, stats_data)
        file = discord.File(fp=image_buffer, filename="compare.png")
        
        await interaction.followup.send(file=file, ephemeral=True)
        
async def setup(bot):
    await bot.add_cog(RankingCommands(bot))
