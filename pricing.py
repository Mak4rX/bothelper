"""Тарифи кіберклубу для калькулятора годин."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

DayType = Literal["weekday", "weekend"]
PackageType = Literal["hour", "package3", "package5", "package10", "package2", "package30"]

MORNING_START_HOUR = 9
MORNING_END_HOUR = 16


def is_morning_rate_active(current_hour: int | None = None) -> bool:
    """Чи діє ранковий тариф: з 09:00 включно до 16:00 невключно."""
    hour = datetime.now().hour if current_hour is None else current_hour
    if not 0 <= hour <= 23:
        raise ValueError("current_hour must be between 0 and 23")
    return MORNING_START_HOUR <= hour < MORNING_END_HOUR


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

    def get_options(self, day_type: DayType, current_hour: int | None = None) -> list[PriceOption]:
        """Повертає доступні варіанти; ранковий тариф діє з 09:00 до 16:00."""
        options = []

        if is_morning_rate_active(current_hour):
            options.append(PriceOption(
                name="🌅 Ранок (09:00–16:00)",
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
        name="🖥️ PC GAMER ZONE (RTX 5060)",
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
        name="🖥️ PC PRO ZONE (RTX 5060Ti)",
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
        name="🖥️ PC BOOTCAMP PRO (RTX 5070)",
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
        name="🎮 TV ZONE (Консолі)",
        morning_price=130,
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
SCHOOL_PACKAGE = {
    "weekday": {
        "hours": 3,
        "price": 130,
        "end_hour": 15,
        "name": "🎒 ШКОЛЯР 3 години (до 16 років, Пн-Чт до 15:00)",
    },
    "weekend": {
        "hours": 3,
        "price": 180,
        "end_hour": 12,
        "name": "🎒 ШКОЛЯР 3 години (до 16 років, Пт-Нд/свята до 12:00)",
    },
}

SCHOOL_ZONES = {"gamer"}


def is_school_package_active(day_type: DayType, current_hour: int | None = None) -> bool:
    """Чи можна зараз продати пакет Школяр для вибраного типу дня."""
    hour = datetime.now().hour if current_hour is None else current_hour
    if not 0 <= hour <= 23:
        raise ValueError("current_hour must be between 0 and 23")
    return hour < SCHOOL_PACKAGE[day_type]["end_hour"]


def apply_discount(price: int, discount_percent: float) -> int:
    """Знижка на ціну, округлення до цілої гривні."""
    if not 0 <= discount_percent <= 100:
        raise ValueError("discount_percent must be between 0 and 100")
    if discount_percent == 0:
        return price
    return round(price * (100 - discount_percent) / 100)


def calculate_hours(amount: int, zone_id: str, day_type: DayType,
                    current_hour: int | None = None,
                    discount_percent: float = 0) -> list[dict]:
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
    if zone_id in SCHOOL_ZONES and is_school_package_active(day_type, current_hour):
        school = SCHOOL_PACKAGE[day_type]
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
                    discount_percent: float = 0) -> list[dict]:
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
    if zone_id in SCHOOL_ZONES and is_school_package_active(day_type, current_hour):
        school = SCHOOL_PACKAGE[day_type]
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
