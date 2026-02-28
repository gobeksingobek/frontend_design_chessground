from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend import db
from backend.queue import enqueue_job, ensure_consumer_group, redis_client
from backend.settings import SETTINGS


class ErrorResponse(BaseModel):
    error_code: str
    detail: str


class ValidationErrorResponse(BaseModel):
    detail: list[dict[str, Any]]


class SidelineCreateRequest(BaseModel):
    game_id: str = Field(min_length=1, examples=["game-12345"])
    move_ply: int = Field(ge=1, examples=[12])
    fen: str = Field(min_length=1, examples=["rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"])
    branch_moves: list[str] = Field(min_length=1, examples=[["d7d5", "c2c4"]])


class SidelineResponse(BaseModel):
    id: str
    game_id: str
    move_ply: int
    requested_by: str
    status: str
    idempotency_key: str
    attempts: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime


app = FastAPI(title="ChessGround API Service")
auth_scheme = HTTPBearer(auto_error=False)


def api_error(status_code: int, error_code: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error_code": error_code, "detail": detail})


async def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme)) -> str:
    expected = SETTINGS.api_auth_token
    if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != expected:
        raise api_error(status_code=401, error_code="UNAUTHORIZED", detail="Invalid or missing bearer token")
    return "api-user"


@app.on_event("startup")
async def on_startup() -> None:
    app.state.db_pool = await db.create_pool()
    await db.ensure_schema(app.state.db_pool)
    app.state.redis = redis_client()
    await ensure_consumer_group(app.state.redis)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await app.state.redis.close()
    await app.state.db_pool.close()


def to_response(record: asyncpg.Record) -> SidelineResponse:
    return SidelineResponse(
        id=str(record["id"]),
        game_id=record["game_id"],
        move_ply=record["move_ply"],
        requested_by=record["requested_by"],
        status=record["status"],
        idempotency_key=record["idempotency_key"],
        attempts=record["attempts"],
        result=record["result"],
        error=record["error"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


@app.post(
    "/sidelines",
    response_model=SidelineResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ValidationErrorResponse, "description": "Validation error"},
    },
)
async def create_sideline(
    payload: SidelineCreateRequest,
    request: Request,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        examples=["sideline-game-12345-ply-12-v1"],
        description="Client-generated key for deduplicating create requests.",
    ),
    principal: str = Depends(require_auth),
) -> SidelineResponse:
    request_id = str(uuid.uuid4())
    serialized_payload = payload.model_dump()

    async with request.app.state.db_pool.acquire() as conn:
        row = await db.insert_sideline_request(
            conn,
            request_id=request_id,
            game_id=payload.game_id,
            move_ply=payload.move_ply,
            requested_by=principal,
            idempotency_key=idempotency_key,
            payload=serialized_payload,
        )

        if row is None:
            existing = await db.fetch_by_idempotency_key(conn, idempotency_key)
            if existing is None:
                raise api_error(
                    status_code=500,
                    error_code="IDEMPOTENCY_CONFLICT_RESOLUTION_FAILED",
                    detail="Idempotency key existed but record lookup failed",
                )
            return to_response(existing)

    await enqueue_job(
        request.app.state.redis,
        {
            "job_id": request_id,
            "idempotency_key": idempotency_key,
            "attempt": "0",
        },
    )

    async with request.app.state.db_pool.acquire() as conn:
        created = await db.fetch_sideline_request(conn, request_id)
    if created is None:
        raise api_error(status_code=500, error_code="CREATE_LOOKUP_FAILED", detail="Created request was not found")
    return to_response(created)


@app.get(
    "/sidelines/{request_id}",
    response_model=SidelineResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Sideline request not found"},
    },
)
async def get_sideline(request_id: str, request: Request, _: str = Depends(require_auth)) -> SidelineResponse:
    async with request.app.state.db_pool.acquire() as conn:
        row = await db.fetch_sideline_request(conn, request_id)
    if row is None:
        raise api_error(status_code=404, error_code="NOT_FOUND", detail="Sideline request not found")
    return to_response(row)


@app.get(
    "/sidelines",
    response_model=list[SidelineResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ValidationErrorResponse, "description": "Validation error"},
    },
)
async def list_sidelines(request: Request, limit: int = 20, _: str = Depends(require_auth)) -> list[SidelineResponse]:
    bounded_limit = min(max(limit, 1), 100)
    async with request.app.state.db_pool.acquire() as conn:
        rows = await db.list_sideline_requests(conn, bounded_limit)
    return [to_response(row) for row in rows]
