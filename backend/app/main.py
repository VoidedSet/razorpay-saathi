"""
main.py — FastAPI entry point.

/api/chat  →  LangGraph graph  →  astream_events  →  SSE to frontend

SSE event protocol (JSON on each `data:` line):
  { "type": "audit",  "agent": "Manager Agent", "detail": "...", "model": "...", "ms": 230 }
  { "type": "token",  "content": "Hello " }
  { "type": "error",  "message": "..." }
  { "type": "done",   "session_phase": "checkout" }   ← client persists this
"""

import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from app.graph import build_graph, AgentState, AGENT_LABELS
from app.config import active_config
from app.db import init_db

load_dotenv()

# Initialize SQLite database schema and seed data
init_db()

app = FastAPI(title="Razorpay Saathi — Agentic Store Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Graph compiled once at startup
_graph = build_graph()

# ── Node classifications ──────────────────────────────────────────────────────
_MANAGER_NODES = {"manager_init", "manager_audit"}
_AGENT_NODES   = {"sales_agent", "billing_agent", "support_agent"}
_ALL_NODES     = _MANAGER_NODES | _AGENT_NODES


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:       str
    session_id:    str        = "default"
    user_id:       str        = "usr_001"
    history:       list[dict] = []    # [{role, content}]
    session_phase: str        = "browsing"  # persisted by client from done event
    # A2A / personalization
    client_type:   str        = "human"     # "human" | "agent"
    cart:          list[dict] = []          # [{name, qty, price, currency}]
    agent_profile: dict       = {}          # A2A: {name, preferences, budget, currency}


# ── SSE stream ────────────────────────────────────────────────────────────────

async def langgraph_stream(req: ChatRequest):
    history_messages = []
    for turn in req.history:
        if turn["role"] == "user":
            history_messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            history_messages.append(AIMessage(content=turn["content"]))

    initial_state: AgentState = {
        "messages":         history_messages + [HumanMessage(content=req.message)],
        "session_id":       req.session_id,
        "user_id":          req.user_id,
        "session_phase":    req.session_phase,
        "user_profile":     {},    # manager_init will populate on first turn
        "cart":             req.cart,
        "audit_log":        [],
        "manager_notes":    [],
        "discount_ceiling": 15.0,  # safe default; manager_init will compute real value
        "client_type":      req.client_type,
        "agent_profile":    req.agent_profile,
    }

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    current_node:      str | None   = None
    node_start_times:  dict         = {}
    node_models:       dict         = {}
    final_phase:       str          = req.session_phase
    last_audit_count:  int          = 0   # track which audit entries are new

    try:
        async for event in _graph.astream_events(initial_state, version="v2"):
            kind: str = event["event"]
            name: str = event.get("name", "")
            meta: dict = event.get("metadata", {})
            data: dict = event.get("data", {})

            # ── Node started ──────────────────────────────────────────────────
            if kind == "on_chain_start" and name in _ALL_NODES:
                current_node = name
                node_start_times[name] = time.monotonic()
                label = AGENT_LABELS.get(name, name)

                if name in _AGENT_NODES:
                    # Show context size + client type tag
                    inp   = data.get("input", {})
                    msgs  = inp.get("messages", [])
                    n_ctx = len(msgs)
                    tag   = "[agent] " if req.client_type == "agent" else ""
                    yield _sse({
                        "type":   "audit",
                        "agent":  label,
                        "detail": f"{tag}ctx={n_ctx} msgs",
                        "model":  None,
                        "ms":     None,
                    })

            # ── LLM call started — capture model name ─────────────────────────
            elif kind == "on_chat_model_start" and current_node:
                model = meta.get("ls_model_name") or name
                node_models[current_node] = model
                label    = AGENT_LABELS.get(current_node, current_node)
                role_tag = "supervisor" if current_node in _MANAGER_NODES else "agent"
                yield _sse({
                    "type":   "audit",
                    "agent":  label,
                    "detail": f"LLM [{role_tag}] → {model}",
                    "model":  model,
                    "ms":     None,
                })

            # ── Node finished — emit new audit_log entries ────────────────────
            elif kind == "on_chain_end" and name in _ALL_NODES:
                elapsed    = _elapsed_ms(node_start_times, name)
                model_used = node_models.get(name)
                output     = data.get("output", {})
                label      = AGENT_LABELS.get(name, name)

                # Read new audit entries from node output
                full_log  = output.get("audit_log", [])
                new_entries = full_log[last_audit_count:]
                last_audit_count = len(full_log)

                for entry in new_entries:
                    yield _sse({
                        "type":   "audit",
                        "agent":  entry.get("agent", label),
                        "detail": entry.get("detail", ""),
                        "model":  model_used,
                        "ms":     elapsed if entry == new_entries[-1] else None,
                    })

                # Capture updated session phase from manager_init
                if name == "manager_init" and "session_phase" in output:
                    final_phase = output["session_phase"]

                current_node = None

            # ── Token stream — agent nodes only ──────────────────────────────
            elif kind == "on_chat_model_stream" and current_node in _AGENT_NODES:
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse({"type": "token", "content": chunk.content})

        # Include updated phase so frontend can persist it
        yield _sse({"type": "done", "session_phase": final_phase})

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done", "session_phase": final_phase})


def _elapsed_ms(start_times: dict, key: str) -> int | None:
    t = start_times.get(key)
    return round((time.monotonic() - t) * 1000) if t else None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        langgraph_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health():
    return {
        "status":     "ok",
        "service":    "razorpay-saathi-backend",
        "llm_config": active_config(),
    }
