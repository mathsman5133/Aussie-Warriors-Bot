from discord.ext import commands
from cogs.utils import checks, paginator, db
from cogs.admin import TabularData

import asyncio
import discord
import re


class war_stats(db.Table):
    war_no = db.Column(db.Integer())
    name = db.Column(db.String())
    tag = db.Column(db.String())
    th = db.Column(db.Integer())
    hitrate = db.Column(db.String())
    defenserate = db.Column(db.String())


class WarStats:
    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.warStatsAutoUpdater())

    LEAGUE_BOT_CHANNEL = 528822099360612352
    CLAN_TAG = '#P0LYJC8C'

    async def __error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

    @commands.command()
    @checks.manage_server()
    @checks.mod_commands()
    async def statsdump(self, ctx):
        """Updates stats in database for current finished war

        You must have `manage_server` permissions to run this command.
        """
        await self.calculateWarStats()
        await ctx.message.add_reaction('\u2705')  # green tick emoji --> success

    @commands.command()
    @checks.restricted_channel(LEAGUE_BOT_CHANNEL)
    async def warstats(self, ctx, th: int = None):
        """Gives you war stats for a max. of 20 wars

        Optional: Specify the TH level of which to get stats. Else all THs will be added to a pagination session
        This command can only be used in #league-bot
        """
        all_ths = [9, 10, 11, 12]

        if not th:
            th = all_ths
        elif th not in all_ths:
            raise commands.BadArgument('Please choose a valid TH: `9`, `10`, `11`, `12`')
        else:
            th = [th]

        entries = []

        for n in th:
            headers = ['Off HR', 'HR %', 'IGN', 'Def', 'Def %', 'Player Tag']
            stats = await self.statsForTh(n)
            base = '{:>7}{:>10}{:>16}{:>10}{:>7}{:>14}'
            table = TabularData()
            table.set_columns(headers)
            table.add_rows(list(r.values()) for r in stats['overall'])
            render = table.render()

            strings = []
            if not stats['overall']:
                entries.append(f'__**No stats found for TH{n}v{n}. Sorry**__\n')
                continue

            for member in stats['overall']:
                strings.append(base.format(member['hitrate'], member['hitratePer'], member['name'],
                                           member['defenserate'], member['defenseratePer'], member['tag']))

            # hr = '\n'.join(strings)

            string = f'__**Stats for TH{n}v{n}**__'
            string = f'{string}```\n{render}\n```'
            #string = f"{string}\n```{base.format('Off HR', 'HR %', 'IGN', 'Def', 'Def %', 'Player Tag')}\n{hr}```"
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
        attacksOnBase = [(attack['attackerTag'], attack['stars']) for members in currentWar['opponent']['members'] if 'attack' in members.keys() for
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

    # Main driver function, calculates all values, updates the db, inserts new values

    # (IT WILL NOT DO ANYTHING IF THE WAR HASN'T ENDED), so make sure this is
    # called after the war has ended and before new war search has begun'''

    async def calculateWarStats(self):
        '''Takes in coc client and db connection as arguement, then calculates the stats for current war,
        updates the war_stats table by removing the 20th war and inserting the latest war'''

        # create cursor & define tag

        # Query to get details for current war
        currentWar = await self.bot.coc.clans(self.CLAN_TAG).currentwar().get(self.bot.coc_token)

        # If war hasn't ended yet don't update or calculate anything
        if currentWar['state'] != 'warEnded':
            return

        # This will store all the rows (Essentially being a list of tuples)
        rows = []

        # Loop over all members of clan and calculate all stats
        for member in currentWar['clan']['members']:

            # Some values which will be used to either calculate stats or be fed directly into database
            playerTownhall = member['townhallLevel']

            #Check if attacks exist
            if 'attacks' in member.keys():
                attacks = member['attacks']

                # Used to store the successful hits i.e 3stars
                successfulHits = []

                # Loop over every attack by member
                for attack in attacks:
                    # Find enemy TH level
                    enemyTownhall = self.getTownHallLevel(attack['defenderTag'], currentWar)

                    # Only count attack if either player th = enemy th
                    if enemyTownhall == playerTownhall:
                        hit = 1 if attack['stars'] == 3 else 0
                        successfulHits.append(hit)

                # calculate hitrate
                hr = str(sum(successfulHits)) + '/' + str(len(successfulHits))
            else:
                #If no attacks set hitrate = 0/0
                hr = '0/0'

            # Get Defenses for the member (Returns defendedAttacks,totalAttacks on base)
            defendedAttacks, totalAttacksOnBase = self.getdefenses(member['tag'], currentWar)

            # Values to be fed into db
            warNo = 1
            playerName = member['name']
            playerTag = member['tag']
            playerTownhall = str(playerTownhall)

            dr = str(defendedAttacks) + '/' + str(totalAttacksOnBase)

            # Save all info into a tuple (Easier to insert into db)
            row = (warNo, playerName, playerTag, playerTownhall, hr, dr)

            # Append row to rows list
            rows.append(row)

        # Finally we'll update the database

        # first we increase the war no for all values in table, since new war has been added
        sql = '''UPDATE war_stats SET war_no = war_no +1;'''
        await self.bot.pool.execute(sql)

        # Next we'll drop all the rows which have war_no greater than 20
        sql = '''DELETE FROM war_stats WHERE war_no>20;'''
        await self.bot.pool.execute(sql)

        # Now we just insert all values from rows one by one
        for row in rows:
            sql = f'''INSERT INTO war_stats(war_no,name,tag,th,hitrate,defenserate) VALUES {row};'''
            await self.bot.pool.execute(sql)

        # Finally close cursor and commit changes
        '''Commenting these for now, idk how ctx.db.execute works, remove if these are not needed'''
        # cursor.close()
        # connection.commit()

        # # Finally Set updateStats = 'false', since this war's stats have been added
        # self.bot.update_stats = 'false'
        # Save value in file
        self.bot.loaded['updateStats'] = 'false'
        await self.bot.save_json()

    async def statsForTh(self, townhallLevel):
        '''Takes in townhall as arguement and gives the stats for that particular townhall level'''

        # Get all the data for the particular townhall
        result = await self.bot.pool.fetch(f"select name,hitrate,defenserate,tag"
                                           f" from war_stats where th = '{townhallLevel}'")

        # Get all distinct name for particular townhall (We will use this to display on discord)
        dump = await self.bot.pool.fetch(f"select distinct name from war_stats where th = '{townhallLevel}'")
        names = [x[0] for x in dump]

        # Create a dict of data for easy processing
        data = [{'name': x[0], 'hitrate': x[1], 'defenserate':x[2], 'tag': x[3]} for x in result]

        # two lists that will store respective stats
        offensiveStats = []
        defensiveStats = []
        overall_stats = []

        # iterate over all names
        for name in names:

            # Variables to hold values to find out hitrates and defenserates
            cummulativeHits = 0
            cummulativeTotalAttacks = 0
            cummulativeDefended = 0
            cummulativeTotalDefenses = 0
            tag = ''

            # Iterate over all data
            for x in data:
                # If the name matches
                if x['name'] == name:
                    # Offensive stats calculations
                    temp_hitrate = x['hitrate'].split('/')
                    cummulativeHits += int(temp_hitrate[0])
                    cummulativeTotalAttacks += int(temp_hitrate[1])

                    # Defensive stats calculations
                    temp_defenserate = x['defenserate'].split('/')
                    cummulativeDefended += int(temp_defenserate[0])
                    cummulativeTotalDefenses += int(temp_defenserate[1])
                    tag += x['tag']

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

    async def warStatsAutoUpdater(self):

        # Infinite loop
        while True:
            # Sleep for 2 mins before querying the API

            await asyncio.sleep(120)

            # Query to get details for current war
            currentWar = await self.bot.coc.clans(self.CLAN_TAG).currentwar().get(self.bot.coc_token)

            # Check if state exists in current war, (This is a check in case of maintainence)
            if 'state' in currentWar.keys():
                # Check if we have to update stats && the war has ended
                # (We can't check for just warEnded because, it will keep updating
                # for same war till the status changes)

                if self.bot.update_stats == 'true':
                    if currentWar['state'] == 'warEnded':
                        await self.calculateWarStats()
                        continue
                # In case updateStats is 'false' (i.e last war ended and it's stats were updated,
                #  so we need to check for next war, once we get a match, we make updateStats 'true')
                elif currentWar['state'] in ['preparation', 'inWar']:
                    self.bot.update_stats = 'true'
                    # Write the value of updateStats in file
                    self.bot.loaded['updateStats'] = 'true'
                    await self.bot.save_json()
                    continue
            else:
                e = discord.Embed(colour=discord.Colour.red())
                # You might want to log the error
                if 'reason' in currentWar.keys():
                    message_string = re.sub('\d', '*', currentWar['message'])  # message may contain ip. obscure that
                    e.add_field(name="Clash of Clans API Error",
                                value=f"Reason: {currentWar['reason']}\nMessage: {message_string}")

                elif not currentWar:
                    e.add_field(name="Clash of Clans API Error",
                                value="The request returned `None`\nIs it an incorrect token?")

                else:
                    e.add_field(name="Clash of Clans API Error",
                                value="Unknown Error")

                await (self.bot.get_channel(self.bot.info_channel_id)).send(embed=e)


def setup(bot):
    bot.add_cog(WarStats(bot))
