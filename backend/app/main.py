"""
main.py — FastAPI entry point.

/api/chat  →  LangGraph graph  →  astream_events  →  SSE to frontend

SSE event protocol (JSON on each `data:` line):
  { "type": "audit", "agent": "Manager Agent", "detail": "...", "model": "qwen2.5:3b", "ms": 230 }
  { "type": "token", "content": "Hello! " }
  { "type": "done" }
  { "type": "error", "message": "..." }
"""

import json
import time
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from app.graph import build_graph, AgentState, AGENT_LABELS
from app.config import active_config

load_dotenv()

app = FastAPI(title="Razorpay Saathi — Agentic Store Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compile graph once at startup (not on every request)
_graph = build_graph()

# Node name sets
_AGENT_NODES = {"sales_agent", "billing_agent", "promo_agent"}
_ALL_NODES   = {"manager"} | _AGENT_NODES


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:       str
    session_id:    str        = "default"
    history:       list[dict] = []  # [{role: "user"|"assistant", content: "..."}]
    # ── A2A / personalization fields ─────────────────────────────────────────
    client_type:   str        = "human"  # "human" | "agent"
    cart:          list[dict] = []       # [{name, qty, price, currency}]
    agent_profile: dict       = {}       # A2A: {name, preferences, budget, currency}


# ── SSE stream generator ──────────────────────────────────────────────────────

async def langgraph_stream(req: ChatRequest):
    """
    Runs the LangGraph graph and converts astream_events into enriched SSE lines.

    Each audit event now carries:
      - model: the LLM model name used at that step
      - ms:    wall-clock milliseconds for the node
      - comm:  inter-agent communication detail (what was passed between nodes)
    """
    history_messages = []
    for turn in req.history:
        if turn["role"] == "user":
            history_messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            history_messages.append(AIMessage(content=turn["content"]))

    initial_state: AgentState = {
        "messages":      history_messages + [HumanMessage(content=req.message)],
        "next_agent":    "",
        "audit_log":     [],
        "client_type":   req.client_type,
        "cart":          req.cart,
        "agent_profile": req.agent_profile,
    }

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    # ── Per-stream tracking ───────────────────────────────────────────────────
    current_node: str | None = None
    node_start_times: dict[str, float] = {}
    node_models: dict[str, str] = {}   # node_name → model name captured from LLM event

    cfg = active_config()              # static config for display

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

                # For agent nodes, show forwarded context + client type
                comm_detail = None
                if name in _AGENT_NODES:
                    inp    = data.get("input", {})
                    msgs   = inp.get("messages", [])
                    n_ctx  = len(msgs)
                    last_human = next(
                        (m.content[:80] + "…" if len(m.content) > 80 else m.content
                         for m in reversed(msgs)
                         if hasattr(m, "type") and m.type == "human"),
                        None,
                    )
                    client_tag = f"[{req.client_type}] " if req.client_type == "agent" else ""
                    comm_detail = (
                        f"{client_tag}ctx={n_ctx} msgs"
                        + (f' | "{last_human}"' if last_human else "")
                    )

                yield _sse({
                    "type":   "audit",
                    "agent":  label,
                    "detail": comm_detail or "Starting…",
                    "model":  node_models.get(name),
                    "ms":     None,
                })

            # ── LLM call started inside a node — capture model name ───────────
            elif kind == "on_chat_model_start" and current_node:
                # LangChain populates ls_model_name in metadata
                model_name = (
                    meta.get("ls_model_name")
                    or meta.get("ls_model_type")
                    or name   # fallback: class name e.g. "ChatOllama"
                )
                node_models[current_node] = model_name
                label = AGENT_LABELS.get(current_node, current_node)

                # Determine routing model vs agent model label
                is_manager = current_node == "manager"
                role_tag = "router" if is_manager else "agent"

                yield _sse({
                    "type":   "audit",
                    "agent":  label,
                    "detail": f"LLM call [{role_tag}] → {model_name}",
                    "model":  model_name,
                    "ms":     None,
                })

            # ── Manager finished → emit routing decision with timing ───────────
            elif kind == "on_chain_end" and name == "manager":
                elapsed = _elapsed_ms(node_start_times, "manager")
                output     = data.get("output", {})
                next_agent = output.get("next_agent", "")
                label_next = AGENT_LABELS.get(next_agent, next_agent)
                model_used = node_models.get("manager", cfg["routing_model"])

                yield _sse({
                    "type":   "audit",
                    "agent":  "Manager Agent",
                    "detail": f"Decision: route → {label_next}",
                    "model":  model_used,
                    "ms":     elapsed,
                })
                current_node = None

            # ── Agent node finished → emit timing + model ─────────────────────
            elif kind == "on_chain_end" and name in _AGENT_NODES:
                elapsed    = _elapsed_ms(node_start_times, name)
                model_used = node_models.get(name, cfg["model"])
                label      = AGENT_LABELS.get(name, name)

                yield _sse({
                    "type":   "audit",
                    "agent":  label,
                    "detail": "Response complete",
                    "model":  model_used,
                    "ms":     elapsed,
                })
                current_node = None

            # ── Token stream — agents only, never manager ─────────────────────
            elif kind == "on_chat_model_stream" and current_node in _AGENT_NODES:
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse({"type": "token", "content": chunk.content})

        yield _sse({"type": "done"})

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})


def _elapsed_ms(start_times: dict, key: str) -> int | None:
    t = start_times.get(key)
    return round((time.monotonic() - t) * 1000) if t else None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        langgraph_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {
        "status":     "ok",
        "service":    "razorpay-saathi-backend",
        "llm_config": active_config(),
    }
