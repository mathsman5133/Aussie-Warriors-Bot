from discord.ext import commands
from cogs.utils import checks, paginator, db
from cogs.admin import TabularData

import asyncio
import discord
import re
import pygsheets
import dateutil
import datetime
import coc


class WarStatsTable(db.Table, table_name='war_stats'):
    war_no = db.Column(db.Integer(), index=True)

    name = db.Column(db.String())
    tag = db.Column(db.String())
    th = db.Column(db.Integer(), index=True)
    hitrate = db.Column(db.String())
    defenserate = db.Column(db.String())


class TempStatsTable(db.Table, table_name='temp_stats'):
    id = db.PrimaryKeyColumn()

    enemy_clan_tag = db.Column(db.String(), index=True)
    attack_number = db.Column(db.Integer())
    enemy_tag = db.Column(db.String())
    attacker_tag = db.Column(db.String())
    name = db.Column(db.String())
    th = db.Column(db.Integer())
    enemy_th = db.Column(db.Integer())
    stars = db.Column(db.Integer())
    percent = db.Column(db.Numeric())
    our_hit = db.Column(db.Boolean(), index=True)


class WarStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stats_updater_task = bot.loop.create_task(self.war_stats_auto_updater())
        self.role_adder_task = bot.loop.create_task(self.war_role_adding_task())

    LEAGUE_BOT_CHANNEL = 528822099360612352
    NERD_BOT_ZONE_CHANNEL = 527373033568993282
    CLAN_TAG = '#P0LYJC8C'

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

        elif isinstance(error, checks.COCError):
            e = discord.Embed(colour=discord.Colour.red())
            e.add_field(name='COC API Error',
                        value=error.msg)
            await ctx.send(embed=e)

    def cog_unload(self):
        self.stats_updater_task.cancel()
        self.role_adder_task.cancel()

    @commands.command()
    @checks.manage_server()
    @checks.mod_commands()
    @checks.clan_status(['preparation', 'inWar', 'warEnded'])
    async def dl_temp(self, ctx):
        """Updates attacks in the `temp_stats` table

        You must have `manage_server` permissions to run this command.
        """
        await self.temporory_war_stats()
        await ctx.tick()

    @commands.command()
    @checks.manage_server()
    @checks.mod_commands()
    async def dl_all(self, ctx):
        """Updates stats in `war_stats` table.

        It will delete all attacks in `temp_stats` table once completed.

        It will not update stats for your current war, unless status is `warEnded`.

        You must have `manage_server` permissions to run this command.
        """
        status, warning_msg, warnings_sent, ts, enemy_tag = \
            await self.get_coc_status(None, 0)

        query = "SELECT DISTINCT enemy_clan_tag FROM temp_stats"

        if status == 'inWar':
            query = f"SELECT DISTINCT enemy_clan_tag FROM temp_stats WHERE enemy_clan_tag != {enemy_tag}"

        tags = await ctx.db.fetch(query)

        query = "DELETE FROM temp_stats WHERE enemy_clan_tag = $1"

        for tag in tags:
            await self.final_war_stats(tag[0])
            await self.bot.pool.execute(query, tag[0])

        await ctx.tick()

    @commands.command()
    @checks.manage_server()
    @checks.mod_commands()
    async def statsheet(self, ctx):
        """Upload the `war_stats` database to google sheets

        You must have `manage_server` permissions to run this command
        """
        await self.DBtoGoogleSheets()
        e = discord.Embed(colour=discord.Colour.green())  # green colour --> success
        e.description = '\u2705 Success! [Link to sheet: here]' \
                        '(https://docs.google.com/spreadsheets/d/' \
                        '15aXj7a7GyDahToZHfSFo4YmH1DfZrwTjIL2an99o4FY/edit?usp=sharing)'
        await ctx.send(embed=e)
        await ctx.tick()  # green tick emoji --> success

    @commands.command()
    async def war_status(self, ctx, tag_or_name: str=None):
        if not tag_or_name:
            tag_or_name = self.bot.AW_CLAN_TAG  # lets set it to AW tag for the lazy

        try:
            clan = await self.bot.coc.get_clan(tag_or_name)
        except coc.NotFound:
            raise commands.BadArgument(':x: Clan Not Found!')  # api returned {reason: 'notFound'} or some other error

        e = discord.Embed(colour=discord.Colour.blue())
        e.add_field(name=clan.name,
                    value=clan.tag)

        if clan.public_war_log:  # we will get errors if warlog is closed
            war = await self.bot.coc.get_current_war(tag_or_name)

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

        await ctx.send(embed=e)

    @commands.command()
    @checks.manage_server()
    async def update_stats(self, ctx, true_false: bool=None):
        if not true_false:
            status = self.bot.loaded['updateStats']  # tell them what status is if not specified
            e = discord.Embed(description=status)
            e.colour = discord.Colour.green() if status == 'true' else discord.Colour.red()  # red = false, green = true
            return await ctx.send(embed=e)  # send and return

        self.bot.mod_commands.append(ctx)  # we don't want to send a mod log if they're just getting status

        true_false = 'true' if true_false else 'false'  # convert that bool to a string true/false

        self.bot.loaded['updateStats'] = true_false
        await self.bot.save_json()  # save that value in json for persistant storage when bot down

        await ctx.tick()  # green tick emoji --> success

    @commands.command()
    @checks.restricted_channel(LEAGUE_BOT_CHANNEL, NERD_BOT_ZONE_CHANNEL)
    async def warstats(self, ctx, th: int = None, owner_only_last_x_wars: int=None):
        """Gives you war stats for a max. of 20 wars

        Optional: Specify the TH level of which to get stats. Else all THs will be added to a pagination session
        Optional: [Owner-only] Specify the number of wars for which to get stats (Between 1 and 20)
        This command can only be used in #league-bot

        """
        all_ths = [9, 10, 11, 12]

        # this is messy, but its saying that owners can specify the number of wars to fetch,
        # if you're not an owner it's 20
        is_owner = True if ctx.author.id in self.bot.owners else False

        if owner_only_last_x_wars and not is_owner:
            await ctx.send('Ahem, only owners may use that filter. I have set it to default `20`')
            owner_only_last_x_wars = 20
        if not owner_only_last_x_wars:
            owner_only_last_x_wars = 20

        # this is checking that if theres no TH, it uses all; if its not a valid TH it tells you,
        # or otherwise turns your TH into a list so we can iterate 1 item
        if not th:
            th = all_ths
        elif th not in all_ths:
            raise commands.BadArgument('Please choose a valid TH: `9`, `10`, `11`, `12`')
        else:
            th = [th]

        entries = []
        headers = ['Off HR', 'HR %', 'IGN', 'Def', 'Def %', 'Player Tag']

        for n in th:
            stats = await self.statsForTh(n, owner_only_last_x_wars)

            if not stats['overall']:
                entries.append(f'__**No stats found for TH{n}v{n}. Sorry**__\n')
                continue  # nothing found in db for some reason. go to next TH

            table = TabularData()  # lets make a nice table for each TH page
            table.set_columns(headers)
            table.add_rows(list(r.values()) for r in stats['overall'])
            render = table.render()

            string = f'__**Stats for TH{n}v{n}**__'
            string = f'{string}```\n{render}\n```'

            entries.append(string)

        pages = paginator.MsgPag(ctx, entries=entries, per_page=1)
        await pages.paginate(start_page=1)

    # First helper function, This is used to find the TH of a player given his/her clash Tag
    def getTownHallLevel(self, clashTag, currentWar):
        # First we search the enemy clan for tag (Assuming it belongs to enemy clan)
        enemySearch = [x['townhallLevel'] for x in currentWar['opponent']['members'] if x['tag'] == clashTag]
        # If it exists, we return TH
        if enemySearch:
            return enemySearch[0]
        else:
            # Else we search and return TH from out clan (i.e the tag belongs to our clan)
            return [x['townhallLevel'] for x in currentWar['clan']['members'] if x['tag']==clashTag][0]

    # Second helper function, This is used to calculate how many attacks were defended by base
    def getdefenses(self, defenderTag, currentWar):
        # Get all the attacks on base (returns [('attackerTag',stars)..] list)
        attacksOnBase = [(attack['attackerTag'], attack['stars']) for members in currentWar['opponent']['members'] if 'attacks' in members.keys() for
                         attack in members['attacks'] if attack['defenderTag'] == defenderTag]

        # varibles to store corresponding values
        defendedAttacks = 0
        totalAttacks = 0

        for attack in attacksOnBase:
            # Get the attacker tag for every attack
            attackerTag = attack[0]
            # In case the TH of attcker(from enemy clan) and defender(from our clan) are same
            if self.getTownHallLevel(attackerTag, currentWar) == self.getTownHallLevel(defenderTag, currentWar):
                # First increase the count of total attacks
                totalAttacks += 1
                # check if it wasn't 3'ed
                if attack[1] != 3:
                    # Then increase defended attacks
                    defendedAttacks += 1
        # Return the values
        return defendedAttacks, totalAttacks

    #Helper function, converts 'A/B' to percentage
    def fracToPer(self, fraction):
        split = fraction.split('/')
        numerator = int(split[0])
        denominator = int(split[1])

        per = f"{numerator * 100 / denominator:.2f}%" if denominator != 0 else '0.00%'

        return per

    # Main driver function, calculates all values, updates the db, inserts new values

    # (IT WILL NOT DO ANYTHING IF THE WAR HASN'T ENDED), so make sure this is
    # called after the war has ended and before new war search has begun'''

    async def temporory_war_stats(self):
        attacks_added = 0

        query = "SELECT attack_number FROM temp_stats WHERE enemy_clan_tag = $1"

        current_war = await self.bot.coc.get_current_war(self.CLAN_TAG)

        dump = await self.bot.pool.fetch(query, current_war.opponent.tag)
        att_orders = [n[0] for n in dump]

        query = """INSERT INTO temp_stats 
                    (enemy_clan_tag, attack_number, enemy_tag, attacker_tag,
                     name, th, enemy_th, stars, percent, our_hit)
                    VALUES ($1, $2, $3, $4,
                            $5, $6, $7, $8,
                            $9, $10)
                """

        async def add_attacks(our_hit: bool):
            added = 0
            if not member.attacks:
                return None

            for attack in member.attacks:

                if attack.order in att_orders:
                    continue

                enemy_th = self.getTownHallLevel(attack.attacker_tag, current_war)

                await self.bot.pool.execute(query,
                                            current_war.opponent.tag,
                                            attack['order'],
                                            attack['defenderTag'],
                                            member['tag'],
                                            member['name'],
                                            member['townhallLevel'],
                                            enemy_th,
                                            attack['stars'],
                                            attack['destructionPercentage'],
                                            our_hit)
                added += 1

            return added

        for member in current_war.clan._members:
            n = await add_attacks(not member.is_opponent)
            if n:
                attacks_added += n

        return attacks_added

    async def final_war_stats(self, tag):
        query = "SELECT * FROM temp_stats WHERE enemy_clan_tag = $1 AND our_hit = True"
        our_hits = await self.bot.pool.fetch(query, tag)

        query = "SELECT * FROM temp_stats WHERE enemy_clan_tag = $1 AND our_hit = False"
        opponent_hits = await self.bot.pool.fetch(query, tag)

        if not our_hits:
            return False

        member_hits = {}
        enemy_hits = {}

        for attack in our_hits:
            if attack['attacker_tag'] in member_hits.keys():
                member_hits[attack['attacker_tag']].append(attack)
            else:
                member_hits[attack['attacker_tag']] = [attack]

        for attack in opponent_hits:
            if attack['enemy_tag'] in enemy_hits.keys():
                enemy_hits[attack['enemy_tag']].append(attack)
            else:
                enemy_hits[attack['enemy_tag']] = [attack]

        sql_rows = []

        for member in member_hits.values():
            successful_hits = []
            defended_attacks = 0
            total_attacks_on_base = 0

            # Loop over every attack by member
            for attack in member:
                # Only count attack if either player th = enemy th
                if attack['th'] == attack['enemy_th']:
                    hit = 1 if attack['stars'] == 3 else 0
                    successful_hits.append(hit)

            if member[0]['attacker_tag'] in enemy_hits.keys():
                for attack in enemy_hits[member[0]['attacker_tag']]:
                    if attack['th'] != attack['enemy_th']:
                        continue

                    total_attacks_on_base += 1
                    if attack['stars'] != 3:
                        defended_attacks += 1

            hr = f'{sum(successful_hits)}/{(len(successful_hits))}'
            war_no = 1
            player_name = member[0]['name']
            if '"' in player_name:
                player_name.replace("'", "''")
                player_name.replace('"', "'")

            player_tag = member[0]['attacker_tag']
            player_th = member[0]['th']

            dr = f'{defended_attacks}/{total_attacks_on_base}'

            row = [war_no, player_name, player_tag, player_th, hr, dr]
            sql_rows.append(row)

        query = "UPDATE war_stats SET war_no = war_no +1;"
        await self.bot.pool.execute(query)

        query = "DELETE FROM war_stats WHERE war_no>20;"
        await self.bot.pool.execute(query)

        query = f"""INSERT INTO war_stats 
                    (war_no, name, tag, th,
                     hitrate, defenserate) VALUES ($1, $2, $3, $4, $5, $6);"""
        for n in sql_rows:
            await self.bot.pool.execute(query, n[0], n[1], n[2], n[3], n[4], n[5])

        query = "DELETE FROM temp_stats WHERE enemy_clan_tag = $1"
        await self.bot.pool.execute(query, tag)

        self.bot.loaded['updateStats'] = 'false'
        await self.bot.save_json()

        return True

    # async def calculateWarStats(self):
    #     """Takes in coc client and db connection as arguement, then calculates the stats for current war,
    #     updates the war_stats table by removing the 20th war and inserting the latest war"""
    #
    #     # create cursor & define tag
    #
    #     # Query to get details for current war
    #     currentWar = await self.bot.coc.clans(self.CLAN_TAG).currentwar().get(self.bot.coc_token)
    #
    #     # If war hasn't ended yet don't update or calculate anything
    #     if currentWar['state'] != 'warEnded':
    #         return
    #
    #     # This will store all the rows (Essentially being a list of tuples)
    #     rows = []
    #
    #     # Loop over all members of clan and calculate all stats
    #     for member in currentWar['clan']['members']:
    #
    #         # Some values which will be used to either calculate stats or be fed directly into database
    #         playerTownhall = member['townhallLevel']
    #
    #         #Check if attacks exist
    #         if 'attacks' in member.keys():
    #             attacks = member['attacks']
    #
    #             # Used to store the successful hits i.e 3stars
    #             successfulHits = []
    #
    #             # Loop over every attack by member
    #             for attack in attacks:
    #                 # Find enemy TH level
    #                 enemyTownhall = self.getTownHallLevel(attack['defenderTag'], currentWar)
    #
    #                 # Only count attack if either player th = enemy th
    #                 if enemyTownhall == playerTownhall:
    #                     hit = 1 if attack['stars'] == 3 else 0
    #                     successfulHits.append(hit)
    #
    #             # calculate hitrate
    #             hr = str(sum(successfulHits)) + '/' + str(len(successfulHits))
    #         else:
    #             #If no attacks set hitrate = 0/0
    #             hr = '0/0'
    #
    #         # Get Defenses for the member (Returns defendedAttacks,totalAttacks on base)
    #         defendedAttacks, totalAttacksOnBase = self.getdefenses(member['tag'], currentWar)
    #
    #         # Values to be fed into db
    #         warNo = 1
    #         playerName = member['name']
    #         playerTag = member['tag']
    #         playerTownhall = str(playerTownhall)
    #
    #         dr = str(defendedAttacks) + '/' + str(totalAttacksOnBase)
    #
    #         # Save all info into a tuple (Easier to insert into db)
    #         row = (warNo, playerName, playerTag, playerTownhall, hr, dr)
    #
    #         # Append row to rows list
    #         rows.append(row)
    #
    #     # Finally we'll update the database
    #
    #     # first we increase the war no for all values in table, since new war has been added
    #     sql = '''UPDATE war_stats SET war_no = war_no +1;'''
    #     await self.bot.pool.execute(sql)
    #
    #     # Next we'll drop all the rows which have war_no greater than 20
    #     sql = '''DELETE FROM war_stats WHERE war_no>20;'''
    #     await self.bot.pool.execute(sql)
    #
    #     # Now we just insert all values from rows one by one
    #     for row in rows:
    #         sql = f'''INSERT INTO war_stats(war_no,name,tag,th,hitrate,defenserate) VALUES {row};'''
    #         await self.bot.pool.execute(sql)
    #
    #     # Finally close cursor and commit changes
    #     '''Commenting these for now, idk how ctx.db.execute works, remove if these are not needed'''
    #     # cursor.close()
    #     # connection.commit()
    #
    #     # # Finally Set updateStats = 'false', since this war's stats have been added
    #     # self.bot.update_stats = 'false'
    #     # Save value in file
    #     self.bot.loaded['updateStats'] = 'false'
    #     await self.bot.save_json()

    async def statsForTh(self, townhallLevel, wars_to_fetch):
        '''Takes in townhall as arguement and gives the stats for that particular townhall level'''

        # Query to get details for current war
        currentMembers = (await self.bot.coc.get_clan(self.CLAN_TAG))._members
        tags = tuple([x.tag for x in currentMembers])

        # Get all the data for the particular townhall
        result = await self.bot.pool.fetch(f"select name,hitrate,defenserate,tag"
                                           f" from war_stats where th = '{townhallLevel}'"
                                           f" and tag in {tags} and war_no <= {wars_to_fetch}")

        # Get all distinct name for particular townhall (We will use this to display on discord)
        dump = await self.bot.pool.fetch(f"select distinct name, tag from war_stats where th = '{townhallLevel}'"
                                         f" and tag in {tags} and war_no <= {wars_to_fetch}")

        # Create a dict of data for easy processing
        data = [{'name': x[0], 'hitrate': x[1], 'defenserate':x[2], 'tag': x[3]} for x in result]

        # two lists that will store respective stats
        offensiveStats = []
        defensiveStats = []
        overall_stats = []

        # iterate over all names
        for name, tag in dump:

            # Variables to hold values to find out hitrates and defenserates
            cummulativeHits = 0
            cummulativeTotalAttacks = 0
            cummulativeDefended = 0
            cummulativeTotalDefenses = 0

            # Iterate over all data
            for x in data:
                # If the name matches
                if x['tag'] == tag:
                    # Offensive stats calculations
                    temp_hitrate = x['hitrate'].split('/')
                    cummulativeHits += int(temp_hitrate[0])
                    cummulativeTotalAttacks += int(temp_hitrate[1])

                    # Defensive stats calculations
                    temp_defenserate = x['defenserate'].split('/')
                    cummulativeDefended += int(temp_defenserate[0])
                    cummulativeTotalDefenses += int(temp_defenserate[1])

            # Format all stats
            hitrate = str(cummulativeHits)+'/'+str(cummulativeTotalAttacks)
            defenserate = str(cummulativeDefended)+'/'+str(cummulativeTotalDefenses)
            try:
                hitratePer = f"{cummulativeHits*100/cummulativeTotalAttacks:.2f}%"
            except ZeroDivisionError:
                hitratePer = '0%'
            try:
                defenseratePer = f"{cummulativeDefended*100/cummulativeTotalDefenses:.2f}%"
            except ZeroDivisionError:
                defenseratePer = '0%'

            # Create 2 dicts, offense and deffense
            overall = {'hitrate': hitrate, 'hitratePer': hitratePer, 'name': name,
                       'defenserate': defenserate, 'defenseratePer': defenseratePer, 'tag': tag}
            overall_stats.append(overall)
            offense = {'name': name, 'hitrate': hitrate, 'hitratePer': hitratePer, 'tag': tag}
            offensiveStats.append(offense)
            defense = {'name': name, 'defenserate': defenserate, 'defenseratePer': defenseratePer, 'tag': tag}
            defensiveStats.append(defense)

        stats = {'offense': offensiveStats, 'defense': defensiveStats, 'overall': overall_stats}

        return stats

    async def get_coc_status(self, warning_msg, warnings_sent):
        try:
            current_war = await self.bot.coc.get_current_war(self.CLAN_TAG)

        except coc.HTTPException as e:
            embed = discord.Embed(colour=discord.Colour.red())
            message_string = re.sub('\d', '\\*', e.message)  # message may contain ip. obscure that
            embed.add_field(name="Clash of Clans API Error",
                            value=f"Reason: {e.reason}\nMessage: {message_string}")

            embed.set_footer(text=f'{warnings_sent} warnings sent (Error persisted for ~{warnings_sent*2} minutes)')

            if warning_msg:
                await warning_msg.edit(embed=e)
                warnings_sent += 1

            else:
                msg = await (self.bot.get_channel(self.bot.info_channel_id)).send(embed=e)
                warning_msg = msg
                warnings_sent += 1

            return None, warning_msg, warnings_sent, None, None

        if warning_msg:
            warning_msg = None
            warnings_sent = 0

        try:
            opponent_tag = current_war.opponent.tag
        except AttributeError:
            opponent_tag = None

        return current_war.state, warning_msg, warnings_sent, current_war.end_time, opponent_tag

    async def war_stats_auto_updater(self):
        warnings_sent = 0
        warning_msg = None

        try:
            while not self.bot.is_closed():
                await self.bot.get_cog('Admin').task_stats('war_stats', False)
                await asyncio.sleep(60)

                status, warning_msg, warnings_sent, ts, enemy_tag = \
                    await self.get_coc_status(warning_msg, warnings_sent)

                if not status:
                    continue

                if status == 'warEnded':
                    if self.bot.update_stats == 'false':
                        continue

                    n = await self.final_war_stats(enemy_tag)
                    if n is True:
                        await self.bot.get_cog('Admin').task_stats('war_stats', True)
                        await (self.bot.get_channel(self.bot.info_channel_id)).send('war-stats-update done')
                    else:
                        await (self.bot.get_channel(self.bot.info_channel_id)).send('tried to finalise stats, '
                                                                                    'but there were no hits!')
                    self.bot.update_stats = 'false'
                    self.bot.loaded['updateStats'] = 'false'
                    await self.bot.save_json()

                    continue

                if status in ['preparation', 'inWar']:
                    self.bot.update_stats = 'true'
                    self.bot.loaded['updateStats'] = 'true'
                    await self.bot.save_json()

                    if ts < 1800:  # half hour
                        await self.temporory_war_stats()
                        await self.bot.get_cog('Admin').task_stats('temp_stats', True)
                        continue

                    await asyncio.sleep(ts - 1801)
                    continue

        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed):
            await self.stats_updater_task.cancel()
            self.stats_updater_task = self.bot.loop.create_task(self.war_stats_auto_updater())

    async def war_role_adding_task(self):
        warnings_sent = 0
        warning_msg = None

        try:
            while not self.bot.is_closed():
                await self.bot.get_cog('Admin').task_stats('war_roles', False)
                await asyncio.sleep(60)

                status, warning_msg, warnings_sent, ts, enemy_tag = \
                    await self.get_coc_status(warning_msg, warnings_sent)

                if status == 'preparation':
                    if self.bot.war_roles == 'false':
                        continue

                    cog = self.bot.get_cog('WarAdmin')
                    e = await cog.give_roles_auto()
                    channel = self.bot.get_channel(self.bot.info_channel_id)
                    if e:
                        await channel.send(embed=e)
                    else:
                        await channel.send('war-roles-auto done')
                        self.bot.war_roles = 'false'
                        self.bot.loaded['warRoles'] = 'false'
                        await self.bot.save_json()

                if status in ['inWar', 'warEnded', 'notInWar']:
                    self.bot.war_roles = 'true'
                    self.bot.loaded['warRoles'] = 'true'
                    await self.bot.save_json()

                if ts:
                    await asyncio.sleep(ts)

        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed):
            await self.stats_updater_task.cancel()
            self.stats_updater_task = self.bot.loop.create_task(self.war_role_adding_task())



    # async def warStatsAutoUpdater(self):
    #     warnings_sent = 0
    #     warning_msg = None
    #     # Infinite loop
    #     try:
    #         while not self.bot.is_closed():
    #             await self.bot.get_cog('Admin').task_stats('war_stats', False)
    #             # Sleep for 2 mins before querying the API
    #
    #             await asyncio.sleep(60)
    #
    #             # Query to get details for current war
    #             currentWar = await self.bot.coc.clans(self.CLAN_TAG).currentwar().get(self.bot.coc_token)
    #
    #             # Check if state exists in current war, (This is a check in case of maintainence)
    #             if 'state' in currentWar.keys():
    #                 if warning_msg:
    #                     warning_msg = None
    #                     warnings_sent = 0
    #
    #                 # Check if we have to update stats && the war has ended
    #                 # (We can't check for just warEnded because, it will keep updating
    #                 # for same war till the status changes)
    #
    #                 if self.bot.update_stats == 'true':
    #                     if currentWar['state'] == 'warEnded':
    #                         await self.calculateWarStats()
    #                         await self.bot.get_cog('Admin').task_stats('war_stats', True)
    #                         await (self.bot.get_channel(self.bot.info_channel_id)).send('war-stats-update done')
    #
    #                         continue
    #                 # In case updateStats is 'false' (i.e last war ended and it's stats were updated,
    #                 #  so we need to check for next war, once we get a match, we make updateStats 'true')
    #                 elif currentWar['state'] in ['preparation', 'inWar']:
    #                     self.bot.update_stats = 'true'
    #                     # Write the value of updateStats in file
    #                     self.bot.loaded['updateStats'] = 'true'
    #                     await self.bot.save_json()
    #                     cog = self.bot.get_cog('WarAdmin')
    #                     e = await cog.give_roles_auto()
    #                     channel = self.bot.get_channel(self.bot.info_channel_id)
    #                     if e:
    #                         await channel.send(embed=e)
    #                     else:
    #                         await channel.send('war-roles-auto done')
    #
    #                     continue
    #             else:
    #                 e = discord.Embed(colour=discord.Colour.red())
    #                 # You might want to log the error
    #                 if 'reason' in currentWar.keys():
    #                     message_string = re.sub('\d', '\\*', currentWar['message'])  # message may contain ip. obscure that
    #                     e.add_field(name="Clash of Clans API Error",
    #                                 value=f"Reason: {currentWar['reason']}\nMessage: {message_string}")
    #
    #                 elif not currentWar:
    #                     e.add_field(name="Clash of Clans API Error",
    #                                 value="The request returned `None`\nIs it an incorrect token?")
    #
    #                 else:
    #                     e.add_field(name="Clash of Clans API Error",
    #                                 value="Unknown Error")
    #
    #                 e.set_footer(text=f'{warnings_sent} warnings sent (Error persisted for ~{warnings_sent*2} minutes)')
    #
    #                 if warning_msg:
    #                     await warning_msg.edit(embed=e)
    #                     warnings_sent += 1
    #
    #                 else:
    #                     msg = await (self.bot.get_channel(self.bot.info_channel_id)).send(embed=e)
    #                     warning_msg = msg
    #                     warnings_sent += 1
    #
    #     except asyncio.CancelledError:
    #         pass
    #     except (OSError, discord.ConnectionClosed):
    #         await self.stats_updater_task.cancel()
    #         self.stats_updater_task = self.bot.loop.create_task(self.warStatsAutoUpdater())

    # Function to send database to Google sheet
    async def DBtoGoogleSheets(self):

        # Autorize client
        sheetsClient = pygsheets.authorize()

        # Open the spreadsheet named 'AW War Stats'
        spreadSheet = sheetsClient.open('AW War Stats')

        # Connect to sheet 1 of spread sheet
        sheet1 = spreadSheet.sheet1

        # Clear all the data in it
        sheet1.clear()

        # Define the columns
        cols = ['War No.', 'Player Name', 'Tag', 'TownHall', 'Hit Rate', 'Hit Rate %', 'Defense Rate', 'Defense Rate %']
        # Set values of first row as cols
        sheet1.update_row(1, cols)

        # get all data from database
        rows = await self.bot.pool.fetch(f"select * from war_stats")

        # Convert it into a form that is accepted by google sheets
        excelData = [[x[0], x[1], x[2], x[3], x[4], self.fracToPer(x[4]), x[5], self.fracToPer(x[5])] for x in rows]

        # Write the data into sheet
        sheet1.update_row(2, excelData)


def setup(bot):
    bot.add_cog(WarStats(bot))
