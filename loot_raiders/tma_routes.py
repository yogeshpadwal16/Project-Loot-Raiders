from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import SessionLocal, Product, PriceHistory, WishlistItem

router = APIRouter(prefix="/api/tma", tags=["Telegram Mini App"])


class WishlistCreate(BaseModel):
    user_id: int
    keyword: str
    target_price: int


class WishlistDelete(BaseModel):
    user_id: int
    keyword: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/deals")
def get_deals(limit: int = 20, db=Depends(get_db)):
    """Fetch recent deals for Mini App display list."""
    results = (
        db.query(Product)
        .order_by(Product.created_at.desc())
        .limit(limit)
        .all()
    )

    deals = []
    for prod in results:
        # Retrieve latest price history
        latest = (
            db.query(PriceHistory)
            .filter_by(product_id=prod.id)
            .order_by(PriceHistory.timestamp.desc())
            .first()
        )
        if latest:
            deals.append({
                "product_id": prod.id,
                "platform": prod.platform,
                "title": prod.title,
                "image_url": prod.image_url,
                "url": prod.url,
                "price": latest.price,
                "mrp": latest.mrp,
                "discount": latest.discount,
                "is_verified_low": latest.is_verified_low,
                "deal_score": latest.deal_score
            })
    return deals


@router.post("/wishlist")
def create_wishlist_alert(payload: WishlistCreate, db=Depends(get_db)):
    """Add a new keyword alert for the TMA user."""
    from wishlist_bot import add_keyword_alert
    resp = add_keyword_alert(payload.user_id, payload.keyword, payload.target_price)
    if "❌" in resp:
        raise HTTPException(status_code=400, detail=resp)
    return {"message": resp}


@router.get("/wishlist/{user_id}")
def get_user_wishlist(user_id: int, db=Depends(get_db)):
    """Retrieve all keyword alerts set by a user."""
    alerts = db.query(WishlistItem).filter_by(user_id=user_id).all()
    return [
        {
            "id": a.id,
            "keyword": a.keyword,
            "target_price": a.target_price,
            "created_at": a.created_at
        }
        for a in alerts
    ]


@router.delete("/wishlist")
def delete_wishlist_alert(payload: WishlistDelete, db=Depends(get_db)):
    """Remove a keyword alert."""
    from wishlist_bot import remove_keyword_alert
    resp = remove_keyword_alert(payload.user_id, payload.keyword)
    if "❌" in resp:
        raise HTTPException(status_code=404, detail=resp)
    return {"message": resp}
