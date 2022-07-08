from datetime import datetime
import discord
from discord.ext import commands
from discord import SlashCommandGroup

from discord import ApplicationContext, Colour, Permissions

from core import checks
from core.base_cog import BaseCog
from core.checks import PermissionLevel


class Modmail(BaseCog):
    _id = "modmail"

    default_cache = {
        "userThreads": {

        },
        "modmailChannel": None,
        "modmailRole": None
    }
    
    _mm = SlashCommandGroup("modmail", "Manages modmail.",
                            default_member_permissions=Permissions(manage_messages=True))

    async def after_load(self):
        if self.cache["modmailChannel"]:
            self.modmail_channel = await self.guild.fetch_channel(self.cache["modmailChannel"])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild != None:
            return

        if str(message.author.id) not in self.cache["userThreads"]:
            embed = discord.Embed(
                description="If you wish to start a modmail thread please use `/start`\nFor ending an active thread please use `/end`", colour=Colour.blue())

            dm_channel = await message.author.create_dm()
            await dm_channel.send(embed=embed)

            return

        thread = await self.guild.fetch_channel(
            self.cache["userThreads"][str(message.author.id)])

        embed = discord.Embed(description=message.content,
                              timestamp=datetime.now(), colour=Colour.blue())
        embed.set_author(
            name=f"{message.author.name}#{message.author.discriminator}", icon_url=message.author.avatar)

        await thread.send(embed=embed)

    # check if the user is ending the session
    ending = False

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if self.ending:
            return

        for user in self.cache["userThreads"]:
            if self.cache["userThreads"][user] == thread.id:
                self.cache["userThreads"].pop(user)

                member = await self.guild.fetch_member(int(user))
                await member.send("Session was closed by staff.")

                break

        await self.update_db()

    @commands.Cog.listener()
    async def on_thread_remove(self, thread):
        if self.ending:
            return

        for user in self.cache["userThreads"]:
            if self.cache["userThreads"][user] == thread.id:
                self.cache["userThreads"].pop(user)

                member = await self.guild.fetch_member(int(user))
                await member.send("Session was closed by staff.")

                break

        await self.update_db()

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        if self.ending:
            return

        if after.archived == False and before.id == after.id:
            return

        for user in self.cache["userThreads"]:
            if self.cache["userThreads"][user] == before.id:
                self.cache["userThreads"].pop(user)

                member = await self.guild.fetch_member(int(user))
                await member.send("Session was closed by staff.")

                break

        await self.update_db()

    @commands.slash_command(name="reply", description="Replies to a user in a modmail thread.", default_member_permissions=Permissions(manage_messages=True))
    @checks.has_permissions(PermissionLevel.MOD)
    async def reply(self, ctx: ApplicationContext, message: discord.Option(str, "The message you wish to reply with.")):
        """
        Replies to a modmail thread.

        """
        
        if type(ctx.channel) != discord.threads.Thread or ctx.channel.parent_id != self.cache["modmailChannel"]:
            embed = discord.Embed(
            title="Error", description="You can't use this command here.", colour=Colour.red())

            await ctx.respond(embed=embed, ephemeral=True)
        
            return

        embed = discord.Embed(description=message,
                              timestamp=datetime.now(), colour=Colour.blue())
        embed.set_author(
            name=f"{ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar)

        for user in self.cache["userThreads"]:
            if self.cache["userThreads"][user] == ctx.channel.id:
                member = await self.guild.fetch_member(int(user))

                dm_channel = await member.create_dm()
                await dm_channel.send(embed=embed)

        await ctx.respond(embed=embed)

    @commands.slash_command(name="start", description="Starts a modmail session.")
    @commands.dm_only()
    async def start(self, ctx: ApplicationContext, title: discord.Option(str, "The title of the thread."),
                    reason: discord.Option(str, "The reason for starting a modmail sessions.")):
        """
        Starts a new modmail thread. DM only command.

        """

        await ctx.defer()

        if str(ctx.author.id) in self.cache["userThreads"]:
            await ctx.respond("Session already started.")

            return

        member = await self.guild.fetch_member(ctx.author.id)

        embed = discord.Embed(
            description=f"{ctx.author.mention}\nReason for mail: {reason}", timestamp=datetime.now(), colour=Colour.green())

        embed.set_author(
            name=f"{member.name}#{member.discriminator}", icon_url=member.display_avatar)
        embed.add_field(name="**Nickname**", value=member.display_name)

        value = ""
        for role in member.roles:
            value += f"{role.mention} "

        embed.add_field(name="**Roles**", value=value)

        message = await self.modmail_channel.send(embed=embed)

        thread = await message.create_thread(name=title)

        role = await self.guild._fetch_role(self.cache["modmailRole"])

        async for member in self.guild.fetch_members(limit=None):
            if role in member.roles:
                await thread.add_user(member)

        self.cache["userThreads"].update({str(ctx.author.id): thread.id})
        await self.update_db()

        await ctx.respond("Session started!")

    @commands.slash_command(name="end", description="Ends a modmail session.")
    @commands.dm_only()
    async def end(self, ctx: ApplicationContext):
        """
        Ends an active modmail thread.

        """

        if str(ctx.author.id) not in self.cache["userThreads"]:
            await ctx.respond("No session found.")

            return

        self.ending = True

        thread = await self.guild.fetch_channel(
            self.cache["userThreads"][str(ctx.author.id)])

        await thread.archive()

        self.cache["userThreads"].pop(str(ctx.author.id))
        await self.update_db()

        self.modmail_channel = await self.guild.fetch_channel(self.cache["modmailChannel"])

        await ctx.respond("Session ended!")

        self.ending = False
        
    @_mm.command(name="setup", description="Sets up the modmail.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _mm_setup(self, ctx, channel: discord.Option(discord.TextChannel, "Modmail channel."), role: discord.Option(discord.Role, "Modmail ping role.")) :
        self.cache["modmailChannel"] = channel.id
        self.cache["modmailRole"] = role.id
                        
        await self.update_db()
        
        embed = discord.Embed(
                title="Success", description=f"Modmail has been setup!", colour=Colour.green())

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Modmail(bot))
