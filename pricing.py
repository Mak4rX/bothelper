"""Тарифи кіберклубу для калькулятора годин."""

from dataclasses import dataclass
from typing import Literal

DayType = Literal["weekday", "weekend"]
PackageType = Literal["hour", "package3", "package5", "package10", "package2", "school"]


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
    morning_price: int  # до 16:00

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

    def get_options(self, day_type: DayType, with_morning: bool = True) -> list[PriceOption]:
        """Повертає всі доступні варіанти для обраного дня."""
        options = []

        if with_morning:
            options.append(PriceOption(
                name="🌅 Ранок (до 16:00)",
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
            options.append(PriceOption(
                name="Пакет 5 годин (Пн-Чт)",
                hours=5,
                price=self.weekday_package5,
                price_per_hour=self.weekday_package5 // 5
            ))
            options.append(PriceOption(
                name="Пакет Ніч 10 годин (Пн-Чт)",
                hours=10,
                price=self.weekday_package10,
                price_per_hour=self.weekday_package10 // 10
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
            options.append(PriceOption(
                name="Пакет 5 годин (Пт-Нд)",
                hours=5,
                price=self.weekend_package5,
                price_per_hour=self.weekend_package5 // 5
            ))
            options.append(PriceOption(
                name="Пакет Ніч 10 годин (Пт-Нд)",
                hours=10,
                price=self.weekend_package10,
                price_per_hour=self.weekend_package10 // 10
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
        weekend_hour=90,
        weekend_package3=240,
        weekend_package5=375,
        weekend_package10=450,
    ),
    "bootcamp": Zone(
        id="bootcamp",
        name="🖥️ PC BOOTCAMP PRO (RTX 5070)",
        morning_price=110,
        weekday_hour=140,
        weekday_package3=390,
        weekday_package5=625,
        weekday_package10=700,
        weekend_hour=180,
        weekend_package3=510,
        weekend_package5=825,
        weekend_package10=900,
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


# Пакет Школяр (окремо)
SCHOOL_PACKAGE = {
    "weekday": {"hours": None, "price": 130, "name": "🎒 ШКОЛЯР (Пн-Чт до 15:00)"},
    "weekend": {"hours": None, "price": 180, "name": "🎒 ШКОЛЯР (Пт-Нд до 12:00)"},
}


def calculate_hours(amount: int, zone_id: str, day_type: DayType) -> list[dict]:
    """Рахує скільки годин можна отримати за дану суму."""
    if zone_id not in ZONES:
        return []

    zone = ZONES[zone_id]
    options = zone.get_options(day_type)

    results = []
    for opt in options:
        if opt.price <= amount:
            full_packages = amount // opt.price
            remaining = amount % opt.price
            total_hours = full_packages * opt.hours

            results.append({
                "package": opt.name,
                "hours": total_hours,
                "price": full_packages * opt.price,
                "remaining": remaining,
            })

    # Додаємо школяр, якщо підходить
    school = SCHOOL_PACKAGE[day_type]
    if amount >= school["price"]:
        packages = amount // school["price"]
        remaining = amount % school["price"]
        results.append({
            "package": school["name"],
            "hours": f"{packages} пакет(и)",
            "price": packages * school["price"],
            "remaining": remaining,
        })

    return results


def calculate_price(hours: float, zone_id: str, day_type: DayType) -> list[dict]:
    """Рахує скільки коштує задана кількість годин."""
    if zone_id not in ZONES:
        return []

    zone = ZONES[zone_id]
    options = zone.get_options(day_type)

    results = []
    for opt in options:
        if opt.hours <= hours:
            packages = int(hours / opt.hours)
            remaining_hours = hours - (packages * opt.hours)
            total_price = packages * opt.price

            results.append({
                "package": opt.name,
                "packages": packages,
                "hours_used": packages * opt.hours,
                "price": total_price,
                "remaining_hours": remaining_hours,
            })

    return results
