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

    async def on_ready(self):
        await tree.sync(guild=discord.Object(id=guild_id))
        LOGGER.info(f'Logged in as name: {self.user.name} id: {self.user.id}')
        await self.change_presence(activity=discord.Game(name=CONFIG['playing_game']))
        LOGGER.info(f'Successfully set status')

    async def setup_hook(self) -> None:
        LOGGER.info('Setting up job')
        self.fetch_player_data.start()

    @tasks.loop(seconds=60)
    async def fetch_player_data(self):
        channel = self.get_channel(CONFIG['notification_channel'])  # channel ID goes here
        LOGGER.info('Attempting fetch player data')
        try:
            cur = self.cnx.cursor()
            cur.execute("SELECT name, level FROM characters WHERE name != 'Admin';")
            LOGGER.info('Successfully fetched player data')
            for player in cur:
                self.players[player[0]] = Player(player[0], player[1])
            cur.close()
            if len(self.previousPlayers) != 0:
                for player in self.players.values():
                    try:
                        previous_player = self.previousPlayers[player.name]
                        if previous_player.level != player.level:
                            level_message = f'{player.name} is now level {player.level}!'
                            for player2 in CONFIG['players']:
                                try:
                                    previous_player2 = self.previousPlayers[player2]
                                    player2 = self.players[player2]
                                    if previous_player.level <= previous_player2.level and player.level > player2.level:
                                        level_message += f' {player.name} has passed {player2.name}!'
                                    if player.level == player2.level and player.name != player2.name:
                                        level_message += f' {player.name} is now the same level as {player2.name}!'
                                except KeyError as e:
                                    LOGGER.info('error getting previous player', str(e))
                            await channel.send(level_message)
                            LOGGER.info(level_message)
                        # if previous_player.job != player.job:
                        #    job_message = f'{player.name} is now a {player.job}!'
                        #    await channel.send(job_message)
                        #    LOGGER.info(job_message)
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
    def __init__(self, name, level):
        self.name = name
        self.level = level


init_logging()
init_config()
intents = discord.Intents.default()
client = MapleBot(intents)
tree = app_commands.CommandTree(client)
guild_id = CONFIG['guild_id']  # Put your server ID in this array.


@tree.command(name="ping", description="Ping StumpBot", guild=discord.Object(id=guild_id))
async def _ping(ctx):  # Defines a new "context" (ctx) command called "ping."
    await ctx.response.send_message(f"Pong! ({client.latency * 1000}ms)")


@tree.command(name="rank", description="Lists the rank for all characters", guild=discord.Object(id=guild_id))
async def _rank(ctx):  # Defines a new "context" (ctx) command called "ping."
    table = texttable.Texttable()
    table.set_cols_align(["l", "l"])
    table.add_row(["Name", "Level"])
    for player in client.previousPlayers.values():
        table.add_row([player.name, player.level])
    await ctx.response.send_message("```\n" + table.draw() + "\n```\n")


async def main():
    # do other async things

    # start the client
    async with client:
        await client.start(CONFIG['bot_token'])


asyncio.run(main())
