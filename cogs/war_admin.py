import discord
from discord.ext import commands


class War_Admin:

    def __init__(self, bot):
        self.bot = bot
        self.bot.IN_WAR_ROLE_ID = 508537319150845992

    async def get_ids(self, ctx):
        '''Takes in the client and connection as arguement, returns 1 tuple of 2 lists (remove,add)'''

        try:

            # Create a cursor & define AW tag
            clanTag = '#P0LYJC8C'

            # Query to get details for current war
            currentWar = await self.bot.coc.clans(clanTag).currentwar().get(self.bot.coc_token)

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
            sql = f'select ID from tag_to_id where Tag in {remove}'
            dump = await ctx.db.fetch(sql)
            idsToRemove = [x[0] for x in dump]

            # To add
            sql = f'select ID from tag_to_id where Tag in {add}'
            dump = ctx.db.fetch(sql)
            idsToAdd = [x[0] for x in dump]

            # Update the table 'last_war' to hold new data

            # first delete the current values in table
            ctx.db.execute('TRUNCATE last_war')

            # Now insert the values
            for tag in currentTags:
                sql = f'''INSERT INTO last_war(Tag) VALUES('{tag}')'''
                ctx.db.execute(sql)

        # In case anything breaks
        except Exception as error:
            raise commands.CommandError(ctx, error)

        # If nothing goes wrong return lists
        return idsToRemove, idsToAdd, []

    @commands.group(name="warrole")
    @commands.has_permissions(manage_roles=True)
    async def war_role(self, ctx):
        """[Group] Manage the inWar role when a (league) war is in progress"""
        pass  # to prevent from throwing error

    @war_role.command(aliases=['all', 'init'])
    async def giveall(self, ctx):
        """
        Initialise war in database, giving the `inWar` role to all currently in war with claimed accounts.

        Requires `Manage_Roles` permission
        """

        ids_to_remove, ids_to_give, not_in_db = await self.get_ids(ctx)

        failed_members_to_give = []
        failed_members_to_remove = []

        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        for user_id in ids_to_remove:
            member = ctx.guild.get_member(user_id)  # get member object
            try:
                await member.remove_roles(role,
                                          reason=f"inWar Role Removal (mass): "  # reason for audit log
                                                 f"{ctx.author.display_name}#{ctx.author.discriminator}"
                                                 f" ({ctx.author.id})"
                                          )
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                failed_members_to_remove.append(member)  # for later we will let them know who failed

        for user_id in ids_to_give:
            member = ctx.guild.get_member(user_id)  # get member object
            try:
                await member.give_roles(role,
                                        reason=f"inWar Role Given (mass): "  # reason for audit log
                                               f"{ctx.author.display_name}#{ctx.author.discriminator} ({ctx.author.id})"
                                        )
            except (discord.Forbidden, discord.HTTPException):  # possible (discord) errors
                failed_members_to_give.append(member)  # for later we will let them know who failed

        if failed_members_to_remove or failed_members_to_give or not_in_db:

            # format the problem people into a string with 1 person per line
            not_in_db = '\n'.join(f'{ign} ({tag})' for (index, (ign, tag)) in enumerate(not_in_db)) or None
            role_add = '\n'.join(f'{user.mention}' for user in failed_members_to_give) or None
            role_remove = '\n'.join(f'{user.mention}' for user in failed_members_to_remove) or None

            e = discord.Embed(colour=discord.Colour.red())  # we're going to send an error embed --> red colour
            e.set_author(name="Errors when dealing with the following")

            if not_in_db:
                e.add_field(name="Members not claimed:", value=not_in_db)  # only include error if there is people on it

            if role_add:
                e.add_field(name="Failed to give role:", value=role_add)  # same

            if role_remove:
                e.add_field(name="Failed to remove role:", value=role_remove)   # same

            e.set_footer(text="Please check bot mod logs for traceback (if applicable)")  # tell them to check bot log

            return await ctx.send(embed=e)

        await ctx.message.add_reaction('\u2705')  # green tick reaction --> all ok, all roles added

    @war_role.command()
    async def add(self, ctx, tag_ign: str, member: discord.Member=None):
        """
        Manually add someone kn war to the `inWar` role.

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
        await ctx.db.execute(query, tag_ign)

        role = ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID)  # get role object

        try:
            await member.give_roles(role,
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
            mentions = ctx.author

        query = "SELECT tag FROM tag_and_id WHERE ID in $1"
        tags = await ctx.db.fetch(query, [n.id for n in mentions])

        query = "DELETE FROM last_war WHERE Tag in $1"
        await ctx.db.execute(query, [n[0] for n in tags])

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
    async def list(self, ctx):
        """
        List everyone with the `inWar` role, both in discord and in the database.
        Helpful to find discrepencies and rectify the issue

        Requires `manage_roles` permission
        """
        query = "SELECT id FROM last_war"
        dump = set(await ctx.db.fetch(query))

        # sort list by user ids (a big int) ascending, so that both are sorted same way,
        # meaning easy to pick inconsistencies between them (shouldnt be to start with)

        with_db_role = [n[0] for n in dump].sort()
        with_discord_role = [n.id for n in ctx.guild.get_role(self.bot.IN_WAR_ROLE_ID).members].sort()

        e = discord.Embed(colour=discord.Colour.blue())  # blue --> nothing changed

        e.add_field(name="Members with inWar role (per db)",
                    value='\n'.join(f'<@{userid}>' for userid in with_db_role) or 'No Members')

        # the reason I used <@id> over user.mention is that it is nice to have roles sorted by something so it is easy
        # to pick people who shouldn't be on one but are on the other etc. (even tho this should not be the case

        e.add_field(name="Members with inWar role (per discord roles)",
                    value='\n'.join(f'<@{userid}>' for userid in with_discord_role) or 'No Members',
                    inline=True)

        await ctx.send(embed=e)

def setup(bot):
    bot.add_cog(War_Admin(bot))
