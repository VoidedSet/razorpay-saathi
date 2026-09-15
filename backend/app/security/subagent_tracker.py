from dataclasses import dataclass, field
from typing import List, Dict, Optional
import uuid
from datetime import datetime, timezone

@dataclass
class SubAgentNode:
    sub_agent_id: str
    parent_id: str
    spawned_at: str
    inherited_scope: List[str]
    depth: int
    status: str
    actions: List[Dict] = field(default_factory=list)

class SubAgentTracker:
    MAX_DEPTH = 3

    def __init__(self, root_agent_id: str, root_scope: List[str]):
        self.root_agent_id = root_agent_id
        self.root_scope = root_scope
        self.nodes: Dict[str, SubAgentNode] = {}

    def spawn(self, parent_id: str, requested_scope: List[str]) -> SubAgentNode:
        """
        Register a new sub-agent. Scope is attenuated (intersection of
        parent's scope and requested scope). Raises if depth exceeded.
        """
        parent_scope = self._get_scope(parent_id)
        # Attenuate scope: only allow what parent has
        effective_scope = [s for s in requested_scope if s in parent_scope]
        depth = self._get_depth(parent_id) + 1

        if depth > self.MAX_DEPTH:
            raise PermissionError(f"Sub-agent depth limit ({self.MAX_DEPTH}) exceeded")

        sub_agent_id = f"sub_{uuid.uuid4().hex[:8]}"
        node = SubAgentNode(
            sub_agent_id=sub_agent_id,
            parent_id=parent_id,
            spawned_at=datetime.now(timezone.utc).isoformat(),
            inherited_scope=effective_scope,
            depth=depth,
            status="active"
        )
        self.nodes[node.sub_agent_id] = node
        return node

    def log_action(self, sub_agent_id: str, action: str, detail: str = ""):
        """Record an action taken by a sub-agent."""
        if sub_agent_id in self.nodes:
            self.nodes[sub_agent_id].actions.append({
                "action": action,
                "detail": detail,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    def terminate(self, sub_agent_id: str):
        """Kill a sub-agent and all its children."""
        if sub_agent_id in self.nodes:
            self.nodes[sub_agent_id].status = "terminated"
            # Cascade termination to children
            for node in self.nodes.values():
                if node.parent_id == sub_agent_id and node.status != "terminated":
                    self.terminate(node.sub_agent_id)

    def terminate_all(self):
        """Kill all sub-agents (called when root delegation is revoked)."""
        for node in self.nodes.values():
            node.status = "terminated"

    def get_correlation_chain(self, sub_agent_id: str) -> List[str]:
        """Walk up the tree: sub_agent → parent → ... → root_agent."""
        chain = []
        current = sub_agent_id
        while current and current != self.root_agent_id:
            chain.append(current)
            node = self.nodes.get(current)
            current = node.parent_id if node else None
        chain.append(self.root_agent_id)
        return chain

    def _get_scope(self, agent_id: str) -> List[str]:
        if agent_id == self.root_agent_id:
            return self.root_scope
        node = self.nodes.get(agent_id)
        return node.inherited_scope if node else []

    def _get_depth(self, agent_id: str) -> int:
        if agent_id == self.root_agent_id:
            return 0
        node = self.nodes.get(agent_id)
        return node.depth if node else 0

    def to_dict(self) -> dict:
        return {
            "root_agent_id": self.root_agent_id,
            "root_scope": self.root_scope,
            "nodes": {k: v.__dict__ for k, v in self.nodes.items()}
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SubAgentTracker':
        tracker = cls(data.get("root_agent_id", ""), data.get("root_scope", []))
        for k, v in data.get("nodes", {}).items():
            tracker.nodes[k] = SubAgentNode(**v)
        return tracker
