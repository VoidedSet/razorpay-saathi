# Razorpay Saathi – Codebase Audit Report

Following a thorough review of the entire repository—including the multi-agent backend, MCP tools, A2A implementations, and the Next.js frontend—here are the findings, categorized by severity, along with suggestions for improvement.

## 🚨 Critical Issues & Bugs

### 1. Application Crash on Campaign Endpoint (`backend/app/main.py`)
- **Location:** `main.py`, Line 387
- **Issue:** The code attempts to import `_HARD_POLICY_MAX_DISCOUNT_PCT` from `app.graph`. However, this constant is defined in `app.state`, not `app.graph`. 
- **Impact:** Any `POST` request to `/api/campaign` will trigger an `ImportError` and immediately crash the server.

### 2. UnboundLocalError in Chat Stream (`backend/app/main.py`)
- **Location:** `main.py`, Lines 235, 275, 280
- **Issue:** The `final_cart` variable is conditionally assigned inside the streaming loop (`if "cart" in output: final_cart = output["cart"]`). However, it is unconditionally accessed at the end of the generator (lines 275 and 280).
- **Impact:** If an agent node executes but does not return a `"cart"` key in its output, the stream will throw an `UnboundLocalError`, breaking the chat response.

## ⚠️ Non-Functional Features & Broken Links

### 3. Missing Campaign Panel / Manager Actions (`frontend/src/app/page.tsx`)
- **Location:** `page.tsx`, Right Sidebar (`agent-right-panel`)
- **Issue:** The UI buttons to trigger the marketing campaigns (Manager Actions) are missing from the current `page.tsx` layout. 
- **Impact:** While the backend endpoints, frontend `CampaignResultCard` component, and relevant CSS (`globals.css`) exist, the user has no way to actually trigger the campaign from the web interface.

### 4. Completely Dead Code (`frontend/src/app/genui.tsx`)
- **Location:** `genui.tsx`
- **Issue:** This file defines several Generative UI components but is **never imported or used** anywhere in the frontend. Furthermore, the CSS classes it relies on (e.g., `.genui-card`, `.genui-checkout`) do not exist in `globals.css`. 
- **Impact:** Bloats the codebase. Currently, `page.tsx` handles its own GenUI rendering internally.

## 🔍 Quality of Product Checks & Inconsistencies

### 5. Category Mismatches (Frontend vs. Backend)
- **Location:** `page.tsx` (`PRODUCTS` array) vs. `backend/app/db.py`
- **Issue:** The hardcoded fallback data in the frontend uses categories like `"vintage"`, `"court"`, `"running"`, and `"classics"`. However, the backend database and the frontend sidebar filters expect `"sneakers"`, `"apparel"`, and `"accessories"`.
- **Impact:** If the backend fails to load or the frontend falls back to the hardcoded data, the sidebar filters will not work properly because the categories do not match.

### 6. Currency Display Inconsistencies
- **Location:** `frontend/src/app/page.tsx`
- **Issue:** The UI mixes the use of the Dollar sign (`$`) and the Indian Rupee sign (`₹`). For example:
  - Line 774 uses `${p.price}`
  - Line 1141 uses a conditional format: `{p.price > 500 ? '₹${p.price.toLocaleString("en-IN")}' : '$${p.price}'}`
  - The cart summary explicitly uses `$` (Lines 1316, 1342).
- **Impact:** Creates a confusing and unpolished user experience, especially since the backend specifically calculates and returns values in INR (`price_inr`).

## 💡 Suggestions & Improvements

1. **Fix Backend Imports:** Update `main.py` (Line 387) to correctly import the policy constant:
   ```python
   from app.state import _HARD_POLICY_MAX_DISCOUNT_PCT
   ```
2. **Initialize Stream Variables:** In `main.py`, initialize `final_cart = req.cart` before the `async for` loop begins to guarantee it always holds a valid state, preventing `UnboundLocalError`.
3. **Restore the Campaign UI:** Re-integrate the Manager Actions/Campaign trigger buttons into the `<aside className="agent-right-panel">` in `page.tsx` so the marketing flow can be demonstrated via the browser, rather than just the terminal script.
4. **Clean up GenUI:** Either delete `genui.tsx` to reduce technical debt, or refactor `page.tsx` to actually import and utilize it (which would require adding the missing CSS).
5. **Harmonize Data:** Update the `PRODUCTS` fallback array in `page.tsx` so that its `category` fields strictly map to `"sneakers"`, `"apparel"`, or `"accessories"`.
6. **Standardize Currency:** Perform a sweeping find-and-replace in `page.tsx` to format all prices using INR. E.g., `₹{value.toLocaleString("en-IN")}`.
7. **Consolidate MCP:** `mcp_server.py` currently runs as a standalone script. For a tighter, production-grade architecture, consider embedding the `FastMCP` server directly into the FastAPI lifecycle in `main.py` (using SSE or stdio transport wrappers if appropriate).
