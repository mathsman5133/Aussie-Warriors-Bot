from discord.ext import commands
import datetime
from cogs.utils import db

class Season(db.Table):
    id = db.PrimaryKeyColumn()

    toggle = db.Column(db.Boolean())
    donationsbytoday = db.Column(db.Integer)
    start_date = db.Column(db.Integer)


class Averages(db.Table):
    id = db.PrimaryKeyColumn()

    userid = db.Column(db.Integer(big=True))
    average = db.Column(db.Numeric())
    warning = db.Column(db.Boolean())


class UpdateCommands:
    def __init__(self, bot):
        self.bot = bot

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
        player = await self.bot.get_coc().players(tag).get()

        for achievement in player['achievements']:
            if achievement['name'] == 'Friend in Need':
                donations = achievement['value']
                break

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
            player = await self.bot.get_coc().players(individual['tag']).get()

            for achievement in player['achievements']:
                if achievement['name'] == 'Friend in Need':
                    current_donations = achievement['value']
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
            player = await self.bot.get_coc().players(individual['tag']).get()

            for achievement in player['achievements']:
                if achievement['name'] == 'Friend in Need':
                    current_donations = achievement['value']
                    break

            donations_this_season = current_donations - individual['starting_donations']
            donations_required_difference = donations_this_season - (await self.donations_by_today())

            try:
                clan = player['clan']['name']
            except KeyError:
                clan = ''

            await self.update_database(donations_this_season, donations_required_difference, clan, individual['tag'])

        await self.refresh_avg()

    @commands.command()
    async def update_required(self, ctx):
        await self.update_donations_by_today()
        await ctx.message.add_reaction('\u2705')

    @commands.command(name='refavg')
    async def _refresh_avg(self, ctx):
        await self.refresh_avg()
        await ctx.message.add_reaction('\u2705')

    @commands.command(name='upd')
    async def _update(self, ctx):
        await self.update()
        await self.update_donations_by_today()
        await ctx.message.add_reaction('\u2705')

    @commands.command()
    async def myupd(self, ctx):
        await self.my_upd(ctx.author.id)
        await ctx.message.add_reaction('\u2705')

        await ctx.send(
            'Updated donations for your claimed accounts. '
            'To see these type `myclaims`, and to find your donations type `mydon`'
        )

    @commands.command(name='manreset')
    async def manual_reset(self, ctx):
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


def setup(bot):
    bot.add_cog(UpdateCommands(bot))
