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

CREATE TABLE IF NOT EXISTS promotions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    title                TEXT NOT NULL,
    start_date           TEXT NOT NULL,
    end_date             TEXT,
    conditions           TEXT NOT NULL,
    cashier_instructions TEXT NOT NULL,
    created_at           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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


SEED_PROMOTIONS = [
    {
        "title": "🎒 Пакет «Школяр» (3 години гри від 130 ₴)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Ігрова перерва після школи — пакет на 3 години гри для відвідувачів до 16 років включно!\n"
            "• Доступний лише у зоні GAMER ZONE (RTX 5060).\n"
            "• Понеділок - Четвер (з 09:00 до 17:00): 130 ₴ за 3 години.\n"
            "• П'ятниця (з 09:00 до 17:00): 180 ₴ за 3 години.\n"
            "• Вихідні (Сб-Нд) та святкові дні (з 09:00 до 15:00): 180 ₴ за 3 години.\n"
            "* Пропозиція діє виключно для відвідувачів віком до 16 років включно."
        ),
        "cashier_instructions": (
            "1. Перевірити вік відвідувача (до 16 років включно, за потреби попросити учнівський квиток або документ).\n"
            "2. Перевірити час: у будні — до 17:00, у вихідні та свята — до 15:00.\n"
            "3. Обрати ПК у зоні GAMER ZONE.\n"
            "4. Пробити пакет «Школяр 3 години»: 130 ₴ (Пн-Чт) або 180 ₴ (Пт-Нд та свята)."
        ),
    },
    {
        "title": "🎖️ Знижка військовослужбовцям (-10%)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Отримай -10% знижки на будь-яке поповнення ігрового балансу!\n"
            "• Знижка поширюється на всі зони клубу.\n"
            "• Пропозиція доступна лише за наявності оригіналу посвідчення УБД (Учасника бойових дій)."
        ),
        "cashier_instructions": (
            "1. Попросити клієнта предʼявити оригінал посвідчення УБД.\n"
            "2. При поповненні балансу застосувати знижку 10% на суму поповнення (або нарахувати бонус згідно з правилами)."
        ),
    },
    {
        "title": "🎓 Студентська знижка (-10%) (Student Discount)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Отримай знижку -10% на всі зони компʼютерного клубу!\n"
            "• Діє для студентів вищих та середніх спеціальних навчальних закладів.\n"
            "• Обовʼязкова наявність дійсного студентського квитка (фізичного або у застосунку «Дія»)."
        ),
        "cashier_instructions": (
            "1. Перевірити дійсність студентського квитка клієнта (термін дії / додаток «Дія»).\n"
            "2. Застосувати знижку 10% на обраний час або пакет у будь-якій зоні (GAMER, PRO, BOOTCAMP, TV)."
        ),
    },
    {
        "title": "👥 Приходь разом з другом (+200 ₴ на баланс)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Приходь разом з другом та отримуйте 200 ₴ на ігровий баланс!\n"
            "• Кількість друзів, яких можна привести — необмежена!\n"
            "• Пропозиція діє тільки для нових користувачів.\n"
            "• Умова активації: поповнення новим клієнтом балансу від 100 ₴."
        ),
        "cashier_instructions": (
            "1. Зареєструвати нового гостя в системі Senet (перевірити, що акаунта раніше не було).\n"
            "2. Прийняти перше поповнення від нового користувача на суму від 100 ₴.\n"
            "3. Нарахувати бонус 200 ₴ на баланс нового гостя.\n"
            "4. Нарахувати бонус 200 ₴ на баланс друга, який його запросив."
        ),
    },
    {
        "title": "⭐ Залиш відгук на Google Maps (1 година безкоштовно)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Залиш відгук про наш клуб на Google Maps — отримай 1 годину гри безкоштовно!\n"
            "• Діє 1 раз для одного клієнта / номера телефону.\n"
            "• Перевірка проводиться касиром через базу Google Відгуків."
        ),
        "cashier_instructions": (
            "1. Попросити гостя показати опублікований відгук на Google Maps.\n"
            "2. Відкрити вкладку «⭐ Відгуки» у CyberHelper, ввести номер телефону або логін.\n"
            "3. Якщо клієнта ще немає у списку — додати запис та нарахувати 1 безкоштовну годину гри на акаунт."
        ),
    },
    {
        "title": "🌅 Тариф «Ранок» (Пн–Чт з 09:00 до 15:00)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Спеціальна знижена ціна на ранкові години:\n"
            "• Діє з Понеділка по Четвер з 09:00 до 15:00.\n"
            "• GAMER ZONE: 50 ₴/год (замість 70 ₴)\n"
            "• PRO ZONE: 60 ₴/год (замість 80 ₴)\n"
            "• BOOTCAMP PRO: 80 ₴/год (замість 100 ₴)\n"
            "• TV ZONE: 130 ₴ за пакет 2 години (замість 300 ₴)"
        ),
        "cashier_instructions": (
            "Тариф активується автоматично в системі з 09:00 до 15:00 у будні дні (Пн-Чт) при виборі погодинної гри."
        ),
    },
    {
        "title": "🌙 Пакет «Ніч 10 годин» (щодня з 22:00 до 08:00)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Нічний пакет діє щодня з 22:00 до 08:00 (10 годин гри):\n"
            "• GAMER ZONE: 350 ₴ (Пн-Чт) / 450 ₴ (Пт-Нд та свята)\n"
            "• PRO ZONE: 400 ₴ (Пн-Чт) / 450 ₴ (Пт-Нд та свята)\n"
            "• BOOTCAMP PRO: 750 ₴ (щодня)\n"
            "• TV ZONE: 450 ₴ (Пн-Чт) / 550 ₴ (Пт-Нд та свята)"
        ),
        "cashier_instructions": (
            "Оформлюється касиром після 22:00 на нічну зміну. Вибрати відповідний пакет «Ніч 10 год» у системі Senet."
        ),
    },
    {
        "title": "⏳ Пакети 30 та 50 годин (не згорають 30 днів)",
        "start_date": "2026-10-07",
        "end_date": None,
        "conditions": (
            "Довгострокові вигідні пакети годин:\n"
            "• Години не згорають протягом 30 днів з моменту покупки.\n"
            "• Після активації пакету неможливо купувати інші пакети, доки не будуть використані ці години.\n"
            "• GAMER ZONE 30 год: 1 699 ₴ (≈56.6 ₴/год)\n"
            "• PRO ZONE 30 год: 1 899 ₴ (≈63.3 ₴/год)\n"
            "• BOOTCAMP PRO 30 год: 2 499 ₴ (≈83.3 ₴/год)"
        ),
        "cashier_instructions": (
            "Попередити гостя, що пакет діє 30 днів і блокує паралельну купівлю інших пакетів до його завершення. Оформити пакет в системі Senet."
        ),
    },
]


async def _seed_default_promotions(db) -> None:
    """Заповнює базу початковими акціями клубу, якщо таблиця порожня."""
    cur = await db.execute("SELECT COUNT(*) FROM promotions")
    row = await cur.fetchone()
    if row and row[0] == 0:
        for p in SEED_PROMOTIONS:
            await db.execute(
                """INSERT INTO promotions
                   (title, start_date, end_date, conditions, cashier_instructions)
                   VALUES (?, ?, ?, ?, ?)""",
                (p["title"], p["start_date"], p["end_date"], p["conditions"], p["cashier_instructions"]),
            )


async def init_db(seed_promotions: bool = True) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        for sql in _MIGRATIONS:
            try:
                await db.execute(sql)
            except aiosqlite.OperationalError:
                pass
        await _migrate_money_to_kopecks(db)
        if seed_promotions:
            await _seed_default_promotions(db)
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
               ORDER BY r.id DESC LIMIT ?""",
            (limit,),
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
               WHERE created_at >= datetime('now', 'localtime', ?)""",
            (f"-{days} days",),
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
        # Видаляємо інкасації, створені суто під цей звіт при закритті зміни,
        # а для зовнішніх інкасацій відв'язуємо report_id, щоб повернути статус pending
        await db.execute(
            "DELETE FROM collections WHERE report_id = ? AND comment = 'Введено при закритті зміни'",
            (report_id,),
        )
        await db.execute(
            "UPDATE collections SET report_id = NULL WHERE report_id = ?",
            (report_id,),
        )
        cur = await db.execute(
            "DELETE FROM reports WHERE id = ?",
            (report_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_collection(collection_id: int) -> bool:
    """Удалить инкассацию (только если ещё не учтена в отчёте)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM collections WHERE id = ? AND report_id IS NULL",
            (collection_id,),
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
            "SELECT close_cash FROM reports ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return row[0] if row else None


# ---------- акції ----------

async def create_promotion(
    title: str,
    start_date: str,
    end_date: str | None,
    conditions: str,
    cashier_instructions: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO promotions
               (title, start_date, end_date, conditions, cashier_instructions)
               VALUES (?, ?, ?, ?, ?)""",
            (title, start_date, end_date, conditions, cashier_instructions),
        )
        await db.commit()
        return cur.lastrowid


async def list_promotions() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, title, start_date, end_date, conditions,
                      cashier_instructions, created_at, updated_at
               FROM promotions
               ORDER BY start_date DESC, id DESC"""
        )
        return await cur.fetchall()


async def get_promotion(promotion_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, title, start_date, end_date, conditions,
                      cashier_instructions, created_at, updated_at
               FROM promotions WHERE id = ?""",
            (promotion_id,),
        )
        return await cur.fetchone()


async def update_promotion(
    promotion_id: int,
    title: str,
    start_date: str,
    end_date: str | None,
    conditions: str,
    cashier_instructions: str,
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE promotions
               SET title = ?, start_date = ?, end_date = ?, conditions = ?,
                   cashier_instructions = ?, updated_at = datetime('now', 'localtime')
               WHERE id = ?""",
            (title, start_date, end_date, conditions, cashier_instructions, promotion_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_promotion(promotion_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM promotions WHERE id = ?",
            (promotion_id,),
        )
        await db.commit()
        return cur.rowcount > 0
