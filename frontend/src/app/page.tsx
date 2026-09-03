"use client";

import { useState, useRef, useEffect, FormEvent } from "react";

// ── Types ────────────────────────────────────────────────────────────────────
interface AuditEvent {
  type: "audit";
  agent: string;
  detail: string;
}

interface TokenEvent {
  type: "token";
  content: string;
}

interface DoneEvent {
  type: "done";
}

type SseEvent = AuditEvent | TokenEvent | DoneEvent;

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

  const sendMessage = async (text: string) => {
    if (!text.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: text, auditLog: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    // Placeholder assistant message we'll fill in as tokens arrive
    const assistantIdx = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", auditLog: [] },
    ]);

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

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
function AuditAccordion({ log }: { log: AuditEvent[] }) {
  const [open, setOpen] = useState(false);
  if (log.length === 0) return null;
  return (
    <div className="audit-accordion">
      <button onClick={() => setOpen((o) => !o)} className="audit-toggle">
        {open ? "▲" : "▼"} Agent Activity ({log.length} steps)
      </button>
      {open && (
        <ul className="audit-list">
          {log.map((e, i) => (
            <li key={i} className="audit-item">
              <span className="audit-agent">{e.agent}</span>
              <span className="audit-detail">{e.detail}</span>
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
    sendMessage(input);
  };

  return (
    <div className="chat-root">
      <header className="chat-header">
        <span className="chat-logo">⚡</span>
        <h1 className="chat-title">Razorpay Saathi</h1>
        <span className="chat-subtitle">Agentic Store Assistant</span>
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
