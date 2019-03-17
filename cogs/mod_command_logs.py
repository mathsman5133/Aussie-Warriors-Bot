import discord
from discord.ext import commands
import datetime
import traceback
import time


class CommandLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.info_channel_id = 527373033568993282
        self.bot.mod_commands = []

    async def on_command(self, ctx):
        ctx.start_time = time.perf_counter()

    async def on_command_completion(self, ctx):
        if ctx not in self.bot.mod_commands:
            return  # if its not a command decorated with @checks.mod_commands()
        if ctx.command.name == 'help':
            return  # for some reason help command gets past too so lets deal with that now

        time_now = time.perf_counter()
        time_taken = round(time_now - ctx.start_time, 4)

        e = discord.Embed(colour=discord.Colour.green())

        e.set_author(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                     icon_url=ctx.author.avatar_url)
        e.description = ':white_check_mark: Command Completed'

        e.add_field(name='Command:',
                    value=ctx.command.qualified_name)
        e.add_field(name='Location:',
                    value=f'Channel: #{ctx.channel.name} ({ctx.channel.id})')
        e.add_field(name='Time taken:',
                    value=f'**{time_taken}** seconds')
        e.timestamp = datetime.datetime.utcnow()

        await self.bot.get_channel(self.bot.info_channel_id).send(embed=e)

    async def on_command_error(self, ctx, error):
        # we dont want logs for this stuff which isnt our problem
        ignored = (commands.NoPrivateMessage, commands.DisabledCommand, commands.CheckFailure,
                   commands.CommandNotFound, commands.UserInputError, discord.Forbidden)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        time_now = time.perf_counter()
        time_taken = round(time_now - ctx.start_time, 4)

        e = discord.Embed(colour=discord.Colour.red())

        e.set_author(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                     icon_url=ctx.author.avatar_url)
        e.title = ':x: Command Error'

        exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
        e.description = f'```py\n{exc}\n```'  # format legible traceback

        e.add_field(name='Command:',
                    value=ctx.command.qualified_name)
        e.add_field(name='Location:',
                    value=f'Channel: #{ctx.channel.name} ({ctx.channel.id})')
        e.add_field(name='Time taken:',
                    value=f'**{time_taken}** seconds')
        e.timestamp = datetime.datetime.utcnow()
        e.set_footer(text="Please ping maths if the solution is not obvious or you don't understand")

        # await self.bot.get_channel(self.bot.info_channel_id).send(embed=e)
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(CommandLogging(bot))
