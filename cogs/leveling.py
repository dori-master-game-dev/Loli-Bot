from curses import nonl
import math
import discord
from discord.ext import commands

from discord.ui import View, Button

from core.checks import PermissionLevel
from core import calculate_level, checks
from core.logger import get_logger

logger = get_logger(__name__)


class Leveling(commands.Cog):
    _id = "leveling"

    exp_given = 1

    default_cache = {
        "userExpData": {
            "inside": {

            },
            "outside": {

            }
        },
        "levelEvents": {

        }
    }

    _lvl = discord.SlashCommandGroup(
        "level", "Contains command to modify the leveling system.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = self.bot.db[self._id]
        self.cache = {}

        self.bot.loop.create_task(self.load_cache())  # this only runs once xD

    async def update_db(self):  # updates database with cache
        await self.db.find_one_and_update(
            {"_id": self._id},
            {"$set": self.cache},
            upsert=True,
        )

    async def load_cache(self):
        db = await self.db.find_one({"_id": self._id})
        if db is None:
            db = self.default_cache

        self.cache = db

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        exp = 0

        if str(member.id) in self.cache["userExpData"]["outside"]:
            exp = self.cache["userExpData"]["outside"][str(member.id)]
            self.cache["userExpData"]["outside"].pop(str(member.id))

        self.cache["userExpData"]["inside"].update(
            {str(member.id): exp})

        await self.update_db()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return

        exp = 0

        if str(member.id) in self.cache["userExpData"]["inside"]:
            exp = self.cache["userExpData"]["inside"][str(member.id)]
            self.cache["userExpData"]["inside"].pop(str(member.id))

        self.cache["userExpData"]["outside"].update(
            {str(member.id): exp})

        await self.update_db()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        await self.update_exp(message.channel, message.author)

    @commands.slash_command(name="rank", description="Gets the rank of a user.")
    @commands.check(checks.has_permissions(PermissionLevel.REGULAR))
    async def rank(self, ctx, user: discord.Option(discord.User, "The user whose rank you want to see, leave it blank to see yours.", required=False)):
        """
        Gets the rank of a user.

        You may leave 'user' blank to get your own rank.

        """

        if user == None:
            user = ctx.author

        if str(user.id) not in self.cache["userExpData"]["inside"]:
            embed = discord.Embed(
                title="User not found",
                description=f"User {user.mention} was not present in the database."
            )

            await ctx.respond(embed=embed)
            return

        cache = self.cache["userExpData"]["inside"]
        sort = sorted(cache.items(), key=lambda x: x[1], reverse=True)

        rank = 0
        exp = 0

        for key, value in sort:
            rank += 1
            if key == str(user.id):
                exp = value

                break

        embed = discord.Embed(
            title=user.display_name,
            description=f"**Level:** {calculate_level.get_level(exp)} \n **Exp:** {exp}/{calculate_level.next_level(exp)} \n **Rank:** {rank}"
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        await ctx.respond(embed=embed)

    @commands.user_command(name="Get user rank")
    @checks.has_permissions(PermissionLevel.REGULAR)
    async def user_rank(self, ctx, user):
        await self.rank(ctx, user)

    @commands.message_command(name="Get meesage rank")
    @checks.has_permissions(PermissionLevel.REGULAR)
    async def message_rank(self, ctx, message):
        await self.rank(ctx, message.author)

    @_lvl.command(name="set", description="Sets the exp of the user to a specified value.")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def _lvl_set(self, ctx,
                       user: discord.Option(discord.User, "The user whose level you wish to change."),
                       mode: discord.Option(str, "How you wish to set the exp", 
                       choices=[discord.OptionChoice("Experience", "exp"), discord.OptionChoice("Level", "level")]),
                       amount: discord.Option(int, "The amount you wish to change the user's exp to", min_value=0)):
        """
        Sets the exp of a user.

        """

        if str(user.id) not in self.cache["userExpData"]["inside"]:
            embed = discord.Embed(
                title="User not found",
                description=f"User {user.mention} was not present in the database."
            )

            await ctx.respond(embed=embed)
            return

        self.cache["userExpData"]["inside"][str(
            user.id)] = amount if mode == "exp" else calculate_level.level_to_exp(amount)

        await self.update_db()

        embed = discord.Embed(
            title="Success!",
            description=f"{user.mention}'s exp was set to {amount}, new level is {calculate_level.get_level(amount)}."
        )

        await ctx.respond(embed=embed)

    @commands.slash_command(name="leaderboard", description="Gets a list of users ordered by level.")
    @commands.check(checks.has_permissions(PermissionLevel.REGULAR))
    async def top(self, ctx: discord.ApplicationContext, page: discord.Option(int, "The page you wish to view.", default=1, min_value=1)):
        """
        Gets the top 10 users in the server.

        Run `{prefix}top [number]` to get the next 10 users starting at rank [number].

        Run `{prefix}top me` to get the people around you in level.

        """

        await ctx.defer()

        async def _callback_left(interaction: discord.Interaction):
            if (interaction.user.id != ctx.author.id):
                await interaction.response.defer()
                return

            nonlocal page
            page = page - 1

            await show_top(page)

            await interaction.response.defer()

        async def _callback_right(interaction):
            if (interaction.user.id != ctx.author.id):
                await interaction.response.defer()
                return

            nonlocal page
            page = page + 1

            await show_top(page)

            await interaction.response.defer()

        async def _callback_close(interaction):
            if (interaction.user.id != ctx.author.id):
                await interaction.response.defer()
                return

            await interaction.response.defer()
            await ctx.delete()

            return

        left = Button(label="◀", style=discord.ButtonStyle.blurple)
        left.callback = _callback_left

        right = Button(label="▶", style=discord.ButtonStyle.blurple)
        right.callback = _callback_right

        close = Button(label="Close", style=discord.ButtonStyle.red)
        close.callback = _callback_close

        if ctx.author.is_on_mobile():
            left.label = ":arrow_left:"
            right.label = ":arrow_right:"

        async def show_top(page):
            users_page = 2

            start = (page - 1) * users_page
            end = start + users_page

            cache = self.cache["userExpData"]["inside"]

            if len(cache.keys()) == 0:
                embed = discord.Embed(
                    title="No users present in the database",
                    description="The database is empty."
                )

                await ctx.interaction.edit_original_message(embed=embed)
                return

            pages = math.ceil(len(cache.keys()) / users_page)

            if page > pages:
                embed = discord.Embed(
                    title="Page was outside range",
                    description=f"There are only {pages} pages in the leaderboard."
                )

                await ctx.interaction.edit_original_message(embed=embed)
                return

            sort = sorted(cache.items(), key=lambda x: x[1], reverse=True)[
                start: end]

            description = ""

            rank = start + 1
            for key, value in sort:
                description += f"**#{rank}.** <@{key}>\n\t Level: `{calculate_level.get_level(int(value))}` \n\t Exp `{value}/{calculate_level.next_level(int(value))}`\n"
                rank += 1

            embed = discord.Embed(
                title=f"{ctx.guild.name}'s leaderboard",
                description=description
            )

            embed.set_footer(text=f"{page}/{pages}")

            left.disabled = page == 1
            right.disabled = page == pages

            lb_view = View(left, close, right)

            await ctx.interaction.edit_original_message(embed=embed, view=lb_view)

        await show_top(page)
        await ctx.delete(delay=60)

    @_lvl.command(name="add", description="Adds a new event associated with a level.")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def _lvl_add(self, ctx, level: discord.Option(int, "The level you wish to add an event to", min_value=1),
                       action: discord.Option(str, "The action you wish to take on hitting that level.",
                                              choices=[discord.OptionChoice("Add role", "add"), discord.OptionChoice("Remove role", "remove")]),
                       role: discord.Option(discord.Role, "The role you wish to take action with."),):
        if str(level) not in self.cache["levelEvents"]:
            self.cache["levelEvents"].update({str(level): []})

        for level_event in self.cache["levelEvents"][str(level)]:
            if level_event["role"] == role.id and level_event["action"] == action:
                embed = discord.Embed(
                    title="Duplicate level event",
                    description=f"Level {level} event '{action} {role.mention}' is already in the database!"
                )

                await ctx.respond(embed=embed)
                return

        self.cache["levelEvents"][str(level)].append(
            {"role": role.id, "action": action})

        embed = discord.Embed(
            title="Success",
            description=f"New level {level} event added: {action} {role.mention}!"
        )

        await self.update_db()
        await ctx.respond(embed=embed)

    @_lvl.command(name="remove", description="Removes an event associated with a level.")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def _lvl_remove(self, ctx, level: discord.Option(int, "The level you wish to change the user's to", min_value=1),
                          action: discord.Option(str, "The action you wish to take on hitting that level.",
                          choices=[discord.OptionChoice("Add role", "add"), discord.OptionChoice("Remove role", "remove")]),
                          role: discord.Option(discord.Role, "The role you wish to take action with.")):
        if str(level) not in self.cache["levelEvents"]:
            embed = discord.Embed(
                title="Level not found",
                description=f"The level was not found in the database."
            )

            await ctx.respond(embed=embed)
            return

        for level_event in self.cache["levelEvents"][str(level)]:
            if level_event["role"] == role.id and level_event["action"] == action:
                self.cache["levelEvents"][str(level)].remove(level_event)

                embed = discord.Embed(
                    title="Success",
                    description=f"Level {level} event '{action} {role.mention}' was removed!"
                )

                await self.update_db()
                await ctx.respond(embed=embed)

                return

            embed = discord.Embed(
                title="Level event not found",
                description=f"The level event was not found in the database."
            )

            await ctx.respond(embed=embed)

    @_lvl.command(name="list", description="Lists all the level events.")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def _lvl_list(self, ctx):
        if len(self.cache["levelEvents"].keys()) == 0:
            embed = discord.Embed(
                title="No level events found",
                description="There were no level events in the database."
            )

            await ctx.respond(embed=embed)
            return

        embed = discord.Embed(title="Level events list")

        for level in self.cache["levelEvents"]:
            value = ""
            for level_event in self.cache["levelEvents"][level]:
                value += f"{level_event['action']} <@&{level_event['role']}>\n"

            embed.add_field(
                name=f"Level {level} events:", value="No level events." if value == "" else value, inline=False)

        await ctx.respond(embed=embed)

    async def update_exp(self, channel, user):
        messages = (await channel.history(limit=10).flatten())[1:]

        for message in messages:
            if not message.author.bot:
                if message.author != user:
                    await self.add_exp(user)

                return

    async def add_exp(self, user: discord.Member):
        if str(user.id) not in self.cache["userExpData"]["inside"]:
            self.cache["userExpData"]["inside"].update(
                {str(user.id): self.exp_given})

            await self.update_db()
            return

        exp = self.cache["userExpData"]["inside"][str(user.id)]
        next_level = calculate_level.next_level(exp)
        level = calculate_level.get_level(exp) + 1

        if exp + self.exp_given >= next_level:
            if str(level) in self.cache["levelEvents"]:
                for level_event in self.cache["levelEvents"][str(level)]:
                    role = user.guild.get_role(level_event["role"])
                    if role == None:
                        logger.error("Role for level event was not found.")
                        continue
                    
                    if level_event["action"] == "add":
                        await user.add_roles(role)
                    elif level_event["action"] == "remove":
                        await user.remove_roles(role)

        self.cache["userExpData"]["inside"][str(user.id)] += self.exp_given
        await self.update_db()


def setup(bot):
    bot.add_cog(Leveling(bot))