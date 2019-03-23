from discord.ext import commands
import discord
from cogs.utils import db, checks, time
import datetime
import asyncio
from cogs.war_admin import list_to_sql_tuple


class WarningsTable(db.Table, table_name='warnings'):
    id = db.PrimaryKeyColumn()

    user_id = db.Column(db.Integer(big=True))
    reason = db.Column(db.String())
    timestamp = db.Column(db.Datetime())
    expires = db.Column(db.Datetime(), index=True)
    active = db.Column(db.Boolean(), index=True)


class Warnings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.LEADER_NOTES_ROOM = 410036214780133398
        self.wait_for_timers_task = self.bot.loop.create_task(self.wait_for_timers())

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            e = discord.Embed(colour=discord.Colour.red())
            e.description = error
            await ctx.send(embed=e)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Missing required argument {error}!')
            await ctx.show_help()

    def cog_unload(self):
        self.wait_for_timers_task.cancel()

    @commands.group(name='warn', aliases=['warnings'], invoke_without_command=True)
    @checks.is_leader()
    async def _warnings(self, ctx, user: discord.Member, *, reason=None):
        """[Group] Manage Server Specific Warnings

        Invoke without a subcommand to warn someone with a reason (same as `warn add`)

        Usage: `{ctx.prefix}warn [user] [reason: optional]`

        You must have `Leadership Team` role to use these commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('warn add'), user=user, reason=reason)

    @_warnings.command()
    async def add(self, ctx, user: discord.Member, *, reason=None):
        """Add a warning to a member

        Usage: `{ctx.prefix}warn add [user] [reason: optional]`

        You must have `Leadership Team` role to use these commands.
        """
        if not reason:
            db_reason = f'Warned by {str(ctx.author)} (no reason)'

        else:
            db_reason = f'Warned by {str(ctx.author)} Reason: {reason}'

        query = "INSERT INTO warnings " \
                "(user_id, reason, timestamp, expires, active)" \
                "VALUES ($1, $2, $3, $4, True) RETURNING id;"
        td = datetime.datetime.utcnow() + datetime.timedelta(days=7)

        dump = await ctx.db.fetchrow(query, user.id,
                                     db_reason, ctx.message.created_at,
                                     td)

        query = "SELECT * FROM warnings WHERE user_id = $1 AND active = True"
        n = await ctx.db.fetch(query, user.id)
        warning_no = len(n)

        await ctx.message.delete()

        try:
            await user.send(f"You have been warned by {str(ctx.author)} for: {reason or 'No Reason'}")
        except discord.Forbidden:
            pass

        e = discord.Embed(colour=0x36393E)
        e.set_author(name=str(user), icon_url=user.avatar_url)
        e.add_field(name=f'Warning No.{warning_no}',
                    value=str(user))
        e.add_field(name='Moderator',
                    value=ctx.author.mention)
        e.add_field(name='Reason',
                    value=reason or 'No Reason')
        e.set_footer(text=f'Warning ID: {dump[0]}.This warning will expire in 7d').timestamp = datetime.datetime.utcnow()

        channel = self.bot.get_channel(self.LEADER_NOTES_ROOM)
        await channel.send(embed=e)

    @_warnings.command(aliases=['delete'])
    async def remove(self, ctx, *warning_ids: int):
        """Remove warning(s) by ID

        Usage: `{ctx.prefix}warn remove [ids to remove seperates by a space]`
        Example: `{ctx.prefix}warn remove 1 21 3 4 53`

        ID can be found by using `{ctx.prefix}warns [user]` or `{ctx.prefix}warn show [user]`.

        You must have `Leadership Team` role to use these commands.
        """
        query = f"UPDATE warnings SET active=False WHERE id IN {list_to_sql_tuple(warning_ids)}"
        await ctx.db.execute(query)

        await ctx.tick()

    @_warnings.command(name='clear')
    async def _clear(self, ctx, *users: discord.Member):
        """Clear warnings for member(s)

        Usage: `{ctx.prefix}warn clear [users seperated by a space]`
        Eg. `{ctx.prefix}warn clear @mathsman @lil @rah @proto`

        You must have `Leadership Team` role to use these commands.
        """
        query = f"UPDATE warnings SET active=False WHERE user_id IN {list_to_sql_tuple([n.id for n in users])}"
        await ctx.db.execute(query)

        await ctx.tick()

    @_warnings.command(aliases=['list'])
    async def show(self, ctx, user: discord.Member=None):
        """Show warnings for a member

        Usage: `{ctx.prefix}warn show [user: optional]`

        Specify no user to get all active warnings.

        You must have `Leadership Team` role to use these commands.
        """

        if not user:
            query = "SELECT id, reason, expires, user_id FROM warnings WHERE active = True"
            dump = await ctx.db.fetch(query)
        else:
            query = "SELECT id, reason, expires, user_id FROM warnings WHERE user_id=$1 AND active = True"
            dump = await ctx.db.fetch(query, user.id)

        e = discord.Embed(colour=0x36393E)
        if user:
            e.set_author(name=str(user), icon_url=user.avatar_url)

        e.title = 'Active Warnings:'
        e.description = '\u200b'
        for n in dump:
            user = self.bot.get_user(n['user_id'])
            expires_in = time.human_timedelta(n['expires'])
            e.add_field(name=f"{str(user)}: Warning ID {n['id']}",
                        value=f"{n['reason']}\nExpires in {expires_in}\n\n",
                        inline=False)

        e.set_footer(text=f'Total Warnings: {len(dump)}').timestamp = datetime.datetime.utcnow()

        await ctx.send(embed=e)

    @commands.command(hidden=True)
    async def warns(self, ctx, user: discord.Member=None):
        """Show warnings for a member

        Usage: `{ctx.prefix}warn show [user: optional]`

        Specify no user to get all active warnings.

        You must have `Leadership Team` role to use these commands.
        """
        await ctx.invoke(self.bot.get_command('warn show'), user=user)

    async def call_timer(self, dump):
        channel = self.bot.get_channel(self.LEADER_NOTES_ROOM)
        user = self.bot.get_user(dump['user_id'])

        e = discord.Embed(colour=0x36393E)
        e.set_author(name=str(user), icon_url=user.avatar_url)
        e.title = 'Automatic Warning Removal'
        e.add_field(name=f"Warning No.{dump['id']}",
                    value=f"{dump['reason']}")
        e.timestamp = datetime.datetime.utcnow()

        await channel.send(embed=e)

        query = "UPDATE warnings SET active=False WHERE id = $1"
        await self.bot.pool.execute(query, dump['id'])

    async def wait_for_timers(self):
        try:
            while not self.bot.is_closed():
                query = "SELECT * FROM warnings WHERE expires < (CURRENT_DATE + $1::interval)" \
                        " AND active=True ORDER BY expires LIMIT 1;"
                dump = await self.bot.pool.fetchrow(query, datetime.timedelta(days=7))

                if not dump:
                    continue

                now = datetime.datetime.utcnow()
                if dump['expires'] >= now:
                    to_sleep = (dump['expires'] - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(dump)

        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed):
            await self.wait_for_timers_task.cancel()
            self.wait_for_timers_task = self.bot.loop.create_task(self.wait_for_timers())


def setup(bot):
    bot.add_cog(Warnings(bot))
