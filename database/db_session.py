import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "loot_raiders.db")

# check_same_thread=False is required for sharing the SQLite connection across Selenium worker threads
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def init_db():
    # Import inside function to prevent circular imports
    from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix
    Base.metadata.create_all(bind=engine)
