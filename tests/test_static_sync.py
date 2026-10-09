"""Vercel віддає `public/` напряму, а FastAPI (Fly/Render/Docker) — `webapp/static/`.

Це два місця для одного й того ж фронтенду, тому копії мають бути ідентичні.
Після змін у `webapp/static/` скопіюйте файли в `public/`.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "webapp" / "static"

# (файл у webapp/static, відповідний файл у public/)
PAIRS = [
    ("index.html", "index.html"),
    ("change.js", "static/change.js"),
    ("cash-register.js", "static/cash-register.js"),
    ("report.js", "static/report.js"),
]


def _normalized(path: Path) -> bytes:
    """Байти файлу без урахування CRLF/LF (git на Windows із autocrlf змінює закінчення рядків)."""
    return path.read_bytes().replace(bytes([13, 10]), bytes([10]))


class StaticSyncTests(unittest.TestCase):
    def test_public_copies_match_webapp_static(self):
        for src_name, public_name in PAIRS:
            public = ROOT / "public" / public_name
            self.assertEqual(
                _normalized(SRC / src_name),
                _normalized(public),
                f"public/{public_name} відрізняється від webapp/static/{src_name}",
            )

    def test_required_public_files_exist(self):
        for name in ("index.html", "static/change.js", "static/cash-register.js", "static/report.js"):
            self.assertTrue((ROOT / "public" / name).is_file(), f"немає public/{name}")


if __name__ == "__main__":
    unittest.main()
