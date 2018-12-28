from discord.ext import commands


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
