"""
Telegram Agent formatting copy, inline buttons, and publishing policy validation.
"""

import time
from typing import Any, Dict, List, Optional
from loot_brain.agents.base_agent import BaseAgent, AgentReport
from loot_brain.context.schemas import TelegramCopy, MemoryCategory, MemoryEntry, MemoryType
from loot_brain.security.permissions import PrivilegeScope, InputSanitizer


class TelegramAgent(BaseAgent):
    """
    Telegram Agent preparing deal syndication copy and inline CTA buttons.
    """

    def __init__(self):
        super().__init__(
            agent_id="telegram_agent",
            name="Telegram Publishing Agent",
            role="Telegram Post Preparation and Policy Check",
            capabilities=["format_post", "generate_buttons", "check_policy"],
            max_privilege_scope=PrivilegeScope.SAFE_WRITE,
        )

    def observe(self, input_data: Any) -> Dict[str, Any]:
        if isinstance(input_data, dict):
            return InputSanitizer.sanitize_dict(input_data)
        return {"title": str(input_data)}

    def understand(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": observation.get("title", "Loot Deal Alert"),
            "deal_price": float(observation.get("deal_price", 0.0)),
            "original_price": float(observation.get("original_price", 0.0)),
            "discount_percentage": float(observation.get("discount_percentage", 0.0)),
            "affiliate_url": observation.get("affiliate_url") or observation.get("url", "https://example.com"),
            "coupon_code": observation.get("coupon_code"),
            "store": observation.get("store", "Store"),
        }

    def plan(self, understood: Dict[str, Any]) -> Dict[str, Any]:
        return understood

    def execute(self, plan: Dict[str, Any]) -> TelegramCopy:
        title = plan["title"]
        deal_p = plan["deal_price"]
        orig_p = plan["original_price"]
        disc = plan["discount_percentage"]
        url = plan["affiliate_url"]
        coupon = plan["coupon_code"]
        store = plan["store"]

        copy_lines = [
            f"🔥 <b>{title}</b>",
            "",
            f"💰 <b>Deal Price:</b> ₹{deal_p:,.2f}" if deal_p > 0 else "💰 <b>Special Deal</b>",
        ]

        if orig_p > deal_p and orig_p > 0:
            copy_lines.append(f"❌ <b>MRP:</b> <s>₹{orig_p:,.2f}</s> ({disc}% OFF)")

        if coupon:
            copy_lines.append(f"🎟️ <b>Use Coupon:</b> <code>{coupon}</code>")

        copy_lines.append(f"🛒 <b>Store:</b> {store}")
        copy_lines.append("")
        copy_lines.append(f"👉 <a href=\"{url}\">BUY NOW BEFORE PRICE RISES</a>")

        buttons = [
            {"text": "⚡ Buy Now", "url": url},
            {"text": "📢 Share Deal", "url": f"https://t.me/share/url?url={url}"},
        ]

        return TelegramCopy(
            text_content="\n".join(copy_lines),
            parse_mode="HTML",
            inline_buttons=buttons,
            campaign_tags=["#LootDeal", f"#{store.replace(' ', '')}"],
        )

    def verify(self, payload: TelegramCopy) -> TelegramCopy:
        if not payload.text_content:
            raise ValueError("Telegram text content cannot be empty")
        return payload

    def report(self, verified: TelegramCopy) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            task_id="",
            success=True,
            data=verified.model_dump(),
        )

    def remember(self, report: AgentReport) -> List[MemoryEntry]:
        mem = MemoryEntry(
            memory_id=f"mem-tg-{int(time.time())}",
            category=MemoryCategory.TELEGRAM,
            memory_type=MemoryType.FACT,
            title="Telegram Post Formatted",
            content=f"Copy generated for {report.data.get('campaign_tags')}",
            confidence=1.0,
            agent_id=self.agent_id,
        )
        return [mem]
