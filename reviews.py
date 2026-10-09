"""Завантаження бази Google Відгуків CyberHelper.

Таблиця: https://docs.google.com/spreadsheets/d/1Q7l94fvXV1zmC11gCxOelnn_Bw-fROqawE3w8JHg08Y/edit?usp=sharing
Аркуш чистої бази: 📥 База_Даних_EF (gid=333018725)

Сервер лише віддає розібрану таблицю; пошук контакту виконує фронтенд.
"""

import csv
import logging
import re
import time
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

SPREADSHEET_ID = "1Q7l94fvXV1zmC11gCxOelnn_Bw-fROqawE3w8JHg08Y"
DATA_GID = "333018725"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={DATA_GID}"

# Кеш у пам'яті процесу (TTL 60 секунд)
_CACHE: dict[str, Any] = {
    "entries": [],
    "last_fetched": 0.0,
    "ttl": 60.0,
}


def normalize_phone(val: str) -> str:
    """Нормалізує номер телефону до 10 цифр (0XX XXXXXXX) або чистих цифр."""
    digits = re.sub(r"\D", "", val)
    if digits.startswith("380") and len(digits) == 12:
        return digits[2:]  # наприклад, '0679119400'
    if len(digits) == 9:
        return "0" + digits
    return digits


def parse_csv_rows(csv_text: str) -> list[dict[str, str]]:
    """Парсить вивантажений CSV Google Таблиці у список валідних записів із колонки B."""
    reader = csv.reader(csv_text.splitlines())
    rows = list(reader)

    # 1. Збираємо примітки та оригінальні записи із зони вставки (якщо є логіни, плойка, PS тощо)
    note_map: dict[str, str] = {}
    raw_map: dict[str, str] = {}
    for r in rows:
        if len(r) > 5 and r[5].strip():
            raw_c = r[5].strip()
            note = r[4].strip() if len(r) > 4 else ""
            parsed_c = r[6].strip() if len(r) > 6 else ""

            keys = [k for k in (raw_c, parsed_c, normalize_phone(raw_c), normalize_phone(parsed_c)) if k]
            for k in keys:
                if note:
                    note_map[k] = note
                raw_map[k] = raw_c

    # 2. Зчитуємо чисту базу виключно з колонки B
    entries: list[dict[str, str]] = []
    for r in rows:
        if not r or len(r) < 2:
            continue

        contact = r[1].strip()
        if not contact:
            continue

        contact_lower = contact.lower()
        if (
            "чистий контакт" in contact_lower
            or "непотрібні" in contact_lower
            or "зона вставки" in contact_lower
            or "телефон / логін" in contact_lower
            or "спарсений контакт" in contact_lower
            or contact.startswith("✨")
            or contact.startswith("📥")
        ):
            continue

        col_c = r[2].strip() if len(r) > 2 else ""
        contact_type = col_c or ("Телефон" if any(char.isdigit() for char in contact) else "Логін")

        norm_c = normalize_phone(contact)
        note = note_map.get(contact) or (note_map.get(norm_c) if norm_c else None) or "Відгук гугл карта"
        raw = raw_map.get(contact) or (raw_map.get(norm_c) if norm_c else None) or contact

        entries.append({
            "clean": contact,
            "type": contact_type,
            "note": note,
            "raw": raw,
            "parsed": contact,
            "status": "ЗАЛИШЕНО В БАЗІ (Google)",
        })

    return entries


def fetch_database(force_refresh: bool = False) -> list[dict[str, str]]:
    """Завантажує чисту базу контактів з Google Таблиці з кешуванням.

    Якщо таблиця недоступна, повертає останній успішний кеш (або порожній список).
    """
    now = time.time()
    if (
        not force_refresh
        and _CACHE["entries"]
        and (now - _CACHE["last_fetched"]) < _CACHE["ttl"]
    ):
        return list(_CACHE["entries"])

    try:
        req = urllib.request.Request(
            SHEET_CSV_URL,
            headers={"User-Agent": "CyberHelper/1.0 (+https://cyberhelper.local)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8")
        parsed = parse_csv_rows(content)
        _CACHE["entries"] = parsed
        _CACHE["last_fetched"] = now
        log.info("Завантажено %d контактів з Google Таблиці", len(parsed))
    except Exception as exc:
        log.warning("Помилка завантаження таблиці відгуків: %s", exc)

    return list(_CACHE["entries"])
