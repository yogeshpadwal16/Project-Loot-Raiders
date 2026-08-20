"""
Configuration and Feature Flags for Local Hugging Face AI Subsystem.
"""

import os
from pydantic import BaseModel


class HFAIConfig(BaseModel):
    """Configuration settings for local Hugging Face AI integration."""
    ENABLE_LOCAL_AI: bool = os.getenv("ENABLE_LOCAL_AI", "false").lower() == "true"
    LOCAL_AI_SHADOW_MODE: bool = os.getenv("LOCAL_AI_SHADOW_MODE", "true").lower() == "true"
    ENABLE_RERANKER: bool = os.getenv("ENABLE_RERANKER", "true").lower() == "true"
    ENABLE_CLASSIFIER: bool = os.getenv("ENABLE_CLASSIFIER", "true").lower() == "true"
    MAX_RERANK_CANDIDATES: int = int(os.getenv("MAX_RERANK_CANDIDATES", "5"))
    INFERENCE_TIMEOUT_SEC: float = float(os.getenv("INFERENCE_TIMEOUT_SEC", "1.0"))
    RERANKER_MODEL_ID: str = os.getenv("RERANKER_MODEL_ID", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    CLASSIFIER_MODEL_ID: str = os.getenv("CLASSIFIER_MODEL_ID", "typeform/distilbert-base-uncased-mnli")
    DEVICE: str = os.getenv("HF_AI_DEVICE", "cpu")
    MAX_SCORE_INFLUENCE: float = float(os.getenv("MAX_SCORE_INFLUENCE", "5.0"))


# Global Singleton Configuration Instance
hf_ai_config = HFAIConfig()
