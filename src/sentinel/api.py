"""HTTP surface over the audit graph, with a review queue that outlives the process.

Run: uvicorn sentinel.api:app --host 0.0.0.0 --port 8000
Needs SENTINEL_API_KEY plus the usual AZURE_OPENAI_* vars. SENTINEL_STATE_DIR (default
./data) is where reviews.db lives — on Azure Container Apps that must be a mounted share,
because the container filesystem does not survive scale-to-zero.
"""

import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

from sentinel.audit import _RANK, build_graph, default_searcher

STATE_DIR = Path(os.environ.get("SENTINEL_STATE_DIR") or Path(__file__).parents[2] / "data")

app = FastAPI(title="Sentinel", description="Audits UK financial promotions against the FCA Handbook.")

_GRAPH = None
_CONN = None
_LOCK = threading.Lock()  # ponytail: one lock for the whole graph — correct at one replica and one reviewer, revisit if throughput ever matters


class AuditRequest(BaseModel):
    text: str
    channel: Literal["promo_email", "promo_social", "promo_web"] = "promo_email"


def _graph():
    """Built once per process, over a sqlite file that outlives the process."""
    global _GRAPH, _CONN
    if _GRAPH is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if _CONN is not None:
            _CONN.close()  # a real restart closes it; an in-process rebuild must too, or the new connection cannot take the exclusive lock below
        # check_same_thread=False: FastAPI runs sync endpoints on a threadpool, so the
        # connection is touched from several threads. _LOCK is what serializes them.
        _CONN = sqlite3.connect(STATE_DIR / "reviews.db", check_same_thread=False)
        saver = SqliteSaver(_CONN)
        saver.setup()  # creates the tables — and sets journal_mode=WAL, which is why the override comes after
        # WAL needs a shared-memory -shm file. Azure Files is SMB and does not support that
        # reliably, so the deployed queue is the one place it would break. DELETE journalling
        # costs concurrency we do not have anyway: max-replicas is 1 and _LOCK serializes writers.
        _CONN.execute("PRAGMA journal_mode=DELETE")
        _GRAPH = build_graph(default_searcher(), checkpointer=saver)
    return _GRAPH


def require_key(x_api_key: str = Header(default="")) -> None:
    """Fails closed: no configured key means no access, never open access."""
    expected = os.environ.get("SENTINEL_API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def _paused_thread_ids(graph) -> list[str]:
    """Distinct thread ids known to the checkpointer, newest first."""
    seen = {}
    for cp in graph.checkpointer.list(None):
        seen.setdefault(cp.config["configurable"]["thread_id"], None)
    return list(seen)


@app.post("/audit", dependencies=[Depends(require_key)])
def post_audit(req: AuditRequest):
    review_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": review_id}}
    with _LOCK:
        state = _graph().invoke({"text": req.text, "channel": req.channel}, config)
    if "__interrupt__" in state:
        pending = state["__interrupt__"][0].value["pending"]
        return JSONResponse(status_code=202, content={"review_id": review_id, "pending": pending})
    return {"review_id": None, "report": state["report"]}


@app.get("/reviews", dependencies=[Depends(require_key)])
def get_reviews():
    out = []
    with _LOCK:
        graph = _graph()
        for thread_id in _paused_thread_ids(graph):
            state = graph.get_state({"configurable": {"thread_id": thread_id}})
            if state.interrupts:
                out.append({"review_id": thread_id, "pending": state.interrupts[0].value["pending"]})
    return {"reviews": out}


@app.post("/reviews/{review_id}/resume", dependencies=[Depends(require_key)])
def post_resume(review_id: str, resolutions: dict[str, str]):
    bad = [v for v in resolutions.values() if v not in _RANK]
    if bad:
        raise HTTPException(status_code=422, detail=f"verdict must be one of {sorted(_RANK)}, got {bad}")
    config = {"configurable": {"thread_id": review_id}}
    with _LOCK:
        graph = _graph()
        if not graph.get_state(config).interrupts:
            raise HTTPException(status_code=404, detail=f"no pending review {review_id}")
        state = graph.invoke(Command(resume=resolutions), config)
    return {"review_id": review_id, "report": state["report"]}
