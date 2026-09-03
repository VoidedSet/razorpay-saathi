"""
main.py — FastAPI entry point.

Step 2 placeholder: /api/chat streams mock SSE tokens.
Real LangGraph integration happens next.
"""

import asyncio
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Razorpay Saathi — Agentic Store Backend")

# Allow the Next.js dev server to reach this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


async def mock_stream(message: str):
    """
    Yields Server-Sent Events (SSE) lines.
    Each event is a JSON object that the frontend will parse.
    Format mirrors what LangGraph will eventually emit.
    """
    # Simulate Manager Agent routing decision
    audit_events = [
        {"type": "audit", "agent": "Manager Agent", "detail": f"Received message: '{message}'"},
        {"type": "audit", "agent": "Manager Agent", "detail": "Routing to: Sales Agent"},
        {"type": "audit", "agent": "Sales Agent",   "detail": "Composing response..."},
    ]

    for event in audit_events:
        yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.3)

    # Simulate streaming tokens from Sales Agent
    reply_tokens = "Hello! I'm your AI Sales Agent powered by Razorpay Saathi. How can I help you today?".split()
    for token in reply_tokens:
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.05)

    # Signal stream end
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        mock_stream(req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # important for nginx proxying
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "razorpay-saathi-backend"}
