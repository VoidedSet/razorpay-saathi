"""
main.py — FastAPI entry point.

/api/chat  →  LangGraph graph  →  astream_events  →  SSE to frontend

SSE event protocol (JSON on each `data:` line):
  { "type": "audit",      "agent": "Manager Agent", "detail": "...", "model": "...", "ms": 230 }
  { "type": "token",      "content": "Hello " }
  { "type": "correction", "message": "Manager policy override: ..." }  ← Manager overrode the response
  { "type": "component",  "component": "product_card", "props": {...} }  ← generative-UI card streamed to the registry
  { "type": "error",      "message": "..." }
  { "type": "done",       "session_phase": "checkout" }   ← client persists this
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
_MANAGER_NODES = {"manager_init", "manager_audit", "sales_tools"}
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


# ── <think> stream filter ───────────────────────────────────────────────────────
# Reasoning models (e.g. Qwen) emit their chain-of-thought as ordinary content
# tokens wrapped in <think>...</think>. We strip those spans from the customer-
# facing token stream, safely across chunk boundaries (a tag may be split between
# two chunks).

def _partial_tag_suffix(s: str, tag: str) -> int:
    """Longest k in [1, len(tag)-1] such that s ends with tag[:k] (a split-open tag)."""
    for k in range(min(len(s), len(tag) - 1), 0, -1):
        if s.endswith(tag[:k]):
            return k
    return 0


class _ThinkStripper:
    """Removes <think>...</think> spans from a streamed token sequence."""

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._in_think = False
        self._buf = ""

    def feed(self, text: str) -> str:
        self._buf += text or ""
        out: list[str] = []
        while self._buf:
            if not self._in_think:
                idx = self._buf.find(self._OPEN)
                if idx != -1:
                    out.append(self._buf[:idx])
                    self._buf = self._buf[idx + len(self._OPEN):]
                    self._in_think = True
                    continue
                keep = _partial_tag_suffix(self._buf, self._OPEN)
                if keep:
                    out.append(self._buf[:-keep])
                    self._buf = self._buf[-keep:]
                else:
                    out.append(self._buf)
                    self._buf = ""
                break
            else:
                idx = self._buf.find(self._CLOSE)
                if idx != -1:
                    self._buf = self._buf[idx + len(self._CLOSE):]
                    self._in_think = False
                    continue
                keep = _partial_tag_suffix(self._buf, self._CLOSE)
                self._buf = self._buf[-keep:] if keep else ""
                break
        return "".join(out)

    def flush(self) -> str:
        """Emit any trailing buffered text at stream end; drop an unclosed think."""
        if self._in_think:
            self._buf = ""
            return ""
        out, self._buf = self._buf, ""
        return out


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
        "manager_correction": "",  # set by manager_audit when a response is overridden
        "ui_components":    [],     # generative-UI components streamed to the frontend registry
        "just_entered_checkout": False,  # set by manager_init; gates the checkout widget
    }

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    current_node:      str | None   = None
    node_start_times:  dict         = {}
    node_models:       dict         = {}
    final_phase:       str          = req.session_phase
    last_audit_count:  int          = 0   # track which audit entries are new
    last_component_count: int       = 0   # track which ui_components are new
    think:  _ThinkStripper | None   = None  # strips <think>...</think> from the live stream

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
                think = _ThinkStripper()   # fresh reasoning-token filter per LLM call
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

                # Manager override → surface it to the customer as a distinct event
                if name == "manager_audit" and output.get("manager_correction"):
                    yield _sse({
                        "type":    "correction",
                        "message": output["manager_correction"],
                    })

                # ── Generative UI components (grounded or agent-authored) ──────────
                # Guard on key presence: only nodes that actually return ui_components
                # advance the counter, so we never re-emit or reset on other nodes.
                if "ui_components" in output:
                    full_components = output.get("ui_components") or []
                    for comp in full_components[last_component_count:]:
                        yield _sse({
                            "type":      "component",
                            "component": comp.get("component", ""),
                            "props":     comp.get("props", {}),
                        })
                    last_component_count = len(full_components)

                current_node = None

            # ── Token stream — agent nodes only (with <think> filtered out) ───
            elif kind == "on_chat_model_stream" and current_node in _AGENT_NODES:
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    visible = think.feed(chunk.content) if think else chunk.content
                    if visible:
                        yield _sse({"type": "token", "content": visible})

            # ── LLM call finished — flush any tail held by the <think> filter ─
            elif kind == "on_chat_model_end" and current_node in _AGENT_NODES:
                if think:
                    tail = think.flush()
                    if tail:
                        yield _sse({"type": "token", "content": tail})

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
