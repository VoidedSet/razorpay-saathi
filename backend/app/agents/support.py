from langchain_core.messages import SystemMessage
from app.config import get_llm
from app.state import AgentState, AGENT_LABELS, _strip_think

def _support_system_prompt(state: AgentState) -> str:
    profile = state.get("user_profile", {})
    name    = profile.get("name", "Customer")
    history = profile.get("purchase_history", [])
    return f"""You are the Customer Support Agent for Razorpay Saathi.
Customer: {name} | Recent purchases: {', '.join(history[-2:]) if history else 'none'}
Help with order issues, returns, refunds, complaints. Be empathetic and solution-focused.
Escalate financial decisions (refunds > ₹1,000) to the Manager Agent. Avoid emojis and decorative symbols."""

async def support_agent_node(state: AgentState) -> dict:
    prompt   = _support_system_prompt(state)
    llm      = get_llm()
    messages = [SystemMessage(content=prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages)
    if hasattr(response, "content") and response.content:
        response.content = _strip_think(response.content)
    return {
        "messages":  [response],
        "audit_log": state.get("audit_log", []) + [{
            "agent":  AGENT_LABELS["support_agent"],
            "detail": f"Response generated ({len(response.content)} chars)",
        }],
    }
