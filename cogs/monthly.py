import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
from . import storage

PANEL_CHANNEL_ID = int(os.environ["PANEL_CHANNEL_ID"])
ROLE_SUB_KOENIGIN_ID = int(os.environ["ROLE_SUB_KOENIGIN_ID"])
ROLE_BOOK_BUYING_GOBLIN_ID = int(os.environ["ROLE_BOOK_BUYING_GOBLIN_ID"])
ROLE_SUB_DRACHE_ID = int(os.environ["ROLE_SUB_DRACHE_ID"])
ROLE_SPEED_READER_ID = int(os.environ["ROLE_SPEED_READER_ID"])
ROLE_DNF_EXPERTIN_ID = int(os.environ["ROLE_DNF_EXPERTIN_ID"])

MONTHLY_SPECIAL_ROLE_IDS = [
    ROLE_SUB_KOENIGIN_ID,
    ROLE_BOOK_BUYING_GOBLIN_ID,
    ROLE_SUB_DRACHE_ID,
    ROLE_SPEED_READER_ID,
    ROLE_DNF_EXPERTIN_ID,
]


class MonthlyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monthly_check.start()

    def cog_unload(self):
        self.monthly_check.cancel()

    @tasks.loop(hours=24)
    async def monthly_check(self):
        now = datetime.now(timezone.utc)
        # Läuft am letzten Tag des Monats, kurz vor Mitternacht UTC
        if now.day == self._last_day_of_month(now) and now.hour == 23:
            await self.run_month_end()

    @monthly_check.before_loop
    async def before_monthly_check(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _last_day_of_month(dt: datetime) -> int:
        next_month = dt.replace(day=28) + discord_timedelta(days=4)
        return (next_month - discord_timedelta(days=next_month.day)).day

    async def run_month_end(self):
        channel = self.bot.get_channel(PANEL_CHANNEL_ID)
        if channel is None:
            print("Panel-Channel nicht gefunden.")
            return
        guild = channel.guild

        users = await storage.get_all_users()
        if not users:
            return

        # Rangliste nach Monatssternen
        ranking = sorted(users.items(), key=lambda kv: kv[1]["monthly_stars"], reverse=True)

        embed = discord.Embed(
            title="🏆 Monats-Rangliste — SUB-Sterne-Challenge",
            color=discord.Color.gold(),
        )
        lines = []
        for i, (uid, data) in enumerate(ranking[:10], start=1):
            member = guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            lines.append(f"**{i}. {name}** — {data['monthly_stars']} ⭐")
        embed.description = "\n".join(lines) if lines else "Keine Daten."

        total_server_stars = sum(d["monthly_stars"] for d in users.values())
        embed.add_field(name="Gesamt gesammelte Sterne (Server, Monat)", value=f"{total_server_stars} ⭐")

        await channel.send(embed=embed)

        # Sonderrollen vergeben
        await self._assign_special_roles(guild, users)

        # Reset
        await storage.reset_month()
        await channel.send("Das Monatskonto wurde zurückgesetzt. Viel Erfolg im neuen Monat! 📚")

    async def _assign_special_roles(self, guild: discord.Guild, users: dict):
        # Alte Sonderrollen allen entfernen
        for role_id in MONTHLY_SPECIAL_ROLE_IDS:
            role = guild.get_role(role_id)
            if role is None:
                continue
            for member in list(role.members):
                await member.remove_roles(role, reason="Monatswechsel")

        if not users:
            return

        def top_member(key_func):
            best_uid, best_val = None, -float("inf")
            for uid, data in users.items():
                val = key_func(data)
                if val > best_val:
                    best_uid, best_val = uid, val
            return best_uid, best_val

        # SUB-Königin: höchste Monatssterne
        uid, val = top_member(lambda d: d["monthly_stars"])
        await self._add_role_if_positive(guild, uid, val, ROLE_SUB_KOENIGIN_ID)

        # Book-Buying-Goblin: meiste Käufe
        uid, val = top_member(lambda d: d["month_stats"].get("gekauft", 0))
        await self._add_role_if_positive(guild, uid, val, ROLE_BOOK_BUYING_GOBLIN_ID)

        # SUB-Drache: größter SUB (manuell eingetragen)
        uid, val = top_member(lambda d: d.get("sub_size", 0))
        await self._add_role_if_positive(guild, uid, val, ROLE_SUB_DRACHE_ID)

        # Speed Reader: meiste Bücher beendet
        uid, val = top_member(
            lambda d: d["month_stats"].get("buchclub_beendet", 0) + d["month_stats"].get("sub_beendet", 0)
        )
        await self._add_role_if_positive(guild, uid, val, ROLE_SPEED_READER_ID)

        # DNF-Expertin: meiste DNF
        uid, val = top_member(lambda d: d["month_stats"].get("dnf", 0))
        await self._add_role_if_positive(guild, uid, val, ROLE_DNF_EXPERTIN_ID)

    async def _add_role_if_positive(self, guild, uid, val, role_id):
        if uid is None or val <= 0:
            return
        member = guild.get_member(int(uid))
        role = guild.get_role(role_id)
        if member and role:
            await member.add_roles(role, reason="Monatliche Sonderrolle")

    @app_commands.command(name="monat-jetzt-beenden", description="Erzwingt Monatsabschluss sofort (Admin, zum Testen)")
    @app_commands.checks.has_permissions(administrator=True)
    async def monat_jetzt_beenden(self, interaction: discord.Interaction):
        await interaction.response.send_message("Monatsabschluss wird ausgeführt...", ephemeral=True)
        await self.run_month_end()


def discord_timedelta(**kwargs):
    from datetime import timedelta
    return timedelta(**kwargs)


async def setup(bot: commands.Bot):
    cog = MonthlyCog(bot)
    await bot.add_cog(cog)
    guild = discord.Object(id=int(os.environ["GUILD_ID"]))
    bot.tree.add_command(cog.monat_jetzt_beenden, guild=guild)
