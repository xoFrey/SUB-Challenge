import os
import asyncio
import discord
from discord.ext import commands
from aiohttp import web
from cogs import storage

# ---------- Konfiguration über Umgebungsvariablen ----------
TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
PANEL_CHANNEL_ID = int(os.environ["PANEL_CHANNEL_ID"])
ROLE_SUB_REKRUT_ID = int(os.environ["ROLE_SUB_REKRUT_ID"])
ROLE_STERNENSAMMLER_ID = int(os.environ["ROLE_STERNENSAMMLER_ID"])
ROLE_BUECHERKRIEGER_ID = int(os.environ["ROLE_BUECHERKRIEGER_ID"])
ROLE_SUB_BEZWINGER_ID = int(os.environ["ROLE_SUB_BEZWINGER_ID"])
ROLE_SUB_KOENIGIN_ID = int(os.environ["ROLE_SUB_KOENIGIN_ID"])
ROLE_BOOK_BUYING_GOBLIN_ID = int(os.environ["ROLE_BOOK_BUYING_GOBLIN_ID"])
ROLE_SUB_DRACHE_ID = int(os.environ["ROLE_SUB_DRACHE_ID"])
ROLE_SPEED_READER_ID = int(os.environ["ROLE_SPEED_READER_ID"])
ROLE_DNF_EXPERTIN_ID = int(os.environ["ROLE_DNF_EXPERTIN_ID"])

intents = discord.Intents.default()
intents.members = True  # nötig um Rollen zu vergeben

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user} (ID: {bot.user.id})")
    guild = discord.Object(id=GUILD_ID)
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"{len(synced)} Slash-Commands synchronisiert.")
    except Exception as e:
        print(f"Fehler beim Sync: {e}")


async def load_extensions():
    await bot.load_extension("cogs.stars")
    await bot.load_extension("cogs.panel")
    await bot.load_extension("cogs.monthly")
    await bot.load_extension("cogs.join")


# ---------- Mini-Webserver, damit UptimeRobot den Bot wachhalten kann ----------
async def handle_ping(request):
    return web.Response(text="Bot lebt!")


async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Webserver läuft auf Port {port}")


async def main():
    await storage.init_pool()
    try:
        async with bot:
            await load_extensions()
            await start_webserver()
            await bot.start(TOKEN)
    finally:
        await storage.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
