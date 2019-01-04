from discord.ext import commands

import discord
import re


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

        return ctx.author.guild_permissions.manage_server

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

        return ctx.channel.id == channel_id

    return commands.check(pred)


def clan_status(state: list):
    async def pred(ctx):
        bot = ctx.bot
        clash_call = await bot.coc.clans(bot.AW_CLAN_TAG).currentwar.get(bot.coc_token)

        e = discord.Embed(colour=discord.Colour.red())

        if 'state' in clash_call.keys():
            if clash_call['state'] not in [state]:
                e.description = (f'AW is not currently in the required `{state}` state.\n '
                                 'Please try again later')

        elif 'reason' in clash_call.keys():
            message_string = re.sub('\d', '*', clash_call['message'])  # message may contain ip. obscure that
            e.add_field(name="Clash of Clans API Error",
                        value=f"Reason: {clash_call['reason']}\nMessage: {message_string}")

        elif not clash_call:
            e.add_field(name="Clash of Clans API Error",
                        value="The request returned `None`\nIs it an incorrect token?")

        else:
            return True  # if none of the above occur its all good

        # the help command invokes checks; we only want to send a message when they're trying to use the command
        if ctx.bot.mod_commands[-1].command.name != 'help':
            await ctx.send(embed=e)

        return False  # one of the errors has been called and the embed send. stop the command from proceeding

    return commands.check(pred)
