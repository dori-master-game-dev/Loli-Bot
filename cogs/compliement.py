import discord
from discord.ext import commands
from discord.ui import Select, View, Button

from discord import ApplicationContext, Colour, Interaction, Permissions, SlashCommandGroup

from discord.ext.commands import BucketType

from core import checks
from core.base_cog import BaseCog
from core.checks import PermissionLevel

import re

from datetime import datetime

import random


class Compliment(BaseCog):
    _id = "compliment"

    default_cache = {
        "userSubmissions": {

        },
        "userCompliments": {

        },
        "complimentsChannel": None,
        "checkChannel": None,
        "cooldown": 1
    }

    _cm = SlashCommandGroup("compliment", "Manages compliment commands.")

    async def after_load(self):
        if self.cache["checkChannel"]:
            self.check_channel = await self.guild.fetch_channel(self.cache["checkChannel"])

        if self.cache["complimentsChannel"]:
            self.compliments_channel = await self.guild.fetch_channel(self.cache["complimentsChannel"])

        for message_id in self.cache["userSubmissions"]:
            message = await self.check_channel.fetch_message(int(message_id))

            await self.add_buttons(message)

        self.bot.loop.call_later(self.cache["cooldown"] * 60, self.compliment_dori)

    def compliment_dori(self):
        """
        Calls asyncronous function.
        
        """

        self.bot.loop.create_task(self._compliment_dori())
        self.bot.loop.call_later(self.cache["cooldown"] * 60, self.compliment_dori)

    async def _compliment_dori(self):
        """
        Compliments Dori.
        
        """

        if len(self.cache["userCompliments"].keys()) == 0:
            return

        user_compliments = random.choice(list(self.cache["userCompliments"].values()))
        compliment = random.choice(user_compliments)

        await self.compliments_channel.send(compliment)
    
    async def add_buttons(self, message: discord.Message):
        """
        Adds buttons for compliments checking.

        """

        submission_info = self.cache["userSubmissions"][str(message.id)]

        async def _accept_callback(interaction: Interaction):
            if str(submission_info["user"]) not in self.cache["userCompliments"]:
                self.cache["userCompliments"].update({str(submission_info["user"]): []})

            self.cache["userCompliments"][str(submission_info["user"])].append(submission_info["compliment"])

            embed = discord.Embed(
                title="Accepted", description=f"Submission `{submission_info['compliment']}` has been accepted", colour=Colour.green())

            await message.edit(embed=embed, view=None)

            try:
                user = await self.guild.fetch_member(str(submission_info["user"]))

                dm_channel = await user.create_dm()
                await dm_channel.send(embed=embed)
            except:
                pass

            self.cache["userSubmissions"].pop(str(message.id))

            await self.update_db()

        async def _deny_callback(interaction: Interaction):
            embed = discord.Embed(
                title="Denied", description=f"Submission `{submission_info['compliment']}` has been denied", colour=Colour.red())

            await message.edit(embed=embed, view=None)

            try:
                user = await self.guild.fetch_member(str(submission_info["user"]))

                dm_channel = await user.create_dm()
                await dm_channel.send(embed=embed)
            except:
                pass

            self.cache["userSubmissions"].pop(str(message.id))

            await self.update_db()


        accept = Button(label="Accept", style=discord.ButtonStyle.green)
        accept.callback = _accept_callback

        deny = Button(label="Deny", style=discord.ButtonStyle.red)
        deny.callback = _deny_callback

        buttons_view = View(accept, deny, timeout=None)

        await message.edit(view=buttons_view)

    @_cm.command(name="submit", description="Submits a new compliment.")
    @checks.has_permissions(PermissionLevel.REGULAR)
    async def _cm_submit(self, ctx: ApplicationContext, compliment: discord.Option(str, "Compliment you want to add.")):
        """
        Submits a new compliement.

        """

        if not self.cache["checkChannel"]:
            embed = discord.Embed(
                title="Error", description="Compliments system has not been set up yet.")
            await ctx.respond(embed=embed, ephemeral=True)

            return

        embed = discord.Embed(
            title=f"New compliment submission by {ctx.author.name}", colour=Colour.blue())

        embed.add_field(name="Compliment", value=compliment)
        embed.add_field(name="User", value=ctx.author.mention)

        message = await self.check_channel.send(embed=embed)

        submission_info = {
            "compliment": compliment,
            "user": ctx.author.id
        }

        self.cache["userSubmissions"].update({str(message.id): submission_info})

        await self.update_db()

        await self.add_buttons(message)

        embed = discord.Embed(
            title="Success", description=f"Compliment has been submitted to staff for review!", colour=Colour.green())

        await ctx.respond(embed=embed)

    
    @_cm.command(name="setup", description="Sets up the compliment system.")
    @commands.cooldown(1, 21600, BucketType.member)
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _cm_setup(self, ctx, compliements_channel: discord.Option(discord.TextChannel, "The channel to send compliments in."),
                        check_channel: discord.Option(discord.TextChannel, "The channel to send compliments in.")):
        """
        Sets up the compliment system.

        """

        self.cache["complimentsChannel"] = compliements_channel.id
        self.cache["checkChannel"] = check_channel.id

        await self.update_db()

        self.check_channel = await self.guild.fetch_channel(self.cache["checkChannel"])
        self.compliments_channel = await self.guild.fetch_channel(self.cache["complimentsChannel"])

        embed = discord.Embed(
            title="Success", description=f"Compliments system has been set up!", colour=Colour.green())

        await ctx.respond(embed=embed)

    @_cm.command(name="cooldown", description="Sets the cooldown between compliments.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _cm_cooldown(self, ctx, cooldown: discord.Option(int, "Cooldown duration in mins", min_value=1, max_value=1440)):
        """
        Sets the cooldown between compliments.

        """

        self.cache["cooldown"] = cooldown
        await self.update_db()

        embed = discord.Embed(
            title="Success", description=f"Cooldown has been set to {cooldown} minutes!", colour=Colour.green())

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Compliment(bot))
