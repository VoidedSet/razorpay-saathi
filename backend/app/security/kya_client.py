from app.security.context import VerifiedContext
from datetime import datetime, timezone, timedelta
import uuid

async def verify_store_entry_proof(challenge_id: str, agent_id: str, signed_assertion: str, merchant_domain: str) -> dict:
    """
    Mock implementation of calling the Connector Backend to verify a proof.
    Since the connector backend isn't built yet, we simulate a successful verification
    using the mocked proof structure.
    
    In a real implementation, this would make an HTTP POST to:
    https://connector.example.com/api/kya/verify
    """
    # For MVP, we simulate parsing the proof to extract claims
    # If the proof is empty or clearly invalid, reject
    if not signed_assertion or len(signed_assertion) < 10:
        return {
            "status": "deny",
            "reason": "Invalid or missing cryptographic proof"
        }
    
    # Mock successful verification and context generation
    # Provide generous default constraints for demo purposes
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=1)
    
    return {
        "status": "allow",
        "verified_context": VerifiedContext(
            correlation_id=f"corr_{uuid.uuid4().hex[:8]}",
            principal_ref="usr_mock_demo_1",
            connector_id="conn_mock_1",
            agent_id=agent_id or "agt_mock_1",
            issuer_ref="self",
            assurance_level="standard",
            scope_codes=["SC-100", "SC-200"],  # discovery, purchase
            constraints={
                "max_txn_inr": 5000,
                "daily_limit_inr": 15000,
                "auto_approve_below": 2000
            },
            issued_at=now.isoformat(),
            expires_at=expires.isoformat(),
            verification_status="verified"
        ).model_dump()
    }
