from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory

tma_router = APIRouter(prefix="/api/tma", tags=["Telegram Mini App"])

# Dependency to get db session for FastAPI
def get_tma_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@tma_router.get("/deals")
def get_active_tma_deals(
    category: str | None = None,
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_tma_db),
):
    """Returns clean JSON list of active deals for rendering inside Telegram Mini App UI."""
    try:
        # Subquery to fetch the latest price history entry ID for each product
        latest_ph_ids = db.query(func.max(PriceHistory.id)).group_by(PriceHistory.product_id)
        
        # Build query loaded with products
        query = db.query(PriceHistory).options(joinedload(PriceHistory.product)).filter(PriceHistory.id.in_(latest_ph_ids))
        
        # Apply category filter dynamically via SQL ILIKE match on product title
        if category:
            query = query.join(Product).filter(Product.title.ilike(f"%{category}%"))
            
        # Get latest deals ordered by price history timestamp desc
        price_histories = query.order_by(PriceHistory.timestamp.desc()).limit(limit).all()
        
        deals = []
        for ph in price_histories:
            p = ph.product
            if not p:
                continue
                
            deals.append({
                "id": p.id,
                "title": p.title,
                "platform": p.platform.capitalize() if p.platform else "Unknown",
                "deal_price": ph.price,
                "mrp": ph.mrp,
                "discount_percent": int(ph.discount) if ph.discount else 0,
                "image_url": p.image_url,
                "buy_url": p.url,
            })
            
        return {"status": "success", "count": len(deals), "deals": deals}
    except Exception as e:
        return {"status": "error", "message": str(e)}
