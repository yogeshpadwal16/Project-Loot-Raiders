import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loot_raiders.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")):
    # Convert postgres:// to postgresql:// for SQLAlchemy 1.4+
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600
    )
else:
    # Default to SQLite with WAL mode
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception as e:
            import logging
            logging.warning(f"Failed to set SQLite PRAGMAs: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from contextlib import contextmanager

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import inside function to prevent circular imports
    from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix, DealVote, UserWalletCard, UserScore, ReferralLog, ChannelGrowthLog
    Base.metadata.create_all(bind=engine)
    
    # Run migration queries to add new columns to products table if they do not exist
    import sqlite3
    import logging
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Add telegram_message_id to products
        try:
            cursor.execute("ALTER TABLE products ADD COLUMN telegram_message_id INTEGER")
        except sqlite3.OperationalError:
            pass # column already exists
            
        # Add telegram_caption to products
        try:
            cursor.execute("ALTER TABLE products ADD COLUMN telegram_caption TEXT")
        except sqlite3.OperationalError:
            pass # column already exists
            
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"Database products table migration failed: {e}")
