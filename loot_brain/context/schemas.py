"""
Structured Pydantic Schemas for Deal Intelligence, Scraping, Memory, Telegram, and Evaluation.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class MemoryCategory(str, Enum):
    PLATFORM = "Platform"
    DEAL = "Deal"
    TELEGRAM = "Telegram"
    AFFILIATE = "Affiliate"
    AGENT = "Agent"
    SYSTEM = "System"
    LEARNING = "Learning"


class MemoryType(str, Enum):
    FACT = "Fact"
    PREFERENCE = "Preference"
    RULE = "Rule"
    SKILL = "Skill"
    ERROR = "Error"
    DECISION = "Decision"
    EXPERIENCE = "Experience"
    OBSERVATION = "Observation"
    HYPOTHESIS = "Hypothesis"
    EXPERIMENT = "Experiment"
    GOAL = "Goal"
    OUTCOME = "Outcome"


class MemoryEntry(BaseModel):
    """Unified Memory Schema supporting dual SQLite/Vector and Obsidian MD representation."""
    memory_id: str
    category: MemoryCategory
    memory_type: MemoryType
    title: str
    content: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    scope: str = "global"
    agent_id: Optional[str] = None
    platform: Optional[str] = None
    provenance: str = "system"
    evidence: List[str] = Field(default_factory=list)
    usefulness_score: float = Field(default=1.0, ge=0.0)
    last_used: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    ttl_days: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    archived: bool = False


class DealPayload(BaseModel):
    """Standardized Deal Data Contract."""
    deal_id: str
    title: str
    original_price: float = Field(ge=0.0)
    deal_price: float = Field(ge=0.0)
    discount_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    merchant: str = "Generic"
    store: str = "Generic"
    url: str
    clean_url: Optional[str] = None
    affiliate_url: Optional[str] = None
    image_url: Optional[str] = None
    category: str = "General"
    coupon_code: Optional[str] = None
    in_stock: bool = True
    seller_rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)

    # AI Reasoning & Evaluation Metrics
    deal_score: float = Field(default=50.0, ge=0.0, le=100.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    quality_score: float = Field(default=50.0, ge=0.0, le=100.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    estimated_savings: float = Field(default=0.0, ge=0.0)
    recommendation: str = "HOLD"  # PUBLISH, REJECT, HOLD, REVIEW
    reasons: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ScrapingPayload(BaseModel):
    """Scraped Content Result Contract."""
    source_url: str
    platform: str
    success: bool
    status_code: int = 200
    raw_html: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    error_message: Optional[str] = None


class TelegramCopy(BaseModel):
    """Telegram Post Formatting Schema."""
    text_content: str
    parse_mode: str = "HTML"
    inline_buttons: List[Dict[str, str]] = Field(default_factory=list)
    image_url: Optional[str] = None
    campaign_tags: List[str] = Field(default_factory=list)


class AffiliateMeta(BaseModel):
    """Affiliate Converter Payload."""
    original_url: str
    converted_url: str
    provider: str  # Amazon, Flipkart, CueLinks, EarnKaro
    tag_used: str
    success: bool
    error: Optional[str] = None


class EvaluationMetrics(BaseModel):
    """AI Evaluation Benchmarking Metrics."""
    task_id: str
    model_name: str
    latency_ms: float
    token_count_prompt: int
    token_count_completion: int
    estimated_cost_usd: float
    accuracy_score: float = Field(ge=0.0, le=1.0)
    false_positive: bool = False
    false_negative: bool = False
    hallucination_flag: bool = False
