"use client";

import { useState, useRef, useEffect, FormEvent } from "react";

// ── Types ────────────────────────────────────────────────────────────────────
interface AuditEvent {
  type: "audit";
  agent: string;
  detail: string;
  model?: string | null;   // LLM model name used at this step
  ms?: number | null;      // wall-clock milliseconds for this node
}

interface TokenEvent {
  type: "token";
  content: string;
}

interface DoneEvent {
  type: "done";
}

interface ErrorEvent {
  type: "error";
  message: string;
}

type SseEvent = AuditEvent | TokenEvent | DoneEvent | ErrorEvent;

interface Message {
  role: "user" | "assistant";
  content: string;
  auditLog: AuditEvent[];
}

// ── Chat hook ─────────────────────────────────────────────────────────────────
function useAgentChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);

  const sendMessage = async (text: string, currentMessages: Message[]) => {
    if (!text.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: text, auditLog: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    // Placeholder assistant message we'll fill in as tokens arrive
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", auditLog: [] },
    ]);

    // Build history for the backend (exclude the placeholder we just added)
    const history = currentMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          const event: SseEvent = JSON.parse(raw);

          setMessages((prev) => {
            const next = [...prev];
            const msg = { ...next[next.length - 1] };

            if (event.type === "audit") {
              msg.auditLog = [...msg.auditLog, event];
            } else if (event.type === "token") {
              msg.content += event.content;
            } else if (event.type === "error") {
              msg.content = `⚠️ Agent error: ${event.message}`;
            }
            next[next.length - 1] = msg;
            return next;
          });
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: "⚠️ Could not reach backend. Is `uvicorn` running on :8000?",
          auditLog: [],
        };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  };

  return { messages, input, setInput, streaming, sendMessage };
}

// ── Components ────────────────────────────────────────────────────────────────

/** Fetches /health once and shows the active model config in the header. */
function ActiveModelBadge() {
  const [cfg, setCfg] = useState<{ provider: string; model: string; routing_model: string } | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((r) => r.json())
      .then((d) => setCfg(d.llm_config))
      .catch(() => {});
  }, []);

  if (!cfg) return null;
  const sameModel = cfg.model === cfg.routing_model;
  return (
    <div className="header-model-info">
      <span className="header-model-label">agent</span>
      <span className="header-model-name">{cfg.model}</span>
      {!sameModel && (
        <>
          <span className="header-model-label">router</span>
          <span className="header-model-name">{cfg.routing_model}</span>
        </>
      )}
    </div>
  );
}

function ModelBadge({ model }: { model?: string | null }) {
  if (!model) return null;
  // Shorten long model names for display
  const short = model.length > 22 ? model.slice(0, 20) + "…" : model;
  return <span className="audit-model-badge" title={model}>{short}</span>;
}

function TimingChip({ ms }: { ms?: number | null }) {
  if (!ms) return null;
  const label = ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
  return <span className="audit-timing">{label}</span>;
}

function AuditAccordion({ log }: { log: AuditEvent[] }) {
  const [open, setOpen] = useState(false);
  if (log.length === 0) return null;

  // Summarise: unique agents + last timing
  const lastMs = [...log].reverse().find((e) => e.ms)?.ms;
  const agents = [...new Set(log.map((e) => e.agent))];
  const summary = agents.join(" → ");

  return (
    <div className="audit-accordion">
      <button onClick={() => setOpen((o) => !o)} className="audit-toggle">
        <span>{open ? "▲" : "▼"}</span>
        <span className="audit-summary">{summary}</span>
        {lastMs && <TimingChip ms={lastMs} />}
        <span className="audit-step-count">{log.length} steps</span>
      </button>
      {open && (
        <ul className="audit-list">
          {log.map((e, i) => (
            <li key={i} className="audit-item">
              <span className="audit-agent">{e.agent}</span>
              <span className="audit-detail">{e.detail}</span>
              <span className="audit-meta">
                <ModelBadge model={e.model} />
                <TimingChip ms={e.ms} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChatBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={`bubble-wrapper ${isUser ? "bubble-user" : "bubble-agent"}`}>
      <div className={`bubble ${isUser ? "bubble-user-inner" : "bubble-agent-inner"}`}>
        {msg.content || <span className="cursor-blink">▌</span>}
      </div>
      {!isUser && <AuditAccordion log={msg.auditLog} />}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Home() {
  const { messages, input, setInput, streaming, sendMessage } = useAgentChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendMessage(input, messages);
  };

  return (
    <div className="chat-root">
      <header className="chat-header">
        <span className="chat-logo">⚡</span>
        <h1 className="chat-title">Razorpay Saathi</h1>
        <span className="chat-subtitle">Agentic Store Assistant</span>
        <ActiveModelBadge />
      </header>

      <main className="chat-messages">
        {messages.length === 0 && (
          <p className="chat-empty">Send a message to start talking to the agents.</p>
        )}
        {messages.map((m, i) => (
          <ChatBubble key={i} msg={m} />
        ))}
        <div ref={bottomRef} />
      </main>

      <form className="chat-form" onSubmit={onSubmit}>
        <input
          id="chat-input"
          className="chat-input"
          type="text"
          placeholder="Ask about a product, request a deal…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={streaming}
          autoComplete="off"
          autoFocus
        />
        <button
          id="chat-send"
          className="chat-send"
          type="submit"
          disabled={streaming || !input.trim()}
        >
          {streaming ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
