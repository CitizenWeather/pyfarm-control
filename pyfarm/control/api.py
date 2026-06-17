from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from pyfarm.control.engine.context import ControlContext


def make_app(ctx: ControlContext) -> FastAPI:
    app = FastAPI(title="pyfarm-control", docs_url=None, redoc_url=None)

    @app.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(ctx.to_status_dict())

    return app
