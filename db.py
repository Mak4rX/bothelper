import aiosqlite

from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    shift         TEXT    NOT NULL,            -- 'day' | 'night'
    open_cash     INTEGER NOT NULL,
    earned        INTEGER NOT NULL,
    expenses      INTEGER NOT NULL,
    collection_id INTEGER,                     -- інкасація, прив'язана до звіту
    close_cash    INTEGER NOT NULL,
    senet         INTEGER NOT NULL,
    surplus       INTEGER NOT NULL,
    report_text   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS collections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    amount     INTEGER NOT NULL,
    comment    TEXT,
    report_id  INTEGER,                        -- звіт, у якому врахована
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

_MIGRATIONS = (
    "ALTER TABLE reports ADD COLUMN collection_id INTEGER",
    "ALTER TABLE collections ADD COLUMN report_id INTEGER",
)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        for sql in _MIGRATIONS:  # міграції для вже існуючої бази
            try:
                await db.execute(sql)
            except aiosqlite.OperationalError:
                pass  # колонка вже існує
        await db.commit()


async def save_report(user_id: int, shift: str, open_cash: int, earned: int,
                      expenses: int, collection_id: int | None,
                      close_cash: int, senet: int, surplus: int,
                      report_text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO reports
               (user_id, shift, open_cash, earned, expenses, collection_id,
                close_cash, senet, surplus, report_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, shift, open_cash, earned, expenses, collection_id,
             close_cash, senet, surplus, report_text),
        )
        report_id = cur.lastrowid
        if collection_id is not None:
            await db.execute(
                "UPDATE collections SET report_id = ? WHERE id = ?",
                (report_id, collection_id),
            )
        await db.commit()
        return report_id


async def last_reports(user_id: int, limit: int = 5) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT shift, close_cash, surplus, report_text, created_at
               FROM reports WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        return await cur.fetchall()


async def stats(user_id: int, days: int) -> aiosqlite.Row | None:
    """Підсумки по звітах за останні N днів."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT COUNT(*)        AS cnt,
                      COALESCE(SUM(earned), 0)   AS earned,
                      COALESCE(SUM(expenses), 0) AS expenses,
                      COALESCE(SUM(surplus), 0)  AS surplus
               FROM reports
               WHERE user_id = ?
                 AND created_at >= datetime('now', 'localtime', ?)""",
            (user_id, f"-{days} days"),
        )
        return await cur.fetchone()


# ---------- інкасації ----------

async def add_collection(user_id: int, amount: int, comment: str | None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO collections (user_id, amount, comment) VALUES (?, ?, ?)",
            (user_id, amount, comment),
        )
        await db.commit()
        return cur.lastrowid


async def get_collection(collection_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, user_id, amount, comment, report_id, created_at"
            "  FROM collections WHERE id = ?",
            (collection_id,),
        )
        return await cur.fetchone()


async def pending_collection(user_id: int) -> aiosqlite.Row | None:
    """Остання інкасація, ще не врахована в жодному звіті."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, amount, comment, created_at
               FROM collections
               WHERE user_id = ? AND report_id IS NULL
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        )
        return await cur.fetchone()


async def last_collections(user_id: int, limit: int = 5) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, amount, comment, report_id, created_at
               FROM collections WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        return await cur.fetchall()


# ---------- автопідстановка каси ----------

async def expected_cash(user_id: int) -> int | None:
    """Скільки готівки має бути в касі на початок нової зміни.

    Береться кінцева каса останнього звіту. Інкасація, врахована в тому
    звіті, вже віднята в close_cash — окремо коригувати не треба.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT close_cash FROM reports WHERE user_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None
