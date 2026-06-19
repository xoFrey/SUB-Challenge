import os
import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool():
    """Erstellt den Connection-Pool und legt die Tabelle an, falls nicht vorhanden."""
    global _pool
    database_url = os.environ["DATABASE_URL"]
    # Neon erfordert SSL
    _pool = await asyncpg.create_pool(dsn=database_url, ssl="require", min_size=1, max_size=5)

    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                monthly_stars NUMERIC NOT NULL DEFAULT 0,
                total_stars NUMERIC NOT NULL DEFAULT 0,
                sub_size INTEGER NOT NULL DEFAULT 0,
                buchclub_beendet INTEGER NOT NULL DEFAULT 0,
                sub_beendet INTEGER NOT NULL DEFAULT 0,
                dnf INTEGER NOT NULL DEFAULT 0,
                pausiert INTEGER NOT NULL DEFAULT 0,
                gekauft INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Falls die Tabelle schon mit altem Schema existiert: fehlende Spalten nachrüsten
        await conn.execute(
            """
            ALTER TABLE users ADD COLUMN IF NOT EXISTS buchclub_beendet INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_beendet INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS pausiert INTEGER NOT NULL DEFAULT 0;
            """
        )


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()


async def _ensure_user(conn, user_id: int):
    await conn.execute(
        "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
        user_id,
    )


async def add_stars(user_id: int, amount: float):
    """Sterne hinzufügen (kann negativ sein). Gibt (monatlich, gesamt) zurück."""
    async with _pool.acquire() as conn:
        await _ensure_user(conn, user_id)
        row = await conn.fetchrow(
            """
            UPDATE users
            SET monthly_stars = monthly_stars + $2,
                total_stars = total_stars + $2
            WHERE user_id = $1
            RETURNING monthly_stars, total_stars
            """,
            user_id,
            amount,
        )
        return float(row["monthly_stars"]), float(row["total_stars"])


async def increment_stat(user_id: int, stat_name: str, amount: int = 1):
    """stat_name muss 'buchclub_beendet', 'sub_beendet', 'dnf', 'pausiert' oder 'gekauft' sein."""
    assert stat_name in ("buchclub_beendet", "sub_beendet", "dnf", "pausiert", "gekauft")
    async with _pool.acquire() as conn:
        await _ensure_user(conn, user_id)
        await conn.execute(
            f"UPDATE users SET {stat_name} = {stat_name} + $2 WHERE user_id = $1",
            user_id,
            amount,
        )


async def get_user(user_id: int):
    async with _pool.acquire() as conn:
        await _ensure_user(conn, user_id)
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return {
            "monthly_stars": float(row["monthly_stars"]),
            "total_stars": float(row["total_stars"]),
            "sub_size": row["sub_size"],
            "month_stats": {
                "buchclub_beendet": row["buchclub_beendet"],
                "sub_beendet": row["sub_beendet"],
                "dnf": row["dnf"],
                "pausiert": row["pausiert"],
                "gekauft": row["gekauft"],
            },
        }


async def set_sub_size(user_id: int, size: int):
    async with _pool.acquire() as conn:
        await _ensure_user(conn, user_id)
        await conn.execute("UPDATE users SET sub_size = $2 WHERE user_id = $1", user_id, size)


async def adjust_sub_size(user_id: int, delta: int):
    """SUB-Größe um delta verändern (kann negativ sein), aber nie unter 0 fallen."""
    async with _pool.acquire() as conn:
        await _ensure_user(conn, user_id)
        row = await conn.fetchrow(
            """
            UPDATE users
            SET sub_size = GREATEST(sub_size + $2, 0)
            WHERE user_id = $1
            RETURNING sub_size
            """,
            user_id,
            delta,
        )
        return row["sub_size"]


async def get_all_users():
    """Gibt dict {user_id_str: {...}} zurück, im gleichen Format wie get_user."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
        result = {}
        for row in rows:
            result[str(row["user_id"])] = {
                "monthly_stars": float(row["monthly_stars"]),
                "total_stars": float(row["total_stars"]),
                "sub_size": row["sub_size"],
                "month_stats": {
                    "buchclub_beendet": row["buchclub_beendet"],
                    "sub_beendet": row["sub_beendet"],
                    "dnf": row["dnf"],
                    "pausiert": row["pausiert"],
                    "gekauft": row["gekauft"],
                },
            }
        return result


async def reset_month():
    """Setzt Monatswerte zurück (Sterne + Statistik-Zähler). Gesamtsterne bleiben erhalten."""
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET monthly_stars = 0,
                buchclub_beendet = 0,
                sub_beendet = 0,
                dnf = 0,
                pausiert = 0,
                gekauft = 0
            """
        )
