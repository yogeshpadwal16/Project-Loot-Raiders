import os
import json
import logging
import urllib.parse
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Database & Scorer imports
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix
from config.settings import load_settings, save_settings
from deal_engine.scorer import calculate_deal_score
from database.operations import verify_historical_low

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
LOG_FILE = os.path.join(BASE_DIR, "execution.log")

# We will import these dynamically to prevent circular imports during start
# core.engine will import web.server, so web.server should lazy-import from core.engine inside methods
_state_ref = None

def get_scraper_state():
    global _state_ref
    if _state_ref is None:
        from core.engine import scraper_state
        _state_ref = scraper_state
    return _state_ref

class ScraperAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log REST requests to execution.log
        logging.getLogger().info(f"REST API: {format % args}")
        
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
        
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def is_authorized(self):
        # Exclude static files, redirects, status, deals, and login from auth checks
        clean_path = self.path.split('?')[0]
        public_endpoints = [
            '/', 
            '/api/login', 
            '/api/status', 
            '/api/deals', 
            '/api/config',
            '/api/analytics',
            '/api/scraper/health',
            '/api/lootmap/events',
            '/api/rewards/scratch'
        ]
        if clean_path in public_endpoints or clean_path.startswith('/api/deals/history') or clean_path.startswith('/api/redirect') or not clean_path.startswith('/api/'):
            return True
            
        # Get token from header or fallback to query parameter
        token = None
        auth_header = self.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split(' ')
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
                
        if not token:
            parsed_url = urllib.parse.urlparse(self.path)
            queries = urllib.parse.parse_qs(parsed_url.query)
            if 'token' in queries and queries['token']:
                token = queries['token'][0].strip()
                
        if not token:
            return False
            
        env_token = os.environ.get("DASHBOARD_SESSION_TOKEN", "admin_session_key_default").strip()
        return token == env_token

    def do_GET(self):
        if not self.is_authorized():
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized access. Invalid or missing token."}).encode('utf-8'))
            return

        # Serve static dashboard files dynamically
        clean_path = self.path.split('?')[0]
        if clean_path == '/':
            clean_path = '/index.html'
            
        path_mappings = {
            '/main.js': '/index.js',
            '/style.css': '/index.css'
        }
        mapped_path = path_mappings.get(clean_path, clean_path)
        local_filename = mapped_path.lstrip('/')
        filepath = os.path.join(DASHBOARD_DIR, local_filename)
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            ext = os.path.splitext(filepath)[1].lower()
            mime_types = {
                '.html': 'text/html',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.json': 'application/json',
                '.svg': 'image/svg+xml',
                '.ico': 'image/x-icon'
            }
            mime = mime_types.get(ext, 'application/octet-stream')
            self._serve_static(filepath, mime)
            return
        
        # API Endpoints
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            state = get_scraper_state()
            status = {
                "is_running": state["is_running"],
                "scans_completed": state["scans_completed"],
                "last_scan_time": state["last_scan_time"],
                "uptime": time.time() - state["uptime_start"],
                "crawler_health": state.get("crawler_health", {})
            }
            self.wfile.write(json.dumps(status).encode('utf-8'))
            
        elif self.path == '/api/selectors':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            db = SessionLocal()
            try:
                matrices = db.query(SelectorMatrix).all()
                data = {}
                for m in matrices:
                    data[m.platform] = {
                        "url": m.url,
                        "card_selector": m.card_selector,
                        "title_selector": m.title_selector,
                        "link_selector": m.link_selector,
                        "image_selector": m.image_selector
                    }
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"{}")
            finally:
                db.close()
                
        elif self.path == '/api/analytics':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                # 1. Total Clicks
                total_clicks = db.query(ClickLog).count()
                
                # 2. Clicks by Platform
                from sqlalchemy import func
                platform_clicks = {}
                # Group by platform (via join Product)
                clicks_by_prod = db.query(ClickLog.product_id, func.count(ClickLog.id)).group_by(ClickLog.product_id).all()
                for prod_id, count in clicks_by_prod:
                    prod = db.query(Product).filter_by(id=prod_id).first()
                    plat = prod.platform if prod else "unknown"
                    platform_clicks[plat] = platform_clicks.get(plat, 0) + count
                    
                # 3. Top Clicked Deals
                top_deals = []
                sorted_clicks = sorted(clicks_by_prod, key=lambda x: x[1], reverse=True)[:5]
                for prod_id, count in sorted_clicks:
                    prod = db.query(Product).filter_by(id=prod_id).first()
                    top_deals.append({
                        "id": prod_id,
                        "title": prod.title[:60] + "..." if prod and prod.title else "Unknown",
                        "clicks": count,
                        "platform": prod.platform if prod else "unknown"
                    })
                    
                # 4. Community Gamification Stats
                from knowledge_base.models import UserScore, ReferralLog
                total_users = db.query(UserScore).count()
                total_points = db.query(func.sum(UserScore.points)).scalar() or 0
                total_referrals = db.query(ReferralLog).count()
                total_votes = db.query(func.sum(UserScore.voted_count)).scalar() or 0
                
                # 5. Conversion rate approximation
                total_deals_posted = db.query(Product).count()
                avg_ctr = (total_clicks / max(1, total_deals_posted)) * 100
                
                # 6. EPC & Financial Estimation (Feature 1, 3, 10 on Admin side)
                estimated_payout_per_click = 4.50  # Average Rs 4.5 commission per click in India
                total_estimated_earnings = total_clicks * estimated_payout_per_click
                reconciled_payouts = int(total_estimated_earnings * 0.94)  # 94% tracking reconciliation rate
                
                # 7. Geo-Targeted User Density (Feature 9 on Admin side)
                geo_targeted_density = {
                    "Maharashtra (Mumbai/Pune)": int(total_clicks * 0.38),
                    "Delhi NCR": int(total_clicks * 0.26),
                    "Karnataka (Bangalore)": int(total_clicks * 0.18),
                    "Tamil Nadu (Chennai)": int(total_clicks * 0.10),
                    "Others": int(total_clicks * 0.08)
                }

                analytics = {
                    "total_clicks": total_clicks,
                    "platform_clicks": platform_clicks,
                    "top_deals": top_deals,
                    "community": {
                        "total_users": total_users,
                        "total_points": int(total_points),
                        "total_referrals": total_referrals,
                        "total_votes": int(total_votes)
                    },
                    "conversion": {
                        "total_deals_posted": total_deals_posted,
                        "average_clicks_per_deal": round(avg_ctr, 1)
                    },
                    "epc_metrics": {
                        "average_epc_rupees": estimated_payout_per_click,
                        "total_estimated_earnings": total_estimated_earnings,
                        "reconciled_earnings": reconciled_payouts,
                        "reconciliation_rate_percent": 94.0
                    },
                    "geo_density": geo_targeted_density
                }
                self.wfile.write(json.dumps(analytics).encode('utf-8'))
            except Exception as e:
                logging.error(f"Analytics query error: {e}")
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            finally:
                db.close()
                
        elif self.path == '/api/deals':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                products = db.query(Product).all()
                deals = []
                from utils.affiliate import generate_auto_cart_url
                settings = load_settings()
                
                for p in products:
                    latest_price = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).first()
                    if not latest_price:
                        continue
                    
                    click_count = db.query(ClickLog).filter_by(product_id=p.id).count()
                    
                    # Premium calculations (Feature 7, 8, 26)
                    auto_cart_url = generate_auto_cart_url(p.url, p.platform, settings)
                    effective_price = int(latest_price.price * 0.95)
                    offline_price = int(min(latest_price.mrp, latest_price.price * 1.25))
                    
                    # AI Forecasting prediction (Feature 1)
                    recommendation = "BUY" if (latest_price.is_verified_low or latest_price.deal_score >= 70) else "WAIT"
                    probability = 92 if latest_price.is_verified_low else 65
                    
                    # AI Glitch Severity / Cancel Risk (Admin Feature 5)
                    from deal_engine.scorer import calculate_cancellation_risk
                    cancel_risk = calculate_cancellation_risk(p.platform, latest_price.price, latest_price.mrp, latest_price.discount, p.title)
                    
                    deals.append({
                        "id": p.id,
                        "platform": p.platform,
                        "title": p.title,
                        "price": latest_price.price,
                        "mrp": latest_price.mrp,
                        "discount": latest_price.discount,
                        "image_url": p.image_url,
                        "url": p.url,
                        "is_verified_low": latest_price.is_verified_low,
                        "deal_score": latest_price.deal_score,
                        "timestamp": latest_price.timestamp,
                        "clicks": click_count,
                        "effective_price": effective_price,
                        "auto_cart_url": auto_cart_url,
                        "offline_price": offline_price,
                        "cancel_risk": cancel_risk,
                        "forecasting": {
                            "recommendation": recommendation,
                            "probability": probability
                        }
                    })
                deals.sort(key=lambda x: x["timestamp"], reverse=True)
                self.wfile.write(json.dumps(deals).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"[]")
            finally:
                db.close()
                
        elif self.path == '/api/raffle/stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            settings = load_settings()
            raffle_entries = settings.get("raffle_entries", [])
            
            data = {
                "prize": "₹500 Amazon Gift Voucher",
                "next_draw_time": "10:00 PM Daily (IST)",
                "total_entries": len(raffle_entries),
                "is_active": True
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return

        elif self.path.startswith('/api/rewards/scratch'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            user_id = params.get('user_id', [None])[0]
            
            if not user_id:
                self.wfile.write(json.dumps({"error": "Missing user_id parameter"}).encode('utf-8'))
                return
                
            import random
            from knowledge_base.models import UserScore
            
            points_won = random.randint(10, 100)
            db = SessionLocal()
            try:
                user_score = db.query(UserScore).filter_by(user_id=str(user_id)).first()
                if not user_score:
                    user_score = UserScore(
                        user_id=str(user_id),
                        username=f"User_{user_id[:5]}",
                        points=0,
                        voted_count=0,
                        referrals_count=0
                    )
                    db.add(user_score)
                
                user_score.points += points_won
                db.commit()
                
                res_data = {
                    "status": "success",
                    "points_won": points_won,
                    "new_total": user_score.points,
                    "message": f"🎉 Congratulations! You scratched and won {points_won} Loot Points!"
                }
                self.wfile.write(json.dumps(res_data).encode('utf-8'))
            except Exception as e:
                logging.error(f"Scratch card reward error: {e}")
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            finally:
                db.close()
            return
                
        elif self.path == '/api/scraper/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Simulated telemetry metrics matching Feature 1 (scraper health)
            data = {
                "active_threads": 4,
                "latency_seconds": 2.15,
                "proxy_pool_size": 25,
                "request_success_rate": 98.4,
                "active_scrapers": [
                    {"name": "Amazon Lightning Worker", "status": "idle", "latency": "1.8s", "checks_count": 1420},
                    {"name": "Amazon Sitewide Scraper", "status": "scraping", "latency": "2.4s", "checks_count": 890},
                    {"name": "Flipkart Clearance Scanner", "status": "idle", "latency": "2.0s", "checks_count": 1150},
                    {"name": "JioMart Grocery Monitor", "status": "scraping", "latency": "2.2s", "checks_count": 640}
                ]
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return

        elif self.path == '/api/lootmap/events':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Live map coordinate simulator for major cities in India (Feature 1 on User website)
            import random
            cities = [
                {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777},
                {"name": "Delhi NCR", "lat": 28.7041, "lng": 77.1025},
                {"name": "Bengaluru", "lat": 12.9716, "lng": 77.5946},
                {"name": "Hyderabad", "lat": 17.3850, "lng": 78.4867},
                {"name": "Pune", "lat": 18.5204, "lng": 73.8567},
                {"name": "Chennai", "lat": 13.0827, "lng": 80.2707},
                {"name": "Kolkata", "lat": 22.5726, "lng": 88.3639},
                {"name": "Ahmedabad", "lat": 23.0225, "lng": 72.5714}
            ]
            
            events = []
            random.seed(int(time.time() / 100)) # stable for 100s windows
            actions = ["clicked deal link", "set price alert", "won scratch raffle", "verified price drop"]
            for _ in range(5):
                city = random.choice(cities)
                action = random.choice(actions)
                events.append({
                    "city": city["name"],
                    "lat": city["lat"] + random.uniform(-0.15, 0.15),
                    "lng": city["lng"] + random.uniform(-0.15, 0.15),
                    "action": action,
                    "timestamp": time.time() - random.randint(10, 300)
                })
            self.wfile.write(json.dumps(events).encode('utf-8'))
            return

        elif self.path.startswith('/api/extension/match'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Chrome Extension ASIN/PID detail matcher (Feature 3 on User website)
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            prod_id = params.get('id', [None])[0]
            
            if not prod_id:
                self.wfile.write(json.dumps({"error": "Missing product id parameter"}).encode('utf-8'))
                return
                
            db = SessionLocal()
            try:
                prod = db.query(Product).filter_by(id=prod_id).first()
                if prod:
                    latest = db.query(PriceHistory).filter_by(product_id=prod.id).order_by(PriceHistory.timestamp.desc()).first()
                    history = db.query(PriceHistory).filter_by(product_id=prod.id).order_by(PriceHistory.timestamp.asc()).all()
                    
                    wallet_recommendations = []
                    user_id = params.get('user_id', [None])[0]
                    if user_id:
                        from deal_engine.bot_listener import get_matching_wallet_offers
                        rec = get_matching_wallet_offers(user_id, ["SBI Card 10% Off", "HDFC Card discount"])
                        wallet_recommendations.append(rec)
                        
                    res_data = {
                        "found": True,
                        "title": prod.title,
                        "platform": prod.platform,
                        "current_price": latest.price if latest else 0,
                        "mrp": latest.mrp if latest else 0,
                        "deal_score": latest.deal_score if latest else 0,
                        "is_verified_low": latest.is_verified_low if latest else False,
                        "history": [{"price": h.price, "timestamp": h.timestamp} for h in history],
                        "wallet_suggestions": wallet_recommendations
                    }
                    self.wfile.write(json.dumps(res_data).encode('utf-8'))
                else:
                    self.wfile.write(json.dumps({"found": False, "message": "Product not yet in database"}).encode('utf-8'))
            except Exception as e:
                logging.error(f"Extension match query error: {e}")
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            finally:
                db.close()
            return

        elif self.path.startswith('/api/deals/history'):
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            deal_id = params.get('id', [None])[0]
            
            if not deal_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing product ID"}).encode('utf-8'))
                return
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                history = db.query(PriceHistory).filter_by(product_id=deal_id).order_by(PriceHistory.timestamp.asc()).all()
                data = [{
                    "price": h.price,
                    "mrp": h.mrp,
                    "discount": h.discount,
                    "timestamp": h.timestamp,
                    "is_verified_low": h.is_verified_low,
                    "deal_score": h.deal_score
                } for h in history]
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"[]")
            finally:
                db.close()
        elif self.path.startswith('/go/'):
            # Cloaker URL redirect (Feature 13)
            parts = self.path.split('/')
            if len(parts) >= 3:
                deal_id = parts[2].split('?')[0].strip()
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=deal_id).first()
                    if product:
                        target_url = product.url
                        
                        # Increment clicks and log click
                        client_ip = self.client_address[0]
                        user_agent = self.headers.get('User-Agent', 'Unknown')
                        click = ClickLog(
                            product_id=deal_id,
                            title=product.title,
                            ip=client_ip,
                            user='CloakedUser',
                            user_agent=user_agent,
                            timestamp=time.time()
                        )
                        db.add(click)
                        db.commit()
                        
                        # Recalculate score and sync JSON
                        latest_price = db.query(PriceHistory).filter_by(product_id=deal_id).order_by(PriceHistory.timestamp.desc()).first()
                        if latest_price:
                            new_score = calculate_deal_score(
                                platform=product.platform,
                                price=latest_price.price,
                                mrp=latest_price.mrp,
                                discount=latest_price.discount,
                                is_verified_low=latest_price.is_verified_low,
                                is_lightning=False,
                                product_id=deal_id,
                                title=product.title
                            )
                            latest_price.deal_score = new_score
                            db.commit()
                            
                            from core.engine import sync_database_to_json
                            sync_database_to_json()
                            
                            # Trigger background message update
                            import threading
                            from deal_engine.notifier import update_telegram_message
                            threading.Thread(target=update_telegram_message, args=(deal_id,), daemon=True).start()
                            
                        self.send_response(302)
                        self.send_header('Location', target_url)
                        self.end_headers()
                        return
                except Exception as e:
                    logging.error(f"Cloaker redirection error: {e}")
                finally:
                    db.close()
                    
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Deal Not Found")
            return
            
        elif self.path.startswith('/api/redirect'):
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            deal_id = params.get('id', [None])[0]
            target_url = params.get('url', [None])[0]
            user = params.get('user', ['Anonymous'])[0]
            
            title = "Unknown Product"
            if deal_id:
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=deal_id).first()
                    if product:
                        title = product.title
                        
                    client_ip = self.client_address[0]
                    user_agent = self.headers.get('User-Agent', 'Unknown')
                    
                    # Log click directly to database
                    click = ClickLog(
                        product_id=deal_id,
                        title=title,
                        ip=client_ip,
                        user=user,
                        user_agent=user_agent,
                        timestamp=time.time()
                    )
                    db.add(click)
                    db.commit()
                    
                    # Recalculate and update the deal_score of this product to reflect the click popularity boost
                    latest_price = db.query(PriceHistory).filter_by(product_id=deal_id).order_by(PriceHistory.timestamp.desc()).first()
                    if latest_price:
                        new_score = calculate_deal_score(
                            platform=product.platform if product else "amazon",
                            price=latest_price.price,
                            mrp=latest_price.mrp,
                            discount=latest_price.discount,
                            is_verified_low=latest_price.is_verified_low,
                            is_lightning=("lightning" in product.platform.lower() if product else False),
                            product_id=deal_id,
                            title=product.title if product else None
                        )
                        latest_price.deal_score = new_score
                        db.commit()
                        
                        # Sync static JSONs to keep dashboard UI elements in sync
                        from core.engine import sync_database_to_json
                        sync_database_to_json()
                        
                        # Trigger Telegram message caption update with hotness gauge in background thread
                        import threading
                        from deal_engine.notifier import update_telegram_message
                        threading.Thread(target=update_telegram_message, args=(deal_id,), daemon=True).start()
                except Exception as e:
                    db.rollback()
                    logging.error(f"Redirect logging error: {e}")
                finally:
                    db.close()
                    
            if target_url:
                self.send_response(302)
                self.send_header('Location', target_url)
                self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing target URL")
                
        elif self.path == '/api/clicks':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                clicks = db.query(ClickLog).order_by(ClickLog.timestamp.desc()).limit(100).all()
                total_clicks = db.query(ClickLog).count()
                whatsapp_clicks = db.query(ClickLog).filter(ClickLog.user == 'WhatsAppShare').count()
                whatsapp_ratio = round((whatsapp_clicks / total_clicks * 100), 1) if total_clicks > 0 else 0.0
                
                clicks_data = [{
                    "deal_id": c.product_id,
                    "title": c.title,
                    "ip": c.ip,
                    "user": c.user,
                    "user_agent": c.user_agent,
                    "timestamp": c.timestamp
                } for c in clicks]
                
                response_data = {
                    "clicks": clicks_data,
                    "stats": {
                        "total_clicks": total_clicks,
                        "whatsapp_clicks": whatsapp_clicks,
                        "whatsapp_ratio": whatsapp_ratio
                    }
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({"clicks": [], "stats": {"total_clicks": 0, "whatsapp_clicks": 0, "whatsapp_ratio": 0.0}}).encode('utf-8'))
            finally:
                db.close()
                
        elif self.path == '/api/settings':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            settings = load_settings()
            self.wfile.write(json.dumps(settings).encode('utf-8'))
            
        elif self.path == '/api/logs/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            # Send initial logs
            initial_lines = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                        initial_lines = f.readlines()[-60:]
                except:
                    pass
            for line in initial_lines:
                try:
                    self.wfile.write(f"data: {json.dumps(line.strip())}\n\n".encode('utf-8'))
                except:
                    return
            try:
                self.wfile.flush()
            except:
                return
            
            # Tail log file
            try:
                with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.5)
                            continue
                        self.wfile.write(f"data: {json.dumps(line.strip())}\n\n".encode('utf-8'))
                        self.wfile.flush()
            except Exception as e:
                pass
                
        elif self.path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            lines = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-100:]
                except Exception as e:
                    lines = [f"Failed to read logs: {e}"]
            self.wfile.write(json.dumps(lines).encode('utf-8'))
        elif self.path == '/api/config':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            settings = load_settings()
            public_config = {
                "telegram_chat_id": settings.get("telegram_chat_id", "@LootRaidersDeals"),
                "telegram_invite_link": settings.get("telegram_invite_link", "https://t.me/LootRaidersDeals")
            }
            self.wfile.write(json.dumps(public_config).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self.is_authorized():
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized access. Invalid or missing token."}).encode('utf-8'))
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        parsed_path = urllib.parse.urlparse(self.path).path
        logging.getLogger().info(f"POST Request: path='{self.path}' parsed='{parsed_path}'")
        
        state = get_scraper_state()
        
        if parsed_path == '/api/selectors':
            try:
                data = json.loads(post_data.decode('utf-8'))
                db = SessionLocal()
                try:
                    for plat_key, config in data.items():
                        matrix = db.query(SelectorMatrix).filter_by(platform=plat_key).first()
                        if not matrix:
                            matrix = SelectorMatrix(platform=plat_key)
                            db.add(matrix)
                        matrix.url = config.get("url", "")
                        matrix.card_selector = config.get("card_selector", "")
                        matrix.title_selector = config.get("title_selector", "")
                        matrix.link_selector = config.get("link_selector", "")
                        matrix.image_selector = config.get("image_selector", "")
                    db.commit()
                except Exception as db_err:
                    db.rollback()
                    raise db_err
                finally:
                    db.close()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/scan':
            state["scan_trigger"] = True
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Manual scan triggered"}).encode('utf-8'))
            
        elif parsed_path == '/api/toggle':
            state["is_running"] = not state["is_running"]
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "is_running": state["is_running"]}).encode('utf-8'))
            
        elif parsed_path == '/api/settings':
            try:
                data = json.loads(post_data.decode('utf-8'))
                save_settings(data)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/login':
            try:
                data = json.loads(post_data.decode('utf-8'))
                username = str(data.get('username', '')).strip().lower()
                password = str(data.get('password', '')).strip()
                logging.getLogger().info(f"Auth attempt: username='{username}'")
                
                # Retrieve credentials from environment variables
                env_user = os.environ.get("DASHBOARD_USERNAME", "yogeshpadwal16").strip().lower()
                env_pass = os.environ.get("DASHBOARD_PASSWORD", "YOUR_DASHBOARD_PASSWORD").strip()
                env_token = os.environ.get("DASHBOARD_SESSION_TOKEN", "admin_session_key_default").strip()
                
                if username == env_user and password == env_pass:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {
                        "status": "success",
                        "token": env_token,
                        "name": "Yogesh Padwal"
                    }
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                else:
                    self.send_response(401)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "failed", "message": "Invalid username or password"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                
        elif parsed_path == '/api/deals/delete':
            try:
                data = json.loads(post_data.decode('utf-8'))
                deal_id = data.get('id')
                if not deal_id:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing deal ID"}).encode('utf-8'))
                    return
                
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=deal_id).first()
                    if product:
                        db.delete(product)
                        db.commit()
                        deleted_count = 1
                    else:
                        deleted_count = 0
                except Exception as db_err:
                    db.rollback()
                    raise db_err
                finally:
                    db.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "deleted": deleted_count}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                
        elif parsed_path == '/api/processes/cleanup':
            try:
                from utils.zombie import run_zombie_cleanup
                run_zombie_cleanup()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "message": "Zombie cleanup execution successful",
                    "killed": []  # Simplified killed list for modular logging
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/manual/crawl':
            try:
                from core.engine import scrape_product_details
                data = json.loads(post_data.decode('utf-8'))
                url = data.get('url', '').strip()
                if not url:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing URL"}).encode('utf-8'))
                    return
                
                result = scrape_product_details(url)
                
                # Convert affiliate link
                settings = load_settings()
                platform = result["platform"]
                aff_url = url
                unique_id = str(int(time.time()))
                
                if platform == "amazon":
                    from utils.parser import extract_amazon_asin
                    asin = extract_amazon_asin(url)
                    if asin:
                        aff_url = f"https://www.amazon.in/dp/{asin}?tag={settings.get('amazon_tag', 'lootraiders-21')}"
                        unique_id = asin
                elif platform == "flipkart":
                    from utils.parser import extract_flipkart_pid
                    pid = extract_flipkart_pid(url)
                    if pid:
                        aff_url = f"https://www.flipkart.com/product/p/itm?pid={pid}&affid={settings.get('flipkart_affid', 'YOUR_FLIPKART_AFFILIATE_ID')}"
                        unique_id = pid
                        
                result["affiliate_url"] = aff_url
                result["unique_id"] = unique_id
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/manual/post':
            try:
                data = json.loads(post_data.decode('utf-8'))
                platform = data.get('platform', 'generic')
                title = data.get('title', '').strip()
                price = int(data.get('price', 0))
                mrp = int(data.get('mrp', 0))
                image_url = data.get('image_url', '').strip()
                affiliate_url = data.get('affiliate_url', '').strip()
                unique_id = data.get('unique_id', str(int(time.time())))
                
                settings = load_settings()
                bot_token = settings.get("telegram_bot_token")
                chat_id = settings.get("telegram_chat_id")
                
                if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
                    raise Exception("Telegram Bot not configured in settings!")
                
                discount = 0.0
                if mrp > 0 and price > 0:
                    discount = ((mrp - price) / mrp) * 100.0
                    
                # Save product in DB to make sure sparkline history is generated/updated
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=unique_id).first()
                    if not product:
                        product = Product(
                            id=unique_id,
                            platform=platform,
                            title=title,
                            image_url=image_url,
                            url=affiliate_url
                        )
                        db.add(product)
                        db.commit()
                        
                    # Save a price history point
                    ph = PriceHistory(
                        product_id=unique_id,
                        price=price,
                        mrp=mrp,
                        discount=discount,
                        is_verified_low=True,
                        deal_score=95.0,
                        timestamp=time.time()
                    )
                    db.add(ph)
                    db.commit()
                except Exception as db_err:
                    db.rollback()
                    logging.error(f"Error logging manual deal to DB: {db_err}")
                finally:
                    db.close()
                
                from deal_engine.notifier import send_telegram_alert
                posted = send_telegram_alert(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    platform=platform,
                    title=title,
                    price=price,
                    mrp=mrp,
                    discount=discount,
                    img_url=image_url,
                    final_url=affiliate_url,
                    is_verified_low=True,
                    deal_score=95.0,
                    unique_id=unique_id
                )
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "posted": posted}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_static(self, filepath, mime):
        if os.path.exists(filepath) and os.path.isfile(filepath):
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

def start_api_server(port=5555):
    # Ensure dashboard folder exists
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    
    server = ThreadingHTTPServer(('0.0.0.0', port), ScraperAPIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logging.info(f"Dashboard REST API engine running at http://0.0.0.0:{port}/")
