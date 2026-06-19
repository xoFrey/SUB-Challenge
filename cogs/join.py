import os
import discord
from discord import app_commands
from discord.ext import commands

ROLE_SUB_REKRUT_ID = int(os.environ["ROLE_SUB_REKRUT_ID"])


class JoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent

    @discord.ui.button(
        label="Ich mache mit!",
        style=discord.ButtonStyle.success,
        emoji="📚",
        custom_id="sub_panel:join_toggle",
    )
    async def join_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_SUB_REKRUT_ID)
        if role is None:
            await interaction.response.send_message("Rolle nicht gefunden, bitte einen Admin informieren.", ephemeral=True)
            return

        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role, reason="Selbst ausgetreten")
            await interaction.response.send_message(
                "Du hast die Challenge verlassen und die Rolle **SUB-Rekrut** verloren. "
                "Klick erneut, um wieder einzusteigen!",
                ephemeral=True,
            )
        else:
            await member.add_roles(role, reason="Selbst beigetreten")
            await interaction.response.send_message(
                "Willkommen bei der SUB-Sterne-Challenge! Du hast jetzt die Rolle **SUB-Rekrut** "
                "und kannst die Buttons im Panel-Channel nutzen. 📚⭐",
                ephemeral=True,
            )


class JoinCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(JoinView())  # damit der Button nach Neustart funktioniert

    @app_commands.command(
        name="beitritt-posten",
        description="Postet den Beitritts-Button für die SUB-Rekrut-Rolle (Admin)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def beitritt_posten(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 Bei der SUB-Sterne-Challenge mitmachen",
            description=(
                "Klick auf den Button unten, um die Rolle **SUB-Rekrut** zu erhalten. "
                "Damit kannst du im Panel-Channel Sterne sammeln!\n\n"
                "Klickst du erneut, verlässt du die Challenge wieder."
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, view=JoinView())


async def setup(bot: commands.Bot):
    cog = JoinCog(bot)
    await bot.add_cog(cog)
    guild = discord.Object(id=int(os.environ["GUILD_ID"]))
    bot.tree.add_command(cog.beitritt_posten, guild=guild)
