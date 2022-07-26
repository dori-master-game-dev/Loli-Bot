import base64
import json

from tabnanny import check
import discord
from discord.ext import commands
from discord.ui import Select, View

from discord import ApplicationContext, Colour, Interaction, Permissions, SlashCommandGroup

from core import checks
from core.base_cog import BaseCog
from core.checks import PermissionLevel

import re


class Embedder(BaseCog):
    _id = "embedder"

    default_cache = {
        "dataStrings": {

        }
    }

    _em = SlashCommandGroup("embedder", "Manages embdding commands.",
                            default_member_permissions=Permissions(manage_messages=True))

    async def decode_data(self, data):
        json_file = base64.urlsafe_b64decode(
            data + '=' * (4 - len(data) % 4)).decode("utf-8")

        return json.loads(json_file)

    @_em.command(name="add", description="Adds a new embeddable object using s URLSafe base64 string of the json file.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _em_add(self, ctx, name: discord.Option(str, "The name of the embeddable object."),
                      data: discord.Option(str, "The URLSafe base64 string of the json file.")):
        """
        Adds a new embeddable object using s URLSafe base64 string of the json file.

        """

        if name in self.cache["dataStrings"]:
            embed = discord.Embed(
                title="Error", description=f"An embeddable object with the name {name} is already present.\nYou can remove it using `/embedder remove name:{name}`.", colour=Colour.red())

            await ctx.respond(embed=embed)

            return

        self.cache["dataStrings"].update({name: data})

        await self.update_db()

        embed = discord.Embed(
            title="Success", description=f"A new embeddable object was added.", colour=Colour.green())

        await ctx.respond(embed=embed)

    @_em.command(name="remove", description="Removes an embeddable object using its name.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _em_remove(self, ctx, name: discord.Option(str, "The name of the embeddable object.")):
        """
        Removes an embeddable object using its name.

        """

        if name not in self.cache["dataStrings"]:
            embed = discord.Embed(
                title="Error", description=f"An embeddable object with the name {name} is not present.\nYou can add it using `/embedder add name:{name}`.", colour=Colour.red())

            await ctx.respond(embed=embed)

            return

        self.cache["dataStrings"].pop(name)

        await self.update_db()

        embed = discord.Embed(
            title="Success", description=f"An embeddable object was removed.", colour=Colour.green())

        await ctx.respond(embed=embed)

    @_em.command(name="list", description="Lists all embeddable objects' names.")
    @checks.has_permissions(PermissionLevel.MOD)
    async def _em_list(self, ctx):
        """
        Lists all embeddable objects' names.

        """

        if len(self.cache["dataStrings"].keys()) == 0:
            embed = discord.Embed(
                title="Error", description=f"No embeddable objects found in the database.", colour=Colour.red())

            await ctx.respond(embed=embed)

            return

        description = ""
        for name in self.cache["dataStrings"]:
            embeddable = await self.decode_data(self.cache["dataStrings"][name])
            description += f"**{name}:** {len(embeddable['messages'])}\n\n"

        embed = discord.Embed(
            title="Embeddable Objects", description=description, colour=Colour.blue())

        await ctx.respond(embed=embed)

    @_em.command(name="send", description="Sends an embeddable object to a channel.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _em_send(self, ctx: ApplicationContext, name: discord.Option(str, "The name of the embeddable object."),
                       channel: discord.Option(discord.TextChannel, "The channel to send it in.", required=False)):
        """
        Sends an embeddable object to a channel.

        """

        if name not in self.cache["dataStrings"]:
            embed = discord.Embed(
                title="Error", description=f"An embeddable object with the name {name} is not present.\nYou can add it using `/embedder add name:{name}`.", colour=Colour.red())

            await ctx.respond(embed=embed)

            return

        if not channel:
            channel = ctx.channel

        embeddable = await self.decode_data(self.cache["dataStrings"][name])

        for message in embeddable["messages"]:
            try:
                if message["data"]["embeds"]:
                    for embed in message["data"]["embeds"]:
                        if not embed["color"]:
                            embed["color"] = 2105893

                if message["data"]["embeds"]:
                    embeds = [discord.Embed.from_dict(
                        embed) for embed in message["data"]["embeds"]]
                else:
                    embeds = None

                await channel.send(content=message["data"]["content"], embeds=embeds)
            except:
                pass

        embed = discord.Embed(
            title="Success", description=f"Embeddable object has been sent.", colour=Colour.green())

        await ctx.respond(embed=embed, ephemeral=True)

    @_em.command(name="edit", description="Edits a message.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _em_edit(self, ctx: ApplicationContext, name: discord.Option(str, "The name of the embeddable object."),
                       index: discord.Option(int, "The index of the message you want to edit it to."),
                       channel: discord.Option(discord.TextChannel, "The channel to send it in."),
                       message_id: discord.Option(str, "The message ID for the message you want to edit.")):
        """
        Edits a message.

        """

        if name not in self.cache["dataStrings"]:
            embed = discord.Embed(
                title="Error", description=f"An embeddable object with the name {name} is not present.\nYou can add it using `/embedder add name:{name}`.", colour=Colour.red())

            await ctx.respond(embed=embed)

            return

        embeddable = await self.decode_data(self.cache["dataStrings"][name])

        if index < 0 or index >= len(embeddable["messages"]):
            embed = discord.Embed(
                title="Error", description=f"Index was outside of range.\nThere are {len(embeddable['messages'])} messages in {name} embedabble.", colour=Colour.red())

            await ctx.respond(embed=embed)

            return

        message = embeddable["messages"][index]

        try:
            if message["data"]["embeds"]:
                for embed in message["data"]["embeds"]:
                    if not embed["color"]:
                        embed["color"] = 2105893

            if message["data"]["embeds"]:
                embeds = [discord.Embed.from_dict(
                    embed) for embed in message["data"]["embeds"]]
            else:
                embeds = None

            try:
                message_to_edit = await channel.fetch_message(int(message_id))
                await message_to_edit.edit(
                    content=message["data"]["content"], embeds=embeds)
            except:
                embed = discord.Embed(
                    title="Error", description=f"Something has gone wrong.", colour=Colour.red())

                await ctx.respond(embed=embed)

                return
        except:
            pass

        embed = discord.Embed(
            title="Success", description=f"Message has been edited.", colour=Colour.green())

        await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(Embedder(bot))
