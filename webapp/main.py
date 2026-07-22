"""FastAPI веб-приложение для управления кассой киберклуба."""

import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
sys.path.append(str(Path(__file__).parent.parent))

from shifts import SCHEMES, build_report, fmt
import db_web as db
from pricing import ZONES, calculate_hours, calculate_price

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

class ReportCreate(BaseModel):
    shift: str       # 'day' | 'night'
    open_cash: int
    close_cash: int  # фізична каса в кінці зміни
    expenses: int
    senet: int


class CollectionCreate(BaseModel):
    amount: int
    comment: Optional[str] = None


class ReportResponse(BaseModel):
    id: int
    shift: str
    open_cash: int
    earned: int
    expenses: int
    close_cash: int
    senet: int
    surplus: int
    report_text: str
    created_at: str
    collection_amount: Optional[int] = None


class StatsResponse(BaseModel):
    cnt: int
    earned: int
    expenses: int
    surplus: int


# ---------- API endpoints ----------

@app.get("/")
async def root():
    """Отдаем главную страницу"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/expected-cash")
async def get_expected_cash():
    """Ожидаемая сумма в кассе (из последнего отчета)"""
    cash = await db.expected_cash()
    return {"expected_cash": cash}


@app.get("/api/pending-collection")
async def get_pending_collection():
    """Неучтенная инкассация"""
    pending = await db.pending_collection()
    if not pending:
        return {"has_pending": False}
    return {
        "has_pending": True,
        "id": pending["id"],
        "amount": pending["amount"],
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

        # Проверяем неучтенную инкассацию
        pending = await db.pending_collection()
        collection_id = pending["id"] if pending else None
        collected = pending["amount"] if pending else 0

        # Генерируем отчет
        text, earned, surplus = build_report(
            scheme, data.open_cash, data.close_cash, data.expenses,
            data.senet, collection=collected
        )

        # Сохраняем
        report_id = await db.save_report(
            shift=data.shift,
            open_cash=data.open_cash,
            earned=earned,
            expenses=data.expenses,
            collection_id=collection_id,
            close_cash=data.close_cash,
            senet=data.senet,
            surplus=surplus,
            report_text=text,
        )

        log.info(f"Создан отчет #{report_id}, смена: {data.shift}, излишек: {surplus}")

        return {
            "id": report_id,
            "report_text": text,
            "close_cash": data.close_cash,
            "earned": earned,
            "surplus": surplus,
            "collection_amount": collected if collected else None,
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
            open_cash=row["open_cash"],
            earned=row["earned"],
            expenses=row["expenses"],
            close_cash=row["close_cash"],
            senet=row["senet"],
            surplus=row["surplus"],
            report_text=row["report_text"],
            created_at=row["created_at"],
            collection_amount=row["collection_amount"],
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
        earned=row["earned"],
        expenses=row["expenses"],
        surplus=row["surplus"],
    )


@app.post("/api/collections")
async def create_collection(data: CollectionCreate):
    """Записать инкассацию"""
    try:
        if data.amount <= 0:
            raise HTTPException(400, "Amount must be positive")

        collection_id = await db.add_collection(data.amount, data.comment)
        log.info(f"Создана инкассация #{collection_id}, сумма: {data.amount}")
        return {"id": collection_id, "amount": data.amount, "comment": data.comment}
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
            "amount": row["amount"],
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
            "weekday_hour": zone.weekday_hour,
            "weekend_hour": zone.weekend_hour,
        }
        for zone in ZONES.values()
    ]


@app.get("/api/calculator/money-to-hours")
async def money_to_hours(amount: int, zone: str, day_type: str):
    """Калькулятор: сумма → часы"""
    if day_type not in ["weekday", "weekend"]:
        raise HTTPException(400, "day_type must be 'weekday' or 'weekend'")

    results = calculate_hours(amount, zone, day_type)
    return {"amount": amount, "zone": zone, "day_type": day_type, "options": results}


@app.get("/api/calculator/hours-to-money")
async def hours_to_money(hours: float, zone: str, day_type: str):
    """Калькулятор: часы → сумма"""
    if day_type not in ["weekday", "weekend"]:
        raise HTTPException(400, "day_type must be 'weekday' or 'weekend'")

    results = calculate_price(hours, zone, day_type)
    return {"hours": hours, "zone": zone, "day_type": day_type, "options": results}


# Статические файлы последними
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
