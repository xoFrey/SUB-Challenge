import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from . import storage
from .stars import build_sternenstand_embed

DELETE_AFTER_SECONDS = 5

ROLE_SUB_REKRUT_ID = int(os.environ["ROLE_SUB_REKRUT_ID"])
ROLE_STERNENSAMMLER_ID = int(os.environ["ROLE_STERNENSAMMLER_ID"])
ROLE_BUECHERKRIEGER_ID = int(os.environ["ROLE_BUECHERKRIEGER_ID"])
ROLE_SUB_BEZWINGER_ID = int(os.environ["ROLE_SUB_BEZWINGER_ID"])

ROLE_THRESHOLDS = [
    (70, ROLE_SUB_BEZWINGER_ID),
    (30, ROLE_BUECHERKRIEGER_ID),
    (10, ROLE_STERNENSAMMLER_ID),
]


async def check_role_rewards(member: discord.Member, total_stars: float):
    """Vergibt automatisch Rollen basierend auf dem Gesamtsternestand."""
    for threshold, role_id in ROLE_THRESHOLDS:
        role = member.guild.get_role(role_id)
        if role is None:
            continue
        if total_stars >= threshold and role not in member.roles:
            await member.add_roles(role, reason=f"{threshold} Sterne erreicht")


def has_sub_rekrut(member: discord.Member) -> bool:
    return any(r.id == ROLE_SUB_REKRUT_ID for r in member.roles)


# ---------- Modal für "Aussortiert" ----------
class AussortiertModal(discord.ui.Modal, title="Aussortierte Bücher"):
    anzahl = discord.ui.TextInput(
        label="Wie viele Bücher hast du aussortiert?",
        placeholder="z.B. 3",
        required=True,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.anzahl.value)
            if n < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Bitte eine gültige positive Zahl eingeben.", ephemeral=True)
            return
        monthly, total = await storage.add_stars(interaction.user.id, n)
        await check_role_rewards(interaction.user, total)
        await interaction.response.send_message(
            f"📦 {n} Buch/Bücher aussortiert: **+{n} ⭐**\nMonat: {monthly} ⭐ | Gesamt: {total} ⭐",
            ephemeral=True,
            delete_after=DELETE_AFTER_SECONDS,
        )


# ---------- SuB-Checkliste (View mit Auswahl-Buttons + Submit) ----------
class SubChecklistView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.selected = set()
        self.message: discord.InteractionMessage | None = None

        options = [
            ("reihe_beendet", "Reihe beendet (+3)"),
            ("ueber_500", "Über 500 Seiten / 15h Hörbuch (+2)"),
            ("zwei_jahre", "Lag 2 Jahre auf dem SUB (+2)"),
            ("buddy_read", "Buddy Read abgeschlossen (+1)"),
            ("laengstes", "Längstes Buch vom SUB (+1)"),
        ]
        for key, label in options:
            self.add_item(self._make_toggle_button(key, label))

        self.add_item(self._make_submit_button())

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏱️ Diese Auswahl ist abgelaufen. Klicke erneut auf **Buch beendet**, um es einzutragen.",
                    view=None,
                )
            except discord.HTTPException:
                pass

    def _make_toggle_button(self, key, label):
        view = self

        class ToggleButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label=label, style=discord.ButtonStyle.secondary)
                self.key = key

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != view.user_id:
                    await interaction.response.send_message("Das ist nicht dein Fenster.", ephemeral=True)
                    return
                if self.key in view.selected:
                    view.selected.discard(self.key)
                    self.style = discord.ButtonStyle.secondary
                else:
                    view.selected.add(self.key)
                    self.style = discord.ButtonStyle.success
                await interaction.response.edit_message(view=view)

        return ToggleButton()

    def _make_submit_button(self):
        view = self

        class SubmitButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Absenden", style=discord.ButtonStyle.primary, row=4)

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != view.user_id:
                    await interaction.response.send_message("Das ist nicht dein Fenster.", ephemeral=True)
                    return

                points_map = {
                    "reihe_beendet": 3,
                    "ueber_500": 2,
                    "zwei_jahre": 2,
                    "buddy_read": 1,
                    "laengstes": 1,
                }
                bonus = sum(points_map[k] for k in view.selected)
                total_gain = 1 + bonus  # +1 Basis für "Buch beendet"

                monthly, total = await storage.add_stars(interaction.user.id, total_gain)
                await storage.increment_stat(interaction.user.id, "sub_beendet")
                await check_role_rewards(interaction.user, total)

                gewaehlt = ", ".join(view.selected) if view.selected else "keine Extras"
                await interaction.response.edit_message(
                    content=(
                        f"📚 Buch beendet (SuB)! Basis +1, Extras: {gewaehlt}\n"
                        f"**Gesamt für diesen Eintrag: +{total_gain} ⭐**\n"
                        f"Monat: {monthly} ⭐ | Gesamt: {total} ⭐"
                    ),
                    view=None,
                )
                await asyncio.sleep(DELETE_AFTER_SECONDS)
                try:
                    await interaction.delete_original_response()
                except discord.HTTPException:
                    pass

        return SubmitButton()


# ---------- BuchClub / SuB Auswahl ----------
class BuchBeendetChoiceView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.message: discord.InteractionMessage | None = None

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏱️ Diese Auswahl ist abgelaufen. Klicke erneut auf **Buch beendet**, um es einzutragen.",
                    view=None,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(label="BuchClub Buch", style=discord.ButtonStyle.primary)
    async def buchclub(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Das ist nicht dein Fenster.", ephemeral=True)
            return
        monthly, total = await storage.add_stars(interaction.user.id, 5)
        await storage.increment_stat(interaction.user.id, "buchclub_beendet")
        await check_role_rewards(interaction.user, total)
        await interaction.response.edit_message(
            content=f"📚 BuchClub-Buch beendet: **+5 ⭐**\nMonat: {monthly} ⭐ | Gesamt: {total} ⭐",
            view=None,
        )
        await asyncio.sleep(DELETE_AFTER_SECONDS)
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

    @discord.ui.button(label="SuB Buch", style=discord.ButtonStyle.secondary)
    async def sub_buch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Das ist nicht dein Fenster.", ephemeral=True)
            return
        view = SubChecklistView(interaction.user.id)
        await interaction.response.edit_message(
            content="Wähle alle zutreffenden Punkte aus und klicke dann **Absenden**:",
            view=view,
        )
        view.message = await interaction.original_response()


# ---------- Hauptpanel ----------
class MainPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent

    @discord.ui.button(label="DNF", style=discord.ButtonStyle.secondary, custom_id="sub_panel:dnf")
    async def dnf(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_sub_rekrut(interaction.user):
            await interaction.response.send_message("Du brauchst die Rolle SUB-Rekrut.", ephemeral=True)
            return
        monthly, total = await storage.add_stars(interaction.user.id, 1)
        await storage.increment_stat(interaction.user.id, "dnf")
        await check_role_rewards(interaction.user, total)
        await interaction.response.send_message(
            f"DNF: **+1 ⭐**\nMonat: {monthly} ⭐ | Gesamt: {total} ⭐", ephemeral=True, delete_after=DELETE_AFTER_SECONDS
        )

    @discord.ui.button(label="Pausiert", style=discord.ButtonStyle.secondary, custom_id="sub_panel:pausiert")
    async def pausiert(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_sub_rekrut(interaction.user):
            await interaction.response.send_message("Du brauchst die Rolle SUB-Rekrut.", ephemeral=True)
            return
        monthly, total = await storage.add_stars(interaction.user.id, 0.5)
        await storage.increment_stat(interaction.user.id, "pausiert")
        await check_role_rewards(interaction.user, total)
        await interaction.response.send_message(
            f"Pausiert: **+0.5 ⭐**\nMonat: {monthly} ⭐ | Gesamt: {total} ⭐", ephemeral=True, delete_after=DELETE_AFTER_SECONDS
        )

    @discord.ui.button(label="Aussortiert", style=discord.ButtonStyle.secondary, custom_id="sub_panel:aussortiert")
    async def aussortiert(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_sub_rekrut(interaction.user):
            await interaction.response.send_message("Du brauchst die Rolle SUB-Rekrut.", ephemeral=True)
            return
        await interaction.response.send_modal(AussortiertModal())

    @discord.ui.button(label="Gekauft", style=discord.ButtonStyle.danger, custom_id="sub_panel:gekauft")
    async def gekauft(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_sub_rekrut(interaction.user):
            await interaction.response.send_message("Du brauchst die Rolle SUB-Rekrut.", ephemeral=True)
            return
        monthly, total = await storage.add_stars(interaction.user.id, -1)
        await storage.increment_stat(interaction.user.id, "gekauft")
        await interaction.response.send_message(
            f"Gekauft: **-1 ⭐**\nMonat: {monthly} ⭐ | Gesamt: {total} ⭐", ephemeral=True, delete_after=DELETE_AFTER_SECONDS
        )

    @discord.ui.button(label="Buch beendet", style=discord.ButtonStyle.success, custom_id="sub_panel:buch_beendet")
    async def buch_beendet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_sub_rekrut(interaction.user):
            await interaction.response.send_message("Du brauchst die Rolle SUB-Rekrut.", ephemeral=True)
            return
        view = BuchBeendetChoiceView(interaction.user.id)
        await interaction.response.send_message(
            "War das ein BuchClub-Buch oder ein SuB-Buch?", view=view, ephemeral=True
        )
        view.message = await interaction.original_response()

    @discord.ui.button(label="Sternenstand", style=discord.ButtonStyle.primary, custom_id="sub_panel:sternenstand")
    async def sternenstand(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await build_sternenstand_embed(interaction.user.id)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(MainPanelView())  # damit Buttons nach Neustart funktionieren

    @app_commands.command(name="panel-posten", description="Postet das SUB-Sterne-Panel in diesen Channel (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_posten(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⭐ SUB-Sterne-Challenge",
            description="Wähle eine Aktion:",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, view=MainPanelView())


async def setup(bot: commands.Bot):
    cog = PanelCog(bot)
    await bot.add_cog(cog)
    guild = discord.Object(id=int(os.environ["GUILD_ID"]))
    bot.tree.add_command(cog.panel_posten, guild=guild)
