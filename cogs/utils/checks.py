from discord.ext import commands

import re


class COCError(commands.CheckFailure):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def is_owner():
    async def pred(ctx):
        if ctx.author.id in ctx.bot.owners:
            return True

        return False

    return commands.check(pred)


def manage_roles():
    async def pred(ctx):
        if is_owner():
            return True

        if ctx.guild is None:
            return False

        return ctx.author.guild_permissions.manage_roles

    return commands.check(pred)


def manage_server():
    async def pred(ctx):
        if is_owner():
            return True

        if not ctx.guild:
            return False

        return ctx.author.guild_permissions.manage_guild

    return commands.check(pred)


def manage_channels():
    async def pred(ctx):
        if is_owner():
            return True

        if not ctx.guild:
            return False

        return ctx.author.guild_permissions.manage_channels

    return commands.check(pred)


def mod_commands():
    def pred(ctx):
        ctx.bot.mod_commands.append(ctx)
        return True
    return commands.check(pred)


def restricted_channel(channel_id):
    def pred(ctx):
        if is_owner():
            return True

        if channel_id == ctx.channel.id:
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
        clash_call = await bot.coc.clans(bot.AW_CLAN_TAG).currentwar.get(bot.coc_token)

        msg = ''

        if 'state' in clash_call.keys():
            if clash_call['state'] not in state:
                msg += (f'AW is not currently in the required `{state}` state.\n '
                        'Please try again later')
            else:
                return True  # if none of the above occur its all good

        elif 'reason' in clash_call.keys():
            message_string = re.sub('\d', '\\*', clash_call['message'])  # message may contain ip. obscure that
            msg += f"Reason: {clash_call['reason']}\nMessage: {message_string}"

        elif not clash_call:
            msg += "The request returned `None`\nIs it an incorrect token?"

        else:
            return True  # if none of the above occur its all good

        raise COCError(msg)

    return commands.check(pred)
