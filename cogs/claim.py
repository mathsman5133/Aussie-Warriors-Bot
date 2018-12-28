import discord
from discord.ext import commands
from cogs.utils import db
from cogs.utils import paginator
from asyncpg import exceptions as pgexceptions
from cogs.utils import checks


class Claims(db.Table):
    id = db.PrimaryKeyColumn()

    userid = db.Column(db.Integer(big=True))
    ign = db.Column(db.String())
    tag = db.Column(db.String())
    starting_donations = db.Column(db.Integer())
    current_donations = db.Column(db.Integer())
    difference = db.Column(db.Numeric())
    clan = db.Column(db.String())
    exempt = db.Column(db.Boolean())


class Claim:
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

        return dump[0]

    @commands.command()
    async def claim(self, ctx, player_tag, mention: discord.Member = None):
        if not mention:
            mention = ctx.author

        if player_tag.startswith('#'):
            query = """SELECT * FROM claims WHERE tag = $1 AND userid = $2"""
        else:
            query = """SELECT * FROM claims WHERE ign = $1 AND userid = $2"""

        dump = await ctx.db.fetchrow(query, player_tag, mention.id)

        if dump:
            ign = dump['ign']
            tag = dump['tag']
            member = ctx.guild.get_member(dump['userid'])
            raise commands.BadArgument(f'{ign} ({tag}) has been claimed by '
                                       f'{member.display_name}#{member.discriminator} ({member.id})')
        if player_tag.startswith('#'):
            try:
                cocplayer = await self.bot.coc.players(player_tag).get(self.bot.coc_token)
            except KeyError:
                raise commands.BadArgument(f'Player tag `{player_tag}` not found!')
        else:
            # search aw players for x ign, then search a4w
            aw_members = await self.bot.coc.clans('#P0LYJC8C').members.get(self.bot.coc_token)
            for awm in aw_members['items']:
                if awm['name'] == player_tag:
                    cocplayer = await self.bot.coc.players(awm['tag']).get(self.bot.coc_token)
                    break
            else:
                a4w_members = await self.bot.coc.clans('#808URP9P').members.get(self.bot.coc_token)
                for a4wm in a4w_members['items']:
                    if a4wm['name'] == player_tag:
                        cocplayer = await self.bot.coc.players(a4wm['tag']).get(self.bot.coc_token)
                        break
                else:
                    raise commands.BadArgument(f"I have checked in AW and A4W "
                                               f"for an IGN matching `{player_tag}` - and couldn't find one!")

        user_id = mention.id
        ign = cocplayer['name']
        tag = cocplayer['tag']

        for achievement in cocplayer['achievements']:
            if achievement['name'] == 'Friend in Need':
                don = achievement['value']
                break
        else:
            return await ctx.send('Unknown error occured with COC API. Sorry')

        starting_donations = don
        current_donations = don
        difference = await self.donations_by_today()

        try:
            clan = cocplayer['clan']['name']
        except KeyError:
            clan = ''

        exempt = False

        query = """
                WITH donation_insert AS (
                    INSERT INTO claims (userid, ign, tag, starting_donations, 
                    current_donations, difference, clan, exempt) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                )
                INSERT INTO tag_to_id (tag, id) VALUES ($3, $1);
                """
        try:
            await ctx.db.execute(query, user_id, ign, tag, starting_donations,
                                 current_donations, difference, clan, exempt)
        except pgexceptions.UniqueViolationError:
            raise commands.BadArgument('Seems tag is already in `tag_to_id` DB, but not claims DB. Sorry')

        await ctx.send(f'{mention.display_name}, you have claimed {ign} ({tag})')

    @commands.command(aliases=['del'])
    async def delete_claim(self, ctx, *, tag_or_ign):

        if tag_or_ign.startswith('#'):
            query = 'SELECT * FROM claims WHERE tag = $1'
            dump = await ctx.db.fetch(query, tag_or_ign)
            if not dump:
                raise commands.BadArgument(f'Player tag {tag_or_ign} has not been claimed!')
            query = 'DELETE FROM claims WHERE tag = $1'
            await ctx.db.execute(query, tag_or_ign)

            query = 'DELETE FROM tag_to_id WHERE tag = $1'
            await ctx.db.execute(query, tag_or_ign)

        else:
            query = 'SELECT * FROM claims WHERE ign = $1'
            dump = await ctx.db.fetchrow(query, tag_or_ign)
            if not dump:
                raise commands.BadArgument(f"IGN {tag_or_ign} has not been claimed!")

            query = 'DELETE FROM claims WHERE ign = $1'
            await ctx.db.execute(query, tag_or_ign)

            query = 'DELETE FROM tag_to_id WHERE tag = $1'
            await ctx.db.execute(query, dump[2][0])

        await ctx.message.add_reaction('\u2705')

    @commands.command()
    @checks.mod_commands()
    async def exempt(self, ctx, tag_or_ign: str, true_false: bool):
        if tag_or_ign.startswith('#'):

            query = 'SELECT * FROM claims WHERE tag = $1'
            dump = await ctx.db.fetch(query, tag_or_ign)
            if not dump:
                raise commands.BadArgument(f'No claimed account with tag {tag_or_ign}')

            query = "UPDATE claims SET exempt=$1 WHERE tag=$2"
            await ctx.db.execute(query, true_false, tag_or_ign)

        else:
            query = 'SELECT * FROM claims WHERE ign = $1'
            dump = await ctx.db.fetch(query, tag_or_ign)
            if not dump:
                raise commands.BadArgument(f'No claimed account with ign {tag_or_ign}')

            query = "UPDATE claims SET exempt=$1 WHERE tag=$2"
            await ctx.db.execute(query, true_false, tag_or_ign)

        await ctx.message.add_reaction('\u2705')

    @commands.command()
    async def exemptlist(self, ctx):
        query = 'SElECT ign, tag, userid FROM claims WHERE exempt = $1'
        dump = await ctx.db.fetch(query, True)

        players = '\n\n'.join(f'{ign} ({tag}): <@{userid}>'
                              for (index, (ign, tag, userid)) in enumerate(dump)) or 'No Members'

        e = discord.Embed(colour=discord.Colour.blue())
        e.set_author(name='Exempt from Donation Tracker: ')
        e.add_field(name='\u200b', value=players)
        e.set_footer(text=f'Total number of exempt accounts: {str(len(dump))}')

        await ctx.send(embed=e)

    @commands.command(aliases=['gc'])
    async def get_claims(self, ctx, mention: discord.Member=None):
        if not mention:
            mention = ctx.author

        query = "SELECT ign, tag FROM claims WHERE userid=$1"
        dump = await ctx.db.fetch(query, mention.id)

        players = '\n\n'.join(f'{ign} ({tag})'
                              for (index, (ign, tag)) in enumerate(dump)) or 'No Members'

        embed = discord.Embed(colour=discord.Colour.blue())
        embed.set_author(name='Claimed Accounts:')
        embed.add_field(name='\u200b', value=players)
        embed.set_footer(text=f'Number of claimed accounts: {len(dump)}')
        await ctx.send(embed=embed)

    @commands.command(aliases=['awgm'])
    async def aw_get_members(self, ctx):
        clan_members = await self.bot.coc.clans('#P0LYJC8C').members.get(self.bot.coc_token)

        query = "SELECT ign, tag, userid FROM claims WHERE clan = $1"
        dump = await ctx.db.fetch(query, 'Aussie Warriors')

        unique_ids = set([n[2] for n in dump])  # unique list of discord id's so can group acc's by discord user

        unique_ids = set([n[2] for n in dump])  # unique list of discord id's so can group acc's by discord user

        claimed_tags = [x['tag'] for x in dump]

        unclaimed_tags = []
        unclaimed_ign = []
        for member in clan_members['items']:
            tag = member['tag']
            name = member['name']
            if tag not in claimed_tags:
                unclaimed_tags.append(tag)
                unclaimed_ign.append(name)

        entries = ['__**Claimed Bases**__']

        # entries.extend(f'{ign} ({tag}): <@{userid}>'
        #                for (index, (ign, tag, userid)) in enumerate(dump) or 'No Members')

        for user in unique_ids:
            #  make string of accounts in format ign (tag): donation\n ...more accounts
            string = '\n'.join(f'   {n[0]} ({n[1]})' for n in dump if n[2] == user)
            new_string = f'<@{user}>\n{string}'  # add the mention at top of string
            entries.append(new_string)  # add to our list of strings

        entries.append('__**Un-Claimed Bases**__')
        entries.extend(f'{unclaimed_ign[index]} ({unclaimed_tags[index]})'
                       for index in range(len(unclaimed_ign)) or 'No Members')

        pages = paginator.EmbedPag(ctx, entries=entries, per_page=12, message=ctx.message)
        await pages.paginate(start_page=1)

    @commands.command(aliases=['a4wgm'])
    async def a4w_get_members(self, ctx):
        clan_members = await self.bot.coc.clans('#808URP9P').members.get()

        query = "SELECT tag, ign, userid FROM claims WHERE clan = $1"
        dump = await ctx.db.fetch(query, 'Aussies 4 War')

        unique_ids = set([n[2] for n in dump])  # unique list of discord id's so can group acc's by discord user

        unique_ids = set([n[2] for n in dump])  # unique list of discord id's so can group acc's by discord user

        claimed_tags = [x['tag'] for x in dump]

        unclaimed_tags = []
        unclaimed_ign = []

        for member in clan_members['items']:
            tag = member['tag']
            name = member['name']
            if tag not in claimed_tags:
                unclaimed_tags.append(tag)
                unclaimed_ign.append(name)

        entries = ['__**Claimed Bases**__']

        # entries.extend(f'{ign} ({tag}): <@{userid}>'
        #                for (index, (ign, tag, userid)) in enumerate(dump) or 'No Members')

        for user in unique_ids:
            #  make string of accounts in format ign (tag): donation\n ...more accounts
            string = '\n'.join(f'{n[0]} ({n[1]})' for n in dump if n[2] == user)
            new_string = f'<@{user}>\n{string}'  # add the mention at top of string
            entries.append(new_string)  # add to our list of strings

        for user in unique_ids:
            #  make string of accounts in format ign (tag): donation\n ...more accounts
            string = '\n'.join(f'   {n[0]} ({n[1]})' for n in dump if n[2] == user)
            new_string = f'<@{user}>\n{string}'  # add the mention at top of string
            entries.append(new_string)  # add to our list of strings

        entries.append('__**Un-Claimed Bases**__')
        entries.extend(f'{unclaimed_ign[index]} ({unclaimed_tags[index]})'
                       for index in range(len(unclaimed_ign)) or 'No Members')

        pages = paginator.EmbedPag(ctx, entries=entries, per_page=12, message=ctx.message)
        await pages.paginate(start_page=1)


def setup(bot):
    bot.add_cog(Claim(bot))
