import discord
from discord.ext import commands

from cogs.utils import checks, db


def list_to_sql_tuple(list_of_things):
    if len(list_of_things) == 0:
        return None
    if len(list_of_things) == 1:
        return f'({list_of_things[0]})'

    return tuple(n for n in list_of_things)


class LastWarTable(db.Table, table_name='last_war'):
    tag = db.Column(db.String())
    userid = db.Column(db.Integer(big=True))


class TagIDTable(db.Table, table_name='tag_to_id'):
    id = db.Column(db.Integer(big=True))
    tag = db.Column(db.String())


class WarAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.IN_WAR_ROLE_ID = 526702907127627793
        self.AW_SERVER_ID = 352298238180851712
        self.NERD_BOT_ZONE_ID = 527373033568993282
        self.CLAN_TAG = '#P0LYJC8C'

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            e = discord.Embed(colour=discord.Colour.red())
            e.description = error
            await ctx.send(embed=e)

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Missing required argument {error}!')
            await ctx.show_help()

        elif isinstance(error, checks.COCError):
            e = discord.Embed(colour=discord.Colour.red())
            e.add_field(name='COC API Error',
                        value=error.msg)
            await ctx.send(embed=e)

    @commands.group(name="warrole")
    @checks.mod_commands()
    @checks.manage_roles()
    @checks.clan_status(['preparation', 'inWar'])
    async def war_role(self, ctx):
        """[Group] Manage the inWar role when a (league) war is in progress
        """
        pass  # to prevent from throwing error

    @war_role.command(aliases=['all', 'init'])
    async def giveall(self, ctx):
        """
        Initialise war in database, giving the `inWar` role to all currently in war with claimed accounts.

        Requires `Manage_Roles` permission
        """
        embed = await self.give_roles(ctx.db, ctx.guild, ctx.author)
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.tick()

    @war_role.command()
    async def add(self, ctx, *members: discord.Member):
        """
        Manually add someone in war to the `inWar` role.

        The preferred method is `?war role init`
        However, pass in a player tag or IGN, and either a mention, user#discrim or id.
        If no member is passed it will assign the role to yourself

        This also adds the member to the database *for this war only*, so please use this over manually giving roles
        """
        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)

        mention_ids = [n.id for n in members]
        # member_tuple = list_to_sql_tuple(mention_ids)
        #
        # query = f"SELECT DISTINCT userid FROM claims WHERE userid in {member_tuple};"
        # dump = await ctx.db.fetch(query)
        #
        # found_ids = []
        # if dump:
        #     fmt = ', '.join(f"('{tag}', {userid})"
        #                     for (index, (tag, userid)) in enumerate(dump))
        #     query = f"INSERT INTO last_war (tag, userid) VALUES {fmt};"
        #     await ctx.db.execute(query)
        #
        # no_claim_ids = list(set(mention_ids) - set(found_ids))
        #
        # if no_claim_ids:
        fmt = ', '.join(f"('Unknown', {userid})"
                        for userid in mention_ids)
        query = f"INSERT INTO last_war (tag, userid) VALUES {fmt};"

        await ctx.db.execute(query)

        errors = []

        for n in members:
            try:
                await n.add_roles(role, reason=f'{str(ctx.author)} '
                                               f'`{ctx.prefix}warrole add [mentions]`')
            except (discord.Forbidden, discord.HTTPException):
                errors.append(n)

        if not errors:
            return await ctx.tick()

        e = discord.Embed(colour=discord.Colour.red())
        fmt = "Could not add roles to the following\n" \
              "Do I have perms? Has someone moved my role down?\n" \
              "Else check some logs somewhere"
        e.description = fmt + '\n'.join(n.mention for n in errors)

        await ctx.send(embed=e)

    @war_role.command()
    async def remove(self, ctx, *mentions: discord.Member):
        """
        Manually remove members(s) from the `inWar` role.

        `war role init` is the preferred method, however this is best when the other not appropriate

        Pass in mentions of members you wish to remove the role from. This could be a mention, user#discrim or id.

        Please use this over manually removing the role as it removes the entry from the database.
        """
        if not mentions:
            mentions = [ctx.author]

        member_tuple = list_to_sql_tuple([n.id for n in mentions])

        query = f"DELETE FROM last_war WHERE userid in {member_tuple};"
        await ctx.db.execute(query)

        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        errors = []
        for member in mentions:
            try:
                await member.remove_roles(role,
                                          reason=f'{str(ctx.author)} - '
                                                 f'{ctx.command.qualified_name}')
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                errors.append(member)

        if not errors:
            return await ctx.tick()

        e = discord.Embed(colour=discord.Colour.red())  # red --> error
        fmt = "Could not remove roles to the following\n" \
              "Do I have perms? Has someone moved my role down?\n" \
              "Else check some logs somewhere"
        e.description = fmt + '\n'.join(n.mention for n in errors)

        return await ctx.send(embed=e)

    @war_role.command()
    async def clear(self, ctx):
        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)

        for n in role.members:
            await n.remove_roles(role, reason=f'{str(ctx.author)} - '
                                              f'{ctx.command.qualified_name}')
        await ctx.tick()

    @war_role.command()
    async def show(self, ctx):
        """
        List everyone with the `inWar` role, both in discord and in the database.
        Helpful to find discrepencies and rectify the issue

        Requires `manage_roles` permission
        """
        query = "SELECT userid, tag FROM last_war"
        dump = await ctx.db.fetch(query)

        with_db_role = [f'<@{n[0]}> - {n[1]}' for n in dump]
        with_discord_role = [n.id for n in ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID).members]

        # sort list by user ids (a big int) ascending, so that both are sorted same way,
        # meaning easy to pick inconsistencies between them (shouldnt be to start with)
        with_db_role.sort()
        with_discord_role.sort()

        e = discord.Embed(colour=discord.Colour.blue())  # blue --> nothing changed
        e.set_author(name="Members with inWar role ")
        e.add_field(name="Per DB",
                    value='\n'.join(n for n in with_db_role) or 'No Members'
                    )

        # the reason I used <@id> over user.mention is that it is nice to have roles sorted by something so it is easy
        # to pick people who shouldn't be on one but are on the other etc. (even tho this should not be the case

        e.add_field(name="Per discord roles",
                    value='\n'.join(f'<@{userid}>' for userid in with_discord_role) or 'No Members',
                    inline=True)

        await ctx.send(embed=e)

    async def give_roles(self, db, guild, author):
        ids_to_remove, ids_to_give, not_in_db = await self.get_ids(db)

        failed_members_to_give = []

        role = guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        for user_id in ids_to_remove:
            member = guild.get_member(int(user_id))  # get member object

            if not member:
                continue

            try:
                await member.remove_roles(role,
                                          reason=f"inWar Role Removal (mass): "  # reason for audit log
                                                 f"{str(author)} ({author.id})"
                                          )
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                continue  # dont care if it failed

        for user_id in ids_to_give:
            member = guild.get_member(int(user_id))  # get member object

            if not member:
                failed_members_to_give.append(user_id)
                continue

            try:
                await member.add_roles(role,
                                       reason=f"inWar Role Given (mass): "  # reason for audit log
                                              f"{str(author)} ({author.id})"
                                       )
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                failed_members_to_give.append(member)  # for later we will let them know who failed

        if failed_members_to_give or not_in_db:

            # format the problem people into a string with 1 person per line
            not_in_db = '\n'.join(f'{ign} ({tag})'
                                  for (index, (ign, tag)) in enumerate(not_in_db)) or None
            role_add = '\n'.join(f'{user.mention}' for user in
                                 failed_members_to_give if isinstance(user, discord.Member)) or None

            if role_add:
                role_add = role_add.join(f'UserID {user_id} - NIS' for user_id in
                                         failed_members_to_give if not isinstance(user_id, discord.Member))
            else:
                role_add = '\n'.join(f'UserID {user_id} - NIS' for user_id in
                                     failed_members_to_give if not isinstance(user_id, discord.Member)) or None

            e = discord.Embed(colour=discord.Colour.red())  # we're going to send an error embed --> red colour
            e.set_author(name="Errors when dealing with the following")

            if not_in_db:
                e.add_field(name="Members not claimed:", value=not_in_db)  # only include error if there is people on it

            if role_add:
                e.add_field(name="Failed to give role:", value=role_add)  # same

            e.set_footer(text="Please check bot logs for traceback (if applicable)")  # tell them to check bot log

            return e

        return None

    async def get_ids(self, db):
        '''Takes in the client and connection as argument, returns 1 tuple of 2 lists (remove,add)'''

        # Create a cursor & define AW tag

        # Query to get details for current war
        currentWar = await self.bot.coc.clans(self.CLAN_TAG).currentwar().get(self.bot.coc_token)

        # Get the list of tags
        currentTags = [x['tag'] for x in currentWar['clan']['members']]

        # Get a list of tags from last war
        sql = 'select tag from last_war'
        dump = await db.fetch(sql)
        lastTags = [x[0] for x in dump]

        # Little bit memory waste T_T
        # Create sets from lists (so finding difference is easy)
        current = set(currentTags)
        last = set(lastTags)

        # people who were in last war but are not in current war
        remove = list_to_sql_tuple(list(last - current))

        # people who are in current war but weren't in last
        add = list_to_sql_tuple(list(current - last))

        # now that we have tags, we just need to query table tag_to_id to get corresponding Ids

        # To remove
        if remove:
            sql = f'SELECT userid FROM claims WHERE tag IN {remove};'
            dump = await db.fetch(sql)
            idsToRemove = [x[0] for x in dump]
        else:
            idsToRemove = []
        # To add

        if add:
            sql = f'SELECT userid from claims where tag in {add};'
            dump = await db.fetch(sql)
            idsToAdd = [x[0] for x in dump]

        else:
            idsToAdd = []

        # We find list of tags which are not present in our database, i.e unclaimed
        sql = 'SELECT tag FROM claims'
        dump = await db.fetch(sql)
        tagsInDb = [x[0] for x in dump]

        tagsInDb = set(tagsInDb)
        unclaimedTags = list(current - tagsInDb)

        # Get ign of people with unclaimed tags
        unclaimed = [(x['name'], tag) for x in currentWar['clan']['members'] for tag in unclaimedTags if x['tag'] == tag]

        # If there are any unclaimed accounts (We don't want to truncate the last war data)
        if unclaimed:
            pass
        else:
            # Update the table 'last_war' to hold new data
            # first delete the current values in table
            await db.execute('TRUNCATE last_war')

            # Now insert the values
            query = f"SELECT tag, userid FROM claims WHERE tag in {list_to_sql_tuple(currentTags)}"
            dump = await db.fetch(query)

            fmt = ', '.join(f"('{tag}', {userid})"
                            for (index, (tag, userid)) in enumerate(dump))
            query = f"INSERT INTO last_war (tag, userid) VALUES {fmt}"
            await db.execute(query)

        # If nothing goes wrong return lists
        return idsToRemove, idsToAdd, unclaimed

    async def give_roles_auto(self):
        guild = self.bot.get_guild(self.AW_SERVER_ID)
        author = guild.get_member(self.bot.user.id)
        e = await self.give_roles(self.bot.pool, guild, author)
        if e:
            await self.bot.get_channel(self.NERD_BOT_ZONE_ID).send(embed=e)

    @commands.command()
    async def testee(self, ctx):
        await self.give_roles_auto()
        await ctx.tick()


def setup(bot):
    bot.add_cog(WarAdmin(bot))
