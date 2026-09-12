# Razorpay Saathi — Comprehensive Codebase Audit Report

**Date:** 2026-09-12  
**Scope:** Full repository — backend (FastAPI, LangGraph, agents, MCP, A2A), frontend (Next.js, GenUI), tests, and documentation.  
**Test Suite:** 24/24 passing ✅  

---

## Table of Contents

1. [Critical Bugs (Application-Breaking)](#1-critical-bugs)
2. [Non-Functional Features & Broken UI](#2-non-functional-features)
3. [MCP (Model Context Protocol) Audit](#3-mcp-audit)
4. [A2A (Agent-to-Agent) Audit](#4-a2a-audit)
5. [Dead Code & Technical Debt](#5-dead-code)
6. [Quality & Consistency Issues](#6-quality-issues)
7. [Security Concerns](#7-security)
8. [React / Frontend Quality](#8-react-quality)
9. [Plan vs. Implementation Gap Analysis](#9-gap-analysis)
10. [Recommendations & Improvements](#10-recommendations)

---

## 1. Critical Bugs

### 🚨 C-1: ImportError crashes `/api/campaign` endpoint
- **File:** `backend/app/main.py`, Line 387
- **Bug:** `from app.graph import _HARD_POLICY_MAX_DISCOUNT_PCT` — but `_HARD_POLICY_MAX_DISCOUNT_PCT` is defined in `app.state`, not `app.graph`.
- **Impact:** Any POST to `/api/campaign` triggers an `ImportError`. The campaign flow is completely broken at runtime.
- **Fix:** Change to `from app.state import _HARD_POLICY_MAX_DISCOUNT_PCT`.

### 🚨 C-2: `UnboundLocalError` in chat SSE stream
- **File:** `backend/app/main.py`, Lines 235, 275, 280
- **Bug:** `final_cart` is only assigned conditionally inside the streaming loop (`if "cart" in output: final_cart = output["cart"]`), but it is unconditionally referenced at the end of the generator and in the exception handler.
- **Impact:** If no agent node returns a `"cart"` key in its output (e.g., the support agent path), the SSE stream crashes with `UnboundLocalError`, and the exception handler itself also crashes, preventing any error recovery.
- **Fix:** Initialize `final_cart = req.cart` before the `async for` loop.

---

## 2. Non-Functional Features

### ⚠️ N-1: Campaign Panel / Manager Actions completely missing from UI
- **File:** `frontend/src/app/page.tsx`, Right Sidebar (`agent-right-panel`, ~line 1229)
- **Issue:** The `aside.agent-right-panel` only contains `CuratedSelectionCarousel` and `Cart Summary`. There is no "Manager Actions" panel with campaign trigger buttons.
- **Impact:** The `triggerCampaign` function (line 887), the `campaignResults` state (line 884), and the `CampaignResultCard` component (line 797) are all defined but **never rendered**. The campaign flow can only be triggered via the terminal script `simulate_stagnant.py`, not from the web UI.

### ⚠️ N-2: "Proceed to Checkout" button is a no-op
- **File:** `frontend/src/app/page.tsx`, Line 1345
- **Issue:** The checkout button in the cart drawer just fires `alert("Mock Razorpay Autonomous Checkout Initiated!")`. It does not transition the user to the Billing Agent or create a Razorpay payment link.
- **Impact:** Users clicking "Checkout" from the classic store view get a browser alert instead of a real checkout flow. The only real checkout path is via the agent chat.

---

## 3. MCP (Model Context Protocol) Audit

### Architecture
- **File:** `backend/app/mcp_server.py` (64 lines)
- **Transport:** Runs as a **standalone stdio process** via `mcp.run()`. It is **not** mounted into `main.py` (FastAPI) and is **not** served over HTTP/SSE.
- **Tools exposed:** Only 2 read-only tools: `search_catalog` and `get_product`.

### Findings

| ID | Severity | Finding |
|---|---|---|
| MCP-1 | **High** | MCP server is stdio-only. No HTTP/SSE transport configured. External agents cannot connect over the network. They must spawn the MCP server as a subprocess. |
| MCP-2 | **High** | Missing transactional tools. `add_to_cart`, `view_cart`, `clear_cart`, `get_offers`, and `checkout` all exist as internal LangGraph tools in `sales.py` but are not exposed via MCP. An external buyer agent can browse but cannot transact. |
| MCP-3 | **Medium** | `test_mcp_buyer_agent.py` **does not test MCP over the wire**. It directly imports the Python functions (`from app.mcp_server import search_catalog, get_product`) and calls them in-process. This is a function-level test, not a protocol integration test. |
| MCP-4 | **Low** | The `search_catalog` tool's `category` and `specs_filter` parameters use `str = None` type hints. In strict type checking, these should be `str | None = None` or use `Optional[str]`. |

---

## 4. A2A (Agent-to-Agent) Audit

### Architecture
- **Endpoint:** `POST /api/a2a/negotiate` in `main.py`
- **Mechanism:** Single-shot synchronous invocation of the full LangGraph (`_graph.ainvoke(initial_state)`). Sets `client_type: "agent"` to adjust agent prompts.

### Findings

| ID | Severity | Finding |
|---|---|---|
| A2A-1 | **High** | Not compliant with any standard A2A protocol (e.g., Google's A2A SDK, OpenAI function calling protocol). It's a custom REST endpoint with a custom JSON schema. |
| A2A-2 | **High** | Single-shot only — no multi-turn negotiation. The `A2ANegotiateRequest` schema has no `history` field, so an external agent cannot conduct a back-and-forth conversation. |
| A2A-3 | **High** | Zero authentication. Any external agent can hit `/api/a2a/negotiate` without API keys, OAuth tokens, or signatures. No rate limiting either. |
| A2A-4 | **Medium** | Agent budget is not enforced. The `budget_inr` field is accepted in the request and stored in the `agent_profile`, but the manager only uses it to cap the tier discount to 5% (line 43 of `manager.py`). It doesn't actually check whether recommended products are within the agent's budget. |
| A2A-5 | **Low** | The response includes `data_payloads` (UI components serialized as JSON) which are designed for rendering, not machine-to-machine consumption. A proper A2A response should return structured product/offer data, not presentation components. |

---

## 5. Dead Code & Technical Debt

| ID | Severity | File | Finding |
|---|---|---|---|
| D-1 | **Medium** | `frontend/src/app/genui.tsx` | Entire file (230 lines) is dead code. Never imported anywhere. Its CSS classes (`.genui-card`, `.genui-checkout`, etc.) don't exist in `globals.css`. `page.tsx` has its own inline GenUI components instead. |
| D-2 | **Medium** | `frontend/src/app/page.module.css` | Entirely unused. `page.tsx` uses only global classes from `globals.css`. |
| D-3 | **Low** | `backend/app/config.py` | `get_routing_llm()` function (line 57) is defined but never called. The manager routing is deterministic — no LLM needed. |
| D-4 | **Low** | `backend/app/db.py` | `get_abandoned_carts()` function (line 507) is defined but never invoked. It was planned for cart-abandonment campaigns. |
| D-5 | **Low** | `globals.css` | ~260 lines of campaign CSS (`.campaign-panel`, `.campaign-trigger-btn`, `.campaign-result-card`, etc.) exist but the JSX that references them was never added to `page.tsx`. |
| D-6 | **Low** | `frontend/src/app/page.tsx` | `campaignResults` state (line 884), `campaignLoading` state (line 885), `triggerCampaign` function (line 887), and `CampaignResultCard` component (line 797) are all defined but never rendered in the JSX tree. |

---

## 6. Quality & Consistency Issues

### Q-1: Currency display inconsistencies (High)
The frontend mixes `$` and `₹` across the app. The backend exclusively uses INR (`price_inr`).

| Location | Currency Shown | Expected |
|---|---|---|
| Curated Selection Carousel (line 774) | `$` | `₹` |
| Classic Product Detail Modal (line 1363) | `$` | `₹` |
| Cart Drawer item price (line 1316) | `$` | `₹` |
| Cart Drawer total (line 1342) | `$` | `₹` |
| Classic Store Card (line 1141) | Conditional (`₹` if > 500, else `$`) | `₹` |
| Agent Cart Summary (line 1257) | `₹` | ✅ |
| GenUI Checkout Widget (line 618) | `₹` | ✅ |
| Campaign Result Card (line 815) | `₹` | ✅ |

### Q-2: Category mismatches (Medium)
- **Fallback `PRODUCTS` array** (lines 101-166): Uses `"vintage"`, `"court"`, `"running"`, `"classics"`.
- **Backend DB categories:** `"sneakers"`, `"apparel"`, `"accessories"`.
- **Sidebar filter:** Expects `"sneakers"`, `"apparel"`, `"accessories"`, `"sale"`.
- **Impact:** If the backend fetch fails (network error, server down), all products fall back to the hardcoded array. The sidebar filter then shows nothing under "sneakers", "apparel", or "accessories".

### Q-3: Hardcoded localhost URLs (Medium)
All backend URLs in `page.tsx` are hardcoded to `http://localhost:8000`. No env vars or `next.config.ts` rewrites are used. This blocks any deployment beyond local development.

### Q-4: Negative cart quantity bug (Low)
- **File:** `backend/app/db.py`, `add_to_cart` function
- **Issue:** No validation that `qty` is positive. A negative quantity passed by the LLM would decrease the cart total incorrectly.

---

## 7. Security Concerns

| ID | Severity | Finding |
|---|---|---|
| S-1 | **High** | Real Groq API key exposed in `backend/.env` (line 21: `gsk_eYn...`). While `.env` is in `.gitignore`, if this file was ever committed, the key is compromised. |
| S-2 | **Medium** | No authentication on any API endpoint — `/api/chat`, `/api/a2a/negotiate`, `/api/campaign`, `/api/mark_stagnant/{id}`. |
| S-3 | **Low** | CORS is hardcoded to `allow_origins=["http://localhost:3000"]`. Needs to be parameterized for production. |
| S-4 | **Low** | `db.get_payment_link` uses `hashlib.sha1` for mock token generation. SHA-1 is cryptographically weak (acceptable for a hackathon mock, but should not ship). |

---

## 8. React / Frontend Quality

| ID | Severity | Finding |
|---|---|---|
| R-1 | **Medium** | Array index used as React `key` in `messages.map`, `components.map`, and checkout items. Causes subtle rendering bugs on reorder/delete. |
| R-2 | **Medium** | `filteredProducts` is re-computed on every render without `useMemo`. Cart modifier functions (`addToCart`, `updateCartQty`) are not wrapped in `useCallback`, causing unnecessary re-renders of child components. |
| R-3 | **Low** | The initial welcome message `useEffect` (line 953) has an empty dependency array `[]` but references the `messages` state variable, which can trigger ESLint warnings and potential stale closure bugs. |
| R-4 | **Low** | `useAgentChat` accepts an inline callback `(newCartData) => {...}` on every render. Inside the async `sendMessage` loop, this callback reference can go stale mid-stream. |

---

## 9. Plan vs. Implementation Gap Analysis

| Plan Section | Status | Notes |
|---|---|---|
| **A. Store Manager Agent** | ✅ Fully built | `manager_init_node` + `manager_audit_node`. DB-grounded ceiling computation, injection guardrails, `guardrails.py` price/hallucination auditing. |
| **B. Sales Agent** | ✅ Fully built | Tool-calling agent with `search_store_catalog`, `add_to_cart`, `view_cart`, `clear_cart`, `render_custom_ui`. GenUI product cards streamed. |
| **C. Billing Agent** | ✅ Fully built | Razorpay Offers API integration (mocked), Payment Link generation, checkout widget GenUI. |
| **D. Promo/Marketing Agent** | ⚠️ Backend built, UI missing | `marketing.py` and `/api/campaign` endpoint exist. Campaign panel UI was never wired into the frontend. |
| **MCP Server** | ⚠️ Partial | Read-only catalog tools. No transactional tools. Stdio-only transport. |
| **A2A Protocol** | ⚠️ Basic | Single-shot REST endpoint. No multi-turn negotiation. No authentication. No standard protocol compliance. |
| **Failure Recovery** | ❌ Missing | Plan promises "Manager intercepts errors, rolls back state, and instructs the child agent". No such error recovery mechanism exists. Errors crash the stream (see C-2). |
| **Cryptographic Budget Gating** | ❌ Missing | Plan mentions "cryptographic/logged approval". Implementation uses plain numeric comparison — no signed approvals or tamper-proof audit logs. |

---

## 10. Recommendations & Improvements

### Must-Fix (Bugs)
1. **Fix C-1:** Change `main.py` line 387 to `from app.state import _HARD_POLICY_MAX_DISCOUNT_PCT`.
2. **Fix C-2:** Add `final_cart = req.cart` before the `async for` loop in `langgraph_stream()`.

### High Priority (Features & UX)
3. **Wire Campaign Panel into UI:** Add the Manager Actions campaign trigger panel to the agent right sidebar. The CSS, state, component, and function all exist — they just need to be rendered in the JSX.
4. **Standardize currency to ₹:** Sweep all price displays in `page.tsx` to consistently use `₹{value.toLocaleString("en-IN")}`. Remove all `$` formatting.
5. **Fix category fallback data:** Update the `PRODUCTS` array categories to match backend DB categories (`sneakers` instead of `vintage`, etc.).
6. **Make Checkout button functional:** Either route to agent chat with "checkout" or call the backend to create a Razorpay payment link directly.

### Medium Priority (Architecture)
7. **Expose MCP transactional tools:** Add `add_to_cart`, `view_cart`, `get_offers` to `mcp_server.py` so external agents can complete purchases, not just browse.
8. **Add SSE transport to MCP:** Mount the MCP server into FastAPI with an SSE transport so external agents can connect over HTTP without spawning a subprocess.
9. **Make A2A stateful:** Add a `history` field to `A2ANegotiateRequest` and store/retrieve session state so agents can conduct multi-turn negotiations.
10. **Add authentication:** At minimum, add API key validation on `/api/a2a/negotiate` and `/api/campaign` endpoints.
11. **Environment-variable-ize frontend URLs:** Use `NEXT_PUBLIC_API_URL` or `next.config.ts` rewrites so the app can be deployed beyond `localhost`.

### Low Priority (Polish)
12. **Delete dead code:** Remove `genui.tsx`, `page.module.css`, and the unused `get_routing_llm()` / `get_abandoned_carts()` functions.
13. **Add input validation:** Validate `qty > 0` in `db.add_to_cart()`.
14. **React performance:** Wrap `filteredProducts` in `useMemo`, cart operations in `useCallback`, and use stable keys instead of array indices.
15. **Error recovery:** Implement the plan's promise of graceful failure recovery — catch agent errors and surface them as user-visible messages instead of crashing the stream.
16. **Upgrade `convo.log`:** This is a raw conversation log sitting in the repo root. Either integrate it into the test fixtures or remove it.

---

*End of audit.*
