import discord
from discord.ext import commands
import datetime
import traceback

class Command_Logging:
    def __init__(self, bot):
        self.bot = bot
        self.bot.info_channel_id = 527373033568993282
        self.bot.mod_commands = []

    async def on_command(self, ctx):
        ctx.start_time = datetime.datetime.utcnow()

    async def on_command_completion(self, ctx):
        if ctx not in self.bot.mod_commands:
            return

        time_taken = datetime.datetime.utcnow() - ctx.start_time
        time_taken_readable = (f'{time_taken.microseconds/1000000} sec'
                               if time_taken.microseconds > 500000 else f'{time_taken.microseconds/1000}ms')

        e = discord.Embed(colour=discord.Colour.green())

        e.set_author(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                     icon_url=ctx.author.avatar_url)
        e.description = ':white_check_mark: Command Completed'

        e.add_field(name='Command:',
                    value=ctx.command.qualified_name)
        e.add_field(name='Location:',
                    value=f'Channel: #{ctx.channel.name} ({ctx.channel.id})')
        e.add_field(name='Time taken:',
                    value=time_taken_readable)
        e.timestamp = datetime.datetime.utcnow()

        await self.bot.get_channel(self.bot.info_channel_id).send(embed=e)

    async def on_command_error(self, ctx, error):
        # we dont want logs for this stuff which isnt our problem
        ignored = (commands.NoPrivateMessage, commands.DisabledCommand, commands.CheckFailure,
                   commands.CommandNotFound, commands.UserInputError, discord.Forbidden)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        time_taken = datetime.datetime.utcnow() - ctx.start_time
        time_taken_readable = (f'{time_taken.microseconds/1000000} sec'
                               if time_taken.microseconds > 500000 else f'{time_taken.microseconds/1000}ms')

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
                    value=time_taken_readable)
        e.timestamp = datetime.datetime.utcnow()
        e.set_footer(text="Please ping maths if the solution is not obvious or you don't understand")

        await self.bot.get_channel(self.bot.info_channel_id).send(embed=e)


def setup(bot):
    bot.add_cog(Command_Logging(bot))
