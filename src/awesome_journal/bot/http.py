"""HTTP frontend: aiohttp app with /health endpoint.

The composition root passes a built `Storage` into `build_http_app`.
Views read it from `request.app` via typed `web.AppKey` and instantiate
controllers ad-hoc.
"""
from __future__ import annotations

from aiohttp import web

from awesome_journal.controllers.health import HealthController
from awesome_journal.db.storage import Storage

STORAGE_KEY: web.AppKey[Storage] = web.AppKey("storage", Storage)


class HealthView(web.View):
    """GET /health — 200 if DB ok, 503 otherwise."""

    @property
    def storage(self) -> Storage:
        return self.request.app[STORAGE_KEY]

    async def get(self) -> web.Response:
        result = await HealthController(self.storage).check()
        if (
            result.ok
            and result.value is not None
            and result.value.db_alive
        ):
            return web.json_response({"status": "ok"})
        reason = result.error or "db unavailable"
        return web.json_response(
            {"status": "degraded", "reason": reason},
            status=503,
        )


def build_http_app(*, storage: Storage) -> web.Application:
    app = web.Application()
    app[STORAGE_KEY] = storage
    app.router.add_view("/health", HealthView)
    return app
