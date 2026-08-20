"""
web/storefront.py
Public Web Deal Storefront & Google SEO Engine.
Renders fast SSR deal catalog with Schema.org/Product structured data for organic search ranking.
Includes AI Truth-in-Pricing analysis, Buy vs Wait verdicts, and Loot Streak Gamification.
"""

import json
import time
from typing import List, Dict, Any, Optional
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from utils.price_truth import analyze_price_truth
from utils.buy_wait_advisor import get_buy_vs_wait_recommendation


def render_json_ld_schema(product: Product, latest_price: PriceHistory) -> str:
    """
    Generates Schema.org Product and Offer JSON-LD structured data for Google Rich Results.
    """
    price_val = latest_price.price if latest_price else 0
    mrp_val = latest_price.mrp if latest_price else price_val
    image_url = product.image_url if (product.image_url and product.image_url.startswith("http")) else "https://lootraiders.com/assets/banner.png"

    schema = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": product.title,
        "image": [image_url],
        "description": f"Grab {product.title} at lowest price ₹{price_val:,} with special discount and instant bank offers on {product.platform.capitalize()}.",
        "sku": product.id,
        "offers": {
            "@type": "Offer",
            "url": product.url or f"https://lootraiders.com/deal/{product.id}",
            "priceCurrency": "INR",
            "price": str(price_val),
            "priceValidUntil": "2026-12-31",
            "itemCondition": "https://schema.org/NewCondition",
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": product.platform.capitalize()
            }
        }
    }
    return f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'


def get_live_deals_feed(category: Optional[str] = None, search: Optional[str] = None, limit: int = 40) -> List[Dict[str, Any]]:
    """Queries live products and prices from database with search and category filters."""
    db = SessionLocal()
    deals = []
    try:
        query = db.query(Product)
        if search:
            query = query.filter(Product.title.like(f"%{search}%"))
        
        products = query.order_by(Product.last_updated.desc()).limit(limit).all()
        for p in products:
            lp = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).first()
            if not lp:
                continue

            price = lp.price
            mrp = lp.mrp or price
            disc = lp.discount or (((mrp - price) / mrp) * 100 if mrp > price else 0)

            # AI Price Truth & Buy/Wait verdict
            truth = analyze_price_truth(p.id, price, mrp)
            advice = get_buy_vs_wait_recommendation(p.id, price)

            deals.append({
                "id": p.id,
                "title": p.title,
                "price": price,
                "mrp": mrp,
                "discount": round(disc, 0),
                "platform": p.platform or "amazon",
                "image_url": p.image_url,
                "url": p.url,
                "deal_score": lp.deal_score or 80.0,
                "is_verified_low": bool(lp.is_verified_low),
                "truth_badge": truth.get("badge_text", ""),
                "verdict_badge": advice.get("verdict_badge", "🎯 BUY NOW"),
                "timestamp": lp.timestamp
            })
    except Exception:
        pass
    finally:
        db.close()
    return deals


def render_storefront_html(category: Optional[str] = None, search: Optional[str] = None) -> str:
    """
    Renders high-conversion, responsive HTML Web Storefront for Loot Raiders.
    """
    deals = get_live_deals_feed(category=category, search=search, limit=48)
    
    # Generate JSON-LD list items for Google Carousel Search
    json_ld_items = []
    for idx, d in enumerate(deals[:10], 1):
        json_ld_items.append({
            "@type": "ListItem",
            "position": idx,
            "item": {
                "@type": "Product",
                "name": d["title"],
                "image": d["image_url"] or "https://lootraiders.com/banner.png",
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": "INR",
                    "price": str(d["price"]),
                    "availability": "https://schema.org/InStock",
                    "url": d["url"]
                }
            }
        })
    
    catalog_schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": json_ld_items
    }
    catalog_json_ld = f'<script type="application/ld+json">\n{json.dumps(catalog_schema, indent=2)}\n</script>'

    deals_cards_html = ""
    for d in deals:
        badge_class = "badge-loot" if d["discount"] >= 50 else "badge-hot"
        badge_text = f"🔥 {d['discount']:.0f}% OFF" if d["discount"] > 0 else "⚡ DEAL"
        img_src = d["image_url"] if (d["image_url"] and d["image_url"].startswith("http")) else "https://via.placeholder.com/300x200?text=Product+Image"
        clean_title = d["title"][:75] + "..." if len(d["title"]) > 75 else d["title"]
        mrp_html = f"<span class='deal-mrp'>₹{d['mrp']:,}</span>" if d['mrp'] > d['price'] else ""

        truth_tag = f"<div class='deal-truth-tag'>{d['truth_badge']}</div>" if d.get("truth_badge") else ""
        verdict_tag = f"<div class='deal-verdict-tag'>{d['verdict_badge']}</div>" if d.get("verdict_badge") else ""

        deals_cards_html += f"""
        <div class="deal-card" id="deal-{d['id']}">
            <div class="deal-badge-container">
                <span class="badge {badge_class}">{badge_text}</span>
                <span class="platform-tag tag-{d['platform']}">{d['platform'].upper()}</span>
            </div>
            <div class="deal-img-wrapper">
                <img src="{img_src}" alt="{d['title']}" loading="lazy" class="deal-img" />
            </div>
            <div class="deal-content">
                <h3 class="deal-title">{clean_title}</h3>
                <div class="deal-pricing">
                    <span class="deal-price">₹{d['price']:,}</span>
                    {mrp_html}
                </div>
                {truth_tag}
                {verdict_tag}
                <div class="deal-actions">
                    <a href="{d['url']}" target="_blank" rel="nofollow noopener" class="btn-buy">
                        🛍️ Buy on {d['platform'].capitalize()}
                    </a>
                    <button class="btn-share" onclick="shareDeal('{d['title']}', '{d['url']}')" title="Share Deal">
                        🔗
                    </button>
                </div>
            </div>
        </div>
        """

    if not deals_cards_html:
        deals_cards_html = """
        <div class="empty-state">
            <h2>🔍 No deals currently match your search</h2>
            <p>We are scanning Amazon & Flipkart 24/7. Check back in a few seconds or explore all deals!</p>
            <a href="/deals" class="btn-primary">View All Live Deals</a>
        </div>
        """

    query_val = search or ''
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Loot Raiders - Live Deals, Price Drops & Loot Glitches in India</title>
    <meta name="description" content="Discover verified loot deals, price glitches, and massive discounts on Amazon & Flipkart in real-time. Join 100,000+ smart shoppers in India!">
    <meta name="keywords" content="loot deals, price drops, amazon discounts, flipkart offers, big billion days, great indian festival, shopping deals india">
    
    <!-- OpenGraph / Social Media -->
    <meta property="og:title" content="Project Loot Raiders - Real-Time Loot Deals & Price Drops">
    <meta property="og:description" content="Instant verified price error alerts and flash sales on Amazon & Flipkart.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://lootraiders.com/deals">
    
    <!-- Structured Data for SEO -->
    {catalog_json_ld}
    
    <style>
        :root {{
            --primary: #f97316;
            --primary-hover: #ea580c;
            --accent: #22c55e;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background-color: var(--bg-dark); color: var(--text-main); line-height: 1.5; }}
        
        /* Top Navigation */
        .navbar {{ background: #1e293b; border-bottom: 1px solid var(--border-color); padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }}
        .logo {{ font-size: 20px; font-weight: 800; color: var(--primary); text-decoration: none; display: flex; align-items: center; gap: 8px; }}
        .nav-links {{ display: flex; gap: 16px; align-items: center; }}
        .btn-tg {{ background: #229ED9; color: white; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px; display: inline-flex; align-items: center; gap: 6px; transition: opacity 0.2s; }}
        .btn-tg:hover {{ opacity: 0.9; }}
        
        /* Gamification Banner */
        .gamification-strip {{ background: linear-gradient(90deg, #ea580c, #f97316); color: white; padding: 12px 20px; text-align: center; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 14px; font-size: 14px; box-shadow: 0 4px 12px rgba(234, 88, 12, 0.3); }}
        .btn-scratch {{ background: #ffffff; color: #ea580c; border: none; padding: 6px 14px; border-radius: 20px; font-weight: 800; cursor: pointer; transition: transform 0.1s; }}
        .btn-scratch:hover {{ transform: scale(1.05); }}
        
        /* Hero Banner */
        .hero {{ text-align: center; padding: 30px 20px 15px; max-width: 900px; margin: 0 auto; }}
        .hero h1 {{ font-size: 32px; font-weight: 900; margin-bottom: 10px; color: #fff; }}
        .hero p {{ color: var(--text-muted); font-size: 16px; margin-bottom: 24px; }}
        
        /* Search & Filter Bar */
        .search-container {{ max-width: 600px; margin: 0 auto 24px; display: flex; gap: 10px; }}
        .search-input {{ flex: 1; padding: 12px 18px; border-radius: 8px; border: 1px solid var(--border-color); background: #1e293b; color: white; font-size: 15px; outline: none; }}
        .search-input:focus {{ border-color: var(--primary); }}
        .btn-search {{ background: var(--primary); color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; cursor: pointer; }}
        .btn-search:hover {{ background: var(--primary-hover); }}
        
        /* Deal Grid */
        .deals-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; padding: 0 20px 60px; }}
        .deal-card {{ background: var(--bg-card); border-radius: 12px; border: 1px solid var(--border-color); overflow: hidden; display: flex; flex-direction: column; transition: transform 0.2s, box-shadow 0.2s; }}
        .deal-card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 20px rgba(0,0,0,0.3); border-color: var(--primary); }}
        
        .deal-badge-container {{ padding: 10px; display: flex; justify-content: space-between; align-items: center; }}
        .badge {{ font-size: 11px; font-weight: 800; padding: 4px 8px; border-radius: 6px; }}
        .badge-loot {{ background: #dc2626; color: white; }}
        .badge-hot {{ background: var(--primary); color: white; }}
        .platform-tag {{ font-size: 10px; font-weight: 800; padding: 3px 6px; border-radius: 4px; background: #334155; color: #cbd5e1; }}
        .tag-amazon {{ background: #ea580c; color: white; }}
        .tag-flipkart {{ background: #2563eb; color: white; }}
        
        .deal-img-wrapper {{ height: 180px; display: flex; align-items: center; justify-content: center; background: white; padding: 10px; overflow: hidden; }}
        .deal-img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
        
        .deal-content {{ padding: 16px; display: flex; flex-direction: column; flex: 1; }}
        .deal-title {{ font-size: 14px; font-weight: 600; color: #f1f5f9; margin-bottom: 10px; height: 42px; overflow: hidden; line-height: 1.4; }}
        .deal-pricing {{ display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }}
        .deal-price {{ font-size: 20px; font-weight: 800; color: var(--accent); }}
        .deal-mrp {{ font-size: 13px; color: var(--text-muted); text-decoration: line-through; }}
        
        .deal-truth-tag {{ font-size: 11px; color: #38bdf8; font-weight: 600; margin-bottom: 4px; }}
        .deal-verdict-tag {{ font-size: 11px; color: #a7f3d0; font-weight: 700; margin-bottom: 12px; }}
        
        .deal-actions {{ display: flex; gap: 8px; margin-top: auto; }}
        .btn-buy {{ flex: 1; background: var(--primary); color: white; text-align: center; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: 700; font-size: 13px; transition: background 0.2s; }}
        .btn-buy:hover {{ background: var(--primary-hover); }}
        .btn-share {{ background: #334155; color: white; border: none; width: 38px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
        .btn-share:hover {{ background: #475569; }}
        
        /* Empty state */
        .empty-state {{ grid-column: 1 / -1; text-align: center; padding: 60px 20px; background: #1e293b; border-radius: 12px; }}
        .empty-state h2 {{ margin-bottom: 10px; }}
        .empty-state p {{ color: var(--text-muted); margin-bottom: 20px; }}
        .btn-primary {{ background: var(--primary); color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 700; }}
        
        /* Footer */
        footer {{ background: #0b1120; border-top: 1px solid var(--border-color); padding: 30px 20px; text-align: center; font-size: 13px; color: var(--text-muted); }}
        footer a {{ color: var(--primary); text-decoration: none; }}
    </style>
</head>
<body>

    <nav class="navbar">
        <a href="/deals" class="logo">🚀 Project Loot Raiders</a>
        <div class="nav-links">
            <a href="https://t.me/LootRaidersDeals" target="_blank" class="btn-tg">
                📢 Join Telegram Channel
            </a>
        </div>
    </nav>

    <div class="gamification-strip">
        <span>🎁 <b>Daily Loot Streak:</b> Claim your free daily reward!</span>
        <button class="btn-scratch" onclick="claimDailyReward()">✨ Scratch & Win</button>
    </div>

    <div class="hero">
        <h1>🔥 Best Loot Deals & Price Drops in India</h1>
        <p>Real-time algorithmically verified deals with AI Fake-Discount Detector & Buy-vs-Wait Advisor.</p>
        
        <form action="/deals" method="GET" class="search-container">
            <input type="text" name="q" placeholder="Search iPhone, AirPods, Shoes, Laptops..." value="{query_val}" class="search-input" />
            <button type="submit" class="btn-search">Search</button>
        </form>
    </div>

    <main class="deals-grid">
        {deals_cards_html}
    </main>

    <footer>
        <p>© 2026 Project Loot Raiders. All Rights Reserved. Curated with automated high-speed scanning infrastructure.</p>
        <p>Disclosure: As an affiliate, we may earn commissions from qualifying purchases made via our links.</p>
    </footer>

    <script>
        function shareDeal(title, url) {{
            const shareText = "🔥 Check out this deal: " + title + "\\n👉 " + url + "\\n\\nJoin @LootRaidersDeals on Telegram!";
            if (navigator.share) {{
                navigator.share({{
                    title: title,
                    text: shareText,
                    url: url
                }}).catch(function() {{}});
            }} else {{
                navigator.clipboard.writeText(shareText).then(function() {{
                    alert("Deal link copied to clipboard!");
                }});
            }}
        }}

        function claimDailyReward() {{
            const btn = document.querySelector('.btn-scratch');
            btn.innerText = 'Scratching...';
            fetch('/api/v1/gamification/scratch?user_id=web_user_' + Math.floor(Math.random() * 10000))
                .then(r => r.json())
                .then(data => {{
                    if (data.status === 'SUCCESS') {{
                        alert('🎉 YOU WON: ' + data.reward_label + ' (+' + data.points_earned + ' Points)!');
                        btn.innerText = '✅ Claimed!';
                        btn.disabled = true;
                    }} else {{
                        alert(data.message || 'Already scratched today!');
                        btn.innerText = '⏳ Tomorrow';
                    }}
                }})
                .catch(() => {{
                    alert('🎉 You unlocked 5x Free Raffle Entries for today!');
                    btn.innerText = '✅ Claimed!';
                }});
        }}
    </script>
</body>
</html>
"""
    return html
