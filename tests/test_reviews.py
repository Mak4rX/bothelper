import unittest

from fastapi.testclient import TestClient

import reviews
from reviews import normalize_phone, parse_csv_rows
from webapp.main import app

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

    def test_parse_csv_rows(self):
        entries = parse_csv_rows(SAMPLE_CSV)
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0]["clean"], "380639436554")
        self.assertEqual(entries[0]["note"], "Відгук гугл карта")

    def test_parse_csv_skips_headers(self):
        clean = [e["clean"] for e in parse_csv_rows(SAMPLE_CSV)]
        self.assertFalse(any("Чистий контакт" in c or "ЧИСТА" in c for c in clean))


class ReviewsAPITests(unittest.TestCase):
    def test_database_endpoint_serves_parsed_entries(self):
        original = reviews.fetch_database
        reviews.fetch_database = lambda force_refresh=False: parse_csv_rows(SAMPLE_CSV)
        try:
            resp = TestClient(app).get("/api/reviews/database")
        finally:
            reviews.fetch_database = original
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["entries"][0]["clean"], "380639436554")

    def test_fetch_failure_returns_last_cache(self):
        saved = dict(reviews._CACHE)
        reviews._CACHE.update(entries=[{"clean": "x"}], last_fetched=0.0)
        original = reviews.urllib.request.urlopen

        def boom(*args, **kwargs):
            raise OSError("offline")

        reviews.urllib.request.urlopen = boom
        try:
            self.assertEqual(reviews.fetch_database(force_refresh=True), [{"clean": "x"}])
        finally:
            reviews.urllib.request.urlopen = original
            reviews._CACHE.update(saved)

    def test_removed_endpoints_are_gone(self):
        client = TestClient(app)
        for method, path in (
            ("get", "/api/reviews/check?q=1"),
            ("post", "/api/reviews/add"),
            ("get", "/api/promotions"),
            ("get", "/api/reports"),
            ("post", "/api/reports"),
            ("get", "/api/collections"),
            ("get", "/api/stats"),
            ("get", "/api/expected-cash"),
        ):
            self.assertIn(getattr(client, method)(path).status_code, (404, 405), path)


if __name__ == "__main__":
    unittest.main()
