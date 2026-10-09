"""FastAPI веб-застосунок CyberHelper: тарифи, калькулятор годин і база Google Відгуків.

Звіти змін, акції та каса зберігаються в localStorage браузера — сервер їх не бачить
і власної бази даних не має (на Vercel файлова система не постійна).
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import sys
sys.path.append(str(Path(__file__).parent.parent))

from pricing import (
    ZONES,
    calculate_hours,
    calculate_price,
    day_type_for_dow,
    get_live_pricing_data,
    get_now_kyiv,
    is_morning_rate_active,
)
import reviews

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Фронтенд віддається з цього ж домену, тому CORS не потрібен.
app = FastAPI(
    title="CyberHelper Web",
    description="Тарифи та калькулятор годин для комп'ютерного клубу",
    version="2.0.0",
)

STATIC_DIR = Path(__file__).parent / "static"

DAY_TYPES = ("weekday", "weekend")


def _check_day_type(day_type: str) -> None:
    if day_type not in DAY_TYPES:
        raise HTTPException(400, "day_type must be 'weekday' or 'weekend'")


# ---------- Сторінка і статичні файли ----------

@app.get("/")
async def root():
    """Головна сторінка."""
    return FileResponse(STATIC_DIR / "index.html")


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
    file_path = STATIC_DIR / filename
    if file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


# ---------- Тарифи і калькулятор ----------

@app.get("/api/zones")
async def get_zones():
    """Список усіх ігрових зон з тарифами."""
    now = get_now_kyiv()
    morning_now = is_morning_rate_active(now.hour, day_type_for_dow(now.weekday()))
    return [
        {
            "id": zone.id,
            "name": zone.name,
            "morning_price": zone.morning_price,
            "morning_hours_count": zone.morning_hours,
            "morning_active": morning_now,
            "morning_hours": "Пн–Чт 09:00–15:00",
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
    dow: int | None = Query(default=None, ge=0, le=6, description="День тижня, 0=Пн"),
    discount: float = Query(default=0, ge=0, le=100),
):
    """Калькулятор: сума → години."""
    _check_day_type(day_type)
    results = calculate_hours(amount, zone, day_type, current_hour=current_hour,
                              discount_percent=discount, dow=dow)
    return {
        "amount": amount,
        "zone": zone,
        "day_type": day_type,
        "discount": discount,
        "morning_active": is_morning_rate_active(current_hour, day_type),
        "options": results,
    }


@app.get("/api/calculator/hours-to-money")
async def hours_to_money(
    hours: float,
    zone: str,
    day_type: str,
    current_hour: int | None = Query(default=None, ge=0, le=23),
    dow: int | None = Query(default=None, ge=0, le=6, description="День тижня, 0=Пн"),
    discount: float = Query(default=0, ge=0, le=100),
):
    """Калькулятор: години → сума."""
    _check_day_type(day_type)
    results = calculate_price(hours, zone, day_type, current_hour=current_hour,
                              discount_percent=discount, dow=dow)
    return {
        "hours": hours,
        "zone": zone,
        "day_type": day_type,
        "discount": discount,
        "morning_active": is_morning_rate_active(current_hour, day_type),
        "options": results,
    }


@app.get("/api/pricing/live")
async def live_pricing(
    hour: int | None = Query(default=None, ge=0, le=23),
    dow: int | None = Query(default=None, ge=0, le=6),
):
    """Актуальні тарифи в усіх зонах та діючі пакети на поточний (або обраний) день і час."""
    return get_live_pricing_data(current_hour=hour, day_of_week=dow)


# ---------- Google Відгуки ----------

@app.get("/api/reviews/database")
def get_reviews_database(refresh: bool = False):
    """Список контактів з Google Таблиці (кешований).

    Звичайна `def`, не `async def`: завантаження таблиці синхронне, і FastAPI
    виконає його в пулі потоків, не блокуючи event loop.
    """
    entries = reviews.fetch_database(force_refresh=refresh)
    return {
        "total": len(entries),
        "entries": entries,
        "spreadsheet_id": reviews.SPREADSHEET_ID,
        "gid": reviews.DATA_GID,
    }


# Статичні файли останніми
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
