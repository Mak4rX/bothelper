"""Тарифи кіберклубу для калькулятора годин."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

try:
    from zoneinfo import ZoneInfo
    KYIV_TZ = ZoneInfo("Europe/Kyiv")
except Exception:
    KYIV_TZ = None


def get_now_kyiv() -> datetime:
    """Повертає поточний час за Києвом (Europe/Kyiv) для коректного визначення тарифів клубу."""
    if KYIV_TZ:
        return datetime.now(KYIV_TZ)
    return datetime.now()


DayType = Literal["weekday", "weekend"]
PackageType = Literal["hour", "package3", "package5", "package10", "package2", "package30"]

# Пн-Чт (dow 0..3) = weekday, Пт-Нд (dow 4..6) = weekend. Свята вибирає касир вручну.
FRIDAY = 4


def day_type_for_dow(dow: int) -> DayType:
    """Тип дня за днем тижня (0=Пн .. 6=Нд)."""
    return "weekday" if dow < FRIDAY else "weekend"


# Тариф «Ранок»: Пн-Чт з 09:00 включно до 15:00 невключно (як в акції «Ранок»).
MORNING_START_HOUR = 9
MORNING_END_HOUR = 15


def _check_hour(hour: int) -> int:
    if not 0 <= hour <= 23:
        raise ValueError("current_hour must be between 0 and 23")
    return hour


def is_morning_rate_active(current_hour: int | None = None,
                           day_type: DayType = "weekday") -> bool:
    """Чи діє ранковий тариф: тільки у будні (Пн-Чт), з 09:00 до 15:00."""
    hour = _check_hour(get_now_kyiv().hour if current_hour is None else current_hour)
    return day_type == "weekday" and MORNING_START_HOUR <= hour < MORNING_END_HOUR


@dataclass
class PriceOption:
    """Один варіант ціни."""
    name: str
    hours: float
    price: int
    price_per_hour: int


@dataclass
class Zone:
    """Ігрова зона з тарифами."""
    id: str
    name: str
    morning_price: int  # з 09:00 до 16:00

    # Понеділок-Четвер
    weekday_hour: int
    weekday_package3: int
    weekday_package5: int
    weekday_package10: int

    # П'ятниця-Неділя
    weekend_hour: int
    weekend_package3: int
    weekend_package5: int
    weekend_package10: int

    # Для TV Zone є пакет 2 години замість 3
    weekday_package2: int = 0
    weekend_package2: int = 0

    # Пакет 30 годин (однакова ціна у будні та вихідні)
    weekday_package30: int = 0
    weekend_package30: int = 0

    # Тривалість ранкового тарифу (для TV Zone це пакет 2 години за 130 грн, для PC — 1 година)
    morning_hours: int = 1

    def get_options(self, day_type: DayType, current_hour: int | None = None) -> list[PriceOption]:
        """Повертає доступні варіанти; ранковий тариф діє Пн-Чт з 09:00 до 15:00."""
        options = []

        if is_morning_rate_active(current_hour, day_type):
            if self.morning_hours > 1:
                options.append(PriceOption(
                    name=f"🌅 Ранок {self.morning_hours} години (Пн-Чт 09:00–15:00)",
                    hours=self.morning_hours,
                    price=self.morning_price,
                    price_per_hour=self.morning_price // self.morning_hours
                ))
            else:
                options.append(PriceOption(
                    name="🌅 Ранок (Пн-Чт 09:00–15:00)",
                    hours=1,
                    price=self.morning_price,
                    price_per_hour=self.morning_price
                ))

        if day_type == "weekday":
            options.append(PriceOption(
                name="1 година (Пн-Чт)",
                hours=1,
                price=self.weekday_hour,
                price_per_hour=self.weekday_hour
            ))
            if self.weekday_package2:
                options.append(PriceOption(
                    name="Пакет 2 години (Пн-Чт)",
                    hours=2,
                    price=self.weekday_package2,
                    price_per_hour=self.weekday_package2 // 2
                ))
            if self.weekday_package3:
                options.append(PriceOption(
                    name="Пакет 3 години (Пн-Чт)",
                    hours=3,
                    price=self.weekday_package3,
                    price_per_hour=self.weekday_package3 // 3
                ))
            if self.weekday_package5:
                options.append(PriceOption(
                    name="Пакет 5 годин (Пн-Чт)",
                    hours=5,
                    price=self.weekday_package5,
                    price_per_hour=self.weekday_package5 // 5
                ))
            if self.weekday_package10:
                options.append(PriceOption(
                    name="Пакет Ніч 10 годин (Пн-Чт)",
                    hours=10,
                    price=self.weekday_package10,
                    price_per_hour=self.weekday_package10 // 10
                ))
            if self.weekday_package30:
                options.append(PriceOption(
                    name="Пакет 30 год (Пн-Чт)",
                    hours=30,
                    price=self.weekday_package30,
                    price_per_hour=self.weekday_package30 // 30
                ))
        else:  # weekend
            options.append(PriceOption(
                name="1 година (Пт-Нд)",
                hours=1,
                price=self.weekend_hour,
                price_per_hour=self.weekend_hour
            ))
            if self.weekend_package2:
                options.append(PriceOption(
                    name="Пакет 2 години (Пт-Нд)",
                    hours=2,
                    price=self.weekend_package2,
                    price_per_hour=self.weekend_package2 // 2
                ))
            if self.weekend_package3:
                options.append(PriceOption(
                    name="Пакет 3 години (Пт-Нд)",
                    hours=3,
                    price=self.weekend_package3,
                    price_per_hour=self.weekend_package3 // 3
                ))
            if self.weekend_package5:
                options.append(PriceOption(
                    name="Пакет 5 годин (Пт-Нд)",
                    hours=5,
                    price=self.weekend_package5,
                    price_per_hour=self.weekend_package5 // 5
                ))
            if self.weekend_package10:
                options.append(PriceOption(
                    name="Пакет Ніч 10 годин (Пт-Нд)",
                    hours=10,
                    price=self.weekend_package10,
                    price_per_hour=self.weekend_package10 // 10
                ))
            if self.weekend_package30:
                options.append(PriceOption(
                    name="Пакет 30 год (Пт-Нд)",
                    hours=30,
                    price=self.weekend_package30,
                    price_per_hour=self.weekend_package30 // 30
                ))

        return options


# Визначення всіх зон
ZONES = {
    "gamer": Zone(
        id="gamer",
        name="🖥️ PC GAMER ZONE",
        morning_price=50,
        weekday_hour=70,
        weekday_package3=180,
        weekday_package5=275,
        weekday_package10=350,
        weekday_package30=1699,
        weekend_package30=1699,
        weekend_hour=80,
        weekend_package3=210,
        weekend_package5=325,
        weekend_package10=450,
    ),
    "pro": Zone(
        id="pro",
        name="🖥️ PC PRO ZONE",
        morning_price=60,
        weekday_hour=80,
        weekday_package3=210,
        weekday_package5=325,
        weekday_package10=400,
        weekday_package30=1899,
        weekend_package30=1899,
        weekend_hour=90,
        weekend_package3=240,
        weekend_package5=375,
        weekend_package10=450,
    ),
    "bootcamp": Zone(
        id="bootcamp",
        name="🖥️ PC BOOTCAMP PRO",
        morning_price=80,
        weekday_hour=100,
        weekday_package3=270,
        weekday_package5=425,
        weekday_package10=750,
        weekday_package30=2499,
        weekend_package30=2499,
        weekend_hour=120,
        weekend_package3=330,
        weekend_package5=525,
        weekend_package10=750,
    ),
    "tv": Zone(
        id="tv",
        name="🎮 TV ZONE",
        morning_price=130,
        morning_hours=2,
        weekday_hour=170,
        weekday_package2=300,
        weekday_package3=435,
        weekday_package5=0,  # немає пакету 5 годин для TV
        weekday_package10=450,
        weekend_hour=200,
        weekend_package2=340,
        weekend_package3=495,
        weekend_package5=0,
        weekend_package10=550,
    ),
}


# Пакет Школяр — для відвідувачів до 16 років включно, тільки PC GAMER.
# Умови з акції «Школяр»: Пн-Чт 130 ₴ до 17:00, Пт 180 ₴ до 17:00,
# Сб-Нд та свята 180 ₴ до 15:00; початок завжди з 09:00.
SCHOOL_START_HOUR = 9

SCHOOL_PACKAGE = {
    "weekday": {
        "hours": 3,
        "price": 130,
        "end_hour": 17,
        "name": "🎒 ШКОЛЯР 3 години (до 16 років, Пн-Чт 09:00–17:00)",
    },
    "weekend": {
        "hours": 3,
        "price": 180,
        "end_hour": 15,
        "name": "🎒 ШКОЛЯР 3 години (до 16 років, Сб-Нд/свята 09:00–15:00)",
    },
}

SCHOOL_PACKAGE_FRIDAY = {
    "hours": 3,
    "price": 180,
    "end_hour": 17,
    "name": "🎒 ШКОЛЯР 3 години (до 16 років, Пт 09:00–17:00)",
}

SCHOOL_ZONES = {"gamer"}


def get_school_package(day_type: DayType, dow: int | None = None) -> dict:
    """Умови пакета Школяр. П'ятниця у «вихідному» тарифі (180 ₴), але до 17:00 —
    як у будні, тому її не відрізнити від Сб-Нд за одним `day_type`: потрібен `dow`.
    Без `dow` (або якщо касир вручну вибрав інший тип дня) рахуємо за `day_type`."""
    if day_type == "weekend" and dow == FRIDAY:
        return SCHOOL_PACKAGE_FRIDAY
    return SCHOOL_PACKAGE[day_type]


def is_school_package_active(day_type: DayType, current_hour: int | None = None,
                             dow: int | None = None) -> bool:
    """Чи можна зараз продати пакет Школяр для вибраного типу дня."""
    hour = _check_hour(get_now_kyiv().hour if current_hour is None else current_hour)
    school = get_school_package(day_type, dow)
    return SCHOOL_START_HOUR <= hour < school["end_hour"]


def apply_discount(price: int, discount_percent: float) -> int:
    """Знижка на ціну, округлення до цілої гривні."""
    if not 0 <= discount_percent <= 100:
        raise ValueError("discount_percent must be between 0 and 100")
    if discount_percent == 0:
        return price
    return round(price * (100 - discount_percent) / 100)


def calculate_hours(amount: int, zone_id: str, day_type: DayType,
                    current_hour: int | None = None,
                    discount_percent: float = 0,
                    dow: int | None = None) -> list[dict]:
    """Рахує скільки годин можна отримати за дану суму."""
    if zone_id not in ZONES:
        return []

    zone = ZONES[zone_id]
    options = zone.get_options(day_type, current_hour=current_hour)

    results = []
    for opt in options:
        price = apply_discount(opt.price, discount_percent)
        if price > 0 and price <= amount:
            full_packages = amount // price
            remaining = amount % price
            total_hours = full_packages * opt.hours

            results.append({
                "package": opt.name,
                "hours": total_hours,
                "price": full_packages * price,
                "remaining": remaining,
            })

    # Пакет ШКОЛЯР доступний лише в Gamer і тільки до граничного часу.
    if zone_id in SCHOOL_ZONES and is_school_package_active(day_type, current_hour, dow):
        school = get_school_package(day_type, dow)
        price = apply_discount(school["price"], discount_percent)
        if price > 0 and amount >= price:
            packages = amount // price
            remaining = amount % price
            results.append({
                "package": school["name"],
                "hours": packages * school["hours"],
                "price": packages * price,
                "remaining": remaining,
            })

    return results


def calculate_price(hours: float, zone_id: str, day_type: DayType,
                    current_hour: int | None = None,
                    discount_percent: float = 0,
                    dow: int | None = None) -> list[dict]:
    """Рахує скільки коштує задана кількість годин."""
    if zone_id not in ZONES:
        return []

    zone = ZONES[zone_id]
    options = zone.get_options(day_type, current_hour=current_hour)

    results = []
    for opt in options:
        if opt.hours <= hours:
            price = apply_discount(opt.price, discount_percent)
            packages = int(hours / opt.hours)
            remaining_hours = hours - (packages * opt.hours)
            total_price = packages * price

            results.append({
                "package": opt.name,
                "packages": packages,
                "hours_used": packages * opt.hours,
                "price": total_price,
                "remaining_hours": remaining_hours,
            })

    # Пакет ШКОЛЯР доступний в обох напрямках калькулятора.
    if zone_id in SCHOOL_ZONES and is_school_package_active(day_type, current_hour, dow):
        school = get_school_package(day_type, dow)
        if hours >= school["hours"]:
            price = apply_discount(school["price"], discount_percent)
            packages = int(hours / school["hours"])
            remaining_hours = hours - (packages * school["hours"])
            results.append({
                "package": school["name"],
                "packages": packages,
                "hours_used": packages * school["hours"],
                "price": packages * price,
                "remaining_hours": remaining_hours,
            })

    return results


def get_live_pricing_data(current_hour: int | None = None, day_of_week: int | None = None) -> dict:
    """Повертає живі ціни та доступні пакети за зонами на даний момент часу."""
    now = get_now_kyiv()
    hour = now.hour if current_hour is None else current_hour
    dow = now.weekday() if day_of_week is None else day_of_week  # 0=Mon .. 6=Sun
    day_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    day_name = day_names[dow]

    day_type = day_type_for_dow(dow)

    # Ранковий тариф: Пн-Чт з 09:00 до 15:00
    morning_active = is_morning_rate_active(hour, day_type)

    # Нічний пакет: щодня з 22:00 до 08:00
    night_active = (hour >= 22 or hour < 8)

    # Пакет Школяр (умови спільні з калькулятором — див. SCHOOL_PACKAGE)
    school = get_school_package(day_type, dow)
    school_active = is_school_package_active(day_type, hour, dow)
    school_price = school["price"]
    school_window = f"{SCHOOL_START_HOUR:02d}:00–{school['end_hour']:02d}:00 ({'Будні' if dow <= FRIDAY else 'Вихідні'})"

    zones_data = []
    for zone_id, zone in ZONES.items():
        if morning_active:
            morn_h = getattr(zone, "morning_hours", 1)
            if morn_h > 1:
                cur_price = zone.morning_price // morn_h
                price_tag = f"🌅 Ранок (пакет {morn_h}г — {zone.morning_price}₴)"
            else:
                cur_price = zone.morning_price
                price_tag = "🌅 Ранок (активний)"
        elif day_type == "weekday":
            cur_price = zone.weekday_hour
            price_tag = "Звичайний (Пн-Чт)"
        else:
            cur_price = zone.weekend_hour
            price_tag = "Вихідний (Пт-Нд)"

        packages = []
        if morning_active:
            morn_h = getattr(zone, "morning_hours", 1)
            packages.append({
                "name": f"🌅 Пакет Ранок ({morn_h} год)" if morn_h > 1 else "🌅 Ранок (1 год)",
                "hours": morn_h,
                "price": zone.morning_price,
                "price_per_hour": round(zone.morning_price / morn_h, 1) if morn_h > 1 else zone.morning_price,
                "active_now": True,
                "note": f"Пакет {morn_h} год · Пн-Чт 09:00–15:00" if morn_h > 1 else "Діє Пн-Чт 09:00–15:00"
            })

        std_hour = zone.weekday_hour if day_type == "weekday" else zone.weekend_hour
        packages.append({
            "name": "1 година",
            "hours": 1,
            "price": std_hour,
            "price_per_hour": std_hour,
            "active_now": not morning_active and not night_active,
            "note": "Базовий тариф"
        })

        pkg2 = zone.weekday_package2 if day_type == "weekday" else zone.weekend_package2
        if pkg2:
            packages.append({
                "name": "Пакет 2 години",
                "hours": 2,
                "price": pkg2,
                "price_per_hour": pkg2 // 2,
                "active_now": True,
                "note": "Тільки TV Zone"
            })

        pkg3 = zone.weekday_package3 if day_type == "weekday" else zone.weekend_package3
        if pkg3:
            packages.append({
                "name": "Пакет 3 години",
                "hours": 3,
                "price": pkg3,
                "price_per_hour": pkg3 // 3,
                "active_now": True,
                "note": f"Вигода: {pkg3 // 3} ₴/год"
            })

        pkg5 = zone.weekday_package5 if day_type == "weekday" else zone.weekend_package5
        if pkg5:
            packages.append({
                "name": "Пакет 5 годин",
                "hours": 5,
                "price": pkg5,
                "price_per_hour": pkg5 // 5,
                "active_now": True,
                "note": f"Вигода: {pkg5 // 5} ₴/год"
            })

        if zone_id == "gamer":
            packages.append({
                "name": "🎒 Пакет Школяр (3 год)",
                "hours": 3,
                "price": school_price,
                "price_per_hour": round(school_price / 3, 1),
                "active_now": school_active,
                "note": f"До 16 р. · {school_window}"
            })

        pkg10 = zone.weekday_package10 if day_type == "weekday" else zone.weekend_package10
        if pkg10:
            packages.append({
                "name": "🌙 Пакет Ніч (10 год)",
                "hours": 10,
                "price": pkg10,
                "price_per_hour": pkg10 // 10,
                "active_now": night_active,
                "note": "22:00–08:00 щодня"
            })

        pkg30 = zone.weekday_package30
        if pkg30:
            packages.append({
                "name": "⏳ Пакет 30 годин",
                "hours": 30,
                "price": pkg30,
                "price_per_hour": round(pkg30 / 30, 1),
                "active_now": True,
                "note": "Не згорає 30 днів"
            })

        zones_data.append({
            "id": zone.id,
            "name": zone.name,
            "current_hour_price": cur_price,
            "price_tag": price_tag,
            "morning_price": zone.morning_price,
            "morning_hours": getattr(zone, "morning_hours", 1),
            "standard_hour": std_hour,
            "packages": packages
        })

    return {
        "hour": hour,
        "minute": now.minute if current_hour is None else 0,
        "dow": dow,
        "day_name": day_name,
        "day_type": day_type,
        "day_type_label": "Будні (Пн–Чт)" if day_type == "weekday" else "Вихідні / свята (Пт–Нд)",
        "morning_active": morning_active,
        "night_active": night_active,
        "school_active": school_active,
        "school_price": school_price,
        "zones": zones_data
    }
