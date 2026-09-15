import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode

# Добавляем корень проекта в пути импорта
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from webapp.main import app as fastapi_app

INDEX_HTML = ROOT_DIR / "webapp" / "static" / "index.html"
STATIC_DIR = ROOT_DIR / "webapp" / "static"

# Запасные маршруты для прямого открытия /api или /api/index.py
@fastapi_app.get("/api")
@fastapi_app.get("/api/")
@fastapi_app.get("/api/index")
@fastapi_app.get("/api/index.py")
async def vercel_entrypoint_fallback():
    return FileResponse(INDEX_HTML)

# Монтируем статику также по пути /api/static на случай префиксов
fastapi_app.mount("/api/static", StaticFiles(directory=STATIC_DIR), name="api_static")


class VercelRoutingMiddleware:
    """Восстанавливает исходный путь запроса, переписанный Vercel."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            query_string = scope.get("query_string", b"").decode("utf-8")
            params = parse_qs(query_string, keep_blank_values=True)

            if "__path" in params:
                subpath = params.pop("__path")[0].strip("/")
                scope["path"] = f"/api/{subpath}" if subpath else "/api"
                scope["raw_path"] = scope["path"].encode("utf-8")
                # Убираем служебный параметр __path из query_string
                scope["query_string"] = urlencode(params, doseq=True).encode("utf-8")
            elif scope.get("path") in ("/api/index.py", "/api/index", "/api/index.py/"):
                scope["path"] = "/"
                scope["raw_path"] = b"/"

        await self.app(scope, receive, send)


app = VercelRoutingMiddleware(fastapi_app)
