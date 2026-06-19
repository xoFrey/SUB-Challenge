import discord
from discord import app_commands
from discord.ext import commands
from . import storage

GUILD_ID = None  # wird beim Laden gesetzt


class StarsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sternenstand", description="Zeigt deinen Monats- und Gesamt-Sternenstand")
    async def sternenstand(self, interaction: discord.Interaction):
        user = await storage.get_user(interaction.user.id)
        stats = user["month_stats"]
        embed = discord.Embed(
            title="⭐ Dein Sternenstand",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Diesen Monat", value=f"{user['monthly_stars']} ⭐", inline=True)
        embed.add_field(name="Gesamt", value=f"{user['total_stars']} ⭐", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Leerzeile

        gelesen = stats["buchclub_beendet"] + stats["sub_beendet"]
        embed.add_field(name="📚 Bücher beendet (Monat)", value=str(gelesen), inline=True)
        embed.add_field(name="　 davon BuchClub", value=str(stats["buchclub_beendet"]), inline=True)
        embed.add_field(name="　 davon SuB", value=str(stats["sub_beendet"]), inline=True)
        embed.add_field(name="❌ DNF (Monat)", value=str(stats["dnf"]), inline=True)
        embed.add_field(name="⏸️ Pausiert (Monat)", value=str(stats["pausiert"]), inline=True)
        embed.add_field(name="🛍️ Gekauft (Monat)", value=str(stats["gekauft"]), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sub-groesse", description="Trage die aktuelle Größe deines SUB ein")
    @app_commands.describe(anzahl="Anzahl Bücher aktuell auf deinem SUB")
    async def sub_groesse(self, interaction: discord.Interaction, anzahl: int):
        if anzahl < 0:
            await interaction.response.send_message("Die Zahl darf nicht negativ sein.", ephemeral=True)
            return
        await storage.set_sub_size(interaction.user.id, anzahl)
        await interaction.response.send_message(f"Dein SUB-Stand wurde auf **{anzahl}** Bücher gesetzt.", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = StarsCog(bot)
    await bot.add_cog(cog)
    import os
    guild = discord.Object(id=int(os.environ["GUILD_ID"]))
    for cmd in [cog.sternenstand, cog.sub_groesse]:
        bot.tree.add_command(cmd, guild=guild)
