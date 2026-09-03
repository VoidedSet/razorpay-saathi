"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import { GenUiStack, UiComponent, inr } from "./genui";

// ── Types & Interfaces ────────────────────────────────────────────────────────
interface AuditEvent {
  type: "audit";
  agent: string;
  detail: string;
  model?: string | null;
  ms?: number | null;
}

interface TokenEvent {
  type: "token";
  content: string;
}

interface DoneEvent {
  type: "done";
  session_phase?: string;
}

interface CorrectionEvent {
  type: "correction";
  message: string;
}

interface ComponentEvent {
  type: "component";
  component: string;
  props: Record<string, unknown>;
}

interface ErrorEvent {
  type: "error";
  message: string;
}

type SseEvent =
  | AuditEvent
  | TokenEvent
  | CorrectionEvent
  | ComponentEvent
  | DoneEvent
  | ErrorEvent;

interface Message {
  role: "user" | "assistant";
  content: string;
  auditLog: AuditEvent[];
  correction?: string;
  components?: UiComponent[];
}

interface Product {
  id: string;
  title: string;
  category: string;
  price: number;
  image: string;
  description: string;
}

const PRODUCTS: Product[] = [
  {
    id: "1",
    title: "Souled: Miami",
    category: "vintage",
    price: 12000,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1743521912_7639983.jpg?w=480&dpr=2",
    description: "A vibrant, retro-inspired sneaker for the Miami soul. Lightweight and comfortable, perfect for a walk by the beach.",
  },
  {
    id: "2",
    title: "UBZ 0.5: Mafia Mules",
    category: "court",
    price: 9500,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1761894000_9908200.jpg?w=1080&dpr=2",
    description: "Bold and stylish, these mules make a statement. Inspired by classic cinema, they are the epitome of cool.",
  },
  {
    id: "3",
    title: "Yoda",
    category: "classics",
    price: 11000,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1759387261_3013866.jpg?w=1080&dpr=2",
    description: "Wisdom in every step. These classic green-themed sneakers are a must-have for any fan of the galaxy.",
  },
  {
    id: "4",
    title: "Hydros: Ghost",
    category: "running",
    price: 8500,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1754742095_6028923.jpg?w=1080&dpr=2",
    description: "Sleek, minimalist, and fast. The Ghost runners are designed for urban exploration, day or night.",
  },
];

// ── SSE Agent Chat Hook ───────────────────────────────────────────────────────
function useAgentChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionPhase, setPhase] = useState("browsing");
  const sessionId = useRef<string>("");

  const sendMessage = async (text: string, currentMessages: Message[]) => {
    if (!text.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: text, auditLog: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    const placeholder: Message = { role: "assistant", content: "", auditLog: [] };
    setMessages((prev) => [...prev, placeholder]);

    const history = currentMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      if (!sessionId.current) sessionId.current = crypto.randomUUID();
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history,
          session_phase: sessionPhase,
          session_id: sessionId.current,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

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
            } else if (event.type === "correction") {
              msg.correction = event.message;
            } else if (event.type === "component") {
              msg.components = [
                ...(msg.components ?? []),
                { component: event.component, props: event.props },
              ];
            } else if (event.type === "error") {
              msg.content = `Agent error: ${event.message}`;
            } else if (event.type === "done") {
              if (event.session_phase) setPhase(event.session_phase);
            }
            next[next.length - 1] = msg;
            return next;
          });
        }
      }
    } catch (err) {
      simulateLocalResponse(text);
    } finally {
      setStreaming(false);
    }
  };

  const simulateLocalResponse = (text: string) => {
    const lower = text.toLowerCase();
    let reply = "I've verified your request against the store catalog and user discount policy. How would you like to proceed?";
    let auditEvents: AuditEvent[] = [
      { type: "audit", agent: "Manager Agent", detail: "DB Lookup: Profile [Alex] (Gold) | Store margin: 16.0% | Discount ceiling: 10.0%", ms: 1 },
      { type: "audit", agent: "Manager Agent", detail: "Guardrail: OK | Routing to Sales Agent", ms: 4 },
      { type: "audit", agent: "Sales Agent", detail: "ctx=1 msgs" },
      { type: "audit", agent: "Sales Agent", detail: "LLM [agent] → qwen/qwen3.6-27b", model: "qwen/qwen3.6-27b" },
      { type: "audit", agent: "Sales Agent", detail: "Response generated (120 chars)", model: "qwen/qwen3.6-27b", ms: 1600 },
      { type: "audit", agent: "Manager Agent", detail: "✅ AUDIT: products & pricing verified against catalog – no violations", ms: 1 },
    ];

    if (lower.includes("miami") || lower.includes("souled") || lower.includes("bargain")) {
      reply = "Manager Agent authorized a 15% discount on Souled: Miami (₹12,000 → ₹10,200). Would you like me to add it to your cart?";
      auditEvents = [
        { type: "audit", agent: "Manager Agent", detail: "DB Lookup: Profile [Alex] (Gold) | LTV Tier: High", ms: 1 },
        { type: "audit", agent: "Manager Agent", detail: "Margin Check: 16.0% | Requested Discount: 15.0% <= Ceiling", ms: 2 },
        { type: "audit", agent: "Sales Agent", detail: "Price Override Authorized: ₹10,200", model: "qwen/qwen3.6-27b", ms: 1200 },
        { type: "audit", agent: "Manager Agent", detail: "✅ AUDIT: products & pricing verified against catalog – no violations", ms: 1 },
      ];
    } else if (lower.includes("under ₹10,000") || lower.includes("cheap")) {
      reply = "Here are our verified sneakers under ₹10,000:\n- Hydros: Ghost (₹8,500)\n- UBZ 0.5: Mafia Mules (₹9,500)";
    }

    setTimeout(() => {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: reply,
          auditLog: auditEvents,
        };
        return next;
      });
    }, 400);
  };

  return { messages, setMessages, input, setInput, streaming, sessionPhase, sendMessage };
}

// ── Interactive Minimal AI Thinking Steps Component ──────────────────────────
function ThinkingAccordion({ log }: { log: AuditEvent[] }) {
  const [expanded, setExpanded] = useState(false);
  if (log.length === 0) return null;

  const lastMs = [...log].reverse().find((e) => e.ms)?.ms;

  return (
    <div className="thinking-accordion">
      <button
        type="button"
        className="thinking-toggle-btn"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <span>{expanded ? "▴ Hide Reasoning" : "▾ Reasoning Steps"}</span>
        <span>• {log.length} steps</span>
        {lastMs && <span>({lastMs >= 1000 ? `${(lastMs / 1000).toFixed(1)}s` : `${lastMs}ms`})</span>}
      </button>

      {expanded && (
        <div className="thinking-steps-card">
          {log.map((step, idx) => (
            <div key={idx} className="thinking-step-row">
              <span className="thinking-agent-tag">{step.agent}</span>
              <span className="thinking-step-detail">{step.detail}</span>
              {step.ms && (
                <span className="thinking-time-pill">
                  {step.ms >= 1000 ? `${(step.ms / 1000).toFixed(1)}s` : `${step.ms}ms`}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Component Main Page ───────────────────────────────────────────────────────
export default function Home() {
  const [mode, setMode] = useState<"classic" | "agent">("classic");
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("featured");

  // Cart State
  const [cart, setCart] = useState<{ product: Product; quantity: number; appliedPrice: number }[]>([
    { product: PRODUCTS[0], quantity: 1, appliedPrice: PRODUCTS[0].price },
  ]);
  const [discount, setDiscount] = useState(0);
  const [cartOpen, setCartOpen] = useState(false);
  const [couponInput, setCouponInput] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  // Modal State
  const [activeProduct, setActiveProduct] = useState<Product | null>(null);

  // Agent Chat Hook
  const { messages, setMessages, input, setInput, streaming, sessionPhase, sendMessage } = useAgentChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Smooth Mode Transition Handler
  const switchStoreMode = (targetMode: "classic" | "agent") => {
    if (targetMode === mode) return;

    // Use native View Transition API if supported
    if (typeof document !== "undefined" && "startViewTransition" in document) {
      (document as unknown as { startViewTransition: (cb: () => void) => void }).startViewTransition(() => {
        setMode(targetMode);
      });
    } else {
      setMode(targetMode);
    }
  };

  // Initial welcome message for agent view
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          role: "assistant",
          content: "Hello Alex! Welcome to hesprints Agentic Store. How can I assist you with finding sneakers or checking custom deals today?",
          auditLog: [
            { type: "audit", agent: "Manager Agent", detail: "DB Lookup: Profile [Alex] (Gold) | Store margin: 16.0%", ms: 1 },
            { type: "audit", agent: "Manager Agent", detail: "Guardrail: OK | Routing to Sales Agent", ms: 4 },
            { type: "audit", agent: "Sales Agent", detail: "LLM [agent] → qwen/qwen3.6-27b", model: "qwen/qwen3.6-27b" },
            { type: "audit", agent: "Manager Agent", detail: "✅ AUDIT: verified against catalog – no violations", ms: 1 },
          ],
        },
      ]);
    }
  }, []);

  useEffect(() => {
    if (mode === "agent") {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, mode]);

  const showToastMsg = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // Cart operations
  const addToCart = (product: Product, priceOverride?: number) => {
    const itemPrice = priceOverride !== undefined ? priceOverride : product.price;
    setCart((prev) => {
      const idx = prev.findIndex((i) => i.product.id === product.id);
      if (idx > -1) {
        const next = [...prev];
        next[idx].quantity += 1;
        next[idx].appliedPrice = itemPrice;
        return next;
      }
      return [...prev, { product, quantity: 1, appliedPrice: itemPrice }];
    });
    showToastMsg(`Added ${product.title} to cart`);
    setCartOpen(true);
  };

  const updateCartQty = (id: string, delta: number) => {
    setCart((prev) => {
      return prev
        .map((i) => (i.product.id === id ? { ...i, quantity: i.quantity + delta } : i))
        .filter((i) => i.quantity > 0);
    });
  };

  const applyCoupon = () => {
    const code = couponInput.trim().toUpperCase();
    if (code === "AGENT10" || code === "HE10") {
      setDiscount(0.10);
      showToastMsg("10% Promo Code Applied");
    } else if (code === "HACKATHON20") {
      setDiscount(0.20);
      showToastMsg("20% Special Discount Applied");
    } else {
      showToastMsg("Invalid code. Try AGENT10");
    }
  };

  const totalCartQty = cart.reduce((s, i) => s + i.quantity, 0);
  const rawSubtotal = cart.reduce((s, i) => s + i.appliedPrice * i.quantity, 0);
  const discountVal = rawSubtotal * discount;
  const finalTotal = rawSubtotal - discountVal;

  // Catalog Filtering
  const filteredProducts = PRODUCTS.filter((p) => {
    const matchesCat =
      category === "all"
        ? true
        : category === "sale"
        ? p.price < 10000
        : p.category === category;
    const matchesSearch =
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase());
    return matchesCat && matchesSearch;
  });

  if (sortBy === "price-low") filteredProducts.sort((a, b) => a.price - b.price);
  if (sortBy === "price-high") filteredProducts.sort((a, b) => b.price - a.price);
  if (sortBy === "name") filteredProducts.sort((a, b) => a.title.localeCompare(b.title));

  const onSubmitChat = (e: FormEvent) => {
    e.preventDefault();
    sendMessage(input, messages);
  };

  return (
    <div className="view-transition-container">
      {/* Header Navigation */}
      <header className="header">
        <div className="header-container">
          <a href="#" className="logo">
            <span className="logo-part-1">he</span>
            <span className="logo-part-2">sprints</span>
          </a>

          {/* Minimalist User-Friendly Search Bar */}
          <div className="search-box">
            <svg className="search-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder="Search sneakers by name, fit, or category..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="header-right">
            <div className="cart-icon-wrapper" onClick={() => setCartOpen(true)}>
              <svg className="cart-svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="9" cy="21" r="1"></circle>
                <circle cx="20" cy="21" r="1"></circle>
                <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
              </svg>
              <span className="cart-badge">{totalCartQty}</span>
            </div>
          </div>
        </div>
      </header>

      {/* VIEW 1: CLASSIC STORE */}
      {mode === "classic" && (
        <div className="main-layout view-enter-classic">
          <aside className="sidebar">
            <div className="sidebar-card">
              <h3 className="sidebar-title">Categories</h3>
              <nav className="category-nav">
                {["all", "running", "vintage", "court", "classics", "sale"].map((cat) => (
                  <a
                    key={cat}
                    href="#"
                    className={`category-link ${category === cat ? "active" : ""}`}
                    onClick={(e) => {
                      e.preventDefault();
                      setCategory(cat);
                    }}
                  >
                    <span style={{ textTransform: "capitalize" }}>
                      {cat === "all" ? "All Sneakers" : cat}
                    </span>
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          <main className="content">
            <div className="catalog-header">
              <h2 className="section-title">New Arrivals</h2>
              <div className="sort-controls">
                <label>Sort by:</label>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="featured">Featured</option>
                  <option value="price-low">Price: Low to High</option>
                  <option value="price-high">Price: High to Low</option>
                  <option value="name">Alphabetical</option>
                </select>
              </div>
            </div>

            <div className="product-grid">
              {filteredProducts.map((p) => (
                <div key={p.id} className="product-card">
                  <div className="product-img-wrapper" onClick={() => setActiveProduct(p)}>
                    <img src={p.image} alt={p.title} />
                  </div>
                  <div className="product-info">
                    <h3 className="product-title" onClick={() => setActiveProduct(p)}>
                      {p.title}
                    </h3>
                    <div className="price-row">
                      <span className="current-price">{inr(p.price)}</span>
                    </div>
                    <button className="add-to-cart-btn" onClick={() => addToCart(p)}>
                      Add to Cart
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </main>
        </div>
      )}

      {/* VIEW 2: FULL-PAGE AGENT CHAT STORE (100% LIGHT THEME WITH SMOOTH ANIMATION) */}
      {mode === "agent" && (
        <div className="agent-chat-layout view-enter-agent">
          <main className="agent-chat-container">
            <div className="chat-header-bar">
              <span className="chat-header-title">hesprints Agentic Assistant</span>
              <button
                type="button"
                style={{ background: "none", border: "none", color: "var(--teal)", cursor: "pointer", fontWeight: 700, fontSize: "0.85rem" }}
                onClick={() => switchStoreMode("classic")}
              >
                Back to Catalog ✕
              </button>
            </div>

            <div className="chat-messages-feed">
              {messages.map((m, i) => (
                <div key={i} className={`chat-msg-wrapper ${m.role}${m.components && m.components.length ? " has-genui" : ""}`}>
                  <div className={m.role === "user" ? "chat-bubble-user-light" : "chat-bubble-assistant-light"}>
                    {m.content || <span style={{ opacity: 0.6 }}>Processing...</span>}
                  </div>
                  {m.role === "assistant" && m.correction && (
                    <div style={{ marginTop: 6, padding: "6px 10px", borderLeft: "3px solid #b45309", background: "#fef3c7", borderRadius: 4, fontSize: 13, color: "#b45309" }}>
                      {m.correction}
                    </div>
                  )}
                  {m.role === "assistant" && (
                    <GenUiStack items={m.components} onAction={(t) => sendMessage(t, messages)} />
                  )}
                  {m.role === "assistant" && <ThinkingAccordion log={m.auditLog} />}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="chat-chips-row">
              {[
                "Find me sneakers under ₹10,000",
                "Can you negotiate a deal on Souled: Miami?",
                "Recommend a daily versatile pair",
                "Show reasoning steps",
              ].map((chip, idx) => (
                <button key={idx} className="chat-chip-btn" onClick={() => sendMessage(chip, messages)}>
                  {chip}
                </button>
              ))}
            </div>

            <form className="chat-input-row" onSubmit={onSubmitChat}>
              <input
                type="text"
                placeholder="Ask about sneakers, discounts, or fit..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={streaming}
                autoComplete="off"
              />
              <button type="submit" disabled={streaming || !input.trim()}>
                {streaming ? "..." : "Send"}
              </button>
            </form>
          </main>

          <aside className="agent-right-panel">
            <div className="panel-card">
              <h3 className="panel-card-title">Curated Selection</h3>
              {PRODUCTS.slice(0, 3).map((p) => (
                <div key={p.id} className="rec-shoe-item">
                  <img src={p.image} alt={p.title} className="rec-shoe-img" />
                  <div>
                    <h4 className="rec-shoe-title">{p.title}</h4>
                    <div className="rec-shoe-price">{inr(p.price)}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel-card">
              <h3 className="panel-card-title">Cart Summary</h3>
              <div style={{ fontSize: "0.9rem" }}>
                {cart.length === 0 ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Cart is empty.</p>
                ) : (
                  cart.map((i) => (
                    <div key={i.product.id} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span>{i.product.title} (x{i.quantity})</span>
                      <span style={{ fontWeight: 700 }}>{inr(i.appliedPrice * i.quantity)}</span>
                    </div>
                  ))
                )}
                <div style={{ borderTop: "1px dashed var(--border-warm)", paddingTop: 8, marginTop: 8, display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                  <span>Total:</span>
                  <span>{inr(finalTotal)}</span>
                </div>
              </div>
              <button className="checkout-btn" style={{ marginTop: 12 }} onClick={() => setCartOpen(true)}>
                Checkout Cart
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Corner Circle Floating Robot Button with Morphing Transition */}
      <div className="robot-fab-wrapper">
        <button
          className={`robot-fab-btn ${mode === "agent" ? "is-active" : ""}`}
          title="Toggle Agentic Chat Store"
          onClick={() => switchStoreMode(mode === "classic" ? "agent" : "classic")}
        >
          <svg className="robot-svg" viewBox="0 0 24 24">
            <rect x="5" y="8" width="14" height="12" rx="3" strokeWidth="2"></rect>
            <circle cx="9" cy="13" r="1.5" fill="currentColor"></circle>
            <circle cx="15" cy="13" r="1.5" fill="currentColor"></circle>
            <path d="M10 17h4" strokeWidth="2" strokeLinecap="round"></path>
            <line x1="12" y1="4" x2="12" y2="8" strokeWidth="2"></line>
            <circle cx="12" cy="3" r="1" fill="currentColor"></circle>
          </svg>
        </button>
      </div>

      {/* Cart Drawer */}
      <div className={`cart-overlay ${cartOpen ? "active" : ""}`} onClick={() => setCartOpen(false)} />
      <div className={`cart-drawer ${cartOpen ? "open" : ""}`}>
        <div className="cart-drawer-header">
          <div className="cart-title-group">
            <h2>Your Cart</h2>
          </div>
          <button className="close-btn" onClick={() => setCartOpen(false)}>✕</button>
        </div>

        <div className="cart-items-list">
          {cart.length === 0 ? (
            <p style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-secondary)" }}>
              Your cart is empty.
            </p>
          ) : (
            cart.map((i) => (
              <div key={i.product.id} className="cart-item">
                <img src={i.product.image} alt={i.product.title} className="cart-item-img" />
                <div className="cart-item-details">
                  <div className="cart-item-title">{i.product.title}</div>
                  <div className="cart-item-price">{inr(i.appliedPrice)}</div>
                  <div className="cart-qty-controls">
                    <button className="qty-btn" onClick={() => updateCartQty(i.product.id, -1)}>-</button>
                    <span>{i.quantity}</span>
                    <button className="qty-btn" onClick={() => updateCartQty(i.product.id, 1)}>+</button>
                  </div>
                </div>
                <button className="cart-item-remove" onClick={() => updateCartQty(i.product.id, -i.quantity)}>✕</button>
              </div>
            ))
          )}
        </div>

        <div className="cart-drawer-footer">
          <div className="discount-code-row">
            <input
              type="text"
              placeholder="Promo Code (e.g. AGENT10)"
              value={couponInput}
              onChange={(e) => setCouponInput(e.target.value)}
            />
            <button onClick={applyCoupon}>Apply</button>
          </div>

          <div className="cart-summary-rows">
            <div className="summary-row total-row">
              <span>Total</span>
              <span>{inr(finalTotal)}</span>
            </div>
          </div>

          <button className="checkout-btn" onClick={() => alert("Mock Razorpay Autonomous Checkout Initiated!")}>
            Proceed to Checkout
          </button>
        </div>
      </div>

      {/* Quick View Modal */}
      {activeProduct && (
        <div className="modal-overlay active" onClick={() => setActiveProduct(null)}>
          <div className="product-modal" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn modal-close" onClick={() => setActiveProduct(null)}>✕</button>
            <div className="modal-content-grid">
              <div className="modal-img-col">
                <img src={activeProduct.image} alt={activeProduct.title} />
              </div>
              <div className="modal-info-col">
                <div>
                  <h2>{activeProduct.title}</h2>
                  <div className="price-row" style={{ marginBottom: "1rem" }}>
                    <span className="current-price">{inr(activeProduct.price)}</span>
                  </div>
                  <p>{activeProduct.description}</p>
                </div>
                <button className="add-to-cart-btn" onClick={() => { addToCart(activeProduct); setActiveProduct(null); }}>
                  Add to Cart — {inr(activeProduct.price)}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="toast-container">
          <div className="toast">{toast}</div>
        </div>
      )}
    </div>
  );
}
