from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class VerifiedContext(BaseModel):
    """
    Represents the verified security context passed from the KYA Security Agent
    to the Manager Agent.
    """
    correlation_id: str = Field(description="Unique session trace ID")
    principal_ref: str = Field(description="Human user reference")
    connector_id: str = Field(description="Durable connector identity")
    agent_id: str = Field(description="Specific agent binding identity")
    issuer_ref: str = Field(description="Who issued the credential")
    assurance_level: str = Field(default="standard")
    scope_codes: List[str] = Field(default_factory=list, description="Allowed scopes e.g., SC-100")
    constraints: Dict = Field(default_factory=dict, description="Constraints e.g., spending limits")
    issued_at: str = Field(description="ISO timestamp")
    expires_at: str = Field(description="ISO timestamp")
    verification_status: str = Field(default="verified")
