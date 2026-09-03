"""
main.py — FastAPI entry point.

/api/chat  →  LangGraph graph  →  astream_events  →  SSE to frontend

SSE event protocol (JSON on each `data:` line):
  { "type": "audit", "agent": "Manager Agent", "detail": "Routing → Sales Agent" }
  { "type": "token", "content": "Hello! " }
  { "type": "done" }
  { "type": "error", "message": "..." }
"""

import json
import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
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

# ── Node names that are "agent" nodes (i.e., ones that stream tokens to UI) ──
_AGENT_NODES = {"sales_agent", "billing_agent", "promo_agent"}
_ALL_NODES   = {"manager"} | _AGENT_NODES


# ── Request / Response ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    history: list[dict] = []    # [{role: "user"|"assistant", content: "..."}]


# ── SSE stream generator ───────────────────────────────────────────────────────

async def langgraph_stream(req: ChatRequest):
    """
    Runs the LangGraph graph and converts astream_events into SSE lines.

    Event filtering logic:
      on_chain_start  (node name in _ALL_NODES)  → emit audit event
      on_chain_end    (name == "manager")         → emit routing audit event
      on_chat_model_stream (inside agent node)    → emit token event
      graph done                                  → emit done event
    """

    # Rebuild conversation history from client-sent history
    from langchain_core.messages import HumanMessage, AIMessage
    history_messages = []
    for turn in req.history:
        if turn["role"] == "user":
            history_messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            history_messages.append(AIMessage(content=turn["content"]))

    initial_state: AgentState = {
        "messages":   history_messages + [HumanMessage(content=req.message)],
        "next_agent": "",
        "audit_log":  [],
    }

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    current_node: str | None = None   # track which node is active

    try:
        async for event in _graph.astream_events(initial_state, version="v2"):
            kind: str = event["event"]
            name: str = event.get("name", "")

            # ── Node started ──────────────────────────────────────────────────
            if kind == "on_chain_start" and name in _ALL_NODES:
                current_node = name
                label = AGENT_LABELS.get(name, name)
                yield _sse({
                    "type":   "audit",
                    "agent":  label,
                    "detail": "Starting…",
                })

            # ── Manager finished → emit routing decision ───────────────────
            elif kind == "on_chain_end" and name == "manager":
                output     = event["data"].get("output", {})
                next_agent = output.get("next_agent", "")
                if next_agent:
                    label = AGENT_LABELS.get(next_agent, next_agent)
                    yield _sse({
                        "type":   "audit",
                        "agent":  "Manager Agent",
                        "detail": f"Approved routing → {label}",
                    })
                current_node = None

            # ── Agent node finished ────────────────────────────────────────
            elif kind == "on_chain_end" and name in _AGENT_NODES:
                current_node = None

            # ── Token stream — only from agent nodes, never from manager ──
            elif kind == "on_chat_model_stream" and current_node in _AGENT_NODES:
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse({"type": "token", "content": chunk.content})

        yield _sse({"type": "done"})

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        langgraph_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
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
