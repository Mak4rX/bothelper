import unittest

from shifts import DAY, build_report, fmt


class ReportTests(unittest.TestCase):
    def test_pending_collection_is_included_in_report_and_calculation(self):
        # Усі грошові значення — у копійках (цілі числа)
        text, earned, surplus = build_report(
            DAY,
            open_cash=1_000_000,   # 10 000 грн
            close_cash=800_000,    # 8 000 грн
            expenses=50_000,       # 500 грн
            senet=350_000,         # 3 500 грн
            collection=500_000,    # 5 000 грн
        )

        self.assertEqual(earned, 350_000)
        self.assertEqual(surplus, 0)
        self.assertIn("Інкасація: 5 000", text)
        self.assertTrue(text.endswith("Надлишок: 0 грн"))

    def test_close_cash_with_kopecks_is_kept_in_report(self):
        # Формат тексту має показувати копійки, коли вони є
        text, earned, surplus = build_report(
            DAY,
            open_cash=1_000_000,
            close_cash=1_114_250,  # 11 142.50 грн
            expenses=0,
            senet=114_250,
            collection=0,
        )

        self.assertEqual(earned, 114_250)
        self.assertIn("Каса готівки ввечері: 11 142,50", text)
        self.assertTrue(text.endswith("Надлишок: 0 грн"))

    def test_fmt_formats_kopecks(self):
        self.assertEqual(fmt(779_100), "7 791")       # цілі гривні — без копійок
        self.assertEqual(fmt(1_114_250), "11 142,50") # з копійками
        self.assertEqual(fmt(-50), "-0,50")
        self.assertEqual(fmt(-1_234_560), "-12 345,60")


if __name__ == "__main__":
    unittest.main()
