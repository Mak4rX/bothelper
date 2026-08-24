import unittest

from pricing import (
    ZONES,
    calculate_compensation,
    calculate_hours,
    calculate_price,
    is_morning_rate_active,
    is_school_package_active,
)


class PricingTests(unittest.TestCase):
    def test_morning_rate_window(self):
        self.assertFalse(is_morning_rate_active(8))
        self.assertTrue(is_morning_rate_active(9))
        self.assertTrue(is_morning_rate_active(15))
        self.assertFalse(is_morning_rate_active(16))

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
        inactive = ZONES["tv"].get_options("weekday", current_hour=16)
        self.assertEqual(active[0].price, 130)
        self.assertIn("09:00–16:00", active[0].name)
        self.assertNotIn(130, [option.price for option in inactive])

    def test_school_package_time_windows(self):
        self.assertTrue(is_school_package_active("weekday", 14))
        self.assertFalse(is_school_package_active("weekday", 15))
        self.assertTrue(is_school_package_active("weekend", 11))
        self.assertFalse(is_school_package_active("weekend", 12))

    def test_school_package_money_to_hours_rules(self):
        weekday = calculate_hours(130, "gamer", "weekday", current_hour=14)
        weekend = calculate_hours(180, "gamer", "weekend", current_hour=11)
        weekday_school = [row for row in weekday if "ШКОЛЯР" in row["package"]]
        weekend_school = [row for row in weekend if "ШКОЛЯР" in row["package"]]
        self.assertEqual(weekday_school[0]["hours"], 3)
        self.assertEqual(weekday_school[0]["price"], 130)
        self.assertEqual(weekend_school[0]["hours"], 3)
        self.assertEqual(weekend_school[0]["price"], 180)
        self.assertIn("до 16 років", weekday_school[0]["package"])

    def test_school_package_stops_at_boundary_and_only_gamer(self):
        self.assertFalse(any(
            "ШКОЛЯР" in row["package"]
            for row in calculate_hours(180, "gamer", "weekday", current_hour=15)
        ))
        self.assertNotIn("school", ZONES)
        for zone_id in ("pro", "bootcamp", "tv"):
            self.assertFalse(any(
                "ШКОЛЯР" in row["package"]
                for row in calculate_hours(180, zone_id, "weekday", current_hour=14)
            ))

    def test_school_package_hours_to_money(self):
        weekday = calculate_price(3, "gamer", "weekday", current_hour=14)
        weekend = calculate_price(3, "gamer", "weekend", current_hour=11)
        self.assertEqual(
            [row["price"] for row in weekday if "ШКОЛЯР" in row["package"]],
            [130],
        )
        self.assertEqual(
            [row["price"] for row in weekend if "ШКОЛЯР" in row["package"]],
            [180],
        )
        self.assertFalse(any(
            "ШКОЛЯР" in row["package"]
            for row in calculate_price(3, "gamer", "weekend", current_hour=12)
        ))

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

    def test_calculate_compensation_standard(self):
        # 100 грн + 35% кешбеку -> 35 грн бонус, 135 грн разом, 65 грн зі знижкою
        res = calculate_compensation(100, 35)
        self.assertEqual(res["amount"], 100)
        self.assertEqual(res["percent"], 35)
        self.assertEqual(res["compensation"], 35.0)
        self.assertEqual(res["total_with_bonus"], 135.0)
        self.assertEqual(res["discounted_price"], 65.0)

    def test_calculate_compensation_edge_cases(self):
        # 0% кешбеку
        zero_pct = calculate_compensation(200, 0)
        self.assertEqual(zero_pct["compensation"], 0.0)
        self.assertEqual(zero_pct["total_with_bonus"], 200.0)
        self.assertEqual(zero_pct["discounted_price"], 200.0)

        # 100% кешбеку
        full_pct = calculate_compensation(150, 100)
        self.assertEqual(full_pct["compensation"], 150.0)
        self.assertEqual(full_pct["total_with_bonus"], 300.0)
        self.assertEqual(full_pct["discounted_price"], 0.0)

        # Дробові відсотки та копійки
        frac = calculate_compensation(100.50, 33.33)
        self.assertEqual(frac["compensation"], 33.5)
        self.assertEqual(frac["total_with_bonus"], 134.0)
        self.assertEqual(frac["discounted_price"], 67.0)

        # Валідація некоректних значень
        with self.assertRaises(ValueError):
            calculate_compensation(100, -5)
        with self.assertRaises(ValueError):
            calculate_compensation(100, 105)
        with self.assertRaises(ValueError):
            calculate_compensation(-10, 20)


if __name__ == "__main__":
    unittest.main()

