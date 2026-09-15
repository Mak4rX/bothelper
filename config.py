import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не заданий. Скопіюй .env.example у .env і встав токен від @BotFather."
    )


def _parse_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


# Пустий набір = доступ відкритий всім
ALLOWED_IDS: set[int] = _parse_ids(os.getenv("ALLOWED_IDS", ""))

DB_PATH: Path = BASE_DIR / "bothelper.db"
