import discord
from discord.ext import commands
import sys
import datetime
import traceback
import json
import os
import functools
import asyncio
import click

import aiohttp
import socket

import git

from cogs.utils.cocapi import ClashOfClans
from cogs.utils.db import Table
from cogs.utils import context

json_location = os.path.join(os.getcwd(), 'creds.json')
REPO_PATH = os.path.join(os.getcwd())
BOT_TOKEN = ''

initial_extensions = [
                      'cogs.claim',
                      'cogs.update_donations',
                      'cogs.donations',
                      'cogs.admin'
                      ]

with open(json_location) as creds:
    creds = json.load(creds)


def run_bot():
    loop = asyncio.get_event_loop()

    try:
        pool = loop.run_until_complete(Table.create_pool(creds['postgresql'], command_timeout=60))
    except Exception as e:
        click.echo('Could not set up PostgreSQL. Exiting.', file=sys.stderr)
        return

    bot = AWBot()
    bot.pool = pool  # add db as attribute
    bot.run()  # run bot


class AWBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('?'), case_insensitive=True)  # setup bot
        self.remove_command('help')

        for e in initial_extensions:
            try:
                self.load_extension(e)  # load cogs
            except Exception as er:
                print(f'Failed to load extension {e}: {er}.', file=sys.stderr)

        self.http_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector
                                                  (resolver=aiohttp.AsyncResolver,
                                                   family=socket.AF_INET))

        self.loaded = creds
        self.coc_token = self.loaded['coctoken']
        self.coc = ClashOfClans(connection=self.http_session, bot=self)

        self.repo = git.Repo(REPO_PATH)
        print(self.repo)

    async def on_message(self, message):
        if message.author.bot:
            return  # ignore bot messages
        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        # we dont want logs for this stuff which isnt our problem
        ignored = (commands.NoPrivateMessage, commands.DisabledCommand, commands.CheckFailure,
                   commands.CommandNotFound, commands.UserInputError, discord.Forbidden)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        e = discord.Embed(colour=discord.Colour.red())
        exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
        e.description = f'```py\n{exc}\n```'  # format legible traceback
        e.timestamp = datetime.datetime.utcnow()

        await ctx.send(embed=e)

    async def on_command(self, ctx):
        await ctx.message.channel.trigger_typing()

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=context.Context)

        if ctx.command is None:
            return

        async with ctx.acquire():
            await self.invoke(ctx)

    async def save_json(self):

        def save_to_json():
            """
            Save json to the file.
            """

            with open(json_location, 'w') as outfile:
                json.dump(self.loaded, outfile)

        thing = functools.partial(save_to_json)
        await self.loop.run_in_executor(None, thing)

    async def update_coc_token(self, new_token):
        self.loaded['coctoken'] = new_token
        await self.save_json()

    async def on_ready(self):
        print(f'Ready: {self.user} (ID: {self.user.id})')

    def run(self):
        try:
            # super().run(BOT_TOKEN)
            super().run(creds['bottoken'])
        except Exception as e:
            print(e)


if __name__ == '__main__':
    run_bot()


