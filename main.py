from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from tinydb import TinyDB, Query
import os
import discord
import asyncio 
import random
import json


# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Simpan data di folder script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_file = os.path.join(BASE_DIR, "player_data.json")

#JSON Setup

with open("config.json", "r") as f:
    config = json.load(f)


# TinyDB setup
player_db = TinyDB('player_data.json')
players = player_db.table('playerdata')
gamedb = TinyDB('game_database.json')
gamedata = gamedb.table('gamedata')  # ⬅️ ambil table yg sama waktu insert
rank_role = {
    "bronze": range(0, 20),
    "silver": range(20, 40),
    "gold": range(40, 80),
    "platinum": range(80, 100),
    "diamond": range(100, 120),
    "emerald": range(120, 140),
    "sapphire": range(140, 160),
    "ruby": range(160, 180),
    "crystal": range(180, 200),
    "opal": range(200, 220),
    "amethyst": range(220, 240),
    "obsidian": range(240, 260),
    "adventurine": range(260, 280),
    "quartz": range(280, 300),
    "topaz": range(300, 320),
    "dark matter": range(320, 340)
}


TOKEN = config["bot_token"]

@bot.event
async def on_ready():
    guild = discord.Object(id=config["guild_id"])
    
    # tambahkan ini supaya command terdaftar sebagai GUILD-scoped
    bot.tree.copy_global_to(guild=guild)

    synced = await bot.tree.sync(guild=guild)
    print(f"✅ Force-synced {len(synced)} command(s) ke server {guild.id}")



@bot.tree.command(name="cg", description="End game.")
@app_commands.describe(game_id="ID game")
@app_commands.checks.has_role("Admin")  # Ganti sesuai nama role yang diizinkan
async def cg(interaction: discord.Interaction, game_id: int):
    await interaction.response.defer(ephemeral=True)

    category = discord.utils.get(interaction.guild.categories, id=config["category_id"])  # Ganti ke ID kategori kamu

    voice_channel_name1 = f"#{game_id} | Team 1"
    voice_channel_name2 = f"#{game_id} | Team 2"
    text_channel_name = f"game-{game_id}".lower()

    voice_channel1 = discord.utils.get(category.voice_channels, name=voice_channel_name1)
    voice_channel2 = discord.utils.get(category.voice_channels, name=voice_channel_name2)
    text_channel = discord.utils.get(category.text_channels, name=text_channel_name)

    if voice_channel1:
        await voice_channel1.delete()
    if voice_channel2:
        await voice_channel2.delete()
    if text_channel:
        await asyncio.sleep(5)
        await text_channel.delete()

    if voice_channel1 or voice_channel2 or text_channel:
        await interaction.followup.send(f"✅ Game #{game_id} channels deleted.", ephemeral=True)
    else:
        await interaction.followup.send("❌ Game ID not found or no matching channels.", ephemeral=True)

@bot.tree.command(name="call", description="Call a player to your current voice channel.")
@app_commands.describe(player="The player you want to call into your voice channel")
async def call(interaction: discord.Interaction, player: discord.Member):
    caller = interaction.user

    # Check if the caller is in a voice channel
    if not caller.voice or not caller.voice.channel:
        await interaction.response.send_message("❌ You must be in a voice channel to use this command.", ephemeral=True)
        return

    voice_channel = caller.voice.channel

    # Grant target player permission to join and speak
    await voice_channel.set_permissions(player, overwrite=discord.PermissionOverwrite(
        connect=True,
        speak=True,
        view_channel=True
    ))

    try:
        # If the player is already in a voice channel, move them
        if player.voice:
            await player.move_to(voice_channel)
        else:
            await player.send(
                f"📞 You’ve been called to **{voice_channel.name}** by {caller.display_name}. Please join the voice channel."
            )
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to move this member.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"✅ {player.mention} has been called to {voice_channel.name}.", ephemeral=True
    )


@bot.tree.command(name="score", description="Admin only: Score game result and MVP.")
@app_commands.describe(game_id="ID game yang ingin dinilai", team_win="Tim pemenang (1 atau 2)", mvp="Nickname MVP (optional)")
@app_commands.checks.has_role("Admin")
async def score(interaction: discord.Interaction, game_id: int, team_win: int, mvp: str = None):

    game_data = get_game_data(game_id)
    if not game_data:
        await interaction.response.send_message("❌ Game ID tidak ditemukan.", ephemeral=True)
        return

    scorelog = bot.get_channel(config["score_channel_id"])

    embed = discord.Embed(title="Scoring System", description=f"🏆 The Winners are Team {team_win}", color=0xFFFFFF)

    team_win_key = f"team{team_win}"
    team_lose_key = f"team{3 - team_win}"

    winners = game_data.get(team_win_key, [])
    losers = game_data.get(team_lose_key, [])

    def update_player_data(member_id, member_data):
        players.update(member_data, Query().Id == str(member_id))

    def update_ranks(player_id):
        result = players.search(Query().Id == str(player_id))
        if result:
            data = result[0]
            elo = data['Elo']
            for rank, elo_range in rank_role.items():
                if elo in elo_range:
                    data['Rank'] = rank
                    players.update(data, Query().Id == str(player_id))
                    break

    winners_log = ""
    losers_log = ""

    for uid in winners:
        pdata = get_player_data(uid)
        if not pdata:
            continue

        before = pdata['Elo']
        rank = pdata['Rank'].lower()
        delta = {
            "bronze": 35,
            "silver": 35,
            "gold": 35,
            "platinum": 30,
            "diamond": 30,
            "emerald": 30,
            "sapphire": 25,
            "ruby": 25,
            "crystal": 25,
            "opal": 20,
            "amethyst": 20,
            "obsidian": 20,
            "adventurine": 15,
            "quartz": 15,
            "topaz": 15,
            "dark matter": 10
        }.get(rank, 20)

        pdata['Elo'] = before + delta
        pdata['TotalMatches'] += 1
        pdata['Wins'] += 1
        update_player_data(uid, pdata)
        update_ranks(uid)

        winners_log += f"<@{uid}> = (+){delta} [{before} ➜ {pdata['Elo']}]\n"

    for uid in losers:
        pdata = get_player_data(uid)
        if not pdata:
            continue

        before = pdata['Elo']
        rank = pdata['Rank'].lower()
        delta = {
            "bronze": -10,
            "silver": -15,
            "gold": -15,
            "platinum": -15,
            "diamond": -15,
            "emerald": -15,
            "sapphire": -20,
            "ruby": -25,
            "crystal": -30,
            "opal": -30,
            "amethyst": -30,
            "obsidian": -30,
            "adventurine": -30,
            "quartz": -35,
            "topaz": -40,
            "dark matter": -40
        }.get(rank, -20)

        pdata['Elo'] = max(before + delta, 0)
        pdata['TotalMatches'] += 1
        pdata['Loses'] += 1
        update_player_data(uid, pdata)
        update_ranks(uid)

        losers_log += f"<@{uid}> = ({delta}) [{before} ➜ {pdata['Elo']}]\n"

    if mvp:
        mvp_player = players.search(Query().Nickname == mvp)
        if mvp_player:
            mvp_data = mvp_player[0]
            mvp_data['TotalMvps'] += 1
            elo_mvp_bonus = 20
            mvp_data['Elo'] += elo_mvp_bonus
            update_player_data(mvp_data['Id'], mvp_data)
            embed.add_field(name=":crown: MVP", value=f"`(+){elo_mvp_bonus}` **{mvp}**", inline=False)

    embed.add_field(name="Winners", value=winners_log or "-", inline=False)
    embed.add_field(name="Losers", value=losers_log or "-", inline=False)
    embed.add_field(name="Scored By", value=f"<@{interaction.user.id}>", inline=False)
    embed.set_footer(text=f"Game #{game_id}")

    await scorelog.send(embed=embed)
    await interaction.response.send_message("✅ Game scored successfully.", ephemeral=True)

def get_game_data(game_id):
    query = Query()
    result = gamedata.search(query.game_id == game_id)
    return result[0] if result else None

def get_player_data(player_id):
    Player = Query()
    result = players.search(Player.Id == str(player_id))
    return result[0] if result else None




@bot.tree.command(name="register", description="Register for the ranked system.")
@app_commands.describe(nickname="Your in-game nickname")
async def register(interaction: discord.Interaction, nickname: str):
    user_id = str(interaction.user.id)

    # Hanya boleh dijalankan di channel register
    if interaction.channel_id != config["register_channel_id"]:
        await interaction.response.send_message("❌ You can only use this command in the register channel.", ephemeral=True)
        return

    Player = Query()

    # Cek apakah user sudah terdaftar
    if players.search(Player.Id == user_id):
        await interaction.response.send_message("❗ You are already registered!", ephemeral=True)
        return

    if players.search(Query().Nickname == nickname):
        await interaction.response.send_message("❗ Nickname already registered", ephemeral=True)
        return
    # Data awal pemain
    new_player = {
        "Id": user_id,
        "Nickname": nickname,
        "Elo": 0,
        "Rank": "bronze",
        "TotalMatches": 0,
        "Wins": 0,
        "Loses": 0,
        "TotalMvps": 0
    }

    players.insert(new_player)
    print(f"✅ Player {nickname} registered successfully.")
    member = interaction.user
    new_nick = f"{nickname}"
    await member.edit(nick=new_nick)

    embed = discord.Embed(
        title="Registration Scrim",
        description=f"**Your Registration Is Successful!**\n\nNickname : **{nickname}**\n\nHave fun and don't forget to comply with the scrim and Discord rules.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="Ranked Statistics")
@app_commands.describe(user="Choose user")
async def stats(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user

    user_id = str(user.id)
    player = players.get(Query().Id == user_id)

    if not player:
        await interaction.response.send_message("You are not registered.", ephemeral=True)
        return

    name = player["Nickname"]
    elo = player["Elo"]
    wins = player["Wins"]
    losses = player["Loses"]
    rank = player["Rank"]
    total_matches = player["TotalMatches"]
    mvps = player["TotalMvps"]
    winrate = (wins / total_matches) * 100 if total_matches > 0 else 0

    embed = discord.Embed(
        title=f"{name}'s Statistics",
        description=(
            f"**Mvps:** {mvps}\n"
            f"**Elo:** {elo}\n"
            f"**Wins:** {wins}\n"
            f"**Losses:** {losses}\n"
            f"**Rank:** {rank}\n"
            f"**Total Matches:** {total_matches}\n"
            f"**Winrate:** {winrate:.0f}%"
        ),
        color=0xFFFFFF
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Top 10 Elo.")
async def leaderboard(interaction: discord.Interaction):
    top_players = sorted(players.all(), key=lambda x: x["Elo"], reverse=True)[:10]

    if not top_players:
        await interaction.response.send_message("few people.")
        return

    embed = discord.Embed(title="🏆 Ranked Leaderboard", color=discord.Color.gold())

    for index, player in enumerate(top_players, start=1):
        user_id = player["Id"]
        nickname = player["Nickname"]
        elo = player["Elo"]
        rank = player["Rank"]
        mvps = player["TotalMvps"]

        embed.add_field(
            name=f"#{index} – {nickname}",
            value=f"<@{user_id}> | Elo: `{elo}` | Rank: `{rank}` | MVP: `{mvps}`",
            inline=False
        )

    embed.set_footer(text="Top 10 Ranked Players • Ranked Bebek")
    await interaction.response.send_message(embed=embed)


@bot.event
async def on_voice_state_update(member, before, after):
    target_channel_id = config["queue_channel_id"]  # ID voice channel yang kamu pakai
    lobby_channel_id = config["lobby_text_channel_id"]  # ID text channel untuk info/error
    max_players = 8  # Jumlah pemain yang ditunggu, misalnya untuk 4v4

    # Jika user baru join ke channel yang ditentukan
    if after.channel and after.channel.id == target_channel_id:
        voice_channel = after.channel

        if len(voice_channel.members) == max_players:
            await asyncio.sleep(2)  # Delay untuk memastikan gak ada yang keluar
            if len(voice_channel.members) == max_players:
                await cgame4v4(member.guild)
            else:
                lobby = bot.get_channel(lobby_channel_id)
                await lobby.send("❌ Something went wrong. Player count changed.")

game_id = 0
game_channel_id = 0


class CaptainPickView(View):
    def __init__(self, available_members, captain, team, count, non_team_members):
        super().__init__(timeout=None)
        self.captain = captain
        self.team = team
        self.count = count
        self.non_team_members = non_team_members
        self.result = False

        self.select = Select(
            placeholder=f"Please pick {count} player...",
            min_values=count,
            max_values=count,
            options=[
                discord.SelectOption(label=member.display_name, value=str(member.id))
                for member in available_members
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.captain:
            await interaction.response.send_message("❌ You are not the captain!", ephemeral=True)
            return

        selected_ids = [int(v) for v in self.select.values]
        selected_members = [m for m in self.non_team_members if m.id in selected_ids]

        self.team.extend(selected_members)
        for member in selected_members:
            self.non_team_members.remove(member)

        await interaction.response.send_message(
            f"✅ {self.captain.mention} Picked: {', '.join(m.mention for m in selected_members)}",
            ephemeral=False
        )
        self.result = True
        self.stop()



async def cgame4v4(guild, members_override=None):
    global game_id 
    global game_channel_id 

    game_id += 1
    lobby_name = f"#{game_id} Lobby"
    game_channel_name = f"#Game-{game_id}"
    team1_channel_name = f"#{game_id} | Team 1"
    team2_channel_name = f"#{game_id} | Team 2"
    queue_channel = guild.get_channel(config["queue_channel_id"])
    members = queue_channel.members

    category = discord.utils.get(guild.categories, id=config["category_id"])
    lobby = await category.create_voice_channel(lobby_name)
    await edit_voice_permissions(members, lobby)
    await move_members_to_channel(members, lobby)
    game_channel = await category.create_text_channel(game_channel_name)
    await edit_channel_permissions(members, game_channel)

    gamedb = TinyDB('game_database.json')

    captains = random.sample(members, 2)
    team1 = [captains[0]]
    team2 = [captains[1]]
    non_team_members = [member for member in members if member not in captains]

    embed = discord.Embed(title="Team Generator", description=f"Team 1: \n{captains[0].mention}\n\nTeam 2:\n{captains[1].mention}")
    await game_channel.send(embed=embed)

    await wait_for_selection(game_channel, captains[0], non_team_members, team1, 1)
    await wait_for_selection(game_channel, captains[1], non_team_members, team2, 2)
    await wait_for_selection(game_channel, captains[0], non_team_members, team1, 2)

    team2.extend(non_team_members)

    game_data = {"game_id": game_id, "team1": [member.id for member in team1], "team2": [member.id for member in team2]}
    game_data_table = gamedb.table('gamedata')
    game_data_table.insert(game_data)

    team1_channel = await category.create_voice_channel(team1_channel_name)
    team2_channel = await category.create_voice_channel(team2_channel_name)

    await edit_voice_permissions(team1, team1_channel)
    await edit_voice_permissions(team2, team2_channel)

    await move_members_to_channel(team1, team1_channel)
    await move_members_to_channel(team2, team2_channel)

    await lobby.delete()
    await team1_channel.edit(region='singapore')
    await team2_channel.edit(region='singapore')

    team1_names = "\n".join([f"<@{member.id}>" for member in team1])
    team2_names = "\n".join([f"<@{member.id}>" for member in team2])
    embed = discord.Embed(title="Team Generator", description=f"Team 1:\n{team1_names}\n\nTeam 2:\n{team2_names}", color=discord.Color.green())
    await game_channel.send(f"Please log on to VenityNetwork\n{team1_names}\n{team2_names}")
    await game_channel.send(embed=embed)

    gamelog = bot.get_channel(config["gamelog_id"])
    embed = discord.Embed(title=f"Game #{game_id} Has Started!", color=discord.Color.green())
    embed.add_field(name="Team 1", value=team1_names, inline=False)
    embed.add_field(name="Team 2", value=team2_names, inline=False)
    embed.set_footer(text="Ranked Bebek")
    await gamelog.send(embed=embed)

async def wait_for_selection(channel, captain, non_team_members, team, count):
    view = CaptainPickView(non_team_members.copy(), captain, team, count, non_team_members)
    await channel.send(f"{captain.mention}, Please Pick {count} Player:", view=view)
    await view.wait()
    if not view.result:
        await channel.send(f"{captain.mention}, Error.")


async def edit_voice_permissions(members, channel):
    overwrites = {
        channel.guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=True, connect=False, use_voice_activation=True),
        channel.guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    for member in members:
        overwrites[member] = discord.PermissionOverwrite(
            connect=True,
            speak=True,
            use_voice_activation=True,
            stream=True
        )

    await channel.edit(overwrites=overwrites)

async def edit_channel_permissions(members, channel):
    overwrites = {
        channel.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        channel.guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    for member in members:
        overwrites[member] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True
        )

    ranked_host_role = discord.utils.get(channel.guild.roles, name="Ranked Host")
    if ranked_host_role:
        overwrites[ranked_host_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True
        )

    await channel.edit(overwrites=overwrites)

async def move_members_to_channel(members, destination_channel):
    for member in members:
        if member.bot:
            continue
        try:
            if member.voice:
                await member.move_to(destination_channel)
        except:
            pass


# Run the bot
bot.run(TOKEN)
