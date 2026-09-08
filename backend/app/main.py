"""Envoy API."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import store
from .agent.engine import start_negotiation
from .config import MODEL_ID, ensure_dirs
from .scenarios import SCENARIOS


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    yield


app = FastAPI(title="Envoy", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DisputeIn(BaseModel):
    text: str
    scenario_id: str | None = None
    title: str | None = None


class DecisionIn(BaseModel):
    action: str  # approved | declined
    note: str | None = None


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": MODEL_ID}


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return [{"id": k, "label": v["label"], "provider": v["provider_name"]} for k, v in SCENARIOS.items()]


@app.get("/api/negotiations")
def negotiations() -> list[dict]:
    return store.list_negotiations()


@app.post("/api/negotiations")
def new_negotiation(body: DisputeIn) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "text is required")
    title = (body.title or text.split("\n")[0])[:90]
    nid = store.create_negotiation(title, text, body.scenario_id)
    start_negotiation(nid)
    return {"id": nid, "title": title}


@app.get("/api/negotiations/{nid}")
def negotiation_detail(nid: str) -> dict:
    neg = store.get_negotiation(nid)
    if not neg:
        raise HTTPException(404, "not found")
    return {
        "negotiation": neg,
        "turns": store.list_turns(nid),
        "decisions": store.list_decisions(nid),
        "settlements": store.list_settlements(nid),
    }


@app.get("/api/decisions")
def decisions() -> list[dict]:
    return store.list_decisions(pending_only=True)


@app.post("/api/decisions/{did}/respond")
def respond(did: str, body: DecisionIn) -> dict:
    action = "approved" if body.action.lower() in {"approved", "approve"} else "declined"
    d = store.resolve_decision(did, action, body.note)
    if not d:
        raise HTTPException(404, "decision not found")
    return {"ok": True, "decision": {**d, "status": action}}


@app.get("/api/ledger")
def ledger() -> dict:
    return {"saved": store.total_saved(), "settlements": store.list_settlements()}


@app.post("/api/reset")
def reset() -> dict:
    store.reset_all()
    return {"ok": True}
