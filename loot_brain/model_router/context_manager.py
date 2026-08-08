"""
Prompt Context Window Budgeting and Memory Pruning Manager.
"""

from typing import Any, Dict, List, Optional


class ContextManager:
    """
    Manages prompt token budgets, prunes long conversation histories,
    and preserves essential System Instructions and Memory Blocks.
    """

    def __init__(self, max_token_budget: int = 8000):
        self.max_token_budget = max_token_budget

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation heuristic (4 characters per token average)."""
        return max(1, len(text) // 4)

    def assemble_prompt_context(
        self,
        system_instruction: str,
        memory_context: str,
        task_input: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Assembles prompt within token budget:
        Priority: System Instruction > Task Input > Memory Context > History
        """
        sys_tokens = self._estimate_tokens(system_instruction)
        task_tokens = self._estimate_tokens(task_input)
        mem_tokens = self._estimate_tokens(memory_context)

        reserved_tokens = sys_tokens + task_tokens + mem_tokens
        remaining_budget = self.max_token_budget - reserved_tokens

        pruned_history: List[str] = []
        if conversation_history and remaining_budget > 0:
            history_budget = remaining_budget
            for msg in reversed(conversation_history):
                msg_str = f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                msg_tokens = self._estimate_tokens(msg_str)
                if history_budget >= msg_tokens:
                    pruned_history.insert(0, msg_str)
                    history_budget -= msg_tokens
                else:
                    break

        blocks = [
            f"[SYSTEM INSTRUCTION]\n{system_instruction}",
            f"[TASK INPUT]\n{task_input}",
        ]

        if memory_context:
            blocks.append(memory_context)

        if pruned_history:
            blocks.append("[CONVERSATION HISTORY]\n" + "\n".join(pruned_history))

        return "\n\n".join(blocks)
