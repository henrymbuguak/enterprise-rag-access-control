"""FastAPI answer service."""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from . import answer, identity, search
from .config import settings
from .db import admin


def _quarantine_count():
    try:
        with admin() as conn:
            return conn.execute("SELECT count(*) FROM quarantine").fetchone()[0]
    except Exception:
        return float("nan")


Gauge("brimmora_quarantined_documents", "Documents currently held in quarantine").set_function(_quarantine_count)


@asynccontextmanager
async def lifespan(_app):
    search.embedder()      # load both models once, before the first request
    search.reranker()
    yield


app = FastAPI(title="Brimmora AI Platform", lifespan=lifespan)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        return identity.verify_token(authorization.removeprefix("Bearer "))
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid token")


def _dev_only():
    if not settings.dev_mode:
        raise HTTPException(404)


@app.post("/ask")
def ask(body: Question, user: str = Depends(current_user)):
    return answer.ask(user, body.question)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/dev/token")
def dev_token(user: str):
    """Stands in for single sign-on. Disabled unless DEV_MODE=true."""
    _dev_only()
    if not identity.user_exists(user):
        raise HTTPException(404, "unknown user")
    return {"token": identity.issue_token(user)}


@app.get("/audit/{request_id}")
def audit(request_id: str):
    _dev_only()
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(404, "unknown request")
    with admin() as conn:
        row = conn.cursor(row_factory=dict_row).execute(
            "SELECT * FROM audit_log WHERE request_id = %s", (rid,)).fetchone()
    if row is None:
        raise HTTPException(404, "unknown request")
    return row


@app.get("/")
def ui():
    page = Path(__file__).with_name("static") / "index.html"
    if not page.exists():
        raise HTTPException(404, "the web UI arrives in Phase 12")
    return FileResponse(page)

