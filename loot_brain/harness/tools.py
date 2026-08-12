"""
Centralized Tool Registry with Safety Levels, Input/Output Schemas,
RBAC Permission Enforcement, and Subsystem Adapters.
"""

from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.security.permissions import SecurityBoundary, PrivilegeScope, SecurityViolationError

logger = logging.getLogger(__name__)


class SideEffectLevel(str, Enum):
    """Safety classification for tool invocation."""
    READ_ONLY = "READ_ONLY"         # Search, query DB, read metrics (Zero state change)
    LOW_RISK = "LOW_RISK"           # Scoring calculations, format conversion (Transient state)
    SIDE_EFFECT = "SIDE_EFFECT"     # Telegram publishing, DB insert, cache write (Reversible/Standard)
    HIGH_IMPACT = "HIGH_IMPACT"     # Config mutation, code patch, scraper selector update (Requires approval)
    IRREVERSIBLE = "IRREVERSIBLE"   # DB truncation, token revocation, production deploy (Strict approval)


class ToolDefinition(BaseModel):
    """Metadata schema defining an agent-accessible capability."""
    name: str
    description: str
    owner_subsystem: str
    required_scope: PrivilegeScope = PrivilegeScope.READ_ONLY
    side_effect_level: SideEffectLevel = SideEffectLevel.READ_ONLY
    timeout_seconds: float = 10.0
    max_retries: int = 3
    enabled: bool = True
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    """Structured result returned by tool execution."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    side_effect_level: SideEffectLevel = SideEffectLevel.READ_ONLY


class ToolRegistry:
    """
    Centralized registry for agent-accessible capabilities in Loot Raiders.
    Enforces RBAC boundaries and side-effect policies before invoking tool handlers.
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._register_default_adapters()

    def register(self, definition: ToolDefinition, handler: Callable[..., Any]) -> None:
        """Register a new tool capability definition and its handler adapter."""
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler
        logger.info(f"[ToolRegistry] Registered tool '{definition.name}' ({definition.side_effect_level.value})")

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_name)

    def list_tools(self) -> List[ToolDefinition]:
        return [t for t in self._tools.values() if t.enabled]

    def execute(
        self,
        tool_name: str,
        agent_id: str,
        kwargs: Dict[str, Any],
        security_boundary: Optional[SecurityBoundary] = None,
        agent_scope: Optional[PrivilegeScope] = None,
    ) -> ToolExecutionResult:
        """
        Executes a registered tool after enforcing security boundaries and side-effect safety.
        """
        start_time = time.time()
        tool_def = self._tools.get(tool_name)

        if not tool_def:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is not registered in ToolRegistry.",
                execution_time_ms=0.0,
            )

        if not tool_def.enabled:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is currently disabled.",
                execution_time_ms=0.0,
                side_effect_level=tool_def.side_effect_level,
            )

        # Enforce RBAC security boundary if provided
        if security_boundary:
            try:
                security_boundary.check_permission(
                    agent_id=agent_id,
                    action_name=f"tool:{tool_name}",
                    required_scope=tool_def.required_scope,
                    agent_max_scope=agent_scope,
                    context={"kwargs_keys": list(kwargs.keys()), "side_effect": tool_def.side_effect_level.value},
                )
            except SecurityViolationError as e:
                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Security Policy Block: {str(e)}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                    side_effect_level=tool_def.side_effect_level,
                )

        # Execute handler function safely
        handler = self._handlers.get(tool_name)
        if not handler:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"No execution handler registered for tool '{tool_name}'.",
                execution_time_ms=(time.time() - start_time) * 1000,
                side_effect_level=tool_def.side_effect_level,
            )

        try:
            res_data = handler(**kwargs)
            duration = (time.time() - start_time) * 1000
            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                data=res_data,
                execution_time_ms=duration,
                side_effect_level=tool_def.side_effect_level,
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[ToolRegistry] Tool execution error '{tool_name}': {e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time_ms=duration,
                side_effect_level=tool_def.side_effect_level,
            )

    def _register_default_adapters(self) -> None:
        """Exposes existing authoritative Loot Raiders capabilities as registered tools."""
        
        # 1. deal.score
        def _score_adapter(price: float, mrp: float, title: str = "", platform: str = "Amazon", discount: Optional[float] = None, is_verified_low: bool = True) -> Dict[str, Any]:
            from deal_engine.scorer import calculate_deal_score
            disc = discount if discount is not None else (((mrp - price) / mrp) * 100.0 if mrp > price else 0.0)
            score = calculate_deal_score(
                platform=platform,
                price=int(price),
                mrp=int(mrp),
                discount=float(disc),
                is_verified_low=is_verified_low,
                title=title,
            )
            return {"deal_score": score, "is_glitch": score >= 80.0}

        self.register(
            ToolDefinition(
                name="deal.score",
                description="Calculates deal discount score and detects price glitch anomalies using Loot Raiders Scorer.",
                owner_subsystem="Deal Engine",
                required_scope=PrivilegeScope.READ_ONLY,
                side_effect_level=SideEffectLevel.LOW_RISK,
            ),
            _score_adapter,
        )

        # 2. affiliate.convert
        def _affiliate_adapter(url: str, platform: str = "amazon") -> Dict[str, Any]:
            from utils.affiliate import get_best_affiliate_url
            converted_url = get_best_affiliate_url(expanded_url=url, platform=platform, settings={})
            return {"converted_url": converted_url, "original_url": url}

        self.register(
            ToolDefinition(
                name="affiliate.convert",
                description="Converts retailer link to Loot Raiders affiliate link with tag 'lootraiders-21'.",
                owner_subsystem="Affiliate Engine",
                required_scope=PrivilegeScope.SAFE_WRITE,
                side_effect_level=SideEffectLevel.LOW_RISK,
            ),
            _affiliate_adapter,
        )

        # 3. dedup.check
        def _dedup_adapter(title: str, price: float = 0.0) -> Dict[str, Any]:
            from utils.semantic_dedup import find_semantic_duplicate
            matched_id = find_semantic_duplicate(title=title, price=int(price))
            return {"is_duplicate": matched_id is not None, "matched_id": matched_id}

        self.register(
            ToolDefinition(
                name="dedup.check",
                description="Checks title and price against ChromaDB vector store for duplicate deals.",
                owner_subsystem="Vector Deduplicator",
                required_scope=PrivilegeScope.READ_ONLY,
                side_effect_level=SideEffectLevel.READ_ONLY,
            ),
            _dedup_adapter,
        )

        # 4. telegram.publish
        def _telegram_publish_adapter(title: str, price: float, mrp: float, url: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
            from deal_engine.notifier import send_deal_to_telegram
            item = {"title": title, "price": price, "mrp": mrp, "affiliate_url": url, "url": url, "platform": "Amazon"}
            success = send_deal_to_telegram(item, target_chat_id=channel_id)
            return {"published": success, "title": title}

        self.register(
            ToolDefinition(
                name="telegram.publish",
                description="Publishes verified deal item to Loot Raiders Telegram Channel with ASCI compliance.",
                owner_subsystem="Telegram Engine",
                required_scope=PrivilegeScope.SAFE_WRITE,
                side_effect_level=SideEffectLevel.SIDE_EFFECT,
            ),
            _telegram_publish_adapter,
        )
