from discord.ext import commands
import discord
import datetime
import dateutil
import asyncio


class WarStatus:
    def __init__(self, bot):
        self.bot = bot

    BALLOON_ICON_URL = "https://vignette.wikia.nocookie.net/clashofclans/images/" \
                       "2/2f/Balloon_info.png/revision/latest/scale-to-width-down/120?cb=20170927230730"

    @commands.group()
    async def search(self, ctx):
        pass

    @search.command()
    async def clan(self, ctx, *, tag_or_name: str):
        clan = await self.search_clans(ctx, tag_or_name)
        war_status = await self.war_status(clan)
        msg = await ctx.send(embed=war_status)
        await msg.add_reaction('\N{BLACK RIGHT-POINTING TRIANGLE}')
        info = [('\N{BLACK RIGHT-POINTING TRIANGLE}', self.current_war)]

        def check(reaction, user):
            if user is None or user.id != ctx.author.id:
                return False

            if reaction.message.id != msg.id:
                return False

            for (emoji, func) in info:
                if reaction.emoji == emoji:
                    self.match = func
                    return True
            return False

        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            return await ctx.send('You took too long. Goodbye.')

        e = await self.match(clan)
        await msg.edit(embed=e)

    async def war_status(self, clan):
        e = discord.Embed(colour=discord.Colour.blue())
        e.add_field(name=clan['name'],
                    value=clan['tag'])

        if clan['isWarLogPublic']:  # we will get errors if warlog is closed
            war = await self.bot.coc.clans(clan['tag']).currentwar.get(self.bot.coc_token)

            e.add_field(name='War State:',
                        value=war['state'],
                        inline=False)

            if 'endTime' in war.keys():  # if state is notInWar we will get errors
                end_time = dateutil.parser.parse(war['endTime'])

                delta = end_time - datetime.datetime.now(datetime.timezone.utc)
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                e.add_field(name='Opponent:',
                            value=f"{war['opponent']['name']}\n"
                                  f"{war['opponent']['tag']}",
                            inline=False)
                e.add_field(name="War End Time:",
                            value=f'{hours} hours {minutes} minutes {seconds} seconds',
                            inline=False)

        return e

    async def search_clans(self, ctx, tag_or_name: str):
        emojis = [
            '1\u20e3',
            '2\u20e3',
            '3\u20e3',
            '4\u20e3',
            '5\u20e3'
                  ]
        info = list()

        if tag_or_name.startswith('#'):
            try_tag = await self.bot.coc.clans(tag_or_name).get(self.bot.coc_token)

            if 'notFound' in try_tag.values():
                raise commands.BadArgument(f'Clan tag {tag_or_name} not found. Please try again')

            return try_tag

        else:
            try_names = (await self.bot.coc.clans(name=tag_or_name, limit=5).get(self.bot.coc_token))['items']

        info.extend((emojis[index], try_names[index]) for index in range(0, len(try_names)))

        string = '\n\n'.join(f"{e} {c['name']} ({c['tag']}) - "
                             f"Lv{c['clanLevel']}; Loc: "
                             f"{c['location']['name'] if 'location' in c.keys() else 'N/A'}"
                             for (index, (e, c)) in enumerate(info))

        e = discord.Embed(colour=discord.Colour.blue())
        e.description = string
        msg = await ctx.send(embed=e)
        for entry in info:
            await msg.add_reaction(entry[0])

        def check(reaction, user):
            if user is None or user.id != ctx.author.id:
                return False

            if reaction.message.id != msg.id:
                return False

            for (emoji, func) in info:
                if reaction.emoji == emoji:
                    self.coc_clan = func
                    return True
            return False

        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            return await ctx.send('You took too long. Goodbye.')

        await msg.delete()
        return self.coc_clan

    async def current_war(self, clan):
        e = discord.Embed(colour=discord.Colour.blue())

        if clan['isWarLogPublic']:  # we will get errors if warlog is closed
            war = await self.bot.coc.clans(clan['tag']).currentwar.get(self.bot.coc_token)
            if war['state'] in ['inWar', 'warEnded']:
                us = war['clan']
                opponent = war['opponent']

                if us['stars'] > opponent['stars']:
                    e.colour = discord.Colour.green()
                elif us['stars'] == opponent['stars']:
                    e.colour = discord.Colour.gold()
                else:
                    e.colour = discord.Colour.red()

                formatus = f"{us['attacks']}/{war['teamSize']*2} attacks\n" \
                           f"{round(us['destructionPercentage'], 2)}%"
                formatopp = f"{round(opponent['destructionPercentage'], 2)}%"

                e.add_field(name=us['name'], value=formatus)

                e.add_field(name=f"Size: {war['teamSize']}vs {war['teamSize']}",
                            value=f"{us['stars']}:star: vs :star:{opponent['stars']}")

                e.add_field(name=opponent['name'], value=formatopp)

                e.set_footer(text=f"War Record: {clan['warWins']}-{clan['warLosses']}-{clan['warTies']}",
                             icon_url=self.BALLOON_ICON_URL)
            else:
                e.colour = discord.Colour.blue()
                e.description = f"Currently in {war['status']} state. Stats are not available. Please check back later."
        else:
            e.colour = discord.Colour.blue()
            e.description = 'Current war not available: war log may be private'

        return e


def setup(bot):
    bot.add_cog(WarStatus(bot))
