import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, event
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("loot_raiders.database")

Base = declarative_base()

class Deal(Base):
    __tablename__ = 'deals'
    
    id = Column(Integer, primary_key=True)
    original_message_id = Column(Integer, unique=True, nullable=False)
    mirrored_message_id = Column(Integer, nullable=True)
    source_channel = Column(String(100), nullable=False)
    target_channel = Column(String(100), nullable=True)
    title = Column(String(500), nullable=True)
    url = Column(String(1000), nullable=True)
    price = Column(Float, nullable=True)
    mrp = Column(Float, nullable=True)
    discount = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    is_expired = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Briefing(Base):
    __tablename__ = 'briefings'
    
    id = Column(Integer, primary_key=True)
    date = Column(String(10), unique=True, nullable=False) # YYYY-MM-DD
    english_text = Column(Text, nullable=False)
    marathi_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# SQLite database file path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot_raiders_new.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"timeout": 30} # Avoid database locked errors
)

# SQLite WAL mode configurations using SQLAlchemy event listener
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    except Exception as e:
        logger.error(f"Error setting SQLite WAL PRAGMAs: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database schema."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")

def get_db():
    """DB session generator helper."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
