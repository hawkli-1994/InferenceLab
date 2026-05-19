"""Health check routes."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from inflab.config import AppSettings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str


def app_settings(request: Request) -> AppSettings:
    return request.app.state.settings


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    settings = app_settings(request)
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )
