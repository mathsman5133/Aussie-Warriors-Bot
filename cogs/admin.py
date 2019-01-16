from contextlib import redirect_stdout
from collections import Counter

from discord.ext import commands
from typing import Union

from cogs.utils import checks, db
from cogs.utils.help import HelpPaginator

import io
import textwrap
import traceback
import datetime
import discord
import subprocess
import copy


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


class Admin:
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

        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()

        e = discord.Embed()
        e.description = str(output, 'utf-8')

        if error:
            e.colour = discord.Colour.red()
            e.add_field(name="Error:", value=str(error, 'utf-8'))

        else:
            e.colour = discord.Colour.green()

        await ctx.send(embed=e)

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
    async def shutdown(self, ctx):
        """Logs out of the bot's current session

        [Owner only command]
        """
        await ctx.message.add_reaction('\u2705')
        await self.bot.logout()
        await self.bot.close()

    @commands.command()
    @checks.is_owner()
    async def reconnect(self, ctx):
        """Logs out and logs back into the bot

        [Owner only command]
        """
        await self.bot.logout()
        await self.bot.start(token=self.bot.loaded['bottoken'])
        await ctx.message.add_reaction('\u2705')


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
            'self': self
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
            await ctx.send(embed=e)
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

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
        total = sum(counter.values())

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

        import time

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

