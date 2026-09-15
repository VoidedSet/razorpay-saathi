import json
from langchain_core.messages import AIMessage, SystemMessage
from app.state import AgentState
from app.security.kya_client import verify_store_entry_proof
from app.security.subagent_tracker import SubAgentTracker

async def security_kya_node(state: AgentState) -> dict:
    """
    The Security / KYA entry gate.
    Runs BEFORE the Manager Agent to authenticate external agents.
    Does NOT use an LLM for the security decision.
    """
    # If the user is a human, bypass KYA (or handle human auth differently)
    if state.get("client_type") != "agent":
        return {"kya_verified": True}
    
    # If already verified in this session, bypass
    if state.get("kya_verified"):
        return {}

    # Extract the proof from the state (we'll assume the A2A endpoint places
    # the raw signed assertion into the state, or we parse it from the message)
    # For MVP, we look for a proof injected into the last message by the endpoint.
    messages = state.get("messages", [])
    if not messages:
        return {}
    
    last_message = messages[-1].content
    
    # In a real scenario, this is passed via headers, but for our MVP demo
    # let's assume the A2A endpoint extracts it and adds it to the state
    # as "kya_proof" or we can parse a dummy one. Let's just simulate verification.
    
    # We call the KYA client
    verification_result = await verify_store_entry_proof(
        challenge_id="chal_123",  # Mocked
        agent_id="agt_mock_1",    # Mocked
        signed_assertion="dummy_signature_data", # Mocked
        merchant_domain="saathi.store"
    )

    audit_entry = {
        "action": "kya_verification",
        "detail": f"Status: {verification_result.get('status')}",
        "timestamp": "now" # In real life, use ISO datetime
    }
    
    if verification_result.get("status") == "allow":
        context = verification_result["verified_context"]
        
        # Initialize SubAgentTracker
        tracker = SubAgentTracker(
            root_agent_id=context["agent_id"],
            root_scope=context["scope_codes"]
        )
        
        return {
            "kya_verified": True,
            "kya_context": context,
            "correlation_id": context["correlation_id"],
            "delegation_scope": context["scope_codes"],
            "delegation_limits": context["constraints"],
            "sub_agent_tracker": tracker.to_dict(),
            "audit_log": [audit_entry],
            "messages": [SystemMessage(content=f"[Security Agent] KYA Verification successful. Admitting agent {context['agent_id']} under principal {context['principal_ref']}. Scopes: {context['scope_codes']}")]
        }
    else:
        # Deny entry
        return {
            "kya_verified": False,
            "audit_log": [audit_entry],
            "messages": [SystemMessage(content=f"[Security Agent] KYA Verification FAILED: {verification_result.get('reason')}")]
        }
