import datetime
import calendar
import asyncio

import discord
from discord.ext import commands
import pytz

from cogs.utils import checks, db
from cogs.donations import ShowDonations
from cogs.admin import Admin


class Season(db.Table):
    id = db.PrimaryKeyColumn()

    toggle = db.Column(db.Boolean(), index=True)
    donationsbytoday = db.Column(db.Integer)
    start_date = db.Column(db.Integer)


class Averages(db.Table):
    id = db.PrimaryKeyColumn()

    userid = db.Column(db.Integer(big=True), index=True)
    average = db.Column(db.Numeric())
    warning = db.Column(db.Boolean(), index=True)


class Update(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.auto_daily_task = bot.loop.create_task(self.auto_daily_updates())
        self.auto_monthly_task = bot.loop.create_task(self.auto_monthly_update())
        self.auto_pings_task = bot.loop.create_task(self.auto_send_pings())

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            e = discord.Embed(colour=discord.Colour.red())
            e.description = error
            await ctx.send(embed=e)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Missing required argument {error}!')
            await ctx.show_help()

    def cog_unload(self):
        self.auto_daily_task.cancel()
        self.auto_monthly_task.cancel()
        self.auto_pings_task.cancel()

    @commands.command()
    @checks.manage_server()
    @checks.mod_commands()
    async def update_required(self, ctx):
        """Manually update the required donations by today
        """
        await self.update_donations_by_today()
        await ctx.message.add_reaction('\u2705')

    @commands.command(name='refavg')
    @checks.manage_server()
    @checks.mod_commands()
    async def _refresh_avg(self, ctx):
        """Manually refresh the averages of all accounts in the database

        [Requires `manage_server` permissions]
        """
        await self.refresh_avg()
        await ctx.message.add_reaction('\u2705')

    @commands.command(name='upd')
    @checks.manage_server()
    @checks.mod_commands()
    async def _update(self, ctx):
        """Manually update the donations of all accounts in the database

        [Requires `manage_server` permissions]
        """
        await self.update()
        await self.update_donations_by_today()
        await ctx.message.add_reaction('\u2705')

    @commands.command()
    async def myupd(self, ctx):
        """Manually updates the donations of your accounts in the database.
        This is the preferred method if you wish to update your accounts; all accounts will update daily
        """
        await self.my_upd(ctx.author.id)
        await ctx.message.add_reaction('\u2705')

        await ctx.send(
            'Updated donations for your claimed accounts. '
            'To see these type `myclaims`, and to find your donations type `mydon`'
        )

    @commands.command(name='manreset')
    @checks.manage_server()
    @checks.mod_commands()
    async def manual_reset(self, ctx):
        """Manually resets the season of donations in the database
        """
        query = "UPDATE season SET toggle = $1"
        await ctx.db.execute(query, False)

        query = "SELECT tag FROM claims"
        dump = await ctx.db.fetch(query)

        await self.new_month()

        for tag in dump:
            print(dump, tag['tag'])
            await self.download_starting_donations(tag['tag'])

        await self.refresh_avg()
        await ctx.message.add_reaction('\u2705')

    async def donations_by_today(self):
        query = "SELECT donationsbytoday FROM season WHERE toggle = $1"
        dump = await self.bot.pool.fetchrow(query, True)

        return dump['donationsbytoday']

    async def update_donations_by_today(self):
        query = "SELECT start_date FROM season WHERE toggle = $1"
        dump = await self.bot.pool.fetchrow(query, True)

        day_of_year = datetime.datetime.utcnow().strftime('%j')
        date_difference = int(day_of_year) - dump['start_date']
        donations_required = date_difference * 13.33

        query = "UPDATE season SET donationsbytoday = $1 WHERE toggle = $2"
        await self.bot.pool.execute(query, donations_required, True)

    async def new_month(self):
        dayofyear = int(datetime.datetime.now().strftime('%j'))

        query = "INSERT INTO season (toggle, donationsbytoday, start_date) VALUES ($1, $2, $3)"
        await self.bot.pool.execute(query, True, 13.3, dayofyear)

    async def new_avg(self, user_id):
        query = "SELECT difference FROM claims WHERE userid = $1"
        dump = await self.bot.pool.fetchrow(query, user_id)

        average_donations = sum(dump) / len(dump)

        if average_donations >= await self.donations_by_today():
            warn = False
        else:
            warn = True

        query = "INSERT INTO averages (userid, average, warning) VALUES($1, $2, $3)"
        await self.bot.pool.execute(query, user_id, average_donations, warn)

    async def download_starting_donations(self, tag):
        player = await self.bot.coc.players(tag).get(self.bot.coc_token)

        for achievement in player['achievements']:
            if achievement['name'] == 'Friend in Need':
                donations = achievement['value']
                break
        else:
            return

        query = "UPDATE claims SET starting_donations=$1 WHERE tag=$2"
        await self.bot.pool.execute(query, donations, tag)

    async def refresh_avg(self):
        query = "DROP TABLE averages"
        await self.bot.pool.execute(query)

        query = """
                CREATE TABLE IF NOT EXISTS averages 
                (id SERIAL PRIMARY KEY, userid BIGINT, average NUMERIC, warning BOOLEAN);
                """
        await self.bot.pool.execute(query)

        query = "SELECT userid FROM claims WHERE clan = 'Aussie Warriors' or clan = 'Aussies 4 War'"
        dump = list(set(await self.bot.pool.fetch(query)))

        for row in dump:
            await self.new_avg(row['userid'])

    async def update_database(self, don, dif, clan, tag):
        query = """
                UPDATE claims SET 
                current_donations=$1,
                difference=$2, 
                clan=$3 
                WHERE tag=$4
                """
        await self.bot.pool.execute(query, don, dif, clan, tag)

    async def my_upd(self, user_id):
        query = "SELECT tag, starting_donations FROM claims WHERE userid = $1"
        dump = await self.bot.pool.fetch(query, user_id)

        for individual in dump:
            player = await self.bot.coc.players(individual['tag']).get(self.bot.coc_token)

            for achievement in player['achievements']:
                if achievement['name'] == 'Friend in Need':
                    current_donations = achievement['value']
                    break
            else:
                break

            donations_this_season = current_donations - individual['starting_donations']
            donations_required_difference = donations_this_season - (await self.donations_by_today())

            try:
                clan = player['clan']['name']
            except KeyError:
                clan = ''

            await self.update_database(donations_this_season, donations_required_difference, clan, individual['tag'])

    async def update(self):
        query = "SELECT tag, starting_donations FROM claims"
        dump = await self.bot.pool.fetch(query)

        for individual in dump:
            player = await self.bot.coc.players(individual['tag']).get(self.bot.coc_token)

            for achievement in player['achievements']:
                if achievement['name'] == 'Friend in Need':
                    current_donations = achievement['value']
                    break
            else:
                break

            donations_this_season = current_donations - individual['starting_donations']
            donations_required_difference = donations_this_season - (await self.donations_by_today())

            clan = player['clan']['name'] if 'clan' in player.keys() else ''

            await self.update_database(donations_this_season, donations_required_difference, clan, individual['tag'])

        await self.refresh_avg()

    async def auto_daily_updates(self):
        try:
            while not self.bot.is_closed():
                await self.bot.get_cog('Admin').task_stats('daily_update', False)

                now = datetime.datetime.now(pytz.timezone('Australia/Sydney'))

                if now.hour == 6:  # if its 6oc
                    await self.update_donations_by_today()
                    await self.update()
                    await self.refresh_avg()
                    await (self.bot.get_channel(self.bot.info_channel_id)).send('auto-daily-update done')
                    await self.bot.get_cog('Admin').task_stats('daily_update', True)

                await asyncio.sleep(3600)  # sleep for an hour

        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed):
            self.auto_daily_task.cancel()
            self.auto_daily_task = self.bot.loop.create_task(self.auto_daily_updates())

    async def auto_monthly_update(self):
        try:
            while not self.bot.is_closed():
                await self.bot.get_cog('Admin').task_stats('monthly_update', False)
                # there is probably a more elegant way of finding the last monday of the month date
                cal = calendar.Calendar(0)
                month = cal.monthdatescalendar(datetime.date.today().year, datetime.date.today().month)
                lastweek = month[-1]
                monday = lastweek[0]

                if datetime.date.today() == monday:  # if its the last monday of the month
                    await self.manual_reset()
                    await self.update_donations_by_today()
                    await self.update()
                    await self.refresh_avg()
                    await (self.bot.get_channel(self.bot.info_channel_id)).send('auto-monthly-update done')

                    await self.bot.get_cog('Admin').task_stats('monthly_update', True)

                await asyncio.sleep(86399)  # sleep for a second less than a day
        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed):
            self.auto_daily_task.cancel()
            self.auto_daily_task = self.bot.loop.create_task(self.auto_daily_updates())

    async def auto_send_pings(self):
        try:
            while not self.bot.is_closed():
                await self.bot.get_cog('Admin').task_stats('send_pings', False)

                show_donations_class = ShowDonations(self.bot)
                today = datetime.datetime.now(pytz.timezone('Australia/Sydney'))

                if today.hour == 7 and today.weekday() == 1:  # if its 7oc on tuesday
                    if self.bot.send_pings == 'true':
                        await show_donations_class.send_donation_pings()
                        await self.bot.get_cog('Admin').task_stats('send_pings', True)

                await asyncio.sleep(3600)  # sleep for an hour

        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed):
            await self.auto_daily_task.cancel()
            self.auto_daily_task = self.bot.loop.create_task(self.auto_daily_updates())


def setup(bot):
    bot.add_cog(Update(bot))
