import os
import time
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot_raiders.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"timeout": 15, "check_same_thread": False}
)

# Enable SQLite WAL (Write-Ahead Logging) and Foreign Keys
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True) # ASIN or PID
    platform = Column(String, nullable=False)
    title = Column(String, nullable=False)
    image_url = Column(String)
    url = Column(String, nullable=False)
    telegram_message_id = Column(Integer)
    created_at = Column(Float, default=time.time)

    prices = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    price = Column(Integer, nullable=False)
    mrp = Column(Integer, nullable=False)
    discount = Column(Float, default=0.0)
    is_verified_low = Column(Boolean, default=False)
    deal_score = Column(Float, default=50.0)
    timestamp = Column(Float, default=time.time)

    product = relationship("Product", back_populates="prices")


class WishlistItem(Base):
    __tablename__ = "user_wishlists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    keyword = Column(String, index=True, nullable=False)
    target_price = Column(Integer, nullable=False)
    created_at = Column(Float, default=time.time)


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_chat_id = Column(Integer, index=True, nullable=False)
    product_id = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False)
    target_price = Column(Integer, nullable=False)
    timestamp = Column(Float, default=time.time)


def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
