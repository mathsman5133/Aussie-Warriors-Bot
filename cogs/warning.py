from discord.ext import commands
import discord
from cogs.utils import db, checks
import datetime
import asyncio


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

    async def cog_unload(self):
        self.wait_for_timers_task.cancel()

    @commands.group(name='warn', aliases=['warnings'], invoke_without_subcommand=True)
    @checks.manage_server()
    async def _warnings(self, ctx, user, *, reason=None):
        """[Group] Manage Server Specific Warnings

        Invoke without a subcommand to warn someone with a reason (same as `warn add`)

        Usage: `warn [user] [reason: optional]`

        You must have `manage_guild` permissions
        """
        if ctx.invoked_subcommand is None:
            user = commands.MemberConverter().convert(ctx, user)
            await ctx.invoke(self.bot.get_command('warn add'), user=user, reason=reason)

    @_warnings.command()
    async def add(self, ctx, user: discord.Member, *, reason=None):
        """Add a warning to a member - server specific

        Usage: `warn add [user] [reason: optional]`

        You must have `manage_guild` permissions
        """
        if not reason:
            db_reason = f'Warned by {str(ctx.author)} (no reason)'

        else:
            db_reason = f'Warned by {str(ctx.author)} Reason: {reason}'

        query = "INSERT INTO warnings " \
                "(user_id, reason, timestamp, expires, active)" \
                "VALUES ($1, $2, $3, (CURRENT_DATE+$4::interval), True) RETURNING id;"
        dump = await ctx.db.fetchrow(query, user.id,
                                     db_reason, ctx.message.created_at,
                                     datetime.timedelta(days=7))

        await ctx.message.delete()

        await user.send(f"You have been warned by {str(ctx.author)} for: {reason or 'No Reason'}")

        e = discord.Embed(colour=0x36393E)
        e.set_author(name=str(user), icon_url=user.avatar_url)
        e.add_field(name=f'Warning No.{dump[0]}',
                    value=str(user))
        e.add_field(name='Moderator',
                    value=ctx.author.mention)
        e.add_field(name='Reason',
                    value=reason or 'No Reason')
        e.set_footer(text='This warning will expire in 7d').timestamp = datetime.datetime.utcnow()

        channel = self.bot.get_channel(self.LEADER_NOTES_ROOM)
        await channel.send(embed=e)

    @_warnings.command(aliases=['delete'])
    async def remove(self, ctx, warning_id: int):
        """Remove a warning from a member

        Usage: `warn add [id to remove]`

        ID can be found by using `warns [user]` or `warn show [user]` and is the number before the warning.

        You must have `manage_guild` permissions
        """
        query = "SELECT * FROM warnings WHERE AND id = $1"
        dump = await ctx.db.fetchrow(query, warning_id)

        if not dump:
            raise commands.BadArgument('Warning ID not found.')

        query = "UPDATE warnings SET active=False WHERE id = $1"
        await ctx.db.execute(query, warning_id)

        await ctx.tick()

    @_warnings.command(name='clear')
    async def _clear(self, ctx, user: discord.Member):
        """Clear warnings for a member - server specific

        Usage: `warn clear [user]`

        You must have `manage_guild` permissions
        """
        query = "UPDATE warnings SET active=False WHERE user_id = $1"
        await ctx.db.execute(query, user.id)

        await ctx.tick()

    @_warnings.command(aliases=['list'])
    async def show(self, ctx, user: discord.Member=None):
        """Show warnings for a member

        Usage: `warn show [user: optional]`

        Specify no user to get warnings of yourself.

        You must have `manage_guild` permissions
        """

        if not user:
            query = "SELECT id, reason, expires FROM warnings WHERE active = True"
            dump = await ctx.db.fetch(query)
        else:
            query = "SELECT id, reason, expires FROM warnings WHERE user_id=$1 AND active = True"
            dump = await ctx.db.fetch(query, user.id)

        e = discord.Embed(colour=0x36393E)
        e.title = 'Active Warnings:'
        for n in dump:
            expires_in = int(n['expires'].total_seconds() / 86400)
            e.add_field(name=f"Warning No. {n['id']}",
                        value=f"{n['reason']}\n\nExpires in {expires_in}d")

        e.set_footer(text=f'Total Warnings: {len(dump)}').timestamp = datetime.datetime.utcnow()

        await ctx.send(embed=e)

    @commands.command(hidden=True)
    async def warns(self, ctx, user: discord.Member=None):
        """Show warnings for a member

        Usage: `warn show [user: optional]`

        Specify no user to get all active warnings.

        You must have `manage_guild` permissions
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
