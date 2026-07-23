import time
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database.db_session import Base
import datetime

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(String, primary_key=True, index=True) # ASIN or Flipkart PID
    platform = Column(String, index=True)
    title = Column(String)
    image_url = Column(String)
    url = Column(String)
    telegram_message_id = Column(Integer, nullable=True)
    telegram_caption = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    prices = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")

class PriceHistory(Base):
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, ForeignKey('products.id'), index=True)
    price = Column(Integer)
    mrp = Column(Integer)
    discount = Column(Float)
    is_verified_low = Column(Boolean, default=False)
    deal_score = Column(Float, default=0.0)
    timestamp = Column(Float, default=time.time)
    
    product = relationship("Product", back_populates="prices")

class ClickLog(Base):
    __tablename__ = 'click_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, index=True)
    title = Column(String)
    ip = Column(String)
    user = Column(String, default='Anonymous')
    user_agent = Column(String)
    timestamp = Column(Float, default=time.time)

class SelectorMatrix(Base):
    __tablename__ = 'selector_matrix'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String, unique=True, index=True)
    url = Column(String)
    card_selector = Column(String)
    title_selector = Column(String)
    link_selector = Column(String)
    image_selector = Column(String)

class AlertSubscription(Base):
    __tablename__ = 'alert_subscriptions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_chat_id = Column(String, index=True)
    product_id = Column(String, index=True)
    platform = Column(String)
    target_price = Column(Integer)
    timestamp = Column(Float, default=time.time)

class DealVote(Base):
    __tablename__ = 'deal_votes'
    
    product_id = Column(String, primary_key=True, index=True)
    vote_type = Column(String, primary_key=True) # 'verify' or 'expire'
    user_id = Column(String, primary_key=True)
    timestamp = Column(Float, default=time.time)

class UserWalletCard(Base):
    __tablename__ = 'user_wallet_cards'
    
    user_id = Column(String, primary_key=True, index=True)
    card_name = Column(String, primary_key=True) # e.g. 'hdfc', 'sbi', 'icici', 'axis', 'onecard'
    timestamp = Column(Float, default=time.time)

class UserScore(Base):
    __tablename__ = 'user_scores'
    
    user_id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=True)
    points = Column(Integer, default=0)
    voted_count = Column(Integer, default=0)
    referrals_count = Column(Integer, default=0)
    timestamp = Column(Float, default=time.time)

class ReferralLog(Base):
    __tablename__ = 'referral_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(String, index=True)
    referred_id = Column(String, unique=True, index=True)
    timestamp = Column(Float, default=time.time)

class ChannelGrowthLog(Base):
    __tablename__ = 'channel_growth_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscribers = Column(Integer)
    timestamp = Column(Float, default=time.time)


class MirroredMessage(Base):
    __tablename__ = 'mirrored_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String, index=True)
    channel_id = Column(String)
    channel_name = Column(String)
    message_id = Column(Integer)
    timestamp = Column(Float, default=time.time)
    raw_text = Column(String)
    extracted_urls = Column(String) # Stored as serialized JSON
    status = Column(String, default='queued') # 'queued', 'processed', 'failed', 'duplicate'
    error_reason = Column(String, nullable=True)


class SourceChannel(Base):
    __tablename__ = 'source_channels'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username_or_invite = Column(String, unique=True, index=True)
    chat_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    added_at = Column(Float, default=time.time)


class ProcessingLog(Base):
    __tablename__ = 'processing_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String, index=True)
    stage = Column(String) # 'listener', 'queue', 'normalization', 'deduplication', 'publisher'
    status = Column(String) # 'success', 'failure', 'retry'
    details = Column(String)
    timestamp = Column(Float, default=time.time)


class SystemHealth(Base):
    __tablename__ = 'system_health'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String, index=True) # 'active_sessions', 'queue_size', 'cpu_usage', 'memory_usage'
    metric_value = Column(Float)
    timestamp = Column(Float, default=time.time)


class RetryHistory(Base):
    __tablename__ = 'retry_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String, index=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(String)
    next_retry_at = Column(Float)
    timestamp = Column(Float, default=time.time)


