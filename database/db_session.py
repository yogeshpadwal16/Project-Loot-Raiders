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
            cursor.execute("PRAGMA busy_timeout=30000")
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
    from knowledge_base.models import (
        Product, PriceHistory, ClickLog, SelectorMatrix, DealVote, 
        UserWalletCard, UserScore, ReferralLog, ChannelGrowthLog,
        MirroredMessage, SourceChannel, ProcessingLog, SystemHealth, RetryHistory,
        PendingNotification
    )
    Base.metadata.create_all(bind=engine)
    
    # Run database-agnostic migration checks using SQLAlchemy Inspector
    import logging
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(engine)
        existing_cols = [col["name"] for col in inspector.get_columns("products")]
        
        migrations = {
            "telegram_message_id": "INTEGER",
            "telegram_caption": "TEXT",
            "last_published_at": "REAL DEFAULT 0.0" if "sqlite" in engine.url.drivername else "DOUBLE PRECISION DEFAULT 0.0",
            "last_published_price": "INTEGER DEFAULT 0",
            "daily_post_count": "INTEGER DEFAULT 0",
            "daily_post_date": "TEXT DEFAULT ''" if "sqlite" in engine.url.drivername else "VARCHAR(10) DEFAULT ''"
        }
        
        with engine.begin() as connection:
            for col_name, col_type in migrations.items():
                if col_name not in existing_cols:
                    alter_sql = f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"
                    connection.execute(text(alter_sql))
                    logging.info(f"[Migration] Successfully added column '{col_name}' to products table.")
    except Exception as e:
        logging.warning(f"[Migration] Database products table migration failed: {e}")

