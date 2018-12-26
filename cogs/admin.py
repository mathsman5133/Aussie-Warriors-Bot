import discord
from discord.ext import commands
import time
import os
import io
from contextlib import redirect_stdout
import textwrap
import traceback
import datetime
from cogs.utils.help import HelpPaginator
import pickle
import csv

db_path = os.path.join(os.getcwd(), 'mathsbots.db')


class GuildCommandStats:
    async def show_guild_stats(self, ctx):
        # emojis for top 5
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{CLAPPING HANDS SIGN}',
            '\N{CLAPPING HANDS SIGN}'
        )
        # make embed with blurple colour
        embed = discord.Embed(colour=discord.Colour.blurple(), title='Command Stats')
        # get first command and number of commands in db
        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT COUNT(*), MIN(used) FROM commands WHERE guild_id = :guild_id",
                                 {'guild_id': ctx.guild.id})
            dump = await c.fetchall()
        # add number of commands to embed
        embed.description = f'{dump[0][0]} commands used.'
        # add first commands date to embed
        embed.set_footer(text="Tracking commands since: ").timestamp = \
            datetime.datetime.strptime(dump[0][1], '%Y-%m-%d %H:%M:%S.%f'
                                                   or datetime.datetime.utcnow())

        # get commands from db and count total number per command
        # get top 5 descending
        async with aiosqlite.connect(db_path) as db:
            c = await db.execute('SELECT command, COUNT(*) as "uses" FROM commands WHERE guild_id = :guild_id'
                                 ' GROUP BY command ORDER BY "uses" DESC LIMIT 5', {'guild_id': ctx.guild.id})
            cmdump = await c.fetchall()
        uses = []
        command = []
        # get uses and command in a nice list which we can use rather than [('!help','5'), ('!ping', '3')]
        for a in cmdump:
            uses.append(a[1])
            command.append(a[0])
        # join them together with emoji
        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(cmdump)) or 'No Commands'
        # add top commands field
        embed.add_field(name='Top Commands', value=value, inline=True)

        # its basically the exact same as above 3x again so I'm not gonna type it out again
        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT command, COUNT(*) as 'uses' FROM commands WHERE guild_id = :guild_id"
                                 " AND used > (CURRENT_TIMESTAMP - 1) "
                                 "GROUP BY command ORDER BY 'uses' DESC LIMIT 5",
                                 {'guild_id': ctx.guild.id})
            todaycmdump = await c.fetchall()

        uses = []
        command = []
        for a in cmdump:
            uses.append(a[1])
            command.append(a[0])
        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(todaycmdump)) or 'No Commands'

        embed.add_field(name='Top Commands Today', value=value, inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)

        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT author_id, COUNT(*) as 'uses' FROM commands WHERE guild_id = :guild_id"
                                 " GROUP BY author_id ORDER BY 'uses' DESC LIMIT 5", {'guild_id': ctx.guild.id})
            authdump = await c.fetchall()
        uses = []
        command = []
        for a in cmdump:
            print(a)
            uses.append(a[1])
            command.append(a[0])

        value = '\n'.join(f'{lookup[index]}: <@!{command}> ({uses} bot uses)'
                          for (index, (command, uses)) in enumerate(authdump)) or 'No bot users.'

        embed.add_field(name='Top Command Users', value=value, inline=True)

        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT author_id, COUNT(*) as 'uses' FROM commands WHERE guild_id = :guild_id"
                                 " AND used > (CURRENT_TIMESTAMP - 1) GROUP BY author_id ORDER BY 'uses' DESC LIMIT 5",
                                 {'guild_id': ctx.guild.id})
            todayauthdump = await c.fetchall()

        uses = []
        command = []
        for a in cmdump:
            print(a)
            uses.append(a[1])
            command.append(a[0])

        value = '\n'.join(f'{lookup[index]}: <@!{command}> ({uses} bot uses)'
                          for (index, (command, uses)) in enumerate(todayauthdump)) or 'No command users.'

        embed.add_field(name='Top Command Users Today', value=value, inline=True)
        await ctx.send(embed=embed)

    async def show_member_stats(self, ctx, member):
        # basically same as show guild stats but for a member
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{CLAPPING HANDS SIGN}',
            '\N{CLAPPING HANDS SIGN}'
        )

        embed = discord.Embed(title='Command Stats', colour=member.colour)
        embed.set_author(name=str(member), icon_url=member.avatar_url)

        # total command uses
        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT COUNT(*), MIN(used) FROM commands WHERE guild_id=:id AND author_id=:aid",
                                 {'id': ctx.guild.id, 'aid': member.id})
            count = await c.fetchall()

        embed.description = f'{count[0][0]} commands used.'
        embed.set_footer(text='First command used').timestamp = \
            datetime.datetime.strptime(count[0][1], '%Y-%m-%d %H:%M:%S.%f'
                                       or datetime.datetime.utcnow())

        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT command, COUNT(*) as 'uses' "
                                 "FROM commands WHERE guild_id = :gid "
                                 "AND author_id = :aid GROUP BY command ORDER BY 'uses' DESC LIMIT 5",
                                 {'gid': ctx.guild.id, 'aid': member.id})
            records = await c.fetchall()

        uses = []
        command = []
        for a in records:
            print(a)
            uses.append(a[1])
            command.append(a[0])

        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(records)) or 'No Commands'

        embed.add_field(name='Most Used Commands', value=value, inline=False)

        async with aiosqlite.connect(db_path) as db:
            c = await db.execute("SELECT command, COUNT(*) as 'uses' "
                                 "FROM commands WHERE guild_id=:gid "
                                 "AND author_id=:aid AND used > (CURRENT_TIMESTAMP - 1) "
                                 "GROUP BY command ORDER BY 'uses' DESC LIMIT 5",
                                 {'gid': ctx.guild.id, 'aid': member.id})
            records = await c.fetchall()
        uses = []
        command = []
        for a in records:
            print(a)
            uses.append(a[1])
            command.append(a[0])

        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(records)) or 'No Commands'

        embed.add_field(name='Most Used Commands Today', value=value, inline=False)
        await ctx.send(embed=embed)


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

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.command()
    async def csv(self, ctx):
        fieldnames = ['', 'ClashID', 'Nick#Discrim', 'UserID']
        after = []
        with open('C:/Users/User/py/aussie-warriors-bot/Clash-Discord-IDs.csv', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            print(csv_reader)
            line = 0
            for n in csv_reader:
                print(n)
                if line == 0:
                    n.append('UserID')
                    line += 1
                else:
                    id = self.bot.get_guild(352298238180851712).get_member_named(n[2])
                    try:
                        n.append(id.id)
                    except:
                        n.append(None)

                    print(id)
                after.append(n)

        print(after)
        with open('C:/Users/User/py/aussie-warriors-bot/pickle.txt', mode='wb') as fp:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            dic = []
            for n in after:
                dic.append({'': n[0], 'ClashID': n[1], 'Nick#Discrim': n[2], 'UserID': n[3]})
            pickle.dump(dic, fp)


        with open('C:/Users/User/py/aussie-warriors-bot/aristocrats_members.csv', mode='w', encoding='utf-8', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['Name', 'ID'])
            for member in self.bot.get_guild(352298238180851712).get_role(390068631708499971).members:
                writer.writerow({'Name': member.name, 'ID': member.id})

    @commands.command()
    async def db_init(self, ctx):
        import os
        import csv
        excel_path = os.path.join(os.getcwd(), 'cogs', 'utils', 'Sidekick_Data.csv')

        '''This only needs to be run one time, it'll create all the tables and populate them with values'''

        # Create a cursor & define Tag

        # Read the excel file containing data
        with open(excel_path) as csv_file:
            print('ok')
            csv_reader = csv.reader(csv_file, delimiter=',')
            print(csv_reader)
            line_count = 0

            for row in csv_reader:
                print(line_count)
                if line_count == 0:
                    line_count += 1

                else:
                    print('ok')
                    Tag = row[1]
                    print(Tag)
                    ID = int(row[3])
                    cocplayer = await self.bot.coc.players(Tag).get(self.bot.coc_token)
                    user_id = ID
                    ign = cocplayer['name']
                    tag = cocplayer['tag']

                    for achievement in cocplayer['achievements']:
                        if achievement['name'] == 'Friend in Need':
                            don = achievement['value']
                            break
                    print('ok')

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
                    print('ok')

    @commands.command()
    async def tti(self, ctx):
        import csv
        excel_path = os.path.join(os.getcwd(), 'cogs', 'utils', 'Sidekick_Data.csv')

        async def oneTimeSetup(coc, connection, coc_token):
            '''This only needs to be run one time, it'll create all the tables and populate them with values'''

            # Create a cursor & define Tag
            cursor = connection
            clanTag = '#P0LYJC8C'

            # #Create a table to store clash tag and discord ID
            # await cursor.execute('Create table Tag_to_ID(Tag VARCHAR(20) PRIMARY KEY,ID VARCHAR(60) NOT NULL)')
            #
            # #Create a table to store tags of last war (tags for current war will be retrived via api and then this table will be updated)
            # await cursor.execute('Create table last_war(Tag VARCHAR(20) PRIMARY KEY)')

            # Read the excel file containing data
            # import pandas as pd
            # df = pd.read_excel(excel_path)
            #
            # #This bit here is gonna look ugly, usually I'd make a seperate function but it's one time only...
            #
            # for index, row in df.iterrows():
            with open(excel_path) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                line_count = 0
                for row in csv_reader:
                    if line_count == 0:
                        line_count += 1
                        pass
                    else:
                        Tag = row[1]
                        ID = row[3]
                        sql = f'''INSERT INTO Tag_to_ID(Tag,ID) VALUES('{Tag}','{ID}')'''
                        await cursor.execute(sql)

            # Cleanup~!
            # del df

            # Next, let's populate the 'last_war' table to store values of current war

            # Query to get details for current war
            currentWar = await coc.clans(clanTag).currentwar().get(coc_token)

            # Get the list of tags
            tags = [x['tag'] for x in currentWar['clan']['members']]

            # populate the table
            for tag in tags:
                sql = f'''INSERT INTO last_war(Tag) VALUES('{tag}')'''
                await cursor.execute(sql)

        await oneTimeSetup(self.bot.coc, ctx.db, self.bot.coc_token)

    @commands.group(name="git")
    async def git(self, ctx):
        pass

    @git.command()
    async def pull(self, ctx):
        origin = self.bot.repo.remotes.origin
        origin.pull()
        await ctx.message.add_reaction('\u2705')

    @git.command()
    async def test(self, ctx):
        await ctx.message.add_reaction('\u2705')

    # @git.command()
    # async def push(self, ctx):
    #     origin = self.bot.repo.remotes.origin
    #     origin.push()
    #     await ctx.message.add_reaction('\u2705')

    @commands.command()
    @commands.is_owner()
    async def stat(self, ctx, *, member: discord.Member = None):
        """Tells you command usage stats for the server or a member.
            PARAMETERS: optional: [member] - a ping, name#discrim or userid
            EXAMPLE: `stats @mathsman` or `stats`
            RESULT: Returns command stats for mathsman or server as a whole"""
        # if no mention show guild stats
        if member is None:
            await GuildCommandStats().show_guild_stats(ctx)
        # else show member stats
        else:
            await GuildCommandStats().show_member_stats(ctx, member)

    @commands.command()
    @commands.is_owner()
    async def load(self, ctx, *, module):
        """Load a cog/extension. Available cogs to reload: `ClaimCommands`, `PlayerCommands`, `ClanCommands`, `DownloadCommands`, `DatabaseCommands`.
                PARAMETERS: [extension name]
                EXAMPLE: `load DownloadCommands`
                RESULT: Loads commands: dl and stopdl. These will now work. Returns result"""
        module = module.lower()
        if not module.startswith("cogs"):
            module = f"cogs.{module}"
        try:
            self.bot.load_extension(module)
        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command()
    @commands.is_owner()
    async def unload(self, ctx, *, module):
        """Unloads a cog/extension. Available cogs to unload: `ClaimCommands`, `PlayerCommands`, `ClanCommands`, `DownloadCommands`.
                PARAMETERS: [extension name]
                EXAMPLE: `unload DownloadCommands`
                RESULT: Unloads commands: dl and stopdl. These will now not work. Returns result"""
        module = module.lower()
        if not module.startswith("cogs"):
            module = f"cogs.{module}"

        try:
            self.bot.unload_extension(module)

        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, *, module):
        module = module.lower()
        if not module.startswith("cogs"):
            module = f"cogs.{module}"

        self.bot.unload_extension(module)
        self.bot.load_extension(module)
        await ctx.send("\N{THUMBS UP SIGN}")

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx):
        await ctx.send("\N{THUMBS UP SIGN}")
        await self.bot.logout()
        await self.bot.close()

    @commands.command()
    @commands.is_owner()
    async def send_message(self,ctx, cid: int, *, message):
        channel = self.bot.get_channel(cid)

        try:
            await channel.send(message)
            await ctx.send("\N{THUMBS UP SIGN}")
        except Exception as e:
            await ctx.send(f'```py\n{e}\n```')

    @commands.command(name='sqlite')
    @commands.is_owner()
    async def _sqlite(self, ctx, *, query: str):
        try:
            start = time.perf_counter()
            async with aiosqlite.connect(db_path) as db:
                c = await db.execute(query)
                dt = (time.perf_counter() - start) * 1000.0
                try:
                    dump = await c.fetchall()
                    desc = c.description
                    await db.commit()
                except:
                    await db.commit()
                    return await ctx.send(f'`{dt:.2f}ms`')
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        if len(dump) == 0:
            return await ctx.send(f'`{dt:.2f}ms`')
        headers = list([r[0] for r in desc])
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r for r in dump))
        render = table.render()
        fmt = f'```\n{render}\n```\n*Returned in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    @commands.command(pass_context=True, hidden=True, name='eval')
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
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

    @commands.command()
    @commands.is_owner()
    async def status(self, ctx, *, status: str):
        try:
            await self.bot.change_presence(activity=discord.Game(name=status, type=0))
            await ctx.send("\N{THUMBS UP SIGN}")
        except Exception as e:
            await ctx.send(f'```py\n{e}\n```')

    @commands.command(name='help')
    async def _help(self, ctx, *, command: str = None):
        """Shows help about a command or cog

        PARAMETERS: optional: command or cog name

        EXAMPLE: `help about`

        RESULT: Returns a help message for `about` command"""

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

    @commands.command(hidden=True)
    async def socketstats(self, ctx):
        delta = datetime.datetime.utcnow() - self.bot.uptime
        minutes = delta.total_seconds() / 60
        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes
        await ctx.send(f'{total} socket events observed ({cpm:.2f}/minute):\n{self.bot.socket_stats}')

    @commands.command(hidden=True)
    async def sql(self, ctx, *, query: str):
        """Run some SQL."""
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


def setup(bot):
    bot.add_cog(Admin(bot))

