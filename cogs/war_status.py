from discord.ext import commands
import discord
import datetime
import dateutil
import asyncio
import coc
from cogs.utils.help import FieldPages


class WarStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.coc.add_events(self.on_clan_member_join, self.on_clan_update, self.on_clan_member_leave,
                                self.on_player_update, self.on_war_attack, self.on_war_state_change,
                                self.on_war_update)

    @commands.command()
    async def start_updates(self, ctx):
        await self.bot.coc.add_clan_update([self.bot.AW_CLAN_TAG, self.bot.A4W_CLAN_TAG], member_updates=True,
                                           retry_interval=100)
        self.bot.coc.add_war_update([self.bot.AW_CLAN_TAG, self.bot.A4W_CLAN_TAG], retry_interval=100)
        self.bot.coc.start_updates('all')

        await ctx.tick()

    BALLOON_ICON_URL = "https://vignette.wikia.nocookie.net/clashofclans/images/" \
                       "2/2f/Balloon_info.png/revision/latest/scale-to-width-down/120?cb=20170927230730"

    @commands.command()
    async def get_player(self, ctx, tag):
        t = await self.bot.coc.get_player(tag)
        await ctx.send(t)

    @commands.group()
    async def search(self, ctx):
        """Group - Search and find info about a COC clan by tag or clan name
        [In beta]
        """
        if not ctx.invoked_subcommand:
            await ctx.show_help('search')

    @search.command()
    async def clan(self, ctx, *, tag_or_name: str):
        """Search + get info about a COC clan by tag or name
        [In beta]
        """
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
        e.add_field(name=clan.name,
                    value=clan.tag)

        if clan.public_war_log:  # we will get errors if warlog is closed
            war = await self.bot.coc.get_current_war(clan.tag)

            e.add_field(name='War State:',
                        value=war.state,
                        inline=False)

            if war.end_time:  # if state is notInWar we will get errors

                hours, remainder = divmod(int(war.end_time.seconds_until), 3600)
                minutes, seconds = divmod(remainder, 60)

                e.add_field(name='Opponent:',
                            value=f"{war.opponent.name}\n"
                                  f"{war.opponent.tag}",
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
            try:
                try_tag = await self.bot.coc.get_clan(tag_or_name)
            except coc.NotFound:
                raise commands.BadArgument(f'Clan tag {tag_or_name} not found. Please try again')

            return try_tag

        else:
            try_names = await self.bot.coc.search_clans(name=tag_or_name, limit=5)

        async for clan in self.bot.coc.get_clans([n.tag for n in try_names]):
            print(clan)

        info.extend((emojis[index], try_names[index]) for index in range(0, len(try_names)))

        string = '\n\n'.join(f"{e} {c.name} ({c.tag}) - "
                             f"Lv{c.level}; Loc: "
                             f"{c.location.name}"
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
                    self.clan = func
                    return True
            return False

        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            return await ctx.send('You took too long. Goodbye.')

        await msg.delete()
        return await self.bot.coc.get_clan(self.clan.tag, cache=True)

    async def current_war(self, clan):
        e = discord.Embed(colour=discord.Colour.blue())

        if not clan.public_war_log:
            e.description = 'Current war not available: war log may be private'
            return e

        war = await self.bot.coc.get_current_war(clan.tag)

        if war.state not in ['inWar', 'warEnded']:
            e.description = f"Currently in {war.state} state. Stats are not available. Please check back later."
            return e

        us = war.clan
        opponent = war.opponent

        if us.stars > opponent.stars:
            e.colour = discord.Colour.green()
        elif us.stars == opponent.stars:
            e.colour = discord.Colour.gold()
        else:
            e.colour = discord.Colour.red()

        formatus = f"{us.attack_count}/{war.team_size*2} attacks\n" \
                   f"{round(us.destruction, 2)}%"
        formatopp = f"{round(opponent.destruction, 2)}%"

        e.add_field(name=str(us), value=formatus)

        e.add_field(name=f"Size: {war.team_size}vs {war.team_size}",
                    value=f"{us.stars}:star: vs :star:{opponent.stars}")

        e.add_field(name=str(opponent), value=formatopp)

        e.set_footer(text=f"War Record: {clan.war_wins}-{clan.war_losses}-{clan.war_ties}",
                     icon_url=self.BALLOON_ICON_URL)

        return e

    def clan_info(self, clan):
        fmt = f'**Name:** {clan.name}\n' \
              f'**Tag:** {clan.tag}\n' \
              f'**Location:** {clan.location.name}\n' \
              f'**Level:** {clan.level}\n' \
              f'**Trophy Count:** {clan.points}\n' \
              f'**Versus Trophy Count:** {clan.versus_points}\n' \
              f'**Member Count:** {clan.member_count}\n\n' \
              f'**Type:** {clan.type}\n' \
              f'**Required Trophies:** {clan.required_trophies}\n' \
              f'**War Frequency:** {clan.war_frequency}\n' \
              f'**Win/Loss/Draw:** {clan.war_wins}/{clan.war_losses}/{clan.war_ties}\n' \
              f'**Public War Log:** {clan.public_war_log}\n\n' \
              f'**Description:**\n\n{clan.description}'

        return fmt

    async def member_info(self, member):
        try_cache = await self.bot.coc.get_player(member.tag, cache=True, fetch=False)
        if try_cache:
            member = try_cache

        fmt = f'**Name:** {member.name}\n' \
              f'**Tag:** {member.tag}\n' \
              f'**Level:** {member.level}\n\n' \
              f'**Trophies:** {member.trophies}\n' \
              f'**Versus Trophies:** {member.versus_trophies}\n' \
              f'**Attack Wins:** {member.attack_wins}\n' \
              f'**Defense Wins:** {member.defense_wins}\n\n' \
              f'**Clan Role:** {member.role}\n' \
              f'**Donations:** {member.donations}\n' \
              f'**Received:** {member.received}\n' \
              f'**Clan Rank:** {member.clan_rank}\n\n'

        if isinstance(member, coc.SearchPlayer):
            aq_lv = member._heroes.get('Archer Queen', 0)
            if aq_lv:
                aq_lv = aq_lv.level
            bk_lv = member._heroes.get('Barbarian King', 0)
            if bk_lv:
                bk_lv = bk_lv.level
            gw_lv = member._heroes.get('Grand Warden', 0)
            if gw_lv:
                gw_lv = gw_lv.level
            bm_lv = member._heroes.get('Battle Machine', 0)
            if bm_lv:
                bm_lv = bm_lv.level
            fmt += f'**Best Trophies**: {member.best_trophies}\n' \
                   f'**Best Versus Trophies:** {member.best_versus_trophies}\n' \
                   f'**War Stars:** {member.war_stars}\n' \
                   f'**Town Hall:** {member.town_hall}\n' \
                   f'**Builder Hall:** {member.builder_hall}\n' \
                   f'**Versus Battle Wins:** {member.versus_attacks_wins}\n' \
                   f'**Heroes (BK/AQ/GW/BM):** {bk_lv}/{aq_lv}/{gw_lv}/{bm_lv}'

        return fmt

    @commands.command()
    async def clan_members(self, ctx, *, clan_tag_or_name: str):
        if clan_tag_or_name.startswith('#'):
            clan = await self.bot.coc.get_clan(clan_tag_or_name, cache=True)
        else:
            clan = await self.search_clans(ctx, clan_tag_or_name)

        to_paginate = []

        to_paginate.append(('Clan Info', self.clan_info(clan)))

        for member in clan.members:
            # member = await self.bot.coc.get_player(member.tag, cache=True)
            to_paginate.append(('Member Info', await self.member_info(member)))

        paginator = FieldPages(ctx=ctx, entries=to_paginate, per_page=1)

        paginator.embed.title = f'Clan Info for {str(clan)}'

        await paginator.paginate()

    def war_log_fmt(self, war):
        days, remainder = divmod(abs(int(war.end_time.seconds_until)), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        fmt = f'**Opponent:** {str(war.opponent)} ({war.opponent.tag})\n' \
              f'**Result:** {war.result}\n\n' \
              f'**War Size:** {war.team_size}v{war.team_size}\n' \
              f'**Clan Attacks Used:** {war.clan.attack_count}/{war.team_size*2}\n\n' \
              f'**Clan Stars:** {war.clan.stars}\n' \
              f'**Clan Destruction:** {round(war.clan.destruction, 2)}%\n' \
              f'**Opponent Stars:** {war.opponent.stars}\n' \
              f'**Opponent Destruction:** {round(war.opponent.destruction, 2)}%\n\n' \
              f'**End Time:** {days}d {hours}h {minutes}m {int(seconds)}s ago'
        return fmt

    def league_war_log_fmt(self, war):
        days, remainder = divmod(abs(int(war.end_time.seconds_until)), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        fmt = f'**Season End Time:** {days}d {hours}h {minutes}m {seconds}s ago\n\n' \
              f'**War Size:** {war.team_size}v{war.team_size}\n' \
              f'**Clan Attacks Used:** {war.attack_count}\n\n' \
              f'**Clan Stars:** {war.stars}\n' \
              f'**Clan Destruction:** {round(war.destruction, 2)}%\n' \
              f'**Opponent Stars:** {war.enemy_stars}\n'
        return fmt

    @commands.command()
    async def clan_warlog(self, ctx, *, clan_tag_or_name: str):
        if clan_tag_or_name.startswith('#'):
            clan = await self.bot.coc.get_clan(clan_tag_or_name, cache=True)
        else:
            clan = await self.search_clans(ctx, clan_tag_or_name)

        to_paginate = []

        to_paginate.append(('Clan Info', self.clan_info(clan)))

        war_log = await self.bot.coc.get_warlog(clan.tag, cache=True)

        for war in war_log:
            if isinstance(war, coc.WarLog):
                to_paginate.append(('War Info', self.war_log_fmt(war)))
            elif isinstance(war, coc.LeagueWarLogEntry):
                to_paginate.append(('League Season Info', self.league_war_log_fmt(war)))

        paginator = FieldPages(ctx=ctx, entries=to_paginate, per_page=1)

        paginator.embed.title = f'War Log Info for {str(clan)}'

        await paginator.paginate()

    def hero_fmt(self, heroes):
        fmt = ''

        for hero in heroes:
            fmt += f'**Hero:** {str(hero)}\n' \
                   f'**Level:** {hero.level}\n' \
                   f'**Max Level:** {hero.max_level}\n\n'
        return fmt

    def spells_fmt(self, spells):
        fmt = ''

        for spell in spells:
            fmt += f'**Spell:** {str(spell)}\n' \
                   f'**Level:** {spell.level}\n' \
                   f'**Max Level:** {spell.max_level}\n\n'

    def troops_fmt(self, troops):
        fmt_home_p1 = ''
        fmt_home_p2 = ''
        fmt_bb = ''

        fmt = '**Troop:** {}\n' \
              '**Level:** {}\n' \
              '**Max Level:** {}\n\n'

        for troop in troops:
            if troop.is_home_base and (len(fmt_home_p1) < 800):
                fmt_home_p1 += fmt.format(str(troop), troop.level, troop.max_level)
            elif (len(fmt_home_p1) > 800) and troop.is_home_base:
                fmt_home_p2 += fmt.format(str(troop), troop.level, troop.max_level)
            elif troop.is_builder_base:
                fmt_bb += fmt.format(str(troop), troop.level, troop.max_level)

        return fmt_home_p1, fmt_home_p2, fmt_bb

    def achievement_fmt(self, achievement):
        fmt = '**Name:** {}\n' \
              '**Stars:** {}/3\n' \
              '**Completed:** {}/{}\n\n' \
              '**Info:** {}\n\n' \
              '**Completion Info:** {}\n\n' \
              '**Village:** {}'
        return fmt.format(str(achievement), achievement.stars, achievement.value,
                          achievement.target, achievement.info, achievement.completion_info,
                          achievement.village)

    @commands.command()
    async def get_player(self, ctx, player_tag):
        player = await self.bot.coc.get_player(player_tag, cache=True)

        to_paginate = []

        to_paginate.append(('Player Info', await self.member_info(player)))
        to_paginate.append(('Hero Information', self.hero_fmt(player.heroes)))
        to_paginate.append(('Spells Information', self.spells_fmt(player.spells)))

        home_troops_p1, home_troops_p2, bb_troops = self.troops_fmt(player.troops)

        to_paginate.append(('Home Base Troops (Part 1)', home_troops_p1))
        to_paginate.append(('Home Base Troops (Part 2)', home_troops_p2))
        to_paginate.append(('Builder Base Troops', bb_troops))

        for achievement in player.achievements:
            if achievement.is_home_base:
                to_paginate.append(('Home Base Achievement', self.achievement_fmt(achievement)))
            elif achievement.is_builder_base:
                to_paginate.append(('Builder Base Achievement', self.achievement_fmt(achievement)))

        p = FieldPages(ctx, entries=to_paginate, per_page=1)
        await p.paginate()

    async def on_clan_update(self, old_clan, new_clan):
        await self.bot.get_channel(527373033568993282).send(new_clan.name)

    async def on_player_update(self, old_player, new_player):
        await self.bot.get_channel(527373033568993282).send(new_player.name)

    async def on_war_update(self, old_war, new_war):
        await self.bot.get_channel(527373033568993282).send(new_war.clan_tag)

    async def on_clan_member_join(self, member):
        await self.bot.get_channel(527373033568993282).send(f'New member {member.name} joined clan {member.clan.name}.')

    async def on_clan_member_leave(self, member):
        await self.bot.get_channel(527373033568993282).send(f'Member {member.name} left clan.')

    async def on_war_state_change(self, state, war):
        await self.bot.get_channel(527373033568993282).send(f'Clan {war.clan.name} just entered {state} state.')

    async def on_war_attack(self, attack):
        await self.bot.get_channel(527373033568993282).send(f'New attack: {attack.attacker.name} just attacked '
                                                            f'{attack.defender.name} for {attack.stars} stars and '
                                                            f'{attack.destrution}%.')


def setup(bot):
    bot.add_cog(WarStatus(bot))
