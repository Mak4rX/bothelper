import sys
from pathlib import Path

# Добавляем корень проекта в пути импорта
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from webapp.main import app
