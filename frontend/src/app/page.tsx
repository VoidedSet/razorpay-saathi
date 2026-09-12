"use client";

import { useState, useRef, useEffect, FormEvent } from "react";

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

interface ErrorEvent {
  type: "error";
  message: string;
}

interface ComponentEvent {
  type: "component";
  component: string;
  props: Record<string, unknown>;
}

type SseEvent = AuditEvent | TokenEvent | CorrectionEvent | DoneEvent | ErrorEvent | ComponentEvent;

// Gen UI component types
interface ProductCardProps {
  id: string;
  name: string;
  brand: string;
  category: string;
  price: number;
  currency: string;
  description: string;
  image?: string;
  stock: number;
  specs: { label: string; value: string }[];
  recommended?: boolean;
}

interface CheckoutItem {
  id: string;
  name: string;
  qty: number;
  price: number;
}

interface CheckoutOffer {
  label: string;
  code: string;
  method: string;
}

interface CheckoutWidgetProps {
  items: CheckoutItem[];
  total: number;
  currency: string;
  offers: CheckoutOffer[];
  payment_link: { url: string; id: string } | null;
  ceiling: number;
}

interface UiComponent {
  component: string;
  props: Record<string, unknown>;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  auditLog: AuditEvent[];
  correction?: string;
  components: UiComponent[];
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
    id: "prod_shoe_miami",
    title: "Souled: Miami",
    category: "vintage",
    price: 120,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1743521912_7639983.jpg?w=480&dpr=2",
    description: "A vibrant, retro-inspired sneaker for the Miami soul. Lightweight and comfortable, perfect for a walk by the beach.",
  },
  {
    id: "prod_shoe_mafia",
    title: "UBZ 0.5: Mafia Mules",
    category: "court",
    price: 95,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1761894000_9908200.jpg?w=1080&dpr=2",
    description: "Bold and stylish, these mules make a statement. Inspired by classic cinema, they are the epitome of cool.",
  },
  {
    id: "prod_shoe_yoda",
    title: "Yoda",
    category: "classics",
    price: 110,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1759387261_3013866.jpg?w=1080&dpr=2",
    description: "Wisdom in every step. These classic green-themed sneakers are a must-have for any fan of the galaxy.",
  },
  {
    id: "prod_shoe_ghost",
    title: "Hydros: Ghost",
    category: "running",
    price: 85,
    image: "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1754742095_6028923.jpg?w=1080&dpr=2",
    description: "Sleek, minimalist, and fast. The Ghost runners are designed for urban exploration, day or night.",
  },
  {
    id: "prod_shoe_hightop",
    title: "TSS Originals: Urban High-Tops",
    category: "court",
    price: 130,
    image: "https://images.unsplash.com/photo-1512374382149-233c42b6a83b?w=600&auto=format&fit=crop",
    description: "High-top silhouette engineered for urban court performance and retro street aesthetics.",
  },
  {
    id: "prod_shoe_cyber",
    title: "Supersonic: Cyber Neon",
    category: "running",
    price: 105,
    image: "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=600&auto=format&fit=crop",
    description: "Dynamic cushioned running sneakers with vibrant neon accents and responsive foam midsoles.",
  },
  {
    id: "prod_shoe_canvas",
    title: "Vintage 77: Classic Canvas",
    category: "classics",
    price: 75,
    image: "https://images.unsplash.com/photo-1607522370275-f14206abe5d3?w=600&auto=format&fit=crop",
    description: "Timeless low-profile canvas sneakers crafted for everyday effortless style and comfort.",
  },
  {
    id: "prod_shoe_stealth",
    title: "Apex: Stealth Black",
    category: "vintage",
    price: 115,
    image: "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=600&auto=format&fit=crop",
    description: "Matte black stealth finish with genuine suede overlays and high-traction rubber outsole.",
  },
];

// ── SSE Agent Chat Hook ───────────────────────────────────────────────────────
function useAgentChat(onCartUpdate?: (cart: any[]) => void) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionPhase, setPhase] = useState("browsing");
  const sessionId = useRef<string>("");

  const sendMessage = async (text: string, currentMessages: Message[]) => {
    if (!text.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: text, auditLog: [], components: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    const placeholder: Message = { role: "assistant", content: "", auditLog: [], components: [] };
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

          const event: any = JSON.parse(raw);

          if (event.type === "done") {
            if (event.session_phase) setPhase(event.session_phase);
            if (event.cart && onCartUpdate) {
              onCartUpdate(event.cart);
            }
          }

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
              msg.components = [...msg.components, { component: event.component, props: event.props }];
            } else if (event.type === "error") {
              msg.content = `Agent error: ${event.message}`;
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
    const auditEvents: AuditEvent[] = [
      { type: "audit", agent: "Manager Agent", detail: "DB Lookup: Profile [Alex] (Gold) | Store margin: 16.0% | Discount ceiling: 10.0%", ms: 1 },
      { type: "audit", agent: "Manager Agent", detail: "Guardrail: OK | Routing to Sales Agent", ms: 4 },
      { type: "audit", agent: "Sales Agent", detail: "LLM [agent] → qwen/qwen3.6-27b", model: "qwen/qwen3.6-27b" },
      { type: "audit", agent: "Manager Agent", detail: "AUDIT: products & pricing verified against catalog – no violations", ms: 1 },
    ];
    if (lower.includes("miami") || lower.includes("souled")) {
      reply = "Manager Agent authorized a 10% discount on Souled: Miami (₹120 → ₹108). Would you like me to add it to your cart?";
    } else if (lower.includes("under ₹100") || lower.includes("under $100") || lower.includes("cheap")) {
      reply = "Here are verified sneakers under ₹100: Vintage 77 Canvas (₹75), Hydros Ghost (₹85), Mafia Mules (₹95).";
    }

    setTimeout(() => {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: reply, auditLog: auditEvents, components: [] };
        return next;
      });
    }, 400);
  };

  return { messages, setMessages, input, setInput, streaming, sessionPhase, sendMessage };
}

// ── Reasoning Timeline (collapsed by default, expandable) ────────────────────
function ThinkingStepperTimeline({ log }: { log: AuditEvent[] }) {
  const [open, setOpen] = useState(false);

  if (!log || log.length === 0) return null;

  const lastMs = [...log].reverse().find((e) => e.ms)?.ms;

  return (
    <div className="stepper-transparent-container">
      <button type="button" className="stepper-main-toggle" onClick={() => setOpen((p) => !p)}>
        <span>{open ? "▾" : "▸"} Reasoning</span>
        <span className="stepper-meta-tag">• {log.length} steps</span>
        {lastMs && <span className="stepper-time-tag">({lastMs >= 1000 ? `${(lastMs / 1000).toFixed(1)}s` : `${lastMs}ms`})</span>}
      </button>

      {open && (
        <div className="stepper-timeline-list">
          {log.map((step, idx) => {
            const isLast = idx === log.length - 1;
            return (
              <div key={idx} className="stepper-item">
                {!isLast && <div className="stepper-line" />}
                <div className={`stepper-circle ${isLast ? "circle-blue" : "circle-done"}`}>
                  {isLast ? (
                    <span>{idx + 1}</span>
                  ) : (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </div>
                <div className="stepper-content-box">
                  <span className="stepper-agent-name">{step.agent}</span>
                  <span className="stepper-summary-line">{step.detail}</span>
                  {step.model && <span className="stepper-model-badge">{step.model}</span>}
                </div>
                {step.ms && (
                  <span className="stepper-step-time">
                    {step.ms >= 1000 ? `${(step.ms / 1000).toFixed(1)}s` : `${step.ms}ms`}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Gen UI: Product Card ──────────────────────────────────────────────────────
function ProductCard({ props, onViewDetail }: { props: ProductCardProps; onViewDetail: (p: ProductCardProps) => void }) {
  const initials = props.brand
    ? props.brand.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase()
    : props.name.slice(0, 2).toUpperCase();

  return (
    <div className={`gen-product-card ${props.recommended ? "gen-product-card-recommended" : ""}`}>
      {props.recommended && <span className="gen-recommended-badge">Recommended</span>}
      {props.image ? (
        <img
          src={props.image}
          alt={props.name}
          className="gen-product-img"
          onClick={() => onViewDetail(props)}
        />
      ) : (
        <div className="gen-product-monogram" onClick={() => onViewDetail(props)}>
          {initials}
        </div>
      )}
      <div className="gen-product-info">
        <div className="gen-product-meta">
          <span className="gen-product-brand">{props.brand}</span>
          <span className="gen-product-dot">·</span>
          <span className="gen-product-category">{props.category}</span>
        </div>
        <h4 className="gen-product-name" onClick={() => onViewDetail(props)}>{props.name}</h4>
        <p className="gen-product-desc">{props.description}</p>
        {props.specs.length > 0 && (
          <div className="gen-product-specs">
            {props.specs.map((s, i) => (
              <div key={i} className="gen-spec-row">
                <span className="gen-spec-label">{s.label}</span>
                <span className="gen-spec-value">{s.value}</span>
              </div>
            ))}
          </div>
        )}
        <div className="gen-product-price">
          {props.currency === "INR" ? "₹" : "$"}{props.price.toLocaleString("en-IN")}
        </div>
      </div>
    </div>
  );
}

// ── Hero Banner Carousel ──────────────────────────────────────────────────────
const HERO_SLIDES = [
  {
    id: 1,
    title: "YEEZY BOOST 350 V2",
    subtitle: "The icon returns in 'Zebra' colorway.",
    image: "/assets/yeezy_sneakers.png",
    cta: "Shop Now"
  },
  {
    id: 2,
    title: "YEEZY SLIDE 'BONE'",
    subtitle: "Minimalist design, maximum comfort.",
    image: "/assets/yeezy_slide_bone.png",
    cta: "Discover More"
  },
  {
    id: 3,
    title: "YEEZY CARGO PANTS",
    subtitle: "Utilitarian style. Signature aesthetic.",
    image: "/assets/yeezy_cargo.png",
    cta: "Explore Apparel"
  },
  {
    id: 4,
    title: "ESSENTIALS HOODIE",
    subtitle: "Everyday comfort.",
    image: "/assets/hoodie+cap.png",
    cta: "Shop Essentials"
  },
  {
    id: 5,
    title: "YEEZY GAP JACKET",
    subtitle: "Form meets function.",
    image: "/assets/jacket.png",
    cta: "View Collection"
  }
];

function HeroCarousel() {
  const N = HERO_SLIDES.length;
  // 3 sets of slides for seamless circular wrapping
  const TRIPLE_SLIDES = [...HERO_SLIDES, ...HERO_SLIDES, ...HERO_SLIDES];

  const trackRef = useRef<HTMLDivElement>(null);
  const [currentIndex, setCurrentIndex] = useState(N);
  const [isTransitioning, setIsTransitioning] = useState(true);
  const [isHovered, setIsHovered] = useState(false);
  const [offsets, setOffsets] = useState<number[]>([]);

  // Function to measure exact offsetLeft of each slide item based on its intrinsic width
  const measureOffsets = () => {
    if (trackRef.current) {
      const children = Array.from(trackRef.current.children) as HTMLElement[];
      if (children.length > 0) {
        const newOffsets = children.map((c) => c.offsetLeft);
        setOffsets(newOffsets);
      }
    }
  };

  useEffect(() => {
    measureOffsets();
    window.addEventListener("resize", measureOffsets);
    return () => window.removeEventListener("resize", measureOffsets);
  }, []);

  // Auto-advance every 3 seconds if not hovered
  useEffect(() => {
    if (isHovered) return;
    const interval = setInterval(() => {
      setIsTransitioning(true);
      setCurrentIndex((prev) => prev + 1);
    }, 3000);
    return () => clearInterval(interval);
  }, [isHovered]);

  // Seamless reset when reaching boundary of middle set
  const handleTransitionEnd = () => {
    if (currentIndex >= N * 2) {
      setIsTransitioning(false);
      setCurrentIndex(N);
    } else if (currentIndex < N) {
      setIsTransitioning(false);
      setCurrentIndex(N * 2 - 1);
    }
  };

  const goToSlide = (idx: number) => {
    setIsTransitioning(true);
    setCurrentIndex(N + idx);
  };

  const goPrev = () => {
    setIsTransitioning(true);
    setCurrentIndex((prev) => prev - 1);
  };

  const goNext = () => {
    setIsTransitioning(true);
    setCurrentIndex((prev) => prev + 1);
  };

  const translateX = offsets[currentIndex] !== undefined ? offsets[currentIndex] : 0;

  return (
    <div
      className="stitched-carousel-container"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className="stitched-carousel-track"
        ref={trackRef}
        onTransitionEnd={handleTransitionEnd}
        style={{
          transform: `translateX(-${translateX}px)`,
          transition: isTransitioning ? "transform 0.75s cubic-bezier(0.16, 1, 0.3, 1)" : "none",
        }}
      >
        {TRIPLE_SLIDES.map((slide, idx) => {
          const isActive = idx === currentIndex;
          const isNext = idx === currentIndex + 1;
          const stateClass = isActive ? "active-slide" : isNext ? "next-slide" : "dimmed-slide";
          return (
            <div
              key={`${slide.id}-${idx}`}
              className={`stitched-slide ${stateClass}`}
              onClick={() => goToSlide(idx % N)}
            >
              <img
                src={slide.image}
                alt={slide.title}
                className="stitched-slide-img"
                onLoad={measureOffsets}
              />
              <div className={`stitched-slide-overlay ${isActive ? "visible-overlay" : ""}`}>
                <h1 className="hero-slide-title-stitched">{slide.title}</h1>
                <p className="hero-slide-subtitle-stitched">{slide.subtitle}</p>
                <button className="hero-slide-btn-stitched">{slide.cta} →</button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Navigation Arrows */}
      <button className="carousel-nav-btn prev-btn" onClick={goPrev} title="Previous slide">
        ‹
      </button>
      <button className="carousel-nav-btn next-btn" onClick={goNext} title="Next slide">
        ›
      </button>

      {/* Indicator Dots */}
      <div className="carousel-dots-wrapper">
        {HERO_SLIDES.map((slide, idx) => (
          <button
            key={slide.id}
            className={`carousel-dot ${currentIndex % N === idx ? "active-dot" : ""}`}
            onClick={() => goToSlide(idx)}
            title={slide.title}
          />
        ))}
      </div>
    </div>
  );
}

// ── Testimonials Carousel ─────────────────────────────────────────────────────
const TESTIMONIALS = [
  { id: 1, name: "Rahul S.", rating: 5, text: "Got my Yeezys delivered in 2 days. The AI Agent made it super easy to checkout!" },
  { id: 2, name: "Sneha P.", rating: 5, text: "Unbelievable experience. The agent found exactly what I wanted and gave me a discount." },
  { id: 3, name: "Karan V.", rating: 4, text: "Great collection of vintage sneakers. Will definitely buy again." },
  { id: 4, name: "Anjali M.", rating: 5, text: "The Razorpay instant discount applied flawlessly. Highly recommended store." },
  { id: 5, name: "Vikram D.", rating: 5, text: "Fastest checkout I've ever experienced. 10/10." },
  { id: 6, name: "Priya T.", rating: 4, text: "Loved the recommendations the AI gave me. Spot on for my style!" }
];

function TestimonialsCarousel() {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setOffset((prev) => (prev + 1) % TESTIMONIALS.length);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  const visibleTestimonials = [
    TESTIMONIALS[offset],
    TESTIMONIALS[(offset + 1) % TESTIMONIALS.length],
    TESTIMONIALS[(offset + 2) % TESTIMONIALS.length],
  ];

  return (
    <div className="sidebar-card mt-4">
      <h3 className="sidebar-title">Recent Reviews</h3>
      <div className="testimonials-wrapper">
        {visibleTestimonials.map((t, idx) => (
          <div key={`${t.id}-${idx}`} className="testimonial-item">
            <div className="testimonial-header">
              <span className="testimonial-name">{t.name}</span>
              <span className="testimonial-rating">{"★".repeat(t.rating)}{"☆".repeat(5 - t.rating)}</span>
            </div>
            <p className="testimonial-text">"{t.text}"</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Gen UI: Checkout Widget ───────────────────────────────────────────────────
function CheckoutWidget({ props }: { props: CheckoutWidgetProps }) {
  const total = props.items.reduce((s, i) => s + i.price * i.qty, 0);

  return (
    <div className="gen-checkout-widget">
      <div className="gen-checkout-header">
        <span className="gen-checkout-title">Order Summary</span>
        <span className="gen-checkout-ceiling">Max discount {props.ceiling}%</span>
      </div>
      <div className="gen-checkout-items">
        {props.items.map((item, i) => (
          <div key={i} className="gen-checkout-item-row">
            <span>{item.name} × {item.qty}</span>
            <span>₹{(item.price * item.qty).toLocaleString("en-IN")}</span>
          </div>
        ))}
        <div className="gen-checkout-total-row">
          <span>Total</span>
          <span>₹{total.toLocaleString("en-IN")}</span>
        </div>
      </div>

      {props.offers.length > 0 && (
        <div className="gen-checkout-offers">
          <div className="gen-checkout-offers-title">Razorpay Bank Offers</div>
          {props.offers.map((offer, i) => (
            <div key={i} className="gen-offer-row">
              <div className="gen-offer-label">{offer.label}</div>
              {offer.code && <span className="gen-offer-code">{offer.code}</span>}
            </div>
          ))}
        </div>
      )}

      {props.payment_link && (
        <a
          href={props.payment_link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="gen-checkout-pay-btn"
        >
          Pay with Razorpay
        </a>
      )}
      {props.payment_link && (
        <div className="gen-checkout-link-id">Link: {props.payment_link.id}</div>
      )}
    </div>
  );
}

// ── Gen UI renderer — renders a list of components after the AI bubble ────────
function GenUIComponents({
  components,
  onViewDetail,
}: {
  components: UiComponent[];
  onViewDetail: (p: ProductCardProps) => void;
}) {
  if (!components || components.length === 0) return null;

  return (
    <div className="gen-ui-block">
      {components.map((comp, i) => {
        if (comp.component === "product_card") {
          return <ProductCard key={i} props={comp.props as unknown as ProductCardProps} onViewDetail={onViewDetail} />;
        }
        if (comp.component === "checkout_widget") {
          return <CheckoutWidget key={i} props={comp.props as unknown as CheckoutWidgetProps} />;
        }
        return null;
      })}
    </div>
  );
}

// ── Product Detail Modal ──────────────────────────────────────────────────────
function ProductDetailModal({
  product,
  onClose,
}: {
  product: { name: string; brand: string; category: string; price: number; currency: string; description: string; image?: string; specs: { label: string; value: string }[] } | null;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!product) return null;
  const symbol = product.currency === "INR" ? "₹" : "$";

  return (
    <div className="modal-overlay active" onClick={onClose}>
      <div className="product-detail-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn modal-close" onClick={onClose}>✕</button>
        <div className="detail-modal-body">
          {product.image ? (
            <div className="detail-modal-img">
              <img src={product.image} alt={product.name} />
            </div>
          ) : (
            <div className="detail-modal-monogram">
              {product.brand
                ? product.brand.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase()
                : product.name.slice(0, 2).toUpperCase()}
            </div>
          )}
          <div className="detail-modal-info">
            <div className="gen-product-meta" style={{ marginBottom: "0.4rem" }}>
              <span className="gen-product-brand">{product.brand}</span>
              <span className="gen-product-dot">·</span>
              <span className="gen-product-category">{product.category}</span>
            </div>
            <h2 className="detail-modal-name">{product.name}</h2>
            <div className="detail-modal-price">{symbol}{product.price.toLocaleString("en-IN")}</div>
            <p className="detail-modal-desc">{product.description}</p>
            {product.specs.length > 0 && (
              <div className="gen-product-specs detail-specs">
                {product.specs.map((s, i) => (
                  <div key={i} className="gen-spec-row">
                    <span className="gen-spec-label">{s.label}</span>
                    <span className="gen-spec-value">{s.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Curated Selection Auto-scrolling Vertical Carousel ────────────────────────
function CuratedSelectionCarousel({
  products,
  onSelectProduct,
}: {
  products: Product[];
  onSelectProduct: (p: Product) => void;
}) {
  const carouselRef = useRef<HTMLDivElement>(null);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      const el = carouselRef.current;
      if (!el) return;
      const isAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 15;
      if (isAtBottom) {
        el.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        el.scrollBy({ top: 70, behavior: "smooth" });
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [isPaused]);

  return (
    <div
      ref={carouselRef}
      className="vertical-carousel"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {products.map((p) => (
        <div key={p.id} className="carousel-card" onClick={() => onSelectProduct(p)}>
          <img src={p.image} alt={p.title} className="rec-shoe-img" />
          <div className="carousel-card-info">
            <h4 className="rec-shoe-title">{p.title}</h4>
            <div className="rec-shoe-price">₹{p.price.toLocaleString("en-IN")}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Campaign Result Card ────────────────────────────────────────────────────
interface CampaignResult {
  campaign_id: number;
  trigger_type: string;
  product: { id: string; name: string; brand: string; image: string; original_price: number; campaign_price: number };
  discount_pct: number;
  tweet: string;
  headline: string;
  body: string;
  payment_link: string;
  link_id: string;
  manager_note: string;
  audit: { agent: string; detail: string }[];
}

function CampaignResultCard({ result, onDismiss }: { result: CampaignResult; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);
  const copyTweet = () => {
    navigator.clipboard.writeText(result.tweet).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  };

  return (
    <div className="campaign-result-card">
      <div className="campaign-card-header">
        <div className="campaign-trigger-badge">{result.trigger_type === "stagnant_inventory" ? "Stagnant Inventory" : "Cart Abandonment"}</div>
        <button className="campaign-dismiss-btn" onClick={onDismiss}>✕</button>
      </div>

      <div className="campaign-product-row">
        {result.product.image && <img src={result.product.image} alt={result.product.name} className="campaign-product-img" />}
        <div>
          <div className="campaign-product-name">{result.product.name}</div>
          <div className="campaign-price-row">
            <span className="campaign-price-original">₹{result.product.original_price.toLocaleString("en-IN")}</span>
            <span className="campaign-price-arrow">→</span>
            <span className="campaign-price-new">₹{result.product.campaign_price.toLocaleString("en-IN")}</span>
            <span className="campaign-discount-badge">{result.discount_pct}% off</span>
          </div>
        </div>
      </div>

      <div className="campaign-copy-section">
        <div className="campaign-copy-label">Generated Tweet</div>
        <div className="campaign-tweet-box">{result.tweet}</div>
        <button className="campaign-copy-btn" onClick={copyTweet}>{copied ? "Copied!" : "Copy Tweet"}</button>
      </div>

      <a href={result.payment_link} target="_blank" rel="noopener noreferrer" className="campaign-pay-link">
        Razorpay Link — {result.link_id}
      </a>

      <div className="campaign-manager-note">{result.manager_note}</div>

      <div className="campaign-audit-trail">
        {result.audit.map((a, i) => (
          <div key={i} className="campaign-audit-row">
            <span className="campaign-audit-agent">{a.agent}</span>
            <span className="campaign-audit-detail">{a.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Component Main Page ───────────────────────────────────────────────────────
export default function Home() {
  const [mode, setMode] = useState<"classic" | "agent">("classic");
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("featured");

  // Dynamic Catalog State loaded from backend SQLite store
  const [products, setProducts] = useState<Product[]>(PRODUCTS);

  useEffect(() => {
    fetch("http://localhost:8000/api/products?limit=100")
      .then((res) => res.json())
      .then((data) => {
        if (data.products && Array.isArray(data.products) && data.products.length > 0) {
          const fetched: Product[] = data.products.map((p: any) => ({
            id: p.id,
            title: p.name,
            category: p.category || "sneakers",
            price: p.price_inr || 0,
            image: p.image_url || "https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&q=80&w=800",
            description: p.description || "",
          }));
          setProducts(fetched);
        }
      })
      .catch((err) => console.warn("Using default catalog fallback:", err));
  }, []);

  // Cart State
  const [cart, setCart] = useState<{ product: Product; quantity: number; appliedPrice: number }[]>([]);
  const [discount, setDiscount] = useState(0);
  const [cartOpen, setCartOpen] = useState(false);
  const [couponInput, setCouponInput] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  // Campaign state
  const [campaignResults, setCampaignResults] = useState<CampaignResult[]>([]);
  const [campaignLoading, setCampaignLoading] = useState<string | null>(null); // product_id being triggered

  const triggerCampaign = async (productId: string, triggerType: string = "stagnant_inventory") => {
    setCampaignLoading(productId);
    try {
      // Simulate stagnant inventory first
      await fetch(`http://localhost:8000/api/mark_stagnant/${productId}`, { method: "POST" });
      const res = await fetch("http://localhost:8000/api/campaign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, trigger_type: triggerType, discount_pct: 12.0 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result: CampaignResult = await res.json();
      setCampaignResults((prev) => [result, ...prev]);
      showToastMsg(`Campaign generated for ${result.product.name}`);
    } catch (err) {
      showToastMsg("Campaign trigger failed — backend offline?");
    } finally {
      setCampaignLoading(null);
    }
  };

  // Product detail modal (for classic store cards)
  const [activeProduct, setActiveProduct] = useState<Product | null>(null);

  // Gen UI product detail modal (for agent chat product cards)
  const [genProductDetail, setGenProductDetail] = useState<ProductCardProps | null>(null);

  // Agent Chat Hook with dynamic cart sync
  const { messages, setMessages, input, setInput, streaming, sessionPhase, sendMessage } = useAgentChat((newCartData) => {
    if (Array.isArray(newCartData)) {
      const updatedCart = newCartData
        .map((c: any) => {
          const pid = c.id || c.product_id;
          const existingProd = products.find((p) => p.id === pid);
          const prodObj: Product = existingProd || {
            id: pid || "item_" + Math.random(),
            title: c.name || c.title || "Sneakers",
            category: c.category || "sneakers",
            price: c.price_inr || c.price || 0,
            image: c.image_url || c.image || "https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&q=80&w=800",
            description: c.description || "",
          };
          return {
            product: prodObj,
            quantity: c.qty || c.quantity || 1,
            appliedPrice: c.price_inr || c.price || prodObj.price,
          };
        });
      setCart(updatedCart);
    }
  });
  const bottomRef = useRef<HTMLDivElement>(null);

  // Smooth Mode Transition Handler
  const switchStoreMode = (targetMode: "classic" | "agent") => {
    if (targetMode === mode) return;
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
            { type: "audit", agent: "Sales Agent", detail: "LLM [agent] → llama-3.3-70b-versatile", model: "llama-3.3-70b-versatile" },
            { type: "audit", agent: "Manager Agent", detail: "AUDIT: verified against catalog – no violations", ms: 1 },
          ],
          components: [],
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
  const filteredProducts = products.filter((p) => {
    const matchesCat =
      category === "all"
        ? true
        : category === "sale"
        ? p.price < 20000
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
            <span className="logo-part-1">ye</span>
            <span className="logo-part-2">ezus</span>
          </a>

          <div className="search-box">
            <svg className="search-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder="Search catalog by brand, model, tags..."
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
              {totalCartQty > 0 && <span className="cart-badge">{totalCartQty}</span>}
            </div>
          </div>
        </div>
      </header>

      {/* VIEW 1: CLASSIC STORE */}
      {mode === "classic" && (
        <div className="classic-store-wrapper view-enter-classic">
          {category === "all" && search === "" && (
            <section className="hero-carousel-section">
              <HeroCarousel />
            </section>
          )}

          <div className="main-layout">
            <aside className="sidebar">
              <div className="sidebar-card">
                <h3 className="sidebar-title">Categories</h3>
                <nav className="category-nav">
                  {["all", "sneakers", "apparel", "accessories", "sale"].map((cat) => (
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
                        {cat === "all" ? "All Products" : cat}
                      </span>
                    </a>
                  ))}
                </nav>
              </div>
              <TestimonialsCarousel />
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
                  <div key={p.id} className="product-card" onClick={() => setActiveProduct(p)}>
                    <img src={p.image} alt={p.title} className="product-card-img" />
                    <div className="product-card-overlay">
                      <div className="product-card-name">{p.title}</div>
                      <div className="product-card-hover-content">
                        <span className="product-card-price">
                          {p.price > 500 ? `₹${p.price.toLocaleString("en-IN")}` : `$${p.price}`}
                        </span>
                        <button 
                          className="product-card-add-btn" 
                          onClick={(e) => {
                            e.stopPropagation();
                            addToCart(p);
                          }}
                        >
                          +
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </main>
          </div>
        </div>
      )}

      {/* VIEW 2: FULL-PAGE AGENT CHAT STORE */}
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
                <div key={i} className={`chat-msg-wrapper ${m.role}`}>
                  <div className={m.role === "user" ? "chat-bubble-user-light" : "chat-bubble-assistant-light"}>
                    {m.content || <span style={{ opacity: 0.6 }}>Processing...</span>}
                  </div>
                  {m.role === "assistant" && m.correction && (
                    <div className="manager-correction-bar">
                      {m.correction}
                    </div>
                  )}
                  {/* Gen UI: render components AFTER the bubble, not during streaming */}
                  {m.role === "assistant" && m.components.length > 0 && (
                    <GenUIComponents
                      components={m.components}
                      onViewDetail={(p) => setGenProductDetail(p)}
                    />
                  )}
                  {m.role === "assistant" && <ThinkingStepperTimeline log={m.auditLog} />}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="chat-chips-row">
              {[
                "Find me sneakers under ₹100",
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
            {/* Curated Selection: Auto-scrolling Vertical Carousel */}
            <div className="panel-card">
              <h3 className="panel-card-title">Curated Selection</h3>
              <CuratedSelectionCarousel products={products} onSelectProduct={(p) => setActiveProduct(p)} />
            </div>

            {/* Cart Summary with Item Thumbnail Icons */}
            <div className="panel-card">
              <h3 className="panel-card-title">Cart Summary</h3>
              {cart.length > 0 && (
                <div className="cart-icons-row">
                  {cart.map((item) => (
                    <div key={item.product.id} className="cart-icon-thumb-wrapper" title={`${item.product.title} (x${item.quantity})`}>
                      <img src={item.product.image} alt={item.product.title} className="cart-icon-thumb" />
                      {item.quantity > 1 && <span className="cart-thumb-qty">{item.quantity}</span>}
                    </div>
                  ))}
                </div>
              )}
              <div style={{ fontSize: "0.9rem" }}>
                {cart.length === 0 ? (
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Cart is empty.</p>
                ) : (
                  <div className="panel-cart-items-list">
                    {cart.map((i) => (
                      <div key={i.product.id} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <span>{i.product.title} (x{i.quantity})</span>
                        <span style={{ fontWeight: 700 }}>₹{(i.appliedPrice * i.quantity).toLocaleString("en-IN")}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ borderTop: "1px dashed var(--border-warm)", paddingTop: 8, marginTop: 8, display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                  <span>Total:</span>
                  <span>₹{finalTotal.toLocaleString("en-IN")}</span>
                </div>
              </div>
              <button className="checkout-btn" style={{ marginTop: 12 }} onClick={() => setCartOpen(true)}>
                Checkout Cart
              </button>
            </div>

            {/* Manager Actions (Campaign) */}
            <div className="panel-card">
              <h3 className="panel-card-title">Manager Actions</h3>
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                <button 
                  className="campaign-trigger-btn"
                  onClick={() => triggerCampaign("prod_06", "stagnant_inventory")}
                  disabled={campaignLoading === "prod_06"}
                  style={{ width: "100%", padding: "0.5rem", background: "var(--teal)", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}
                >
                  {campaignLoading === "prod_06" ? "Simulating..." : "Simulate Stagnant (Miami)"}
                </button>
              </div>
              <div className="campaign-results-list" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {campaignResults.map((res, i) => (
                  <CampaignResultCard key={i} result={res} onDismiss={() => {
                    setCampaignResults(prev => prev.filter((_, idx) => idx !== i));
                  }} />
                ))}
              </div>
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
                  <div className="cart-item-price">₹{i.appliedPrice.toLocaleString("en-IN")}</div>
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
              <span>₹{finalTotal.toLocaleString("en-IN")}</span>
            </div>
          </div>
          <button 
            className="checkout-btn" 
            onClick={() => {
              setCartOpen(false);
              if (mode !== "agent") switchStoreMode("agent");
              sendMessage("I want to checkout my cart", messages);
            }}
          >
            Proceed to Checkout
          </button>
        </div>
      </div>

      {/* Classic Store: Product Detail Modal */}
      {activeProduct && (
        <div className="modal-overlay active" onClick={() => setActiveProduct(null)}>
          <div className="product-detail-modal" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn modal-close" onClick={() => setActiveProduct(null)}>✕</button>
            <div className="detail-modal-body">
              <div className="detail-modal-img">
                <img src={activeProduct.image} alt={activeProduct.title} />
              </div>
              <div className="detail-modal-info">
                <span className="gen-product-category">{activeProduct.category}</span>
                <h2 className="detail-modal-name">{activeProduct.title}</h2>
                <div className="detail-modal-price">₹{activeProduct.price.toLocaleString("en-IN")}</div>
                <p className="detail-modal-desc">{activeProduct.description}</p>
                <button
                  className="add-to-cart-btn"
                  style={{ marginTop: "1.5rem" }}
                  onClick={() => { addToCart(activeProduct); setActiveProduct(null); }}
                >
                  Add to Cart — ₹{activeProduct.price.toLocaleString("en-IN")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Agent View: Gen UI Product Detail Modal */}
      {genProductDetail && (
        <ProductDetailModal
          product={genProductDetail}
          onClose={() => setGenProductDetail(null)}
        />
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
