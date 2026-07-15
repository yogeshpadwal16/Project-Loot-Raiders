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
