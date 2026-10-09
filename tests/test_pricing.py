import unittest

from pricing import (
    ZONES,
    calculate_hours,
    calculate_price,
    get_live_pricing_data,
    is_morning_rate_active,
    is_school_package_active,
)


class PricingTests(unittest.TestCase):
    def test_morning_rate_window(self):
        # Пн-Чт з 09:00 включно до 15:00 невключно
        self.assertFalse(is_morning_rate_active(8))
        self.assertTrue(is_morning_rate_active(9))
        self.assertTrue(is_morning_rate_active(14))
        self.assertFalse(is_morning_rate_active(15))

    def test_morning_rate_not_on_weekend(self):
        for hour in (9, 12, 14):
            self.assertFalse(is_morning_rate_active(hour, "weekend"))
        for zone in ZONES.values():
            options = zone.get_options("weekend", current_hour=11)
            self.assertFalse(any("Ранок" in o.name for o in options))
        self.assertFalse(any(
            "Ранок" in row["package"]
            for row in calculate_hours(500, "gamer", "weekend", current_hour=11)
        ))

    def test_tv_zone_has_no_zero_price_options(self):
        for day_type in ("weekday", "weekend"):
            for current_hour in (10, 18):
                options = ZONES["tv"].get_options(day_type, current_hour=current_hour)
                self.assertTrue(options)
                self.assertTrue(all(option.price > 0 for option in options))
                self.assertNotIn(5, [option.hours for option in options])

    def test_tv_zone_calculators_do_not_divide_by_zero(self):
        money_options = calculate_hours(500, "tv", "weekday", current_hour=18)
        price_options = calculate_price(5, "tv", "weekday", current_hour=18)
        self.assertTrue(money_options)
        self.assertTrue(price_options)
        self.assertTrue(all(option["price"] > 0 for option in money_options))
        self.assertTrue(all(option["price"] > 0 for option in price_options))

    def test_morning_option_only_during_morning_window(self):
        active = ZONES["tv"].get_options("weekday", current_hour=9)
        inactive = ZONES["tv"].get_options("weekday", current_hour=15)
        self.assertEqual(active[0].price, 130)
        self.assertEqual(active[0].hours, 2)
        self.assertEqual(active[0].price_per_hour, 65)
        self.assertIn("09:00–15:00", active[0].name)
        self.assertNotIn(130, [option.price for option in inactive])

        # Розрахунок у калькуляторі: 130 грн дає 2 години гри
        money_morn = calculate_hours(130, "tv", "weekday", current_hour=10)
        morn_opt = next(o for o in money_morn if "Ранок" in o["package"])
        self.assertEqual(morn_opt["hours"], 2)
        self.assertEqual(morn_opt["price"], 130)

        # Розрахунок ціни за 2 години гри у ранковий час
        price_morn = calculate_price(2, "tv", "weekday", current_hour=10)
        morn_price_opt = next(o for o in price_morn if "Ранок" in o["package"])
        self.assertEqual(morn_price_opt["price"], 130)

    def test_school_package_time_windows(self):
        # Пн-Чт: до 17:00
        self.assertTrue(is_school_package_active("weekday", 16, dow=2))
        self.assertFalse(is_school_package_active("weekday", 17, dow=2))
        # Пт: теж до 17:00, хоча тариф «вихідний»
        self.assertTrue(is_school_package_active("weekend", 16, dow=4))
        self.assertFalse(is_school_package_active("weekend", 17, dow=4))
        # Сб-Нд: до 15:00
        self.assertTrue(is_school_package_active("weekend", 14, dow=5))
        self.assertFalse(is_school_package_active("weekend", 15, dow=5))
        self.assertTrue(is_school_package_active("weekend", 14, dow=6))
        self.assertFalse(is_school_package_active("weekend", 15, dow=6))
        # Раніше 09:00 пакет не діє
        self.assertFalse(is_school_package_active("weekday", 8, dow=2))

    def test_school_package_money_to_hours_rules(self):
        weekday = calculate_hours(130, "gamer", "weekday", current_hour=16, dow=1)
        friday = calculate_hours(180, "gamer", "weekend", current_hour=16, dow=4)
        saturday = calculate_hours(180, "gamer", "weekend", current_hour=14, dow=5)
        weekday_school = [row for row in weekday if "ШКОЛЯР" in row["package"]]
        friday_school = [row for row in friday if "ШКОЛЯР" in row["package"]]
        saturday_school = [row for row in saturday if "ШКОЛЯР" in row["package"]]
        self.assertEqual(weekday_school[0]["hours"], 3)
        self.assertEqual(weekday_school[0]["price"], 130)
        self.assertEqual(friday_school[0]["price"], 180)
        self.assertEqual(saturday_school[0]["price"], 180)
        self.assertIn("до 16 років", weekday_school[0]["package"])

    def test_school_package_stops_at_boundary_and_only_gamer(self):
        self.assertFalse(any(
            "ШКОЛЯР" in row["package"]
            for row in calculate_hours(180, "gamer", "weekday", current_hour=17, dow=1)
        ))
        self.assertNotIn("school", ZONES)
        for zone_id in ("pro", "bootcamp", "tv"):
            self.assertFalse(any(
                "ШКОЛЯР" in row["package"]
                for row in calculate_hours(180, zone_id, "weekday", current_hour=14, dow=1)
            ))

    def test_school_package_hours_to_money(self):
        weekday = calculate_price(3, "gamer", "weekday", current_hour=14, dow=0)
        friday = calculate_price(3, "gamer", "weekend", current_hour=16, dow=4)
        saturday = calculate_price(3, "gamer", "weekend", current_hour=11, dow=5)
        self.assertEqual([r["price"] for r in weekday if "ШКОЛЯР" in r["package"]], [130])
        self.assertEqual([r["price"] for r in friday if "ШКОЛЯР" in r["package"]], [180])
        self.assertEqual([r["price"] for r in saturday if "ШКОЛЯР" in r["package"]], [180])
        self.assertFalse(any(
            "ШКОЛЯР" in row["package"]
            for row in calculate_price(3, "gamer", "weekend", current_hour=15, dow=6)
        ))

    def test_school_package_without_dow_follows_day_type(self):
        # Без дня тижня п'ятницю не відрізнити від Сб-Нд — рахуємо за типом дня
        self.assertTrue(is_school_package_active("weekday", 16))
        self.assertFalse(is_school_package_active("weekend", 16))

    def test_calculator_and_live_pricing_agree(self):
        """Калькулятор і «живі» тарифи мають давати однакову відповідь в усі години тижня."""
        for dow in range(7):
            day_type = "weekday" if dow <= 3 else "weekend"
            for hour in range(24):
                live = get_live_pricing_data(current_hour=hour, day_of_week=dow)
                self.assertEqual(
                    live["morning_active"],
                    is_morning_rate_active(hour, day_type),
                    f"ранок dow={dow} hour={hour}",
                )
                self.assertEqual(
                    live["school_active"],
                    is_school_package_active(day_type, hour, dow),
                    f"школяр dow={dow} hour={hour}",
                )
                calc = calculate_hours(1000, "gamer", day_type, current_hour=hour, dow=dow)
                calc_school = [r for r in calc if "ШКОЛЯР" in r["package"]]
                self.assertEqual(bool(calc_school), live["school_active"], f"dow={dow} hour={hour}")
                if calc_school:
                    per_package = calc_school[0]["price"] // (calc_school[0]["hours"] // 3)
                    self.assertEqual(per_package, live["school_price"], f"dow={dow} hour={hour}")

    def test_package30_calculations(self):
        # PC GAMER: 1699 грн за 30 год
        gamer_hours = calculate_hours(1699, "gamer", "weekday", current_hour=18)
        gamer_opt = [r for r in gamer_hours if "30" in r["package"]]
        self.assertTrue(gamer_opt)
        self.assertEqual(gamer_opt[0]["hours"], 30)
        self.assertEqual(gamer_opt[0]["price"], 1699)

        # PC PRO: 1899 грн за 30 год
        pro_price = calculate_price(30, "pro", "weekend", current_hour=18)
        pro_opt = [r for r in pro_price if "30" in r["package"]]
        self.assertTrue(pro_opt)
        self.assertEqual(pro_opt[0]["price"], 1899)

        # PC BOOTCAMP: 2499 грн за 30 год
        bootcamp_price = calculate_price(30, "bootcamp", "weekday", current_hour=18)
        bootcamp_opt = [r for r in bootcamp_price if "30" in r["package"]]
        self.assertTrue(bootcamp_opt)
        self.assertEqual(bootcamp_opt[0]["price"], 2499)

    def test_live_pricing_data(self):
        # Будень 11:00 (Вівторок, dow=1) -> Ранок активний, Школяр 130
        data_tue_morn = get_live_pricing_data(current_hour=11, day_of_week=1)
        self.assertTrue(data_tue_morn["morning_active"])
        self.assertFalse(data_tue_morn["night_active"])
        self.assertTrue(data_tue_morn["school_active"])
        self.assertEqual(data_tue_morn["school_price"], 130)
        gamer_tue = next(z for z in data_tue_morn["zones"] if z["id"] == "gamer")
        self.assertEqual(gamer_tue["current_hour_price"], 50)

        # П'ятниця 19:00 (dow=4) -> Вихідні, Ранок не активний, Ніч не активна
        data_fri_eve = get_live_pricing_data(current_hour=19, day_of_week=4)
        self.assertFalse(data_fri_eve["morning_active"])
        self.assertFalse(data_fri_eve["night_active"])
        self.assertFalse(data_fri_eve["school_active"])
        gamer_fri = next(z for z in data_fri_eve["zones"] if z["id"] == "gamer")
        self.assertEqual(gamer_fri["current_hour_price"], 80)

        # Субота 23:30 (dow=5, hour=23) -> Ніч активна
        data_sat_night = get_live_pricing_data(current_hour=23, day_of_week=5)
        self.assertTrue(data_sat_night["night_active"])
        gamer_night = next(z for z in data_sat_night["zones"] if z["id"] == "gamer")
        night_pkg = next(p for p in gamer_night["packages"] if "Ніч" in p["name"])
        self.assertTrue(night_pkg["active_now"])
        self.assertEqual(night_pkg["price"], 450)


if __name__ == "__main__":
    unittest.main()

