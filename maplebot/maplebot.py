import asyncio
import sys

import aiohttp
import discord
import logging
import logging.config
import logging.handlers
import os
import shutil
import yaml

from discord_slash import SlashCommand

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
        super().__init__(*args, **kwargs)

        # create the background task and run it in the background
        self.bg_task = self.loop.create_task(self.fetch_player_data())
        self.players = {}
        self.previousPlayers = {}

    async def on_ready(self):
        LOGGER.info(f'Logged in as name: {self.user.name} id: {self.user.id}')
        await self.change_presence(activity=discord.Game(name=CONFIG['playing_game']))
        LOGGER.info(f'Successfully set status')

    async def fetch_player_data(self):
        await self.wait_until_ready()
        channel = self.get_channel(CONFIG['notification_channel'])  # channel ID goes here
        while not self.is_closed():
            async with aiohttp.ClientSession() as session:
                async with session.get(CONFIG['player_api']) as r:
                    LOGGER.info('Attempting fetch player data')
                    try:
                        if r.status == 200:
                            new_data = await r.json()
                            LOGGER.info('Successfully fetched player data')
                            for player in new_data['data']:
                                if player[1] in CONFIG['players'] or player[2] == CONFIG['guild_name']:
                                    self.players[player[1]] = Player(player[0], player[1], player[2], player[3],
                                                                     player[4])
                            if len(self.previousPlayers) != 0:
                                for player in self.players.values():
                                    try:
                                        previous_player = self.previousPlayers[player.name]
                                    except KeyError as e:
                                        LOGGER.info('old_player does not exist, recently added?', str(e))
                                    if previous_player.level != player.level:
                                        message = f'{player.name} is now level {player.level}!'
                                        for player2 in CONFIG['players']:
                                            try:
                                                previous_player2 = self.previousPlayers[player2]
                                                player2 = self.players[player2]
                                                if previous_player.level <= previous_player2.level and player.level > player2.level:
                                                    message += f' {player.name} has passed {player2.name}!'
                                                if player.level == player2.level and player.name != player2.name:
                                                    message += f' {player.name} is now the same level as {player2.name}!'
                                            except KeyError as e:
                                                LOGGER.info('error getting previous player', str(e))
                                        await channel.send(message)
                                        LOGGER.info(message)
                            else:
                                LOGGER.info('Nothing in the previous dict')
                            self.previousPlayers = self.players.copy()
                            self.players.clear()
                        else:
                            LOGGER.info(f'Error fetching players: {r.status}')
                    except:
                        e = sys.exc_info()[0]
                        LOGGER.info('Error getting players:', str(e))
            await asyncio.sleep(CONFIG['poll_seconds'])  # task runs every 5 minutes

    async def on_message(self, message):
        if message.author == client.user:
            return

        if message.content.startswith('$hello'):
            await message.channel.send('Hello!')


class Player(object):
    def __init__(self, rank, name, guild, job, level):
        self.rank = rank
        self.name = name
        self.guild = guild
        self.job = job
        self.level = level


init_logging()
init_config()
client = MapleBot()
slash = SlashCommand(client, sync_commands=True)

guild_ids = CONFIG['guild_ids']  # Put your server ID in this array.


@slash.slash(name="ping", guild_ids=guild_ids)
async def _ping(ctx):  # Defines a new "context" (ctx) command called "ping."
    await ctx.respond()
    await ctx.send(f"Pong! ({client.latency * 1000}ms)")


client.run(CONFIG['bot_token'])
