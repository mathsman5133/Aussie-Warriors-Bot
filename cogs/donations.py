import discord
from discord.ext import commands
import cogs.utils.paginator as paginator
from cogs.utils import checks


class Show_Donations:
    def __init__(self, bot):
        self.bot = bot

    async def __error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            e = discord.Embed(colour=discord.Colour.red())
            e.description = error
            await ctx.send(embed=e)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Missing required argument {error}!')
            await ctx.show_help()

    async def donations_by_today(self):
        query = "SELECT donationsbytoday FROM season WHERE toggle = $1"
        dump = await self.bot.pool.fetchrow(query, True)

        return dump['donationsbytoday']

    @commands.command(aliases=['mydon'])
    async def don(self, ctx, mention: discord.Member=None):
        if not mention:
            mention = ctx.author

        query = 'SELECT ign, tag, difference FROM claims WHERE userid = $1'
        dump = await ctx.db.fetch(query, mention.id)

        players = []
        try:
            players.extend(f'{ign} ({tag}): `{donations} donations` '
                           for (index, (ign, tag, donations)) in enumerate(dump))
        except TypeError:
            players.append('__**No Accounts**__')

        pages = paginator.EmbedPag(ctx, entries=players, per_page=20, message=ctx.message)
        await pages.paginate(start_page=1)

        # e = discord.Embed(colour=discord.Colour.blue())
        # e.set_author(name='Donations required by today: ' + str(await self.donations_by_today()))
        # e.add_field(name='\u200b', value=players)
        # await ctx.send(embed=e)

    @commands.command()
    async def awdon(self, ctx):
        query = "SELECT userid, ign, tag, difference FROM claims WHERE clan = $1 ORDER BY userid ASC;"
        dump = await ctx.db.fetch(query, 'Aussie Warriors')

        unique_ids = set([n[0] for n in dump])  # unique list of discord id's so can group acc's by discord user

        members = []  # list of each discord user after we have made our string
        for user in unique_ids:
            #  make string of accounts in format ign (tag): donation\n ...more accounts
            string = '\n'.join(f'{n[1]} ({n[2]}): `{n[3]} don`' for n in dump if n[0] == user)
            new_string = f'<@{user}>\n{string}'  # add the mention at top of string
            members.append(new_string)  # add to our list of strings

        pages = paginator.EmbedPag(ctx, entries=members, per_page=10, message=ctx.message)  # paginate it
        await pages.paginate(start_page=1)

        # e = discord.Embed(colour=discord.Colour.green())
        # e.set_author(name='Donations required by today: ' + str(await self.donations_by_today()))
        # e.add_field(name='\u200b', value=players)
        # await ctx.send(embed=e)

    @commands.command()
    async def a4wdon(self, ctx):
        query = "SELECT ign, tag, userid, difference FROM claims WHERE clan = $1"
        dump = await ctx.db.fetch(query, 'Aussies 4 War')

        unique_ids = set([n[0] for n in dump])  # unique list of discord id's so can group acc's by discord user

        members = []  # list of each discord user after we have made our string
        for user in unique_ids:
            #  make string of accounts in format ign (tag): donation\n ...more accounts
            string = '\n'.join(f'{n[1]} ({n[2]}): `{n[3]} don`' for n in dump if n[0] == user)
            new_string = f'<@{user}>\n{string}'  # add the mention at top of string
            members.append(new_string)  # add to our list of strings

        pages = paginator.EmbedPag(ctx, entries=members, per_page=10, message=ctx.message)
        await pages.paginate(start_page=1)

        # e = discord.Embed(colour=discord.Colour.green())
        # e.set_author(name='Donations required by today: ' + str(await self.donations_by_today()))
        # e.add_field(name='\u200b', value=players)
        # await ctx.send(embed=e)

    @commands.command()
    async def avg(self, ctx, mention: discord.Member=None):
        if mention:
            query = "SELECT userid, average FROM averages WHERE userid = $1"
            dump = await ctx.db.fetchrow(query, mention.id)
        else:
            query = "SELECT userid, average FROM averages WHERE warning = $1"
            dump = await ctx.db.fetch(query, True)

        players = []
        try:
            players.extend(f'<@{userid}>: `{avgdon} donations`'
                           for (index, (userid, avgdon)) in enumerate(dump))
        except TypeError:
            players.append('No Accounts')

        pages = paginator.EmbedPag(ctx, entries=players, per_page=20, message=ctx.message)
        await pages.paginate(start_page=1)

    @commands.command(name='myavg')
    async def myavg(self, ctx):
        await ctx.invoke(self.avg, ctx.author)

    async def send_donation_pings(self):
        query = "SELECT userid, average FROM averages WHERE warning = $1"
        dump = await self.bot.fetch(query, True)

        players = '\n'.join(f'<@{userid}>: `{avgdon} donations`'
                            for (userid, avgdon) in enumerate(dump) or 'No Accounts')

        ping = ''.join(f'<@{userid}>, ' for userid in dump)

        e = discord.Embed(colour=discord.Colour.blue())
        e.title = 'Average Donation List - Warnings only'
        e.description = players
        self.bot.donation_ping_webhook.send(embed=e)
        self.bot.donation_ping_webhook.send(
            f'{ping}\nThe average donations of all your accounts currently have '
            f'less than the required: {str(self.donations_by_today())} troop space by today. '
            f'\nPlease find your IGN above and donate some troops! '
            f'\nIf you want to check your donations, please type `don` and `avg` in <#462931331308060673>. ')
        eh = discord.Embed(colour=9546812)
        eh.add_field(name='Donation Rules',
                     value='As per <#390046705023713280>, '
                           'the required donations is 400 per month, for both clans. '
                           'This equates to 100 per week, or roughly 13.3 per day. \n\n '
                           'The bot will ping people whom have an average of all accounts'
                           'less than the required donations '
                           'for that day of the month once a week, at approx. Tuesday 5pm EST, '
                           'or Wednesday 7am AEST. \n\nIf any messages have been sent in error, '
                           'or something isnt working, please ping <@230214242618441728>')
        self.bot.donation_ping_webhook.send(embed=eh)

    @commands.command()
    # @checks.manage_server()
    @checks.mod_commands()
    async def send_pings(self, ctx):
        await self.send_donation_pings()
        await ctx.message.delete()


def setup(bot):
    bot.add_cog(Show_Donations(bot))
