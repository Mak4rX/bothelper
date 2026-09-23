"""Модуль для роботи з базою Google Відгуків CyberHelper.

Таблиця: https://docs.google.com/spreadsheets/d/1Q7l94fvXV1zmC11gCxOelnn_Bw-fROqawE3w8JHg08Y/edit?usp=sharing
Аркуш чистої бази: 📥 База_Даних_EF (gid=333018725)
"""

import csv
import logging
import re
import time
import urllib.request
import urllib.error
import json
from typing import Any, Optional

log = logging.getLogger(__name__)

SPREADSHEET_ID = "1Q7l94fvXV1zmC11gCxOelnn_Bw-fROqawE3w8JHg08Y"
DATA_GID = "333018725"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={DATA_GID}"

# Кеш у пам'яті (TTL 60 секунд)
_CACHE: dict[str, Any] = {
    "entries": [],
    "last_fetched": 0.0,
    "ttl": 60.0,
}

# Локально додані контакти (до синхронізації з Google)
_LOCAL_ADDED: list[dict[str, str]] = []


def normalize_phone(val: str) -> str:
    """Нормалізує номер телефону до 10 цифр (0XX XXXXXXX) або чистих цифр."""
    digits = re.sub(r"\D", "", val)
    if digits.startswith("380") and len(digits) == 12:
        return digits[2:]  # наприклад, '0679119400'
    if len(digits) == 9:
        return "0" + digits
    return digits


def normalize_login(val: str) -> str:
    """Нормалізує логін / нікнейм для зіставлення."""
    return val.strip().lstrip("@").lower()


def parse_csv_rows(csv_text: str) -> list[dict[str, str]]:
    """Парсить вивантажений CSV Google Таблиці у список валідних записів."""
    reader = csv.reader(csv_text.splitlines())
    rows = list(reader)
    entries: list[dict[str, str]] = []

    for r in rows:
        if not r or len(r) < 2:
            continue

        col_b = r[1].strip()
        # Пропускаємо службові рядки та заголовки
        col_b_lower = col_b.lower()
        if (
            not col_b
            or "чистий контакт" in col_b_lower
            or "непотрібні" in col_b_lower
            or col_b.startswith("✨")
        ):
            continue

        col_c = r[2].strip() if len(r) > 2 else ""
        col_e = r[4].strip() if len(r) > 4 else ""
        col_f = r[5].strip() if len(r) > 5 else ""
        col_g = r[6].strip() if len(r) > 6 else ""
        col_h = r[7].strip() if len(r) > 7 else ""

        # Якщо є рядок статусу, перевіряємо, чи це відгук Google
        # Зазвичай '✅ ЗАЛИШЕНО В БАЗІ (Google)' або не пусте col_b
        entries.append({
            "clean": col_b,
            "type": col_c or ("Телефон" if any(char.isdigit() for char in col_b) else "Логін"),
            "note": col_e or "Відгук гугл карта",
            "raw": col_f or col_b,
            "parsed": col_g or col_b,
            "status": col_h or "ЗАЛИШЕНО В БАЗІ (Google)",
        })

    return entries


def fetch_database(force_refresh: bool = False) -> list[dict[str, str]]:
    """Завантажує чисту базу контактів з Google Таблиці з кешуванням."""
    now = time.time()
    if (
        not force_refresh
        and _CACHE["entries"]
        and (now - _CACHE["last_fetched"]) < _CACHE["ttl"]
    ):
        all_entries = list(_CACHE["entries"])
        all_entries.extend(_LOCAL_ADDED)
        return all_entries

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
        # Якщо вже є кеш, використовуємо його
        if not _CACHE["entries"]:
            # Повертаємо хоча б локально додані
            return list(_LOCAL_ADDED)

    all_entries = list(_CACHE["entries"])
    all_entries.extend(_LOCAL_ADDED)
    return all_entries


def check_contact(query: str, entries: Optional[list[dict[str, str]]] = None) -> dict[str, Any]:
    """Перевіряє номер або нікнейм по базі відгуків.

    Повертає:
        {
            "query": query,
            "found": True/False,
            "status": "❌ ВЖЕ В БАЗІ: ..." або "✅ НЕМАЄ В БАЗІ: ...",
            "matches": [ ...список збігів... ],
            "contact_type": "📱 Телефон" | "👤 Логін"
        }
    """
    q = query.strip()
    if not q:
        return {
            "query": "",
            "found": False,
            "status": "Введіть номер телефону або логін",
            "matches": [],
            "contact_type": "Невідомо",
        }

    if entries is None:
        entries = fetch_database()

    q_phone = normalize_phone(q)
    is_phone_query = len(q_phone) >= 9 and any(c.isdigit() for c in q)
    contact_type = "Телефон" if is_phone_query else "Логін"
    q_login = normalize_login(q)

    matched_entries = []

    for entry in entries:
        raw_text = f"{entry.get('clean', '')} {entry.get('raw', '')} {entry.get('parsed', '')}"

        # 1. Перевірка телефону
        phone_match = False
        if is_phone_query:
            # Шукаємо всі телефоноподібні послідовності цифр
            extracted_phones = re.findall(r"\+?\d[\d\s\-\(\)]{7,}\d", raw_text)
            for p in extracted_phones:
                norm_p = normalize_phone(p)
                if len(norm_p) >= 9:
                    if norm_p == q_phone or norm_p[-9:] == q_phone[-9:]:
                        phone_match = True
                        break
            if not phone_match:
                # Також пряма перевірка clean на випадок формату без спецсимволів
                clean_phone = normalize_phone(entry.get("clean", ""))
                if clean_phone and (clean_phone == q_phone or clean_phone[-9:] == q_phone[-9:]):
                    phone_match = True

        # 2. Перевірка логіна/ніку
        login_match = False
        if not phone_match:
            # Розбиваємо текст на токени (слова)
            tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9_\-\.]+", raw_text)]
            if q_login in tokens:
                login_match = True

        if phone_match or login_match:
            matched_entries.append(entry)

    if matched_entries:
        if contact_type == "Телефон":
            status_text = "ВЖЕ В БАЗІ: Отримав за відгук Google Карта!"
        else:
            status_text = "ВЖЕ В БАЗІ: Логін знайдено у Відгуках Google!"
        return {
            "query": q,
            "found": True,
            "status": status_text,
            "matches": matched_entries,
            "contact_type": contact_type,
            "total_matches": len(matched_entries),
        }
    else:
        if contact_type == "Телефон":
            status_text = "НЕМАЄ В БАЗІ: Новий клієнт (акція доступна!)"
        else:
            status_text = "НЕМАЄ В БАЗІ: Новий логін (акція доступна!)"
        return {
            "query": q,
            "found": False,
            "status": status_text,
            "matches": [],
            "contact_type": contact_type,
            "total_matches": 0,
        }


def add_contact(
    contact: str,
    note: str = "Відгук гугл карта",
    script_url: Optional[str] = None,
) -> dict[str, Any]:
    """Додає контакт у локальний кеш та, за наявності script_url, відправляє у Google Таблицю."""
    c = contact.strip()
    n = note.strip() or "Відгук гугл карта"

    if not c:
        return {"success": False, "error": "Поле контакту порожнє"}

    contact_type = "📱 Телефон" if any(ch.isdigit() for ch in c) and len(normalize_phone(c)) >= 9 else "👤 Логін"

    new_entry = {
        "clean": c,
        "type": contact_type,
        "note": n,
        "raw": c,
        "parsed": c,
        "status": "✅ ЗАЛИШЕНО В БАЗІ (Google)",
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    _LOCAL_ADDED.append(new_entry)

    google_sync_status = "local_only"
    if script_url:
        try:
            payload = json.dumps({"contact": c, "note": n}).encode("utf-8")
            req = urllib.request.Request(
                script_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                google_sync_status = "synced"
                log.info("Успішно надіслано в Google Таблицю: %s", result)
        except Exception as exc:
            google_sync_status = f"sync_failed: {exc}"
            log.warning("Помилка відправки в Google Таблицю: %s", exc)

    return {
        "success": True,
        "entry": new_entry,
        "google_sync": google_sync_status,
        "formatted_row": f"{n}\t{c}",  # Зручно для копіювання у буфер
    }
