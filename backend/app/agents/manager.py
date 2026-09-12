import re
from app import db
from app import guardrails
from app.state import (
    AgentState,
    _HARD_POLICY_MAX_DISCOUNT_PCT,
    _detect_phase,
    _INJECTION_PATTERNS,
    _strip_think,
)

async def manager_init_node(state: AgentState) -> dict:
    """
    Supervisor — runs BEFORE every agent turn.
    1. Load user profile & store balance sheet from SQLite DB
    2. Compute discount ceiling (user tier × store balance sheet profit margin)
    3. Detect session phase (browsing / checkout / support)
    4. Run guardrails on incoming message
    """
    updates: dict = {}
    new_entries: list[dict] = []
    notes = list(state.get("manager_notes", []))

    user_id = state.get("user_id") or "usr_001"

    # ── 1. Load profile & store financial bounds from SQLite DB ─────────────────
    profile = state.get("user_profile", {})
    if not profile:
        profile = db.get_user_profile(user_id)
        if not profile:
            fallback_key = "agt_001" if state.get("client_type") == "agent" else "usr_001"
            profile = db.get_user_profile(fallback_key) or {
                "name": "Alex", "tier": "gold", "total_spend_inr": 145000,
                "purchase_history": [], "preferences": [], "discount_ceiling_pct": 10
            }

        # Overlay A2A agent_profile fields if provided
        ap = state.get("agent_profile", {})
        if ap:
            if "name"        in ap: profile["name"]        = ap["name"]
            if "preferences" in ap: profile["preferences"] = ap["preferences"]
            if "budget"      in ap:
                profile["discount_ceiling_pct"] = min(profile.get("discount_ceiling_pct", 5), 5)

        updates["user_profile"] = profile

        # Read balance sheet to set dynamic financial bounds
        bs = db.get_balance_sheet()
        store_max_disc = bs.get("max_discount_allowed_pct", 12)
        user_tier_max  = profile.get("discount_ceiling_pct", 5)

        ceiling = float(min(user_tier_max, store_max_disc, _HARD_POLICY_MAX_DISCOUNT_PCT))
        updates["discount_ceiling"] = ceiling

        new_entries.append({
            "agent":  "Manager Agent",
            "detail": (
                f"DB Lookup: Profile [{profile.get('name')}] ({profile.get('tier','').title()}) | "
                f"Store margin: {bs.get('profit_margin_pct', 16)}% | "
                f"Discount ceiling: {ceiling}%"
            ),
        })

    # ── 2. Detect phase ───────────────────────────────────────────────────────
    last_msg      = state["messages"][-1].content
    current_phase = state.get("session_phase", "browsing")
    new_phase     = _detect_phase(last_msg, current_phase)
    updates["session_phase"] = new_phase
    # Surface the checkout widget only on the FIRST turn we enter checkout — not on
    # every later billing turn (payment-mode follow-ups, etc.).
    updates["just_entered_checkout"] = new_phase == "checkout" and current_phase != "checkout"

    if new_phase != current_phase:
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"Phase transition: {current_phase} → {new_phase}",
        })

    # ── 3. Guardrails ─────────────────────────────────────────────────────────
    violation = None
    for pattern, label in _INJECTION_PATTERNS:
        if re.search(pattern, last_msg, re.IGNORECASE):
            violation = label
            break

    if violation:
        notes.append(f"Guardrail: {violation} detected in message")
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"GUARDRAIL TRIGGERED: {violation} — request sanitised",
        })
    else:
        target = {"checkout": "Billing", "support": "Support"}.get(new_phase, "Sales")
        new_entries.append({
            "agent":  "Manager Agent",
            "detail": f"Guardrail: OK | Routing to {target} Agent",
        })

    updates["manager_notes"] = notes
    updates["audit_log"]     = state.get("audit_log", []) + new_entries
    return updates


async def manager_audit_node(state: AgentState) -> dict:
    """
    Supervisor — runs AFTER every agent turn.

    Validates the agent's response against the live catalog and the
    Manager-approved discount ceiling (see guardrails.audit_response):
      • hallucinated product ids     → blocked
      • absolute-rupee discounts      → caught (not just literal "N% off")
      • explicit over-ceiling "N%"    → caught
    A dirty response also produces a user-visible Manager correction.
    """
    new_entries: list[dict] = []
    notes = list(state.get("manager_notes", []))
    updates: dict = {}

    last_ai = next(
        (m for m in reversed(state["messages"])
         if hasattr(m, "type") and m.type == "ai" and m.content),
        None,
    )

    if last_ai:
        ceiling = state.get("discount_ceiling", _HARD_POLICY_MAX_DISCOUNT_PCT)
        cart    = db.get_cart(state.get("session_id", "default"))
        budget  = state.get("agent_profile", {}).get("budget_inr") if state.get("client_type") == "agent" else None
        audit   = guardrails.audit_response(_strip_think(last_ai.content), ceiling, cart, budget)

        new_entries.extend(guardrails.audit_log_entries(audit, ceiling))

        if not audit["clean"]:
            updates["manager_correction"] = guardrails.build_manager_correction(audit, ceiling)
            for pid in audit["hallucinated_ids"]:
                notes.append(f"VIOLATION: hallucinated product {pid}")
            for v in audit["price_violations"]:
                notes.append(
                    f"VIOLATION: {v['name']} quoted ₹{v['quoted']:,} "
                    f"(≈{v['effective_pct']:g}% > {ceiling:g}% ceiling)"
                )
            for v in audit["pct_violations"]:
                notes.append(f"VIOLATION: {v['pct']:g}% {v['type']} > {ceiling:g}% ceiling")
            for v in audit.get("budget_violations", []):
                notes.append(f"VIOLATION: {v}")

    updates["manager_notes"] = notes
    updates["audit_log"]     = state.get("audit_log", []) + new_entries
    return updates
