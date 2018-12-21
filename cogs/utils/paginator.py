import discord
import asyncio


class CannotPaginate(Exception):
    pass


class MsgPag:
    'Implements a paginator that queries the user for the\n    pagination interface.\n    Pages are 1-index based, not 0-index based.\n    If the user does not reply within 2 minutes, the pagination\n    interface exits automatically.\n    '

    def __init__(self, ctx, *, message, entries, per_page):
        self.ctx = ctx
        self.bot = ctx.bot
        self.channel = ctx.channel
        self.entries = entries
        self.message = ctx.message
        self.author = message.author
        self.per_page = per_page
        (pages, left_over) = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self.maximum_pages = pages
        self.embed = discord.Embed()
        self.paginating = len(entries) > per_page
        self.reaction_emojis = [('⏮', self.first_page), ('◀', self.previous_page), ('▶', self.next_page),
                                ('⏭', self.last_page), ('🔢', self.numbered_page), ('⏹', self.stop_pages),
                                ('ℹ', self.show_help)]
        print(self.message)
        guild = self.message.guild
        if guild is not None:
            self.permissions = self.message.channel.permissions_for(guild.me)
        else:
            self.permissions = self.message.channel.permissions_for(self.bot.user)
        if (not self.permissions.embed_links):
            raise CannotPaginate('Bot does not have embed links permission.')

    def get_page(self, page):
        base = (page - 1) * self.per_page
        return self.entries[base:base + self.per_page]
    async def show_page(self, page, *, first=False):
        self.current_page = page
        entries = self.get_page(page)
        p = '```'
        for t in entries:
            p += (t)
        print(p)
        self.embed.set_footer(text='Page %s/%s (%s entries)' % (page, self.maximum_pages, len(self.entries)))
        if (not self.paginating):
            self.embed.description = '\n'.join(p)
            return await self.message.channel.send(content=p + '```')
        if (not first):
            self.embed.description = '\n'.join(p)
            await self.message.edit(content=p + '\nPage %s/%s (%s entries) ```'%(page, self.maximum_pages, len(self.entries)))
            return
        if (not self.permissions.add_reactions):
            raise CannotPaginate('Bot does not have add reactions permission.')
        if (not self.permissions.read_message_history):
            raise CannotPaginate('Bot does not have Read Message History permission.')
        #p.append('```')
        p += ('\nPage %s/%s (%s entries) ```\nConfused? React with ℹ for more info.'%(page, self.maximum_pages, len(self.entries)))
        self.embed.description = '\n'.join(p)
        self.message = await self.ctx.send(content = p)
        for (reaction, _) in self.reaction_emojis:
            if (self.maximum_pages == 2) and (reaction in ('⏭', '⏮')):
                continue
            try:
                await self.message.add_reaction(reaction)
            except discord.NotFound:
                return

    async def checked_show_page(self, page):
        if (page != 0) and (page <= self.maximum_pages):  # verify we can actually use the pagination session
            await self.show_page(page)

    async def first_page(self):
        'goes to the first page'
        await self.show_page(1)

    async def last_page(self):
        'goes to the last page'
        await self.show_page(self.maximum_pages)

    async def next_page(self):
        'goes to the next page'
        await self.checked_show_page(self.current_page + 1)

# no |<< or >>| buttons if we only have two pages

    async def previous_page(self):  # we can't forbid it if someone ends up using it but remove
        'goes to the previous page'  # it from the default set
        await self.checked_show_page(self.current_page - 1)

    async def show_current_page(self):
        if self.paginating:
            await self.show_page(self.current_page)  # If the message isn't found, we don't care about clearing anything

    async def numbered_page(self):
        'lets you type a page number to go to'
        to_delete = []
        to_delete.append(await self.message.channel.send('What page do you want to go to?'))
        msg = await self.bot.wait_for('message', check=(lambda m: m.content.isdigit()), timeout=30.0)
        if msg is not None:
            page = int(msg.content)
            to_delete.append(msg)
            if (page != 0) and (page <= self.maximum_pages):
                await self.show_page(page)
            else:
                to_delete.append(await self.ctx.send('Invalid page given. (%s/%s)' % (page, self.maximum_pages)))
                await asyncio.sleep(5)
        else:
            to_delete.append(await self.message.channel.send('Took too long.'))
            await asyncio.sleep(5)
        try:
            await self.channel.delete_messages(to_delete)
        except Exception:
            pass

    async def show_help(self):
        'shows this message'
        e = discord.Embed()
        messages = ['Welcome to the interactive paginator!\n']
        messages.append(
            'This interactively allows you to see pages of text by navigating with reactions. They are as follows:\n')
        for (emoji, func) in self.reaction_emojis:
            messages.append('%s %s' % (emoji, func.__doc__))
        e.description = '\n'.join(messages)
        e.colour = 7572439
        e.set_footer(text='We were on page %s before this message.' % self.current_page)
        await self.message.edit(embed=e)

        async def go_back_to_current_page():
            await asyncio.sleep(60.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())

    async def stop_pages(self):
        'Moves to next group of pages: offence, defence, or a new war/player'
        await self.message.delete()
        if self.to_del:
            await self.channel.delete_messages(self.to_del)
        self.paginating = False

    def react_check(self, reaction, user):
        if (user is None) or (user.id != self.author.id):
            return False
        for (emoji, func) in self.reaction_emojis:
            if reaction.emoji == emoji:
                self.match = func
                return True
        return False

    async def paginate(self, start_page=1, to_del=None):
        'Actually paginate the entries and run the interactive loop if necessary.'
        self.to_del = to_del
        print(to_del)
        await self.show_page(start_page, first=True)
        while self.paginating:
            try:
                react, user = await self.bot.wait_for('reaction_add', check=self.react_check, timeout=120.0)
            except asyncio.TimeoutError:
                self.paginating = False
                try:
                    await self.message.clear_reactions()
                except:
                    pass
                finally:
                    break
            if react is None:
                self.paginating = False
                try:  # blurple
                    await self.message.clear_reactions()
                except:
                    pass
                finally:
                    break
            try:
                await self.message.remove_reaction(react, user)
            except:
                pass
            await self.match()

class EmbedPag:
    'Implements a paginator that queries the user for the\n    pagination interface.\n    Pages are 1-index based, not 0-index based.\n    If the user does not reply within 2 minutes, the pagination\n    interface exits automatically.\n    '

    def __init__(self, ctx, *, message, entries, per_page):
        self.ctx = ctx
        self.bot = ctx.bot
        self.channel = ctx.channel
        self.entries = entries
        self.message = ctx.message
        self.author = message.author
        self.per_page = per_page
        (pages, left_over) = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self.maximum_pages = pages
        self.embed = discord.Embed()
        self.paginating = len(entries) > per_page
        self.reaction_emojis = [('⏮', self.first_page), ('◀', self.previous_page), ('▶', self.next_page),
                                ('⏭', self.last_page), ('🔢', self.numbered_page), ('⏹', self.stop_pages),
                                ('ℹ', self.show_help)]
        print(self.message)
        guild = self.message.guild
        if guild is not None:
            self.permissions = self.message.channel.permissions_for(guild.me)
        else:
            self.permissions = self.message.channel.permissions_for(self.bot.user)
        if (not self.permissions.embed_links):
            raise CannotPaginate('Bot does not have embed links permission.')

    def get_page(self, page):
        base = (page - 1) * self.per_page
        return self.entries[base:base + self.per_page]

    async def show_page(self, page, *, first=False):
        self.current_page = page
        entries = self.get_page(page)
        p = []
        for t in entries:
            p.append(f'{t} \n')
        self.embed.set_footer(text=f'Page {page}/{self.maximum_pages} ({len(self.entries)} entries)')
        if (not self.paginating):
            self.embed.set_author(name="Average Donation List - Warnings only")
            self.embed.description = '\n'.join(p)
            self.embed.set_footer(text="Type `don` to find total donations of your accounts")
            return await self.message.channel.send(embed=self.embed)
        if (not first):
            self.embed.description = '\n'.join(p)
            await self.message.edit(embed=self.embed)
            return
        if (not self.permissions.add_reactions):
            raise CannotPaginate('Bot does not have add reactions permission.')
        if (not self.permissions.read_message_history):
            raise CannotPaginate('Bot does not have Read Message History permission.')
        p.append('')
        p.append('Confused? React with ℹ for more info.')
        self.embed.description = '\n'.join(p)
        self.message = await self.message.channel.send(embed=self.embed)
        for (reaction, _) in self.reaction_emojis:
            if (self.maximum_pages == 2) and (reaction in ('⏭', '⏮')):
                continue
            try:
                await self.message.add_reaction(reaction)
            except discord.NotFound:
                return

    async def checked_show_page(self, page):
        if (page != 0) and (page <= self.maximum_pages):  # verify we can actually use the pagination session
            await self.show_page(page)

    async def first_page(self):
        'goes to the first page'
        await self.show_page(1)

    async def last_page(self):
        'goes to the last page'
        await self.show_page(self.maximum_pages)

    async def next_page(self):
        'goes to the next page'
        await self.checked_show_page(self.current_page + 1)

    # no |<< or >>| buttons if we only have two pages

    async def previous_page(self):  # we can't forbid it if someone ends up using it but remove
        'goes to the previous page'  # it from the default set
        await self.checked_show_page(self.current_page - 1)

    async def show_current_page(self):
        if self.paginating:
            await self.show_page(self.current_page)  # If the message isn't found, we don't care about clearing anything

    async def numbered_page(self):
        'lets you type a page number to go to'
        to_delete = []
        to_delete.append(await self.message.channel.send('What page do you want to go to?'))
        msg = await self.bot.wait_for('message', check=(lambda m: m.content.isdigit()), timeout=30.0)
        if msg is not None:
            page = int(msg.content)
            to_delete.append(msg)
            if (page != 0) and (page <= self.maximum_pages):
                await self.show_page(page)
            else:
                to_delete.append(await self.message.channel.send('Invalid page given. (%s/%s)' % (page, self.maximum_pages)))
                await asyncio.sleep(5)
        else:
            to_delete.append(await self.message.channel.send('Took too long.'))
            await asyncio.sleep(5)
        try:
            await self.channel.delete_messages(to_delete)
        except Exception:
            pass

    async def show_help(self):
        'shows this message'
        e = discord.Embed()
        messages = ['Welcome to the interactive paginator!\n']
        messages.append(
            'This interactively allows you to see pages of text by navigating with reactions. They are as follows:\n')
        for (emoji, func) in self.reaction_emojis:
            messages.append('%s %s' % (emoji, func.__doc__))
        e.description = '\n'.join(messages)
        e.colour = 7572439
        e.set_footer(text='We were on page %s before this message.' % self.current_page)
        await self.message.edit(embed=e)

        async def go_back_to_current_page():
            await asyncio.sleep(60.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())

    async def stop_pages(self):
        'Moves to next group of pages: offence, defence, or a new war/player'
        await self.message.delete()
        self.paginating = False

    def react_check(self, reaction, user):
        if (user is None) or (user.id != self.author.id):
            return False
        for (emoji, func) in self.reaction_emojis:
            if reaction.emoji == emoji:
                self.match = func
                return True
        return False

    async def paginate(self, start_page=1):
        'Actually paginate the entries and run the interactive loop if necessary.'
        await self.show_page(start_page, first=True)
        while self.paginating:
            try:
                react, user = await self.bot.wait_for('reaction_add', check=self.react_check, timeout=120.0)
            except asyncio.TimeoutError:
                self.paginating = False
                try:
                    await self.message.clear_reactions()
                except:
                    pass
                finally:
                    break
            if react is None:
                self.paginating = False
                try:  # blurple
                    await self.message.clear_reactions()
                except:
                    pass
                finally:
                    break
            try:
                await self.message.remove_reaction(react, user)
            except:
                pass
            await self.match()


