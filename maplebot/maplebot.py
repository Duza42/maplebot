import asyncio
import logging
import logging.config
import logging.handlers
import os
import shutil
import sys

import discord
import texttable
import yaml
import mysql.connector

from discord import app_commands
from discord.ext import tasks, commands

# Configuration File Locations
CONFIG_PATH = "config/"
SAMPLES_PATH = "samples/"
MAIN_CONFIG_FILE = "config.yaml"
LOGGING_CONFIG_FILE = "logging.yaml"

CHARACTER_QUERY = """SELECT characters.name, characters.level, characters.job, guilds.name \
FROM characters \
LEFT JOIN guilds on guilds.guildid = characters.guildid \
WHERE characters.name != 'Admin' \
ORDER BY characters.level DESC;"""

LOGGEDIN_QUERY = """SELECT count(name) \
FROM accounts \
WHERE loggedin != 0"""

JOBS = {
    0: 'Beginner',
    100: 'Warrior',
    110: 'Fighter',
    111: 'Crusader',
    112: 'Hero',
    120: 'Page',
    121: 'White Knight',
    122: 'Paladin',
    130: 'Spearman',
    131: 'Dragon Knight',
    132: 'Dark Knight',
    200: 'Magician',
    210: 'F/P Wizard',
    211: 'F/P Mage',
    212: 'F/P ArchMage',
    220: 'I/L Wizard',
    221: 'I/L Mage',
    222: 'I/L ArchMage',
    230: 'Cleric',
    231: 'Priest',
    232: 'Bishop',
    300: 'Bowman',
    310: 'Hunter',
    311: 'Ranger',
    312: 'Bowmaster',
    320: 'Crossbowman',
    321: 'Sniper',
    322: 'Marksman',
    400: 'Thief',
    410: 'Assassin',
    411: 'Hermit',
    412: 'Night Lord',
    420: 'Bandit',
    421: 'Chief Bandit',
    422: 'Shadower',
    500: 'Pirate',
    510: 'Brawler',
    511: 'Marauder',
    512: 'Buccaneer',
    520: 'Gunslinger',
    521: 'Outlaw',
    522: 'Corsair',
    800: 'Maple Leaf Brigadier',
    900: 'GM',
    910: 'Super GM',
    1000: 'Noblesse',
    1100: 'Dawn Warrior 1',
    1110: 'Dawn Warrior 2',
    1111: 'Dawn Warrior 3',
    1112: 'Dawn Warrior 4',
    1200: 'Blaze Wizard 1',
    1210: 'Blaze Wizard 2',
    1211: 'Blaze Wizard 3',
    1212: 'Blaze Wizard 4',
    1300: 'Wind Archer 1',
    1310: 'Wind Archer 2',
    1311: 'Wind Archer 3',
    1312: 'Wind Archer 4',
    1400: 'Night Walker 1',
    1410: 'Night Walker 2',
    1411: 'Night Walker 3',
    1412: 'Night Walker 4',
    1500: 'Thunder Breaker 1',
    1510: 'Thunder Breaker 2',
    1511: 'Thunder Breaker 3',
    1512: 'Thunder Breaker 4',
    2000: 'Legend',
    2001: 'Evan',
    2100: 'Aran 1',
    2110: 'Aran 2',
    2111: 'Aran 3',
    2112: 'Aran 4',
    2200: 'Evan 1',
    2210: 'Evan 2',
    2211: 'Evan 3',
    2212: 'Evan 4',
    2213: 'Evan 5',
    2214: 'Evan 6',
    2215: 'Evan 7',
    2216: 'Evan 8',
    2217: 'Evan 9',
    2218: 'Evan 10'
}


# Read data from YAML file
def read_yaml_file(filename):
    try:
        with open(filename) as yaml_file:
            data = yaml.safe_load(yaml_file)
            return data
    except IOError as error:
        if LOGGER is None:
            print(f"File error: {str(error)}")
        else:
            LOGGER.error(f"File error: {str(error)}")


# Write data to YAML file
def write_yaml_file(filename, data):
    try:
        with open(filename, 'w') as yaml_file:
            yaml_file.write(yaml.safe_dump(data))
    except IOError as error:
        if LOGGER is None:
            print(f"File error: {str(error)}")
        else:
            LOGGER.error(f"File error: {str(error)}")


# Initialize logging
def init_logging():
    global LOGGER
    if not os.path.isfile(CONFIG_PATH + LOGGING_CONFIG_FILE):
        print("Copying default logging config file...")
        try:
            shutil.copy2(SAMPLES_PATH + LOGGING_CONFIG_FILE, CONFIG_PATH)
        except IOError as error:
            print(f"Unable to copy default logging config file. {str(error)}")
    logging_config = read_yaml_file(CONFIG_PATH + LOGGING_CONFIG_FILE)

    log_path = os.path.dirname(logging_config['handlers']['file']['filename'])
    try:
        if not os.path.exists(log_path):
            os.makedirs(log_path)
    except IOError:
        print("Unable to create log folder")
    logging.config.dictConfig(logging_config)
    LOGGER = logging.getLogger("maplebot")
    LOGGER.debug("Logging initialized...")


# Initialize configuration
def init_config():
    global CONFIG
    LOGGER.debug("Reading configuration...")
    if not os.path.isfile(CONFIG_PATH + MAIN_CONFIG_FILE):
        LOGGER.info("Copying default config file...")
        try:
            shutil.copy2(SAMPLES_PATH + MAIN_CONFIG_FILE, CONFIG_PATH)
        except IOError as error:
            LOGGER.error(f"Unable to copy default config file. {str(error)}")
    CONFIG = read_yaml_file(CONFIG_PATH + MAIN_CONFIG_FILE)


class MapleBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(intents=intents, **kwargs)
        self.players = {}
        self.previousPlayers = {}
        self.cnx = mysql.connector.connect(
            host=CONFIG["db_host"],
            port=CONFIG["db_port"],
            user=CONFIG["db_user"],
            database=CONFIG["db_database"],
            password=CONFIG["db_password"])
        self.cnx.autocommit = True

    async def on_ready(self):
        await tree.sync(guild=discord.Object(id=guild_id))
        LOGGER.info(f'Logged in as name: {self.user.name} id: {self.user.id}')

    async def setup_hook(self) -> None:
        LOGGER.info('Setting up job')
        self.fetch_player_data.start()

    @tasks.loop(seconds=60)
    async def fetch_player_data(self):
        channel = self.get_channel(CONFIG['notification_channel'])  # channel ID goes here
        LOGGER.info('Attempting fetch player data')
        try:
            cur = self.cnx.cursor()
            cur.execute(LOGGEDIN_QUERY)
            for loggedin in cur:
                await self.change_presence(activity=discord.Game(name=f'{loggedin[0]} online'))
            cur.close()

            cur = self.cnx.cursor()
            cur.execute(CHARACTER_QUERY)
            LOGGER.info('Successfully fetched player data')
            for player in cur:
                self.players[player[0]] = Player(player[0], player[1], JOBS[player[2]], str(player[3] or ''))
            cur.close()
            if len(self.previousPlayers) != 0:
                for player in self.players.values():
                    try:
                        previous_player = self.previousPlayers[player.name]
                        if previous_player.level != player.level:
                            level_message = f'{player.name} is now level {player.level}!'
                            for player2 in self.players.values():
                                try:
                                    previous_player2 = self.previousPlayers[player2.name]
                                    if previous_player.level <= previous_player2.level and player.level > player2.level:
                                        level_message += f' {player.name} has passed {player2.name}!'
                                    if player.level == player2.level and player.name != player2.name:
                                        level_message += f' {player.name} is now the same level as {player2.name}!'
                                except KeyError as e:
                                    LOGGER.info('error getting previous player', str(e))
                            await channel.send(level_message)
                            LOGGER.info(level_message)
                        if previous_player.job != player.job:
                            job_message = f'{player.name} is now a {player.job}!'
                            await channel.send(job_message)
                            LOGGER.info(job_message)
                    except KeyError as e:
                        LOGGER.info('old_player does not exist, recently added?', str(e))

            else:
                LOGGER.info('Nothing in the previous dict')
            self.previousPlayers = self.players.copy()
            self.players.clear()
        except:
            e = sys.exc_info()[0]
            LOGGER.info('Error getting players:', str(e))
        await asyncio.sleep(CONFIG['poll_seconds'])

    @fetch_player_data.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()

    async def on_message(self, message):
        if message.author == client.user:
            return

        if message.content.startswith('$hello'):
            await message.channel.send('Hello!')


class PlayerNotfications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None


class Player(object):
    def __init__(self, name, level, job, guild):
        self.name = name
        self.level = level
        self.job = job
        self.guild = guild


init_logging()
init_config()
intents = discord.Intents.default()
client = MapleBot(intents)
tree = app_commands.CommandTree(client)
guild_id = CONFIG['guild_id']  # Put your server ID in this array.


def sort_by_level(player: Player):
    return player.level


@tree.command(name="ping", description="Ping StumpBot", guild=discord.Object(id=guild_id))
async def _ping(ctx):  # Defines a new "context" (ctx) command called "ping."
    await ctx.response.send_message(f"Pong! ({client.latency * 1000}ms)")


@tree.command(name="rank", description="Lists the rank for all characters", guild=discord.Object(id=guild_id))
async def _rank(ctx):  # Defines a new "context" (ctx) command called "ping."
    table = texttable.Texttable()
    table.set_cols_align(["l", "l", "l"])
    table.set_cols_dtype(["t", "t", "t"])
    table.add_row(["Name", "Level", "Job"])
    table.set_cols_width([11, 5, 18])
    player_list = list(client.previousPlayers.values())
    player_list.sort(key=sort_by_level, reverse=True)
    for i in range(14):
        player = player_list[i]
        table.add_row([f"{player.name} ", player.level, f"{player.job} "])
    await ctx.response.send_message("```\n" + table.draw() + "\n```\n")


client.run(CONFIG['bot_token'], log_handler=None)
