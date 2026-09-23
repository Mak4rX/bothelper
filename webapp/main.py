"""FastAPI веб-приложение для управления кассой киберклуба."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
sys.path.append(str(Path(__file__).parent.parent))

from shifts import SCHEMES, build_report, fmt
import db_web as db
from pricing import (
    ZONES,
    calculate_compensation,
    calculate_hours,
    calculate_price,
    is_morning_rate_active,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Инициализация базы данных...")
    await db.init_db()
    log.info("Веб-приложение запущено")
    yield
    # Shutdown
    log.info("Веб-приложение остановлено")


app = FastAPI(
    title="BotHelper Web",
    description="Веб-интерфейс для управления кассой киберклуба",
    version="1.0.0",
    lifespan=lifespan
)

# CORS настройки (в продакшене укажите конкретные домены)
ALLOWED_ORIGINS = ["*"]  # TODO: заменить на конкретные домены в продакшене

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Модели ----------

def to_kopecks(grivnas: float) -> int:
    """Переводить гривні (можливо дробові з копійками) у копійки.

    Рахуємо цілими копійками — float для грошей не тримаємо ніде далі.
    Погрішність float на рівні 1e-9 приводимо round() до найближчої копійки.
    """
    return round(grivnas * 100)


def to_grivnas(kopecks: int) -> int | float:
    """Назад для API-відповіді: ціле число, якщо копійок 0, інакше float з 2 знаками."""
    kopecks = int(kopecks)
    return kopecks // 100 if kopecks % 100 == 0 else round(kopecks / 100, 2)


class ReportCreate(BaseModel):
    shift: str          # 'day' | 'night'
    open_cash: float    # приймаємо копійки: 11142.5 або 11142,50
    close_cash: float   # фізична каса в кінці зміни
    expenses: float = 0
    collection: float = 0  # інкасація, введена у формі закриття зміни
    senet: float = 0
    note: str = ""      # необов'язкова нотатка до результату


class CollectionCreate(BaseModel):
    amount: float
    comment: Optional[str] = None


class ReportResponse(BaseModel):
    id: int
    shift: str
    open_cash: float
    earned: float
    expenses: float
    close_cash: float
    senet: float
    surplus: float
    report_text: str
    created_at: str
    collection_amount: Optional[float] = None


class StatsResponse(BaseModel):
    cnt: int
    earned: float
    expenses: float
    surplus: float


# ---------- API endpoints ----------

@app.get("/")
async def root():
    """Отдаем главную страницу"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
@app.get("/favicon-16x16.png", include_in_schema=False)
@app.get("/favicon-32x32.png", include_in_schema=False)
@app.get("/favicon-48x48.png", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/android-chrome-192x192.png", include_in_schema=False)
@app.get("/android-chrome-512x512.png", include_in_schema=False)
@app.get("/logo.png", include_in_schema=False)
@app.get("/logo.svg", include_in_schema=False)
@app.get("/site.webmanifest", include_in_schema=False)
@app.get("/manifest.json", include_in_schema=False)
async def static_root_files(request: Request):
    filename = request.url.path.lstrip("/")
    file_path = Path(__file__).parent / "static" / filename
    if file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/expected-cash")
async def get_expected_cash():
    """Ожидаемая сумма в кассе (из последнего отчета). У гривнях з копійками."""
    cash = await db.expected_cash()
    return {"expected_cash": to_grivnas(cash) if cash is not None else None}


@app.get("/api/pending-collection")
async def get_pending_collection():
    """Неучтенная инкассация"""
    pending = await db.pending_collection()
    if not pending:
        return {"has_pending": False}
    return {
        "has_pending": True,
        "id": pending["id"],
        "amount": to_grivnas(pending["amount"]),
        "comment": pending["comment"],
        "created_at": pending["created_at"],
    }


@app.post("/api/reports")
async def create_report(data: ReportCreate):
    """Создать отчет о закрытии смены"""
    try:
        if data.shift not in SCHEMES:
            raise HTTPException(400, "Invalid shift type")

        scheme = SCHEMES[data.shift]

        # Переводимо гривні (з можливими копійками) у копійки — все далі й зберігаємо цілими
        open_cash = to_kopecks(data.open_cash)
        close_cash = to_kopecks(data.close_cash)
        expenses = to_kopecks(data.expenses)
        senet = to_kopecks(data.senet)
        collection = to_kopecks(data.collection)

        if collection < 0:
            raise HTTPException(400, "Collection amount cannot be negative")

        # Если ранее была сохранена неучтенная инкассация, используем её.
        # Если кассир ввёл сумму прямо в закрытии смены — создаём запись здесь.
        pending = await db.pending_collection()
        collection_id = None
        collected = collection

        if pending and collection > 0:
            collection_id = pending["id"]
            if collection != pending["amount"]:
                await db.update_pending_collection(collection_id, collection)
        elif pending and collection == 0:
            await db.delete_collection(pending["id"])
        elif collection > 0:
            collection_id = await db.add_collection(collection, "Введено при закритті зміни")

        # Генерируем отчет (усі суми — копійки)
        text, earned, surplus = build_report(
            scheme, open_cash, close_cash, expenses,
            senet, collection=collected, note=data.note
        )

        # Сохраняем
        report_id = await db.save_report(
            shift=data.shift,
            open_cash=open_cash,
            earned=earned,
            expenses=expenses,
            collection_id=collection_id,
            close_cash=close_cash,
            senet=senet,
            surplus=surplus,
            report_text=text,
        )

        log.info(f"Создан отчет #{report_id}, смена: {data.shift}, излишек: {surplus}")

        return {
            "id": report_id,
            "shift": data.shift,
            "open_cash": to_grivnas(open_cash),
            "earned": to_grivnas(earned),
            "expenses": to_grivnas(expenses),
            "close_cash": to_grivnas(close_cash),
            "senet": to_grivnas(senet),
            "surplus": to_grivnas(surplus),
            "report_text": text,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "collection_amount": to_grivnas(collected) if collected else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Ошибка при создании отчета: {e}")
        raise HTTPException(500, f"Internal server error: {str(e)}")


@app.get("/api/reports", response_model=list[ReportResponse])
async def get_reports(limit: int = 20):
    """Получить последние отчеты"""
    rows = await db.last_reports(limit=limit)
    result = []
    for row in rows:
        result.append(ReportResponse(
            id=row["id"],
            shift=row["shift"],
            open_cash=to_grivnas(row["open_cash"]),
            earned=to_grivnas(row["earned"]),
            expenses=to_grivnas(row["expenses"]),
            close_cash=to_grivnas(row["close_cash"]),
            senet=to_grivnas(row["senet"]),
            surplus=to_grivnas(row["surplus"]),
            report_text=row["report_text"],
            created_at=row["created_at"],
            collection_amount=to_grivnas(row["collection_amount"]) if row["collection_amount"] is not None else None,
        ))
    return result


@app.get("/api/stats")
async def get_stats(days: int = 7):
    """Статистика за N дней"""
    row = await db.stats(days)
    if not row or not row["cnt"]:
        return StatsResponse(cnt=0, earned=0, expenses=0, surplus=0)
    return StatsResponse(
        cnt=row["cnt"],
        earned=to_grivnas(row["earned"]),
        expenses=to_grivnas(row["expenses"]),
        surplus=to_grivnas(row["surplus"]),
    )


@app.post("/api/collections")
async def create_collection(data: CollectionCreate):
    """Записать инкассацию"""
    try:
        amount_kop = to_kopecks(data.amount)
        if amount_kop <= 0:
            raise HTTPException(400, "Amount must be positive")

        collection_id = await db.add_collection(amount_kop, data.comment)
        log.info(f"Создана инкассация #{collection_id}, сумма: {amount_kop}")
        return {"id": collection_id, "amount": to_grivnas(amount_kop), "comment": data.comment}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Ошибка при создании инкассации: {e}")
        raise HTTPException(500, f"Internal server error: {str(e)}")


@app.get("/api/collections")
async def get_collections(limit: int = 10):
    """Последние инкассации"""
    rows = await db.last_collections(limit=limit)
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "amount": to_grivnas(row["amount"]),
            "comment": row["comment"],
            "report_id": row["report_id"],
            "created_at": row["created_at"],
        })
    return result


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: int):
    """Удалить отчет по ID"""
    deleted = await db.delete_report(report_id)
    if not deleted:
        raise HTTPException(404, "Report not found")
    log.info(f"Удален отчет #{report_id}")
    return {"ok": True}


@app.delete("/api/collections/{collection_id}")
async def delete_collection(collection_id: int):
    """Удалить инкассацию (только неучтённую)"""
    deleted = await db.delete_collection(collection_id)
    if not deleted:
        raise HTTPException(404, "Collection not found or already used in a report")
    log.info(f"Удалена инкассация #{collection_id}")
    return {"ok": True}


@app.get("/api/zones")
async def get_zones():
    """Список всех игровых зон с тарифами"""
    return [
        {
            "id": zone.id,
            "name": zone.name,
            "morning_price": zone.morning_price,
            "morning_active": is_morning_rate_active(),
            "morning_hours": "09:00–16:00",
            "weekday_hour": zone.weekday_hour,
            "weekend_hour": zone.weekend_hour,
            "package30": zone.weekday_package30,
        }
        for zone in ZONES.values()
    ]


@app.get("/api/calculator/money-to-hours")
async def money_to_hours(
    amount: int,
    zone: str,
    day_type: str,
    current_hour: int | None = Query(default=None, ge=0, le=23),
    discount: float = Query(default=0, ge=0, le=100),
):
    """Калькулятор: сумма → часы."""
    if day_type not in ["weekday", "weekend"]:
        raise HTTPException(400, "day_type must be 'weekday' or 'weekend'")

    results = calculate_hours(amount, zone, day_type, current_hour=current_hour,
                              discount_percent=discount)
    return {
        "amount": amount,
        "zone": zone,
        "day_type": day_type,
        "discount": discount,
        "morning_active": is_morning_rate_active(current_hour),
        "options": results,
    }


@app.get("/api/calculator/hours-to-money")
async def hours_to_money(
    hours: float,
    zone: str,
    day_type: str,
    current_hour: int | None = Query(default=None, ge=0, le=23),
    discount: float = Query(default=0, ge=0, le=100),
):
    """Калькулятор: часы → сумма."""
    if day_type not in ["weekday", "weekend"]:
        raise HTTPException(400, "day_type must be 'weekday' or 'weekend'")

    results = calculate_price(hours, zone, day_type, current_hour=current_hour,
                              discount_percent=discount)
    return {
        "hours": hours,
        "zone": zone,
        "day_type": day_type,
        "discount": discount,
        "morning_active": is_morning_rate_active(current_hour),
        "options": results,
    }


@app.get("/api/calculator/compensation")
async def get_compensation(
    amount: float = Query(ge=0),
    percent: float = Query(default=35, ge=0, le=100),
):
    """Калькулятор: компенсація / кешбек та знижка."""
    try:
        return calculate_compensation(amount, percent)
    except ValueError as e:
        raise HTTPException(400, str(e))


# Статические файлы последними
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
