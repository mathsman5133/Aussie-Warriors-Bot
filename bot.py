from discord.ext import commands
import sys
import json
import os
import functools
import asyncio
import datetime

import aiohttp

import git

from cogs.utils.cocapi import ClashOfClans
from cogs.utils.db import Table
from cogs.utils import context

json_location = os.path.join(os.getcwd(), 'creds.json')
REPO_PATH = os.path.join(os.getcwd())

initial_extensions = [
                      'cogs.claim',
                      'cogs.update_donations',
                      'cogs.donations',
                      'cogs.admin',
                      'cogs.war_admin',
                      'cogs.mod_command_logs',
                      'cogs.war_stats'
                      ]

with open(json_location) as creds:
    creds = json.load(creds)


class AWBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('?'), case_insensitive=True)  # setup bot
        self.remove_command('help')

        for e in initial_extensions:
            try:
                self.load_extension(e)  # load cogs
            except Exception as er:
                print(f'Failed to load extension {e}: {er}.', file=sys.stderr)

        # our json loaded creds file with tokens
        self.loaded = creds

        self.coc_token = self.loaded['coctoken']

        if 'updateStats' in self.loaded.keys():
            self.update_stats = self.loaded['updateStats']
        else:
            self.loaded['updateStats'] = 'false'
            print('No updateStats value found. I have set it to default false')

        self.coc = ClashOfClans(bot=self)

        # github repo object based on main directory we're in. used for `git pull` commands
        self.repo = git.Repo(REPO_PATH)

        # list of owner userids to use in owner only command check
        self.owners = [
            230214242618441728,
            341026885985239051
        ]
        self.AW_CLAN_TAG = '#P0LYJC8C'
        self.loaded_extensions = initial_extensions  # for our reload_all command
        self.uptime = datetime.datetime.utcnow()

    async def on_message(self, message):
        if message.author.bot:
            return  # ignore bot messages
        await self.process_commands(message)

    async def on_command(self, ctx):
        # make bot 'type' so impatient people know we have received the command, if it is a long computation
        await ctx.message.channel.trigger_typing()

    async def process_commands(self, message):
        # we have a couple attributes to add to context, lets add them now (easy db connection etc.)
        ctx = await self.get_context(message, cls=context.Context)

        if ctx.command is None:
            return  # if there's no command invoked return

        async with ctx.acquire():
            await self.invoke(ctx)  # invoke command with our database connection

    async def save_json(self):
        """Coroutine helper to save our json file
        """
        def save_to_json():
            """
            Save json to the file.
            """

            with open(json_location, 'w') as outfile:
                json.dump(self.loaded, outfile)

        thing = functools.partial(save_to_json)
        await self.loop.run_in_executor(None, thing)

        self.coc_token = self.loaded['coctoken']  # update these as they won't automatically change with json file
        self.update_stats = self.loaded['updateStats']  # ''

    async def update_coc_token(self, new_token):
        """Update the coc api token in the creds json file
        """
        self.loaded['coctoken'] = new_token
        await self.save_json()

    async def on_ready(self):
        """Useful for knowing when bot has connected
        """
        print(f'Ready: {self.user} (ID: {self.user.id})')

    def httpsession(self):
        return aiohttp.ClientSession(loop=asyncio.get_event_loop())


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    try:
        # configure the database connection
        pool = loop.run_until_complete(Table.create_pool(creds['postgresql'], command_timeout=60))

        bot = AWBot()
        bot.pool = pool  # add db as attribute
        bot.run(creds['bottoken'])  # run bot

    except Exception as e:
        print(e)
        print('Could not set up PostgreSQL. Exiting.')




