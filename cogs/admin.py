from contextlib import redirect_stdout
from collections import Counter

from discord.ext import commands
from typing import Union

from cogs.utils import checks, db
from cogs.utils.help import HelpPaginator

import io
import time
import textwrap
import traceback
import datetime
import discord
import subprocess
import copy
import os
import sys
import asyncio
import inspect
import timeit


def bool_converter(string: str):
    lowered = string.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False


INVALID_METHODS = ['close', 'event', 'set_cache']


class Commands(db.Table):
    id = db.PrimaryKeyColumn()

    guild_id = db.Column(db.Integer(big=True), index=True)
    channel_id = db.Column(db.Integer(big=True))
    author_id = db.Column(db.Integer(big=True), index=True)
    used = db.Column(db.Datetime)
    prefix = db.Column(db.String)
    command = db.Column(db.String, index=True)


class Tasks(db.Table):
    id = db.PrimaryKeyColumn()

    task_name = db.Column(db.String, index=True)
    used = db.Column(db.Datetime)
    completed = db.Column(db.Boolean, index=True)


async def run_subprocess(cmd, loop=None):
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        res = await proc.communicate()
    except NotImplementedError:
        loop = loop or asyncio.get_event_loop()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        res = await loop.run_in_executor(None, proc.communicate)
    return [s.decode('utf8') for s in res]


class TabularData:
    def __init__(self):
        self._widths = []
        self._columns = []
        self._rows = []

    def set_columns(self, columns):
        self._columns = columns
        self._widths = [len(c) + 2 for c in columns]

    def add_row(self, row):
        rows = [str(r) for r in row]
        self._rows.append(rows)
        for index, element in enumerate(rows):
            width = len(element) + 2
            if width > self._widths[index]:
                self._widths[index] = width

    def add_rows(self, rows):
        for row in rows:
            self.add_row(row)

    def render(self):
        """Renders a table in rST format.
        Example:
        +-------+-----+
        | Name  | Age |
        +-------+-----+
        | Alice | 24  |
        |  Bob  | 19  |
        +-------+-----+
        """

        sep = '+'.join('-' * w for w in self._widths)
        sep = f'+{sep}+'

        to_draw = [sep]

        def get_entry(d):
            elem = '|'.join(f'{e:^{self._widths[i]}}' for i, e in enumerate(d))
            return f'|{elem}|'

        to_draw.append(get_entry(self._columns))
        to_draw.append(sep)

        for row in self._rows:
            to_draw.append(get_entry(row))

        to_draw.append(sep)
        return '\n'.join(to_draw)


class Plural:
    def __init__(self, **attr):
        iterator = attr.items()
        self.name, self.value = next(iter(iterator))

    def __str__(self):
        v = self.value
        if v == 0 or v > 1:
            return f'{v} {self.name}s'
        return f'{v} {self.name}'


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = ''

    async def on_command(self, ctx):
        command = ctx.command.qualified_name
        self.bot.command_stats[command] += 1
        message = ctx.message
        if ctx.guild is None:
            guild_id = None
        else:
            guild_id = ctx.guild.id

        query = """INSERT INTO commands (guild_id, channel_id, author_id, used, prefix, command)
                           VALUES ($1, $2, $3, $4, $5, $6)
                """

        await self.bot.pool.execute(query, guild_id, ctx.channel.id, ctx.author.id, message.created_at, ctx.prefix,
                                    command)

    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1

    async def task_stats(self, task_name, completed):
        self.bot.task_stats[task_name] += 1

        if completed:
            self.bot.tasks_completed[task_name] += 1

        now = datetime.datetime.utcnow()
        query = """INSERT INTO tasks (task_name, used, completed)
                    VALUES ($1, $2, $3)"""

        await self.bot.pool.execute(query, task_name, now, completed)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def db_init(self, ctx):
        import os
        import csv
        excel_path = os.path.join(os.getcwd(), 'cogs', 'utils', 'Sidekick_Data.csv')

        '''This only needs to be run one time, it'll create all the tables and populate them with values'''

        # Create a cursor & define Tag

        # Read the excel file containing data
        with open(excel_path) as csv_file:

            csv_reader = csv.reader(csv_file, delimiter=',')

            line_count = 0

            for row in csv_reader:
                if line_count == 0:
                    line_count += 1

                else:
                    Tag = row[1]
                    ID = int(row[3])

                    cocplayer = await self.bot.coc.players(Tag).get(self.bot.coc_token)
                    user_id = ID
                    ign = cocplayer['name']
                    tag = cocplayer['tag']

                    for achievement in cocplayer['achievements']:
                        if achievement['name'] == 'Friend in Need':
                            don = achievement['value']
                            break

                    starting_donations = don
                    current_donations = don
                    difference = 13

                    try:
                        clan = cocplayer['clan']['name']
                    except KeyError:
                        clan = ''

                    exempt = False

                    query = """INSERT INTO claims (userid, ign, tag, starting_donations, 
                                        current_donations, difference, clan, exempt) 
                                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"""

                    await ctx.db.execute(query, user_id, ign, tag, starting_donations, current_donations,
                                         difference, clan, exempt)

    @commands.command()
    @checks.is_owner()
    async def bash(self, ctx, *, cmd):
        """Run a bash command from within the bot
        """

        output, error = await run_subprocess(cmd)

        if error:
            out = f"stdout:\n{output}\nstderr:\n{error}"
        else:
            out = output

        await ctx.send(f"```{out}```")

    @commands.command()
    async def ping(self, ctx):
        duration = self.bot.latency * 1000
        await ctx.send('Pong! {:.2f}ms'.format(duration))

    @commands.command()
    @checks.is_owner()
    async def coctoken(self, ctx):
        """Manually update COCAPI Token
        [Owner only command]
        """
        token = await self.bot.coc.new_token()
        self.bot.loaded['coctoken'] = token
        await self.bot.save_json()
        await ctx.message.add_reaction('\u2705')  # green tick --> success

    @commands.group()
    @checks.is_owner()
    async def git(self, ctx):
        """Manages use of git [pull | push] during runtime

        [Owner only command]
        """
        pass

    @git.command()
    async def pull(self, ctx):
        """Pulls from repo initiated in main directory during runtime

        [Owner only command]
        """
        origin = self.bot.repo.remotes.origin
        origin.pull()
        await ctx.message.add_reaction('\u2705')

    @git.command()
    async def push(self, ctx):
        """Pushes code in main directory to initiated repo. [Not working]

        [Owner only command]
        """
        origin = self.bot.repo.remotes.origin
        origin.push()
        await ctx.message.add_reaction('\u2705')

    @commands.command()
    @checks.is_owner()
    async def load(self, ctx, *, module):
        """Load a cog during runtime
        [Owner only command]
        """

        module = module.lower()
        if not module.startswith("cogs"):
            module = f"cogs.{module}"
        try:
            self.bot.load_extension(module)
        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.message.add_reaction('\u2705')

    @commands.command()
    @checks.is_owner()
    async def unload(self, ctx, *, module):
        """Unload a cog during runtime
        [Owner only command]
        """
        module = module.lower()
        if not module.startswith("cogs"):
            module = f"cogs.{module}"

        try:
            self.bot.unload_extension(module)

        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.message.add_reaction('\u2705')

    @commands.command()
    @checks.is_owner()
    async def reload(self, ctx, *, module):
        """Reloads a cog during runtime
        [Owner only command]
        """
        module = module.lower()
        if not module.startswith("cogs"):
            module = f"cogs.{module}"

        try:
            self.bot.unload_extension(module)
            self.bot.load_extension(module)
        except:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.message.add_reaction('\u2705')

    @commands.command()
    @checks.is_owner()
    async def reload_all(self, ctx):
        """Reloads all cogs initiated on startup of bot

        [Owner only command]
        """
        for extension in self.bot.loaded_extensions:
            try:
                self.bot.unload_extension(extension)
                self.bot.load_extension(extension)
            except:
                await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        await ctx.message.add_reaction('\u2705')

    @commands.command()
    @checks.is_owner()
    async def logout(self, ctx):
        """Logs out of the bot's current session

        [Owner only command]
        """
        await ctx.message.add_reaction('\u2705')
        await self.bot.logout()

    @commands.command()
    @checks.is_owner()
    async def restart(self, ctx):
        """Logs out and logs back into the bot

        [Owner only command]
        """
        os.execve(sys.executable, ['python3.6', 'bot.py'], os.environ)

    @commands.command()
    @checks.is_owner()
    async def update_and_restart(self, ctx):
        await run_subprocess("git fetch origin master && git reset --hard FETCH_HEAD")
        await run_subprocess("python3.6 -m pip install --upgrade -r requirements.txt")
        os.execve(sys.executable, ['python3.6', 'bot.py'], os.environ)

    @commands.command()
    @checks.is_owner()
    async def send_text(self, ctx, channel_id: int, *, message):
        """Allows you to send a plain text message to a channel with the bot.

        Parameters: Channel ID (int), message
        Eg. ?send_text 12345678 this is my message

        [Owner only command]
        """
        channel = self.bot.get_channel(channel_id)

        try:
            await channel.send(message)
            await ctx.message.add_reaction('\u2705')
        except:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @commands.command()
    @checks.is_owner()
    async def send_embed(self, ctx, channel_id: int, *, message):
        """Allows you to send a embeded message to a channel with the bot.

        Parameters: Channel ID (int), message
        Eg. ?send_text 12345678 this is my message

        [Owner only command]
        """
        channel = self.bot.get_channel(channel_id)

        if not channel:
            return ctx.send("Invalid channel ID: either I am not in that server or it doesn't exist")

        if ctx.message.attachments:
            message = message + ctx.message.attachments[0].url

        e = discord.Embed(colour=discord.Colour.blue())  # blue --> informative
        e.description = message

        try:
            await channel.send(embed=e)
            await ctx.message.add_reaction('\u2705')
        except:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @commands.command()
    @checks.is_owner()
    async def status(self, ctx, *, status: str):
        """Updates the bot's playing status

        [Owner only command]
        """
        try:
            await self.bot.change_presence(activity=discord.Game(name=status, type=0))
            await ctx.message.add_reaction('\u2705')
        except:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @commands.command(name='eval')
    @checks.is_owner()
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code

        [Owner only command]
        """

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result,
            'self': self,
            'coc': self.bot.coc
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            error = getattr(e, 'original', e)
            e = discord.Embed(colour=discord.Colour.red())
            exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
            e.description = f'```py\n{exc}\n```'  # format legible traceback
            e.timestamp = datetime.datetime.utcnow()

            if len(exc) > 2000:
                fp = io.BytesIO(exc.encode('utf-8'))
                await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
            else:
                await ctx.send(embed=e)
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    if len(value) > 2000:
                        fp = io.BytesIO(value.encode('utf-8'))
                        await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
                    else:
                        await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                if len(value) > 2000:
                    fp = io.BytesIO(value.encode('utf-8'))
                    await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
                else:
                    await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command()
    async def teval(self, ctx, *, body: str):
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result,
            'self': self,
            'coc': self.bot.coc
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'
        import ast
        try:
            r = ast.literal_eval(body)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        await ctx.send(f'```py\n{r}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            error = getattr(e, 'original', e)
            e = discord.Embed(colour=discord.Colour.red())
            exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
            e.description = f'```py\n{exc}\n```'  # format legible traceback
            e.timestamp = datetime.datetime.utcnow()

            if len(exc) > 2000:
                fp = io.BytesIO(exc.encode('utf-8'))
                await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
            else:
                await ctx.send(embed=e)
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    if len(value) > 2000:
                        fp = io.BytesIO(value.encode('utf-8'))
                        await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
                    else:
                        await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                if len(value) > 2000:
                    fp = io.BytesIO(value.encode('utf-8'))
                    await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
                else:
                    await ctx.send(f'```py\n{value}{ret}\n```')

    # @commands.command()
    # async def timeit(self, ctx, *, body: str):
    #     attributes = body.split('.')
    #     call = self.bot.coc
    #     result = ''
    #     for attr in attributes:
    #         if attr in ['coc', 'coc_client']:
    #             continue
    #         if '(' in attr:
    #             new_attr = attr.split('(')[0]
    #             func = getattr(call, new_attr)
    #             params = attr.split('(')[1][:-1].split(',')
    #             args = []
    #             kwargs = {}
    #             for p in params:
    #                 sp = p.split('=')
    #                 if len(sp) == 1:
    #                     args.append(p)
    #                     continue
    #                 kwargs[sp[0]] = sp[1]
    #             if asyncio.iscoroutinefunction(func):
    #                 res = await func(*args, **kwargs)
    #             else:
    #                 res = func(*args, **kwargs)
    #
    #             result = res
    #

    @commands.command()
    async def timeit(self, ctx):
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send('Welcome! Please type the name of the function you would like to time today'
                       ' eg. if you wanted to use `coc.get_clan(...)` you would type `get_clan`.')

        msg = await self.bot.wait_for('message', check=check)

        try:
            method = getattr(self.bot.coc, msg.content)
        except AttributeError:
            return await ctx.send('Could not find the method provided! Please see the docs: '
                                  'https://cocpy.readthedocs.io/en/latest/')

        if method.__name__ in INVALID_METHODS:
            return await ctx.send('Valid method not provided (this is a private method not for public use.)')

        try:
            ispct = inspect.signature(method)
        except TypeError:
            return await ctx.send('Valid method not provided (you passed an attribute - not a method). '
                                  'Please see the docs for more info: https://cocpy.readthedocs.io/en/latest/')

        args = [n for n in ispct.parameters]
        args_to_pass = {}
        if args:
            for arg in args:
                await ctx.send(f'What would you like to pass for the {arg} parameter?')
                msg = await self.bot.wait_for('message', check=check)
                if bool_converter(msg.content) is True:
                    args_to_pass[arg] = True
                elif bool_converter(msg.content) is False:
                    args_to_pass[arg] = False
                else:
                    args_to_pass[arg] = msg.content
        try:
            to_use_cache = args_to_pass.pop('cache', False)
            to_fetch = args_to_pass.pop('fetch', True)

            if inspect.iscoroutinefunction(method):
                s = time.perf_counter()
                result = await method(cache=to_use_cache, fetch=to_fetch,
                                      **args_to_pass)
                f = time.perf_counter()
            else:
                s = time.perf_counter()
                result = await method(cache=to_use_cache, fetch=to_fetch,
                                      **args_to_pass)
                f = time.perf_counter()
        except Exception as e:
            exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
            return await ctx.send(f'Oops, something broke!\n```py\n{exc}\n```')

        time_taken = (f - s)*1000
        if len(str(result)) < 2000:
            await ctx.send(f'Awesome! Time Taken: {time_taken}ms\n```py\nResults:\n{result}\n```')
        else:
            fp = io.BytesIO(str(result).encode('utf-8'))
            await ctx.send(f'Too many results... but you took {time_taken}ms!', file=discord.File(fp, 'results.txt'))

        async def attribute_access(cls):
            await ctx.send('Please type the name of any attribute you would like to get of the results you found. '
                           'I will time attribute access, too.')

            msg = await self.bot.wait_for('message', check=check)

            s = time.perf_counter()
            try:
                attribute = getattr(cls, msg.content)
            except AttributeError:
                return await ctx.send('Could not find the attribute provided! Please see the docs: '
                                      f'https://cocpy.readthedocs.io/en/latest/api.html#coc.{cls.__class__.__name__}')

            f = time.perf_counter()

            time_taken = (f - s)*1000
            if len(str(attribute)) < 2000:
                await ctx.send(f'Awesome! Time Taken: {time_taken}ms\n```py\nResults:\n{str(attribute)}\n```')
            else:
                fp = io.BytesIO(str(attribute).encode('utf-8'))
                await ctx.send(f'Too many results... but you took {time_taken}ms!', file=discord.File(fp, 'results.txt'))

            return attribute

        attribute = result
        while True:
            try:
                attribute.__module__
            except AttributeError:
                break
            result = await attribute_access(attribute)
            if isinstance(result, discord.Message):
                return
            attribute = result

        return await ctx.send('All done! Thanks...')

    def time(self, *, function_string, to_repeat):
        async def fctn():
            function_string
        # fctn = f"async dec func(): return {function_string}"
        return timeit.timeit(fctn(), to_repeat)

    @commands.command()
    async def loop_timer(self, ctx, to_repeat: int=10):
        if to_repeat > 10:
            return await ctx.send('Can\'t loop through this function more than 10 times. Sorry.')
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send('Welcome! Please type the name of the function you would like to time today'
                       ' eg. if you wanted to use `coc.get_clan(...)` you would type `get_clan`.')

        msg = await self.bot.wait_for('message', check=check)

        try:
            method = getattr(self.bot.coc, msg.content)
        except AttributeError:
            return await ctx.send('Could not find the method provided! Please see the docs: '
                                  'https://cocpy.readthedocs.io/en/latest/')

        if method.__name__ in INVALID_METHODS:
            return await ctx.send('Valid method not provided (this is a private method not for public use.)')

        try:
            ispct = inspect.signature(method)
        except TypeError:
            return await ctx.send('Valid method not provided (you passed an attribute - not a method). '
                                  'Please see the docs for more info: https://cocpy.readthedocs.io/en/latest/')

        args = [n for n in ispct.parameters]
        args_to_pass = {}
        if args:
            for arg in args:
                await ctx.send(f'What would you like to pass for the {arg} parameter?')
                msg = await self.bot.wait_for('message', check=check)
                if bool_converter(msg.content) is True:
                    args_to_pass[arg] = True
                elif bool_converter(msg.content) is False:
                    args_to_pass[arg] = False
                else:
                    args_to_pass[arg] = msg.content
        try:
            to_use_cache = args_to_pass.pop('cache', False)
            to_fetch = args_to_pass.pop('fetch', True)

            async def func():
                return await method(cache=to_use_cache, fetch=to_fetch,
                                    **args_to_pass)

            env = {'func': await func()}
            env.update(globals())

            time_taken = timeit.timeit('func', globals=env, number=to_repeat)
            result = await func()

        except Exception as e:
            exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
            return await ctx.send(f'Oops, something broke!\n```py\n{exc}\n```')

        await ctx.send(f'```\nTime Taken: {time_taken}ms\nLoops: {to_repeat}\n'
                       f'Time Per Loop (avg): {time_taken / to_repeat}```')

        async def attribute_access(cls):
            await ctx.send('Please type the name of any attribute you would like to get of the results you found. '
                           'I will time attribute access, too.')

            attribute = (await self.bot.wait_for('message', check=check)).content

            try:
                getattr(cls, attribute)
            except AttributeError:
                return await ctx.send('Could not find the attribute provided! Please see the docs: '
                                      f'https://cocpy.readthedocs.io/en/latest/api.html#coc.{cls.__class__.__name__}')

            await ctx.send('Please type the number of loops you wish to repeat (must be <1000)')
            msg = await self.bot.wait_for('message', check=check)
            to_repeat = int(msg.content)
            if to_repeat > 1000:
                return await ctx.send('Goodbye. Loops must be below 1000, *like I told you*.')

            env = {'cls': cls,
                   'attribute': attribute}
            env.update(globals())

            time_taken = timeit.timeit('getattr(cls, attribute)', globals=env, number=to_repeat)
            attribute = getattr(cls, attribute)

            await ctx.send(f'```\nTime Taken: {time_taken}ms\nLoops: {to_repeat}\n'
                           f'Time Per Loop (avg): {time_taken / to_repeat}```')

            return attribute

        attribute = result
        while True:
            try:
                attribute.__module__
            except AttributeError:
                break
            result = await attribute_access(attribute)
            if isinstance(result, discord.Message):
                return
            attribute = result

        return await ctx.send('All done! Thanks...')







    @commands.command(name='help')
    async def _help(self, ctx, *, command: str = None):
        """Shows help about a command or cog

        Parameters: command or cog (optional, string)
        Eg. `?help about` or `?help Admin`
        """

        try:
            # if no command supplied to get help for run default help paginator
            if command is None:
                p = await HelpPaginator.from_bot(ctx)
            else:
                # get command from bot
                entity = self.bot.get_cog(command) or self.bot.get_command(command)
                # if nothing found return
                if entity is None:
                    clean = command.replace('@', '@\u200b')
                    return await ctx.send(f'Command or category "{clean}" not found.')

                # if its a command do help paginator for commands
                elif isinstance(entity, commands.Command):
                    p = await HelpPaginator.from_command(ctx, entity)

                # if its a cog do help paginator for cog
                else:
                    p = await HelpPaginator.from_cog(ctx, entity)

            # start paginating
            await p.paginate()
        except Exception as e:
            await ctx.send(e)

    @commands.command()
    async def socketstats(self, ctx):
        """Tells you how many socket stats the bot has observed during uptime
        """
        delta = datetime.datetime.utcnow() - self.bot.uptime
        minutes = delta.total_seconds() / 60
        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes
        await ctx.send(f'{total} socket events observed ({cpm:.2f}/minute):\n{self.bot.socket_stats}')

    @commands.command()
    async def commandstats(self, ctx, limit=20):
        """Shows command stats.
        Use a negative number for bottom instead of top.
        This is only for the current session.
        """
        counter = self.bot.command_stats
        width = len(max(counter, key=len))

        if limit > 0:
            common = counter.most_common(limit)
        else:
            common = counter.most_common()[limit:]

        output = '\n'.join(f'{k:<{width}}: {c}' for k, c in common)

        await ctx.send(f'```\n{output}\n```')

    @commands.command()
    async def taskstats(self, ctx):
        """Tells you how many tasks (checking for war status ended/donations etc) have been run
        """
        await ctx.send(f'Total tasks run since uptime: \n{self.bot.task_stats}'
                       f'\nTotal tasks actually completed: \n{self.bot.tasks_completed}')

    @commands.command()
    async def uptime(self, ctx):
        """Returns how long the bot has been running for
        """
        await ctx.send(f'Uptime: **{self.get_bot_uptime()}**')

    @commands.command()
    @checks.is_owner()
    async def sql(self, ctx, *, query: str):
        """Run some SQL.

        [Owner only command]
        """
        # the imports are here because I imagine some people would want to use
        # this cog as a base for their other cog, and since this one is kinda
        # odd and unnecessary for most people, I will make it easy to remove
        # for those people.


        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = ctx.db.execute
        else:
            strategy = ctx.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {Plural(row=rows)} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    def get_bot_uptime(self):
        now = datetime.datetime.utcnow()
        delta = now - self.bot.uptime
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if days:
            fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
        else:
            fmt = '{h} hours, {m} minutes, and {s} seconds'

        return fmt.format(d=days, h=hours, m=minutes, s=seconds)

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.command(hidden=True)
    @checks.is_owner()
    async def sudo(self, ctx, who: Union[discord.Member, discord.User], *, command: str):
        """Run a command as another user."""
        msg = copy.copy(ctx.message)
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg)
        new_ctx.db = ctx.db
        await self.bot.invoke(new_ctx)


def setup(bot):
    if not hasattr(bot, 'command_stats'):
        bot.command_stats = Counter()

    if not hasattr(bot, 'socket_stats'):
        bot.socket_stats = Counter()

    if not hasattr(bot, 'task_stats'):
        bot.task_stats = Counter()

    if not hasattr(bot, 'tasks_completed'):
        bot.tasks_completed = Counter()

    bot.add_cog(Admin(bot))

