"use client";

/**
 * genui.tsx — Generative UI component registry.
 *
 * The backend streams `{ type: "component", component, props }` SSE events. Each
 * `component` name maps to a predefined React renderer below; the agent "fills in
 * the values" (props) while the server grounds every authoritative field (id /
 * price / total / payment link) so numbers can't be hallucinated. Anything the
 * agent needs that isn't predefined arrives as `custom` (authored via the
 * render_custom_ui tool), and any unknown name falls back to the same renderer.
 */

export interface UiComponent {
  component: string;
  props: Record<string, unknown>;
}

type OnAction = (message: string) => void;

/** Format an integer amount as Indian Rupees, e.g. 32999 → "₹32,999". */
export const inr = (n: number): string =>
  `₹${Math.round(Number(n) || 0).toLocaleString("en-IN")}`;

// ── Prop contracts (mirror the backend builders in graph.py) ────────────────────
interface ProductCardProps {
  id: string;
  name: string;
  brand?: string;
  category?: string;
  price: number;
  image?: string;
  emoji?: string;
  description?: string;
  specs?: { label: string; value: string }[];
  recommended?: boolean;
}

interface CheckoutItem {
  name: string;
  qty: number;
  price: number;
  emoji?: string;
}

interface CheckoutProps {
  items: CheckoutItem[];
  total: number;
  offers?: { label: string; code?: string; method?: string }[];
  payment_link?: { url: string; id: string } | null;
  ceiling?: number;
}

interface CustomProps {
  title?: string;
  body?: string;
  bullets?: string[];
  cta?: { label: string; message: string } | null;
}

// ── Predefined components ───────────────────────────────────────────────────────

function ProductCard({ data, onAction }: { data: ProductCardProps; onAction: OnAction }) {
  const { name, brand, category, price, image, emoji, description, specs, recommended } = data;
  return (
    <div className={`genui-card genui-product${recommended ? " is-recommended" : ""}`}>
      {recommended && <span className="genui-badge">★ Recommended</span>}
      <div className="genui-product-media">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt={name} />
        ) : (
          <span className="genui-emoji" aria-hidden="true">{emoji || "🛍️"}</span>
        )}
      </div>
      <div className="genui-product-body">
        {(brand || category) && (
          <div className="genui-product-brand">
            {[brand, category].filter(Boolean).join(" · ")}
          </div>
        )}
        <h4 className="genui-product-name">{name}</h4>
        {description && <p className="genui-product-desc">{description}</p>}
        {specs && specs.length > 0 && (
          <ul className="genui-spec-list">
            {specs.map((s, i) => (
              <li key={i}>
                <span className="genui-spec-key">{s.label}</span>
                <span className="genui-spec-val">{s.value}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="genui-product-footer">
          <span className="current-price">{inr(price)}</span>
          <button
            type="button"
            className="genui-btn"
            onClick={() => onAction(`Add the ${name} to my cart`)}
          >
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  );
}

function CheckoutWidget({ data }: { data: CheckoutProps }) {
  const { items, total, offers, payment_link, ceiling } = data;
  return (
    <div className="genui-card genui-checkout">
      <div className="genui-checkout-head">
        <span className="genui-checkout-title">🧾 Order Summary</span>
        {typeof ceiling === "number" && (
          <span className="genui-ceiling">Max discount {ceiling}%</span>
        )}
      </div>

      <div className="genui-checkout-items">
        {(items ?? []).map((it, i) => (
          <div key={i} className="genui-checkout-row">
            <span>
              {it.emoji ? `${it.emoji} ` : ""}
              {it.name} <span className="genui-muted">× {it.qty}</span>
            </span>
            <span className="genui-mono">{inr(it.price * it.qty)}</span>
          </div>
        ))}
      </div>

      <div className="genui-checkout-total">
        <span>Total</span>
        <span className="current-price">{inr(total)}</span>
      </div>

      {offers && offers.length > 0 && (
        <div className="genui-offers">
          <div className="genui-offers-title">Razorpay Bank Offers</div>
          {offers.map((o, i) => (
            <div key={i} className="genui-offer-row">
              <span>💳 {o.label}</span>
              {o.code && <code className="genui-offer-code">{o.code}</code>}
            </div>
          ))}
        </div>
      )}

      {payment_link && payment_link.url ? (
        <a
          className="genui-pay-btn"
          href={payment_link.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Pay with Razorpay →
        </a>
      ) : (
        <button type="button" className="genui-pay-btn" disabled>
          Add items to generate a payment link
        </button>
      )}
      {payment_link && payment_link.id && (
        <div className="genui-plink-id">Link: {payment_link.id}</div>
      )}
    </div>
  );
}

function CustomCard({ data, onAction }: { data: CustomProps; onAction: OnAction }) {
  const { title, body, bullets, cta } = data;
  const empty = !title && !body && !(bullets && bullets.length) && !cta;
  return (
    <div className="genui-card genui-custom">
      {title && <h4 className="genui-custom-title">{title}</h4>}
      {body && <p className="genui-custom-body">{body}</p>}
      {bullets && bullets.length > 0 && (
        <ul className="genui-custom-bullets">
          {bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}
      {cta && cta.label && (
        <button
          type="button"
          className="genui-btn"
          onClick={() => onAction(cta.message || cta.label)}
        >
          {cta.label}
        </button>
      )}
      {empty && <p className="genui-custom-body genui-muted">Unsupported UI component.</p>}
    </div>
  );
}

// ── Registry dispatch ───────────────────────────────────────────────────────────

function GenUiComponent({ item, onAction }: { item: UiComponent; onAction: OnAction }) {
  switch (item.component) {
    case "product_card":
      return <ProductCard data={item.props as unknown as ProductCardProps} onAction={onAction} />;
    case "checkout_widget":
      return <CheckoutWidget data={item.props as unknown as CheckoutProps} />;
    case "custom":
    default: // unknown component name → graceful custom fallback
      return <CustomCard data={item.props as unknown as CustomProps} onAction={onAction} />;
  }
}

/** Renders a message's streamed components: product cards in a strip, others stacked. */
export function GenUiStack({ items, onAction }: { items?: UiComponent[]; onAction: OnAction }) {
  if (!items || items.length === 0) return null;
  const cards = items.filter((i) => i.component === "product_card");
  const others = items.filter((i) => i.component !== "product_card");
  return (
    <div className="genui-stack">
      {cards.length > 0 && (
        <div className="genui-strip">
          {cards.map((c, i) => (
            <GenUiComponent key={`c${i}`} item={c} onAction={onAction} />
          ))}
        </div>
      )}
      {others.map((c, i) => (
        <GenUiComponent key={`o${i}`} item={c} onAction={onAction} />
      ))}
    </div>
  );
}
