"""Модуль базы данных для веб-приложения (без привязки к user_id)."""

import aiosqlite
from pathlib import Path

# На хостингу: DB_PATH=/data/bothelper.db (Railway volume)
# На Vercel: DB_PATH=/tmp/bothelper.db (оскільки коренева ФС read-only)
# Локально: поряд з файлом
import os
if os.environ.get("VERCEL"):
    _default = Path("/tmp/bothelper.db")
else:
    _default = Path(__file__).resolve().parent / "bothelper.db"
DB_PATH = Path(os.environ.get("DB_PATH", str(_default)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # створюємо директорію якщо немає

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    shift         TEXT    NOT NULL,
    open_cash     INTEGER NOT NULL,
    earned        INTEGER NOT NULL,
    expenses      INTEGER NOT NULL,
    collection_id INTEGER,
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
    report_id  INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

_MIGRATIONS = (
    "ALTER TABLE reports ADD COLUMN collection_id INTEGER",
    "ALTER TABLE collections ADD COLUMN report_id INTEGER",
)

# Одноразова міграція грошових колонок у копійки.
# Значення множимо на 100 саме там, де ще були «цілі гривні» (округлення .00).
_MONEY_MIGRATION_MARK = "PRAGMA user_version"


# Використовуємо виртуальный user_id для веб-приложения
WEB_USER_ID = 0


async def _migrate_money_to_kopecks(db) -> None:
    """Усі грошові суми переводимо з гривень у копійки (×100), один раз.

    Визначник — флаг у meta-таблиці, бо старих записів із «цілими гривнями»
    вже неможливо відрізнити від нових копійкових тільки за числом.
    """
    await db.execute(
        "CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    cur = await db.execute("SELECT value FROM _meta WHERE key = 'money_unit'")
    row = await cur.fetchone()
    if row and row[0] == "kopecks":
        return

    money_cols = ("open_cash", "earned", "expenses", "close_cash", "senet", "surplus")
    for col in money_cols:
        await db.execute(f"UPDATE reports SET {col} = {col} * 100")
    await db.execute("UPDATE collections SET amount = amount * 100")
    await db.execute(
        "INSERT INTO _meta (key, value) VALUES ('money_unit', 'kopecks') "
        "ON CONFLICT(key) DO UPDATE SET value = 'kopecks'"
    )


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        for sql in _MIGRATIONS:
            try:
                await db.execute(sql)
            except aiosqlite.OperationalError:
                pass
        await _migrate_money_to_kopecks(db)
        await db.commit()


async def save_report(shift: str, open_cash: int, earned: int,
                      expenses: int, collection_id: int | None,
                      close_cash: int, senet: int, surplus: int,
                      report_text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO reports
               (user_id, shift, open_cash, earned, expenses, collection_id,
                close_cash, senet, surplus, report_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (WEB_USER_ID, shift, open_cash, earned, expenses, collection_id,
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


async def last_reports(limit: int = 20) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT r.id, r.shift, r.open_cash, r.earned, r.expenses,
                      r.close_cash, r.senet, r.surplus, r.report_text,
                      r.created_at, c.amount as collection_amount
               FROM reports r
               LEFT JOIN collections c ON r.collection_id = c.id
               WHERE r.user_id = ?
               ORDER BY r.id DESC LIMIT ?""",
            (WEB_USER_ID, limit),
        )
        return await cur.fetchall()


async def stats(days: int) -> aiosqlite.Row | None:
    """Подсумки по отчетах за последние N дней."""
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
            (WEB_USER_ID, f"-{days} days"),
        )
        return await cur.fetchone()


# ---------- инкассации ----------

async def add_collection(amount: int, comment: str | None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO collections (user_id, amount, comment) VALUES (?, ?, ?)",
            (WEB_USER_ID, amount, comment),
        )
        await db.commit()
        return cur.lastrowid


async def update_pending_collection(collection_id: int, amount: int) -> bool:
    """Змінити суму ще не врахованої інкасації."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE collections SET amount = ?
               WHERE id = ? AND user_id = ? AND report_id IS NULL""",
            (amount, collection_id, WEB_USER_ID),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_collection(collection_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, user_id, amount, comment, report_id, created_at"
            "  FROM collections WHERE id = ?",
            (collection_id,),
        )
        return await cur.fetchone()


async def pending_collection() -> aiosqlite.Row | None:
    """Последняя инкассация, еще не учтенная ни в одном отчете."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, amount, comment, created_at
               FROM collections
               WHERE user_id = ? AND report_id IS NULL
               ORDER BY id DESC LIMIT 1""",
            (WEB_USER_ID,),
        )
        return await cur.fetchone()


async def last_collections(limit: int = 10) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, amount, comment, report_id, created_at
               FROM collections WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (WEB_USER_ID, limit),
        )
        return await cur.fetchall()


# ---------- удаление ----------

async def delete_report(report_id: int) -> bool:
    """Удалить отчет. Возвращает True если запись была."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Відв'язуємо інкасацію від звіту щоб вона знову стала pending
        await db.execute(
            "UPDATE collections SET report_id = NULL WHERE report_id = ?",
            (report_id,),
        )
        cur = await db.execute(
            "DELETE FROM reports WHERE id = ? AND user_id = ?",
            (report_id, WEB_USER_ID),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_collection(collection_id: int) -> bool:
    """Удалить инкассацию (только если ещё не учтена в отчёте)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM collections WHERE id = ? AND user_id = ? AND report_id IS NULL",
            (collection_id, WEB_USER_ID),
        )
        await db.commit()
        return cur.rowcount > 0


# ---------- автоподстановка кассы ----------

async def expected_cash() -> int | None:
    """Сколько наличных должно быть в кассе на начало новой смены.

    Берется конечная касса последнего отчета. Инкассация, учтенная в том
    отчете, уже отнята в close_cash — отдельно корректировать не нужно.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT close_cash FROM reports WHERE user_id = ?"
            " ORDER BY id DESC LIMIT 1",
            (WEB_USER_ID,),
        )
        row = await cur.fetchone()
        return row[0] if row else None
