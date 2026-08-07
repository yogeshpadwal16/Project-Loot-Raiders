# database/repository.py
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import time
from sqlalchemy.orm import Session
from knowledge_base.models import Product, PriceHistory

class DealRepository(ABC):
    @abstractmethod
    def get_product_by_id(self, db: Session, unique_id: str) -> Optional[Product]:
        """Queries product table for specific ID."""
        pass

    @abstractmethod
    def create_product(self, db: Session, unique_id: str, platform: str, title: str, img_url: str, final_url: str) -> Product:
        """Creates a new product record."""
        pass

    @abstractmethod
    def update_product(self, db: Session, unique_id: str, title: str, img_url: str, final_url: str) -> Product:
        """Updates product metadata."""
        pass

    @abstractmethod
    def add_price_history(self, db: Session, unique_id: str, price: int, mrp: int, discount: float, is_verified_low: bool, deal_score: float) -> PriceHistory:
        """Adds a price history record for a product."""
        pass

    @abstractmethod
    def get_price_history(self, db: Session, unique_id: str) -> List[PriceHistory]:
        """Gets all price history records for a product."""
        pass

class SQLAlchemyDealRepository(DealRepository):
    def get_product_by_id(self, db: Session, unique_id: str) -> Optional[Product]:
        return db.query(Product).filter_by(id=unique_id).first()

    def create_product(self, db: Session, unique_id: str, platform: str, title: str, img_url: str, final_url: str) -> Product:
        product = Product(
            id=unique_id,
            platform=platform,
            title=title,
            image_url=img_url,
            url=final_url
        )
        db.add(product)
        db.flush()
        return product

    def update_product(self, db: Session, unique_id: str, title: str, img_url: str, final_url: str) -> Product:
        product = self.get_product_by_id(db, unique_id)
        if product:
            product.title = title
            product.image_url = img_url
            product.url = final_url
        return product

    def add_price_history(self, db: Session, unique_id: str, price: int, mrp: int, discount: float, is_verified_low: bool, deal_score: float) -> PriceHistory:
        price_hist = PriceHistory(
            product_id=unique_id,
            price=price,
            mrp=mrp,
            discount=discount,
            is_verified_low=is_verified_low,
            deal_score=deal_score,
            timestamp=time.time()
        )
        db.add(price_hist)
        return price_hist

    def get_price_history(self, db: Session, unique_id: str) -> List[PriceHistory]:
        return db.query(PriceHistory).filter_by(product_id=unique_id).all()
