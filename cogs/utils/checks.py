from discord.ext import commands

import re
import coc


class COCError(commands.CheckFailure):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def is_owner_pred(ctx):
    if ctx.author.id in ctx.bot.owners:
        return True

    return False


def is_owner():
    def pred(ctx):
        return is_owner_pred(ctx)

    return commands.check(pred)


def manage_roles():
    def pred(ctx):
        if is_owner_pred(ctx):
            return True

        if ctx.guild is None:
            return False

        return ctx.channel.permissions_for(ctx.author).manage_roles

    return commands.check(pred)


def manage_server():
    def pred(ctx):
        if is_owner_pred(ctx):
            return True

        if not ctx.guild:
            return False

        return ctx.channel.permissions_for(ctx.author).manage_guild

    return commands.check(pred)


def manage_channels():
    def pred(ctx):
        if is_owner_pred(ctx):
            return True

        if not ctx.guild:
            return False

        return ctx.channel.permissions_for(ctx.author).manage_channels

    return commands.check(pred)

def is_leader():
    leader_role = 390067025395056650
    def pred(ctx):
        if is_owner_pred(ctx):
            return True

        if leader_role in [n.id for n in ctx.author.roles]:
            return True
        return False
    return commands.check(pred)

def mod_commands():
    def pred(ctx):
        ctx.bot.mod_commands.append(ctx)
        return True
    return commands.check(pred)


def restricted_channel(*channel_ids):
    def pred(ctx):
        if is_owner_pred(ctx):
            return True

        if ctx.channel.id in channel_ids:
            return True

        return False

    return commands.check(pred)


def clan_status(state: list):
    async def pred(ctx):

        # This may be a little confusing so let me explain it. It will search COCAPI to ensure clan is in required state
        # If not, the error msg is saying so. Else it goes through a couple other checks to make sure IP etc are working
        # It then sends to COCERROR so we can add both our own message and call it when we want to (for commands)
        # and let it fall silently when we dont want it (help command)
        # See the error handlers in `war_admin.py` and `war_stats.py` for more info
        # Of course if it is in the correct war state it will return True and the command will proceed

        bot = ctx.bot
        try:
            clash_call = await bot.coc.get_current_war(bot.AW_CLAN_TAG)
        except (coc.NotFound, coc.Forbidden, coc.InvalidArgument) as e:
            raise COCError(e.message)

        if clash_call.state not in state:
            raise COCError(f'AW is not currently in the required `{state}` state.\n '
                            'Please try again later')

        return True  # if none of the above occur its all good

    return commands.check(pred)
