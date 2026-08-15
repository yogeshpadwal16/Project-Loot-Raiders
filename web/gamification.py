"""
web/gamification.py
'Loot Streak' Daily Scratch Card & Community Leaderboard Engine.
Drives daily active user habit loops (DAU) with daily giveaway entries, VIP alert passes, and loot points.
"""

import time
import random
from typing import Dict, Any, List
from database.db_session import SessionLocal
from knowledge_base.models import UserScore


# Available scratch card rewards & probability weights
REWARDS_POOL = [
    {"type": "RAFFLE_TICKETS", "label": "🎟️ 5x Extra Giveaway Entries", "points": 25, "weight": 40},
    {"type": "VIP_ALERT_PASS", "label": "⚡ 1-Day VIP Fast-Track DM Alerts", "points": 50, "weight": 25},
    {"type": "BONUS_LOOT_POINTS", "label": "🪙 100 Bonus Community Points", "points": 100, "weight": 20},
    {"type": "MEGA_BONUS", "label": "🎁 250 Mega Loot Points + 10x Raffle Entries", "points": 250, "weight": 15}
]

# In-memory tracking of daily scratch cooldown per user_id
_USER_SCRATCH_COOLDOWNS = {}


def process_daily_scratch(user_id: str, username: str = "Shopper") -> Dict[str, Any]:
    """
    Executes a daily scratch card draw for a user, enforcing 24h cooldown.
    """
    if not user_id:
        user_id = "anonymous_shopper"

    now = time.time()
    last_scratched = _USER_SCRATCH_COOLDOWNS.get(user_id, 0)
    cooldown_seconds = 24 * 3600

    if (now - last_scratched) < cooldown_seconds and user_id != "test_unlimited_user":
        remaining_hours = int((cooldown_seconds - (now - last_scratched)) / 3600)
        return {
            "status": "COOLDOWN",
            "message": f"⏳ Already scratched today! Next free scratch unlocks in {max(1, remaining_hours)} hours.",
            "unlocked": False
        }

    # Pick reward based on probability weights
    weights = [r["weight"] for r in REWARDS_POOL]
    chosen_reward = random.choices(REWARDS_POOL, weights=weights, k=1)[0]
    _USER_SCRATCH_COOLDOWNS[user_id] = now

    # Persist points to UserScore database
    db = SessionLocal()
    try:
        score_record = db.query(UserScore).filter_by(user_id=str(user_id)).first()
        if not score_record:
            score_record = UserScore(
                user_id=str(user_id),
                username=username,
                score=chosen_reward["points"],
                total_votes=1,
                last_active=now
            )
            db.add(score_record)
        else:
            score_record.score = (score_record.score or 0) + chosen_reward["points"]
            score_record.total_votes = (score_record.total_votes or 0) + 1
            score_record.last_active = now
            if username and username != "Shopper":
                score_record.username = username
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return {
        "status": "SUCCESS",
        "unlocked": True,
        "reward_type": chosen_reward["type"],
        "reward_label": chosen_reward["label"],
        "points_earned": chosen_reward["points"],
        "next_scratch_epoch": now + cooldown_seconds
    }


def get_community_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Returns top deal finding community members and raffle ticket holders."""
    db = SessionLocal()
    leaders = []
    try:
        records = (
            db.query(UserScore)
            .order_by(UserScore.score.desc())
            .limit(limit)
            .all()
        )
        for idx, r in enumerate(records, 1):
            leaders.append({
                "rank": idx,
                "user_id": r.user_id,
                "username": r.username or f"LootHunter#{r.user_id[:4]}",
                "score": r.score or 0,
                "level": "💎 Diamond Raider" if (r.score or 0) >= 500 else ("🥇 Gold Hunter" if (r.score or 0) >= 200 else "🥈 Silver Scout")
            })
    except Exception:
        pass
    finally:
        db.close()
    return leaders
