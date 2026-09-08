"""SQLite persistence for Envoy: negotiations, transcript turns, decision
cards, settlements, savings ledger."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any

from .config import DB_PATH

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _db_init(_conn)
    return _conn


def _db_init(c: sqlite3.Connection) -> None:
    c.execute(
        """CREATE TABLE IF NOT EXISTS negotiations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, raw_text TEXT NOT NULL,
            scenario_id TEXT, status TEXT NOT NULL DEFAULT 'queued',
            strategy TEXT, outcome TEXT, summary TEXT,
            created_at REAL, updated_at REAL)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS turns (
            id TEXT PRIMARY KEY, neg_id TEXT NOT NULL, ts REAL NOT NULL,
            side TEXT NOT NULL, intent TEXT, message TEXT NOT NULL, offer TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY, neg_id TEXT NOT NULL, ts REAL NOT NULL,
            kind TEXT NOT NULL, question TEXT NOT NULL, payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending', response TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS settlements (
            id TEXT PRIMARY KEY, neg_id TEXT NOT NULL, ts REAL NOT NULL,
            amount REAL NOT NULL, currency TEXT NOT NULL,
            terms TEXT NOT NULL, reference TEXT NOT NULL)"""
    )
    c.commit()


def now() -> float:
    return time.time()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ------------------------------------------------------------ negotiations --

def create_negotiation(title: str, raw_text: str, scenario_id: str | None = None) -> str:
    nid = new_id()
    with _lock:
        _db().execute(
            "INSERT INTO negotiations (id,title,raw_text,scenario_id,status,created_at,updated_at) VALUES (?,?,?,?,'queued',?,?)",
            (nid, title, raw_text, scenario_id, now(), now()),
        )
        _db().commit()
    add_turn(nid, "system", "opened", f"Dispute received: {title}")
    return nid


def update_negotiation(nid: str, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock:
        _db().execute(
            f"UPDATE negotiations SET {cols}, updated_at=? WHERE id=?",
            (*fields.values(), now(), nid),
        )
        _db().commit()


def get_negotiation(nid: str) -> dict[str, Any] | None:
    row = _db().execute("SELECT * FROM negotiations WHERE id=?", (nid,)).fetchone()
    return dict(row) if row else None


def list_negotiations() -> list[dict[str, Any]]:
    rows = _db().execute("SELECT * FROM negotiations ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------- turns --

def add_turn(nid: str, side: str, intent: str, message: str, offer: dict | None = None) -> str:
    tid = new_id()
    with _lock:
        _db().execute(
            "INSERT INTO turns (id,neg_id,ts,side,intent,message,offer) VALUES (?,?,?,?,?,?,?)",
            (tid, nid, now(), side, intent, message, json.dumps(offer) if offer else None),
        )
        _db().commit()
    return tid


def list_turns(nid: str) -> list[dict[str, Any]]:
    rows = _db().execute(
        "SELECT * FROM turns WHERE neg_id=? ORDER BY ts ASC", (nid,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["offer"] = json.loads(d["offer"]) if d["offer"] else None
        out.append(d)
    return out


# ---------------------------------------------------------------- decisions --

def create_decision(nid: str, kind: str, question: str, payload: dict) -> str:
    did = new_id()
    with _lock:
        _db().execute(
            "INSERT INTO decisions (id,neg_id,ts,kind,question,payload,status) VALUES (?,?,?,?,?,?,'pending')",
            (did, nid, now(), kind, question, json.dumps(payload)),
        )
        _db().commit()
    add_turn(nid, "system", "needs_you", question, payload.get("offer"))
    update_negotiation(nid, status="needs_you")
    return did


def resolve_decision(did: str, action: str, response: str | None = None) -> dict | None:
    with _lock:
        row = _db().execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone()
        if not row:
            return None
        _db().execute(
            "UPDATE decisions SET status=?, response=? WHERE id=?", (action, response, did)
        )
        _db().commit()
    d = dict(row)
    d["payload"] = json.loads(d["payload"] or "{}")
    return d


def get_decision(did: str) -> dict | None:
    row = _db().execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"] or "{}")
    return d


def list_decisions(nid: str | None = None, pending_only: bool = False) -> list[dict[str, Any]]:
    q = "SELECT * FROM decisions"
    cond, args = [], []
    if nid:
        cond.append("neg_id=?"); args.append(nid)
    if pending_only:
        cond.append("status='pending'")
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY ts ASC"
    rows = _db().execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"] or "{}")
        out.append(d)
    return out


# --------------------------------------------------------------- settlements --

def record_settlement(nid: str, amount: float, currency: str, terms: str) -> str:
    sid = new_id()
    ref = f"ENV-{new_id().upper()}"
    with _lock:
        _db().execute(
            "INSERT INTO settlements (id,neg_id,ts,amount,currency,terms,reference) VALUES (?,?,?,?,?,?,?)",
            (sid, nid, now(), amount, currency, terms, ref),
        )
        _db().commit()
    add_turn(nid, "system", "settled", f"Settlement executed: {currency} {amount:,.0f} — {terms}")
    update_negotiation(nid, status="settled", outcome=f"{currency} {amount:,.0f}")
    return sid


def list_settlements(nid: str | None = None) -> list[dict[str, Any]]:
    q = "SELECT * FROM settlements"
    args: list = []
    if nid:
        q += " WHERE neg_id=?"
        args.append(nid)
    q += " ORDER BY ts ASC"
    rows = _db().execute(q, args).fetchall()
    return [dict(r) for r in rows]


def total_saved() -> dict[str, float]:
    rows = _db().execute("SELECT currency, SUM(amount) AS total FROM settlements GROUP BY currency").fetchall()
    return {r["currency"]: r["total"] for r in rows}
