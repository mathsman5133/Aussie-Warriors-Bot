import discord
from discord.ext import commands
import asyncpg.exceptions as pgexceptions

from cogs.utils import checks, db


class LastWarTable(db.Table, table_name='last_war'):
    tag = db.Column(db.String())


class TagIDTable(db.Table, table_name='tag_to_id'):
    id = db.Column(db.Integer(big=True))
    tag = db.Column(db.String())

class RolesCTX(object):
    pass


class WarAdmin:
    def __init__(self, bot):
        self.bot = bot
        self.bot.IN_WAR_ROLE_ID = 526702907127627793
        self.AW_SERVER_ID = 352298238180851712
        self.CLAN_TAG = '#P0LYJC8C'

    async def __error(self, ctx, error):
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
                        value=error.msg )
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
        embed = await self.give_roles(ctx)
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.message.add_reaction('\u2705')  # green tick emoji --> success

    @war_role.command()
    async def add(self, ctx, tag_ign: str, member: discord.Member=None):
        """
        Manually add someone in war to the `inWar` role.

        The preferred method is `?war role init`
        However, pass in a player tag or IGN, and either a mention, user#discrim or id.
        If no member is passed it will assign the role to yourself

        This also adds the member to the database *for this war only*, so please use this over manually giving roles
        """
        if not member:
            member = ctx.author

        if not tag_ign.startswith('#'):
            aw_members = await self.bot.coc.clans('#P0LYJC8C').members.get(self.bot.coc_token)
            for awm in aw_members['items']:
                if awm['name'] == tag_ign:
                    tag_ign = awm['tag']
                    break
            else:
                raise commands.BadArgument(f'IGN {tag_ign} not found in AW.')

        query = f"INSERT INTO last_war VALUES ($1)"
        try:
            await ctx.db.execute(query, tag_ign)
        except pgexceptions.UniqueViolationError:
            pass

        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        try:
            await member.add_roles(role,
                                   reason=f"inWar Role Given: "  # reason for audit log
                                          f"{ctx.author.display_name}#{ctx.author.discriminator} ({ctx.author.id})"
                                   )
        except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
            e = discord.Embed(colour=discord.Colour.red())  # red --> error
            e.description = 'Could not give role. Is their roles higher than mine? Else check bot-log'
            return await ctx.send(embed=e)

        await ctx.message.add_reaction('\u2705')  # green tick reaction --> all ok, all roles added

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

        ids = ()
        ids = ids + tuple(str(n.id) for n in mentions)
        if len(ids) == 1:
            ids = ids + ('123456789',)

        query = f"SELECT tag FROM tag_to_id WHERE id in {ids};"

        tags = await ctx.db.execute(query)
        tags = tuple(n[0] for n in tags)

        query = f"DELETE FROM last_war WHERE Tag in {tags};"
        await ctx.db.execute(query)

        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        try:
            for mention in mentions:
                await mention.remove_roles(role,
                                           reason=f"inWar Role Removed: "  # reason for audit log
                                                  f"{ctx.author.display_name}#{ctx.author.discriminator} "
                                                  f"({ctx.author.id})"
                                           )
        except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
            e = discord.Embed(colour=discord.Colour.red())  # red --> error
            e.description = 'Could not give role. Is their roles higher than mine? Else check bot-log'
            return await ctx.send(embed=e)

        await ctx.message.add_reaction('\u2705')  # green tick reaction --> all ok, all roles added

    @war_role.command()
    async def show(self, ctx):
        """
        List everyone with the `inWar` role, both in discord and in the database.
        Helpful to find discrepencies and rectify the issue

        Requires `manage_roles` permission
        """
        query = "SELECT tag FROM last_war"
        tags = await ctx.db.fetch(query)

        tags = tuple(n[0] for n in tags)

        sql = f'select ID from tag_to_id where Tag in {tags};'

        dump = set(await ctx.db.fetch(sql))

        with_db_role = [n[0] for n in dump]
        with_discord_role = [n.id for n in ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID).members]

        # sort list by user ids (a big int) ascending, so that both are sorted same way,
        # meaning easy to pick inconsistencies between them (shouldnt be to start with)
        with_db_role.sort()
        with_discord_role.sort()

        e = discord.Embed(colour=discord.Colour.blue())  # blue --> nothing changed
        e.set_author(name="Members with inWar role ")
        e.add_field(name="Per DB",
                    value='\n'.join(f'<@{userid}>' for userid in with_db_role) or 'No Members'
                    )

        # the reason I used <@id> over user.mention is that it is nice to have roles sorted by something so it is easy
        # to pick people who shouldn't be on one but are on the other etc. (even tho this should not be the case

        e.add_field(name="Per discord roles",
                    value='\n'.join(f'<@{userid}>' for userid in with_discord_role) or 'No Members',
                    inline=True)

        await ctx.send(embed=e)

    async def give_roles(self, ctx):
        ids_to_remove, ids_to_give, not_in_db = await self.get_ids(ctx)

        failed_members_to_give = []
        failed_members_to_remove = []

        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        for user_id in ids_to_remove:
            member = ctx.guild.get_member(int(user_id))  # get member object

            if not member:
                failed_members_to_remove.append(user_id)
                continue

            try:
                await member.remove_roles(role,
                                          reason=f"inWar Role Removal (mass): "  # reason for audit log
                                                 f"{ctx.author.display_name}#{ctx.author.discriminator}"
                                                 f" ({ctx.author.id})"
                                          )
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                failed_members_to_remove.append(member)  # for later we will let them know who failed

        for user_id in ids_to_give:
            member = ctx.guild.get_member(int(user_id))  # get member object

            if not member:
                failed_members_to_give.append(user_id)
                continue

            try:
                await member.add_roles(role,
                                       reason=f"inWar Role Given (mass): "  # reason for audit log
                                              f"{ctx.author.display_name}#{ctx.author.discriminator} ({ctx.author.id})"
                                       )
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                failed_members_to_give.append(member)  # for later we will let them know who failed

        if failed_members_to_remove or failed_members_to_give or not_in_db:

            # format the problem people into a string with 1 person per line
            not_in_db = '\n'.join(f'{ign} ({tag})'
                                  for (index, (ign, tag)) in enumerate(not_in_db)) or None
            role_add = '\n'.join(f'{user.mention}' for user in
                                 failed_members_to_give if isinstance(user, discord.Member)) or None
            role_remove = '\n'.join(f'{user.mention}' for user in
                                    failed_members_to_remove if isinstance(user, discord.Member)) or None

            if role_add:
                role_add = role_add.join(f'UserID {user_id} - NIS' for user_id in
                                         failed_members_to_give if not isinstance(user_id, discord.Member))
            else:
                role_add = '\n'.join(f'UserID {user_id} - NIS' for user_id in
                                     failed_members_to_give if not isinstance(user_id, discord.Member)) or None

            if role_remove:
                role_remove = role_remove.join(f'UserID {user_id} - NIS' for user_id in
                                               failed_members_to_remove if not isinstance(user_id, discord.Member))
            else:
                role_remove = '\n'.join(f'UserID {user_id} - NIS' for user_id in
                                        failed_members_to_remove if not isinstance(user_id, discord.Member)) or None

            e = discord.Embed(colour=discord.Colour.red())  # we're going to send an error embed --> red colour
            e.set_author(name="Errors when dealing with the following")

            if not_in_db:
                e.add_field(name="Members not claimed:", value=not_in_db)  # only include error if there is people on it

            if role_add:
                e.add_field(name="Failed to give role:", value=role_add)  # same

            if role_remove:
                e.add_field(name="Failed to remove role:", value=role_remove)  # same

            e.set_footer(text="Please check bot logs for traceback (if applicable)")  # tell them to check bot log

            return e

        return None

    async def get_ids(self, ctx):
        '''Takes in the client and connection as argument, returns 1 tuple of 2 lists (remove,add)'''

        # Create a cursor & define AW tag

        # Query to get details for current war
        currentWar = await self.bot.coc.clans(self.CLAN_TAG).currentwar().get(self.bot.coc_token)

        # Get the list of tags
        currentTags = [x['tag'] for x in currentWar['clan']['members']]

        # Get a list of tags from last war
        sql = 'select * from last_war'
        dump = await ctx.db.fetch(sql)
        lastTags = [x[0] for x in dump]

        # Little bit memory waste T_T
        # Create sets from lists (so finding difference is easy)
        current = set(currentTags)
        last = set(lastTags)

        # people who were in last war but are not in current war
        remove = tuple(last - current)

        # people who are in current war but weren't in last
        add = tuple(current - last)

        # now that we have tags, we just need to query table tag_to_id to get corresponding Ids

        # To remove
        if remove:
            sql = f'select ID from tag_to_id where Tag in {remove};'
            dump = await ctx.db.fetch(sql)
            idsToRemove = [x[0] for x in dump]
        else:
            idsToRemove = []
        # To add

        if add:
            sql = f'select ID from tag_to_id where Tag in {add};'
            dump = await ctx.db.fetch(sql)
            idsToAdd = [x[0] for x in dump]

        else:
            idsToAdd = []

        # We find list of tags which are not present in our database, i.e unclaimed
        sql = 'select Tag from tag_to_id'
        dump = await ctx.db.fetch(sql)
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
            await ctx.db.execute('TRUNCATE last_war')

            # Now insert the values
            for tag in currentTags:
                sql = f'''INSERT INTO last_war(Tag) VALUES('{tag}')'''
                await ctx.db.execute(sql)

        # In case anything breaks
        # except Exception as error:
        #     raise commands.CommandError(ctx.message.content, error)

        # If nothing goes wrong return lists
        return idsToRemove, idsToAdd, unclaimed

    async def give_roles_auto(self):
        ctx = RolesCTX()
        ctx.db = self.bot.pool
        ctx.guild = self.bot.get_guild(self.AW_SERVER_ID)
        ctx.author = ctx.guild.get_member(self.bot.user.id)
        await self.give_roles(ctx=ctx)



def setup(bot):
    bot.add_cog(WarAdmin(bot))
