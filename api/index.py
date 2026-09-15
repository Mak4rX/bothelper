import sys
from pathlib import Path

# Добавляем корень проекта в пути импорта
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from webapp.main import app as fastapi_app

INDEX_HTML = ROOT_DIR / "webapp" / "static" / "index.html"
STATIC_DIR = ROOT_DIR / "webapp" / "static"

# Запасные маршруты для Vercel (если Vercel обращается напрямую к функции /api или /api/index.py)
@fastapi_app.get("/api")
@fastapi_app.get("/api/")
@fastapi_app.get("/api/index")
@fastapi_app.get("/api/index.py")
async def vercel_entrypoint_fallback():
    return FileResponse(INDEX_HTML)

# Монтируем статику также по пути /api/static на случай префиксов от Vercel
fastapi_app.mount("/api/static", StaticFiles(directory=STATIC_DIR), name="api_static")


class VercelRoutingMiddleware:
    """Перенаправляет запросы, переписанные Vercel, на правильные маршруты FastAPI."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Если Vercel передал путь функции /api/index.py или /api/index
            if path in ("/api/index.py", "/api/index", "/api/index.py/", "/api", "/api/"):
                headers = dict(scope.get("headers", []))
                matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")
                if matched_path and matched_path not in ("/api/index.py", "/api/index", "/api"):
                    scope["path"] = matched_path
                else:
                    scope["path"] = "/"
        await self.app(scope, receive, send)


app = VercelRoutingMiddleware(fastapi_app)
