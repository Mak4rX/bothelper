import tempfile
import unittest
from pathlib import Path

import db_web as db


class PromotionDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "promotions.db"
        await db.init_db()

    async def asyncTearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    async def test_crud_and_unlimited_end_date(self):
        promotion_id = await db.create_promotion(
            "Нічний тариф",
            "2026-10-01",
            None,
            "Для всіх клієнтів після 21:00.",
            "Обрати нічний тариф і застосувати ціну з акції.",
        )
        rows = await db.list_promotions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], promotion_id)
        self.assertIsNone(rows[0]["end_date"])

        updated = await db.update_promotion(
            promotion_id,
            "Нічний тариф (оновлено)",
            "2026-10-02",
            "2026-12-31",
            "Оновлені умови.",
            "Оновлені кроки на касі.",
        )
        self.assertTrue(updated)
        row = await db.get_promotion(promotion_id)
        self.assertEqual(row["title"], "Нічний тариф (оновлено)")
        self.assertEqual(row["end_date"], "2026-12-31")

        self.assertTrue(await db.delete_promotion(promotion_id))
        self.assertIsNone(await db.get_promotion(promotion_id))
        self.assertFalse(await db.delete_promotion(promotion_id))

    async def test_multiple_promotions_survive_reinitialization(self):
        await db.create_promotion(
            "Перша акція", "2026-10-01", "2026-10-31", "Умова", "Каса"
        )
        await db.init_db()
        rows = await db.list_promotions()
        self.assertEqual([row["title"] for row in rows], ["Перша акція"])


if __name__ == "__main__":
    unittest.main()
