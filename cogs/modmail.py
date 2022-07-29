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

        if str(message.author.id) in self.cache["userThreads"] and not self.cache["userThreads"][str(message.author.id)]["active"]:
            embed = discord.Embed(
                description="If you wish to start a modmail thread please use `/start`\nFor ending an active thread please use `/end`", colour=Colour.blue())

            dm_channel = await message.author.create_dm()
            await dm_channel.send(embed=embed)

            return

        thread_info = self.cache["userThreads"][str(message.author.id)]["active"]
        thread = await self.guild.fetch_channel(
            thread_info[list(thread_info.keys())[0]]["thread"])

        embed = discord.Embed(description=message.content,
                              timestamp=datetime.now(), colour=Colour.blue())
        embed.set_author(
            name=f"{message.author.name}#{message.author.discriminator}", icon_url=message.author.avatar)

        await thread.send(embed=embed)

    # check if the user is ending the session
    ending = False

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
            thread_info = self.cache["userThreads"][user]["active"]
            if thread_info:
                if thread_info[list(thread_info.keys())[0]]["thread"] == ctx.channel.id:
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

        if str(ctx.author.id) in self.cache["userThreads"] and self.cache["userThreads"][str(ctx.author.id)]["active"]:
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

        members = [member async for member in self.guild.fetch_members(limit=None)]

        for member in members:
            if role in member.roles:
                await thread.add_user(member)

        thread_info = {
            "active": {
                f"{message.id}": {
                    "title": title,
                    "reason": reason,
                    "thread": thread.id
                }
            }
        }

        self.cache["userThreads"].update({str(ctx.author.id): thread_info})
        await self.update_db()

        await ctx.respond("Session started!")

    @commands.slash_command(name="end", description="Ends a modmail session.")
    @commands.dm_only()
    async def end(self, ctx: ApplicationContext):
        """
        Ends an active modmail thread.

        """

        if str(ctx.author.id) not in self.cache["userThreads"] or (str(ctx.author.id) in self.cache["userThreads"] and not self.cache["userThreads"][str(ctx.author.id)]["active"]):
            await ctx.respond("No session found.")

            return

        self.ending = True

        thread_info = self.cache["userThreads"][str(ctx.author.id)]["active"]

        thread = await self.guild.fetch_channel(thread_info[list(thread_info.keys())[0]]["thread"])

        await thread.archive()

        self.cache["userThreads"][str(ctx.author.id)]["acitve"] = None
        self.cache["userThreads"][str(ctx.author.id)].append(thread_info)

        await self.update_db()

        self.modmail_channel = await self.guild.fetch_channel(self.cache["modmailChannel"])

        await ctx.respond("Session ended!")

        self.ending = False

    @_mm.command(name="list", description="Lists the modmails of a member.")
    @checks.has_permissions(PermissionLevel.MOD)
    async def _mm_list(self, ctx, member: discord.Option(discord.Member, "Member you want to see the mails of.")):
        """
        Lists the modmails of a member.

        """

        if str(ctx.author.id) not in self.cache["userThreads"]:
            embed = discord.Embed(
                title="Error", description="This user does not have any modmails.", colour=Colour.red())

            ctx.respond(embed=embed)

            return

        embed = discord.Embed(
            title=f"{member.name}'s modmails", colour=Colour.blue())

        mails = self.cache["userThreads"][str(member.id)]

        for mail in mails:
            if mails[mail]:
                if mail == "active":
                    info = mails[mail][list(mails[mail].keys())[0]]
                    mail = list(mails[mail].keys())[0]
                embed.add_field(
                    name=mail, value=f"**Title:** {info['title']}\n**Reason:** {info['reason']}\n**Thread ID:** {info['thread']}")

        await ctx.respond(embed=embed)

    @_mm.command(name="setup", description="Sets up the modmail.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _mm_setup(self, ctx, channel: discord.Option(discord.TextChannel, "Modmail channel."), role: discord.Option(discord.Role, "Modmail ping role.")):
        """
        Sets up the modmail.

        """

        self.cache["modmailChannel"] = channel.id
        self.cache["modmailRole"] = role.id

        await self.update_db()

        embed = discord.Embed(
            title="Success", description=f"Modmail has been setup!", colour=Colour.green())

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Modmail(bot))
