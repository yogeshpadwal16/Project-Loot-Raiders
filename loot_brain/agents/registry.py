"""
Central Agent Registry for Loot Brain Autonomous Agents.
"""

from typing import Any, Dict, List, Optional
from loot_brain.agents.base_agent import BaseAgent, AgentReport


class AgentNotFoundError(Exception):
    """Raised when an unregistered agent ID is requested."""
    pass


class AgentRegistry:
    """
    Manages registration, lifecycle invocation, and discovery of Loot Brain agents.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Registers an agent instance."""
        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        """Unregisters an agent by ID."""
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> BaseAgent:
        """Retrieves registered agent or raises AgentNotFoundError."""
        if agent_id not in self._agents:
            raise AgentNotFoundError(f"Agent '{agent_id}' is not registered in AgentRegistry.")
        return self._agents[agent_id]

    def list_agents(self) -> List[Dict[str, Any]]:
        """Lists metadata of all registered agents."""
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "role": a.role,
                "capabilities": a.capabilities,
                "max_privilege_scope": a.max_privilege_scope.value,
                "state": a.state.value,
            }
            for a in self._agents.values()
        ]

    def dispatch(self, agent_id: str, task_id: str, input_data: Any) -> AgentReport:
        """Dispatches a task to the targeted agent."""
        agent = self.get_agent(agent_id)
        return agent.run_lifecycle(task_id=task_id, input_data=input_data)
