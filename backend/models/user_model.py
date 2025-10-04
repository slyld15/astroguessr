# user_store.py
from typing import Dict, Any, List
import time
import heapq

class InMemoryUserStore:
    """
    Demo amaçlı basit in-memory kullanıcı deposu.
    user_data yapısı:
    {
      user_id: {
        "score": int,
        "streak": int,
        "badges": [str,...],
        "last_active": timestamp
      }
    }
    """

    def __init__(self):
        self.user_data: Dict[str, Dict] = {}

    def _ensure_user(self, user_id: str):
        if user_id not in self.user_data:
            self.user_data[user_id] = {"score": 0, "streak": 0, "badges": [], "last_active": time.time()}

    def get_user(self, user_id: str) -> Dict:
        self._ensure_user(user_id)
        return self.user_data[user_id]

    def update_user(self, user_id: str, **kwargs):
        self._ensure_user(user_id)
        for k, v in kwargs.items():
            self.user_data[user_id][k] = v
        self.user_data[user_id]["last_active"] = time.time()

    def increment_score(self, user_id: str, delta: int):
        self._ensure_user(user_id)
        self.user_data[user_id]["score"] = max(0, self.user_data[user_id]["score"] + delta)
        self.user_data[user_id]["last_active"] = time.time()

    def get_leaderboard(self, top_n: int = 10) -> List[Dict]:
        """
        Basit top-N leaderboard. Daha hızlı sorgular için prod-da DB sorgusu kullan.
        """
        items = [(v["score"], uid) for uid, v in self.user_data.items()]
        # en yüksekten sırala
        top = heapq.nlargest(top_n, items)
        return [{"user_id": uid, "score": score, "streak": self.user_data[uid]["streak"]} for score, uid in top]

    def award_badge(self, user_id: str, badge: str):
        self._ensure_user(user_id)
        if badge not in self.user_data[user_id]["badges"]:
            self.user_data[user_id]["badges"].append(badge)
