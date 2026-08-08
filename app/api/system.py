"""Routes système — hors contexte métier (liveness, santé infra)."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession, SettingsDep

router = APIRouter(tags=["Système"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
    database: Literal["up", "down"]


@router.get("/health", response_model=HealthResponse, summary="Santé du service")
async def health(session: DbSession, settings: SettingsDep) -> HealthResponse:
    database: Literal["up", "down"] = "up"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # un échec de ping ne doit pas remonter en 500
        database = "down"

    return HealthResponse(
        status="ok" if database == "up" else "degraded",
        service=settings.app_name,
        environment=settings.environment,
        database=database,
    )
