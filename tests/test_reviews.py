import unittest
from fastapi.testclient import TestClient
from webapp.main import app

from reviews import (
    normalize_phone,
    normalize_login,
    parse_csv_rows,
    check_contact,
    add_contact,
)

SAMPLE_CSV = """✨ ЧИСТА БАЗА,,,,📥 ЗОНА ВСТАВКИ,,,
Усі непотрібні номери САМІ ВИДАЛЯЮТЬСЯ,,,,,,,
,
№,Чистий контакт у базі,Тип контакту,,Стовпчик E: Примітка,Стовпчик F: Телефон / Логін,Спарсений контакт,Результат рядка
1,380639436554,📱 Телефон,,Відгук гугл карта,HQCK (380639436554),380639436554,✅ ЗАЛИШЕНО В БАЗІ (Google)
2,380971818343,📱 Телефон,,Відгук гугл карта,TSEJ (380971818343),380971818343,✅ ЗАЛИШЕНО В БАЗІ (Google)
3,+380985184647,📱 Телефон,,Відгук Гугл Карта,C737 (+380985184647),+380985184647,✅ ЗАЛИШЕНО В БАЗІ (Google)
4,"buuurmalda\n+380961051420",📱 Телефон,,Відгук гугл карта,"buuurmalda\n+380961051420","buuurmalda\n+380961051420",✅ ЗАЛИШЕНО В БАЗІ (Google)
5,0974403535,📱 Телефон,,відгук гугл карта,0974403535,0974403535,✅ ЗАЛИШЕНО В БАЗІ (Google)
"""

class ReviewsTests(unittest.TestCase):
    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+380679119400"), "0679119400")
        self.assertEqual(normalize_phone("380679119400"), "0679119400")
        self.assertEqual(normalize_phone("0679119400"), "0679119400")
        self.assertEqual(normalize_phone("067-911-94-00"), "0679119400")
        self.assertEqual(normalize_phone("+38 (067) 911 94 00"), "0679119400")

    def test_normalize_login(self):
        self.assertEqual(normalize_login("  @hqck "), "hqck")
        self.assertEqual(normalize_login("Karma1488"), "karma1488")

    def test_parse_csv_rows(self):
        entries = parse_csv_rows(SAMPLE_CSV)
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0]["clean"], "380639436554")
        self.assertEqual(entries[0]["note"], "Відгук гугл карта")

    def test_check_contact_found_by_phone(self):
        entries = parse_csv_rows(SAMPLE_CSV)
        res = check_contact("0639436554", entries)
        self.assertTrue(res["found"])
        self.assertIn("ВЖЕ В БАЗІ", res["status"])
        self.assertEqual(len(res["matches"]), 1)

        res2 = check_contact("+380639436554", entries)
        self.assertTrue(res2["found"])

        res3 = check_contact("0974403535", entries)
        self.assertTrue(res3["found"])

    def test_check_contact_found_by_login(self):
        entries = parse_csv_rows(SAMPLE_CSV)
        res = check_contact("hqck", entries)
        self.assertTrue(res["found"])
        self.assertIn("Логін", res["status"])

        res2 = check_contact("buuurmalda", entries)
        self.assertTrue(res2["found"])

    def test_check_contact_not_found(self):
        entries = parse_csv_rows(SAMPLE_CSV)
        res = check_contact("0991112233", entries)
        self.assertFalse(res["found"])
        self.assertIn("НЕМАЄ В БАЗІ", res["status"])

        res2 = check_contact("super_new_user", entries)
        self.assertFalse(res2["found"])
        self.assertIn("НЕМАЄ В БАЗІ", res2["status"])

    def test_add_contact_locally(self):
        res = add_contact("0509998877", "Відгук гугл карта")
        self.assertTrue(res["success"])
        check_res = check_contact("0509998877")
        self.assertTrue(check_res["found"])


class ReviewsAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_api_check_existing_contact(self):
        resp = self.client.get("/api/reviews/check", params={"q": "0639436554"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["found"])
        self.assertIn("ВЖЕ В БАЗІ", data["status"])

    def test_api_check_new_contact(self):
        resp = self.client.get("/api/reviews/check", params={"q": "0999999999"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["found"])
        self.assertIn("НЕМАЄ В БАЗІ", data["status"])

    def test_api_add_contact(self):
        resp = self.client.post("/api/reviews/add", json={"contact": "0681112233", "note": "Відгук гугл карта"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

        # Now should be found
        check_resp = self.client.get("/api/reviews/check", params={"q": "0681112233"})
        self.assertEqual(check_resp.status_code, 200)
        self.assertTrue(check_resp.json()["found"])
