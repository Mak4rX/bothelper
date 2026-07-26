"""Telegram-бот помічник для киберклубу.

Головна функція — генерація звіту «Закриття зміни»:
діалогом збирає цифри, сам рахує кінцеву касу та надлишок/недостачу.
Початкову касу підставляє з попередньої зміни, підтримує інкасацію.
Керування — кнопками внизу екрана (slash-команди теж працюють).
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import db
from config import BOT_TOKEN, ALLOWED_IDS
from shifts import SCHEMES, build_report, fmt

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Тексти кнопок головного меню
BTN_REPORT = "📋 Закриття зміни"
BTN_COLLECT = "💰 Інкасація"
BTN_HISTORY = "🕓 Історія"
BTN_STATS = "📊 Статистика"
BTN_CANCEL = "❌ Скасувати"


class ReportForm(StatesGroup):
    open_cash  = State()   # каса на початку зміни
    close_cash = State()   # каса в кінці зміни (фізична)
    expenses   = State()   # торгівельні витрати
    senet      = State()   # нараховано у сенеті


class CollectForm(StatesGroup):
    amount = State()      # сума інкасації
    comment = State()     # коментар (необов'ково)


# ---------- допоміжне ----------

def allowed(user_id: int) -> bool:
    return not ALLOWED_IDS or user_id in ALLOWED_IDS


def parse_amount(text: str) -> int | None:
    """Приймає '886', '8 680', '8,680'. Повертає None, якщо не число."""
    cleaned = text.replace(" ", "").replace(",", "").strip()
    if cleaned.lstrip("-").isdigit():
        return int(cleaned)
    return None


def main_keyboard() -> ReplyKeyboardMarkup:
    """Постійна клавіатура внизу екрана."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_REPORT), KeyboardButton(text=BTN_COLLECT)],
            [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def shift_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="☀️ Денна", callback_data="shift:day"),
        InlineKeyboardButton(text="🌙 Нічна", callback_data="shift:night"),
    ]])


def confirm_keyboard(yes: str, no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Так", callback_data=yes),
        InlineKeyboardButton(text="✏️ Ні, введу сам", callback_data=no),
    ]])


# ---------- старт / скасування ----------

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    if not allowed(msg.from_user.id):
        return await msg.answer("⛔ У тебе немає доступу до цього бота.")
    await msg.answer(
        "Привіт! Я бот-помічник киберклубу 🤖\n\n"
        "Керуй мною кнопками внизу екрана 👇",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("cancel"))
@dp.message(F.text == BTN_CANCEL)
async def cmd_cancel(msg: Message, state: FSMContext):
    if await state.get_state() is None:
        return await msg.answer("Нічого скасовувати.", reply_markup=main_keyboard())
    await state.clear()
    await msg.answer("Скасовано ✅", reply_markup=main_keyboard())


# ---------- кнопки головного меню ----------
# ВАЖЛИВО: зареєстровані ДО FSM-хендлерів — кнопки працюють навіть
# посеред діалогу (текст кнопки не сприйметься як число).

@dp.message(Command("report"))
@dp.message(F.text == BTN_REPORT)
async def cmd_report(msg: Message, state: FSMContext):
    if not allowed(msg.from_user.id):
        return await msg.answer("⛔ У тебе немає доступу.")
    await state.clear()
    await msg.answer("Яка зміна закривається?", reply_markup=shift_keyboard())


@dp.message(Command("history"))
@dp.message(F.text == BTN_HISTORY)
async def cmd_history(msg: Message):
    if not allowed(msg.from_user.id):
        return await msg.answer("⛔ У тебе немає доступу.")
    rows = await db.last_reports(msg.from_user.id, limit=5)
    if not rows:
        return await msg.answer("Звітів поки немає. Натисни «📋 Закриття зміни».",
                                reply_markup=main_keyboard())
    for row in rows:
        icon = "☀️" if row["shift"] == "day" else "🌙"
        await msg.answer(f"{icon} {row['created_at']}\n\n{row['report_text']}")


@dp.message(Command("stats"))
@dp.message(F.text == BTN_STATS)
async def cmd_stats(msg: Message):
    if not allowed(msg.from_user.id):
        return await msg.answer("⛔ У тебе немає доступу.")

    parts: list[str] = []
    for days, title in ((7, "7 днів"), (30, "30 днів")):
        row = await db.stats(msg.from_user.id, days)
        if row and row["cnt"]:
            parts.append(
                f"📊 За {title}:\n"
                f"• Звітів: {row['cnt']}\n"
                f"• Зароблено готівки: {fmt(row['earned'])} грн\n"
                f"• Витрати: {fmt(row['expenses'])} грн\n"
                f"• Надлишок/недостача: {fmt(row['surplus'])} грн"
            )
        else:
            parts.append(f"📊 За {title}: звітів немає.")
    await msg.answer("\n\n".join(parts), reply_markup=main_keyboard())


# ---------- інкасація ----------

@dp.message(Command("collect"))
@dp.message(F.text == BTN_COLLECT)
async def cmd_collect(msg: Message, state: FSMContext):
    if not allowed(msg.from_user.id):
        return await msg.answer("⛔ У тебе немає доступу.")
    await state.clear()
    await state.set_state(CollectForm.amount)

    text = "💰 Інкасація.\n\nСкільки готівки забрано з каси? (грн)"
    pending = await db.pending_collection(msg.from_user.id)
    if pending:
        text += (
            f"\n\n⚠️ Попередня інкасація {fmt(pending['amount'])} грн "
            f"({pending['created_at']}) ще не врахована в жодному звіті — "
            "буде додана до наступного звіту разом з цією."
        )
    await msg.answer(text)


@dp.message(CollectForm.amount)
async def collect_amount(msg: Message, state: FSMContext):
    value = parse_amount(msg.text)
    if value is None or value <= 0:
        return await msg.answer("Введи суму більше нуля, наприклад: 5000")
    await state.update_data(amount=value)
    await state.set_state(CollectForm.comment)
    await msg.answer("Коментар? (наприклад: «забрав власник»).\n"
                     "Якщо не треба — надішли «-»")


@dp.message(CollectForm.comment)
async def collect_comment(msg: Message, state: FSMContext):
    comment = None if msg.text.strip() == "-" else msg.text.strip()
    data = await state.get_data()
    await state.clear()

    await db.add_collection(msg.from_user.id, data["amount"], comment)
    text = f"✅ Інкасацію записано: {fmt(data['amount'])} грн"
    if comment:
        text += f" ({comment})"
    text += "\nВона буде врахована в наступному звіті «Закриття зміни»."
    await msg.answer(text, reply_markup=main_keyboard())


# ---------- діалог генерації звіту (FSM) ----------

@dp.callback_query(F.data.startswith("shift:"))
async def pick_shift(cb: CallbackQuery, state: FSMContext):
    scheme = SCHEMES[cb.data.split(":", 1)[1]]
    await state.update_data(shift=scheme.code, collection_id=None)
    await cb.answer()

    # Автопідстановка каси з попередньої зміни
    expected = await db.expected_cash(cb.from_user.id)
    if expected is not None:
        await state.update_data(suggested_open=expected)
        await cb.message.edit_text(
            f"{scheme.title}.\n\n"
            f"За минулим звітом у касі має бути {fmt(expected)} грн.\n"
            f"{scheme.open_label} — підтверджуєш цю суму?",
            reply_markup=confirm_keyboard("open:suggested", "open:manual"),
        )
    else:
        await state.set_state(ReportForm.open_cash)
        await cb.message.edit_text(
            f"{scheme.title}.\n\n{scheme.open_label}? (грн)"
        )


@dp.callback_query(F.data == "open:suggested")
async def open_suggested(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    scheme = SCHEMES[data["shift"]]
    await state.update_data(open_cash=data["suggested_open"])
    await state.set_state(ReportForm.close_cash)
    await cb.message.edit_text(f"{scheme.close_label}? (порахуй скільки зараз у касі, грн)")
    await cb.answer()


@dp.callback_query(F.data == "open:manual")
async def open_manual(cb: CallbackQuery, state: FSMContext):
    scheme = SCHEMES[(await state.get_data())["shift"]]
    await state.set_state(ReportForm.open_cash)
    await cb.message.edit_text(f"{scheme.open_label}? Введи суму вручну (грн)")
    await cb.answer()


@dp.message(ReportForm.open_cash)
async def got_open(msg: Message, state: FSMContext):
    value = parse_amount(msg.text)
    if value is None or value < 0:
        return await msg.answer("Введи число, наприклад: 7791")
    await state.update_data(open_cash=value)

    data = await state.get_data()
    scheme = SCHEMES[data["shift"]]

    # Попередження про розбіжність з попередньою зміною
    suggested = data.get("suggested_open")
    if suggested is not None and suggested != value:
        diff = value - suggested
        sign = "+" if diff > 0 else "−"
        await msg.answer(
            f"⚠️ Розбіжність з минулою зміною: {sign}{fmt(abs(diff))} грн "
            f"(за звітом було {fmt(suggested)}, ти приймаєш {fmt(value)})."
        )

    await state.set_state(ReportForm.close_cash)
    await msg.answer(f"{scheme.close_label}? (порахуй скільки зараз у касі, грн)")


@dp.message(ReportForm.close_cash)
async def got_close_cash(msg: Message, state: FSMContext):
    value = parse_amount(msg.text)
    if value is None or value < 0:
        return await msg.answer("Введи число, наприклад: 2952")
    await state.update_data(close_cash=value)
    await state.set_state(ReportForm.expenses)
    await msg.answer("Торгівельні витрати? (грн, якщо немає — 0)")


@dp.message(ReportForm.expenses)
async def got_expenses(msg: Message, state: FSMContext):
    value = parse_amount(msg.text)
    if value is None or value < 0:
        return await msg.answer("Введи число, наприклад: 0 або 150")
    await state.update_data(expenses=value)

    data = await state.get_data()
    scheme = SCHEMES[data["shift"]]

    # Чи є неврахована інкасація?
    pending = await db.pending_collection(msg.from_user.id)
    if pending:
        comment = f" ({pending['comment']})" if pending["comment"] else ""
        await state.update_data(collection_id=pending["id"])
        await msg.answer(
            f"💰 Є неврахована інкасація: {fmt(pending['amount'])} грн{comment}.\n"
            f"Вона буде віднята в цьому звіті."
        )

    collected = pending["amount"] if pending else 0
    earned_calc = data["close_cash"] - data["open_cash"] + value + collected
    await state.set_state(ReportForm.senet)
    await msg.answer(
        f"Скільки готівки нарахував у сенеті? (грн)\n\n"
        f"ℹ️ Розраховане зароблено: {fmt(earned_calc)} грн"
    )


@dp.message(ReportForm.senet)
async def got_senet(msg: Message, state: FSMContext):
    value = parse_amount(msg.text)
    if value is None or value < 0:
        return await msg.answer("Введи число, наприклад: 9569")

    data = await state.get_data()
    scheme = SCHEMES[data["shift"]]

    collection_id = data.get("collection_id")
    collected = 0
    if collection_id is not None:
        row = await db.get_collection(collection_id)
        collected = row["amount"] if row else 0

    text, earned, surplus = build_report(
        scheme, data["open_cash"], data["close_cash"], data["expenses"],
        value, collection=collected,
    )
    await db.save_report(
        user_id=msg.from_user.id,
        shift=scheme.code,
        open_cash=data["open_cash"],
        earned=earned,
        expenses=data["expenses"],
        collection_id=collection_id,
        close_cash=data["close_cash"],
        senet=value,
        surplus=surplus,
        report_text=text,
    )
    await state.clear()
    await msg.answer(text, reply_markup=main_keyboard())


# ---------- запуск ----------

async def main():
    await db.init_db()
    log.info("Бот запущений")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
