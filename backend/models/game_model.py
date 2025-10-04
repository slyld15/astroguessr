# game_model.py
"""
game_model.py
Provides user-account storage for AstroGuessr:
"""
from typing import Dict, Any, List, Optional
import sqlite3
import threading
import time
import os
import contextlib
import json

# Helper: default user dict
def _default_user_dict(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "score": 0,
        "streak": 0,
        "total_correct": 0,
        "last_active": time.time(),
        "badges": []
    }

# In-memory store (fallback)
class InMemoryUserStore:
    """
    Simple in-memory store with the same API as SQLiteUserStore.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.user_data: Dict[str, Dict[str, Any]] = {}

    def create_user(self, user_id: str, **fields):
        with self._lock:
            if user_id in self.user_data:
                return
            u = _default_user_dict(user_id)
            u.update(fields)
            self.user_data[user_id] = u

    def get_user(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            if user_id not in self.user_data:
                self.create_user(user_id)
            # Return a copy to avoid accidental mutation by callers
            return dict(self.user_data[user_id])

    def update_user(self, user_id: str, **fields):
        with self._lock:
            if user_id not in self.user_data:
                self.create_user(user_id)
            self.user_data[user_id].update(fields)
            self.user_data[user_id]["last_active"] = time.time()

    def increment_score(self, user_id: str, delta: int):
        with self._lock:
            if user_id not in self.user_data:
                self.create_user(user_id)
            # Ensure integer arithmetic and non-negative score
            self.user_data[user_id]["score"] = max(0, int(self.user_data[user_id].get("score", 0)) + int(delta))
            self.user_data[user_id]["last_active"] = time.time()

    def award_badge(self, user_id: str, badge: str):
        with self._lock:
            if user_id not in self.user_data:
                self.create_user(user_id)
            badges = self.user_data[user_id].setdefault("badges", [])
            if badge not in badges:
                badges.append(badge)
            self.user_data[user_id]["last_active"] = time.time()

    def get_leaderboard(self, top_n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            items = sorted(self.user_data.values(), key=lambda u: u.get("score", 0), reverse=True)
            return [dict(user_id=u["user_id"], score=u["score"], streak=u["streak"]) for u in items[:top_n]]

    def delete_user(self, user_id: str):
        with self._lock:
            if user_id in self.user_data:
                del self.user_data[user_id]

    def list_users(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self.user_data.values())
            if limit is not None:
                items = items[:limit]
            return [dict(u) for u in items]

# SQLite-backed store
class SQLiteUserStore:
    """
    SQLite-backed user store. Stores:
    - users table: user_id (PK), score, streak, total_correct, last_active
    - badges table: user_id, badge_name, awarded_at
    """

    def __init__(self, db_path: str = "astroguesser_users.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        # Ensure directory exists for file-based DB
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.exists(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception:
                pass
        # Initialize DB / schema
        self._ensure_schema()

    @contextlib.contextmanager
    def _get_conn(self):
        # Use check_same_thread=False to allow usage from different threads (we still lock)
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()

    def _ensure_schema(self):
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                # users table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    score INTEGER NOT NULL DEFAULT 0,
                    streak INTEGER NOT NULL DEFAULT 0,
                    total_correct INTEGER NOT NULL DEFAULT 0,
                    last_active REAL NOT NULL DEFAULT 0
                )
                """)
                # badges table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS badges (
                    user_id TEXT NOT NULL,
                    badge_name TEXT NOT NULL,
                    awarded_at REAL NOT NULL,
                    PRIMARY KEY (user_id, badge_name)
                )
                """)
                # optional: indexes for performance
                cur.execute("CREATE INDEX IF NOT EXISTS idx_users_score ON users(score DESC)")
                conn.commit()

    # CRUD + helpers
    def create_user(self, user_id: str, **fields):
        with self._lock:
            now = time.time()
            score = int(fields.get("score", 0))
            streak = int(fields.get("streak", 0))
            total_correct = int(fields.get("total_correct", 0))
            last_active = float(fields.get("last_active", now))
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                INSERT OR IGNORE INTO users(user_id, score, streak, total_correct, last_active)
                VALUES (?, ?, ?, ?, ?)
                """, (user_id, score, streak, total_correct, last_active))
                conn.commit()

    def _row_to_user_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        if row is None:
            return {}
        user_id = row["user_id"]
        badges = self._get_badges(user_id)
        return {
            "user_id": user_id,
            "score": int(row["score"]),
            "streak": int(row["streak"]),
            "total_correct": int(row["total_correct"]),
            "last_active": float(row["last_active"]),
            "badges": badges
        }

    def get_user(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                if row is None:
                    # create default
                    self.create_user(user_id)
                    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                    row = cur.fetchone()
                return self._row_to_user_dict(row)

    def update_user(self, user_id: str, **fields):
        """
        Update provided fields on user. Supported: score, streak, total_correct, last_active.
        Non-present fields are left unchanged.
        """
        allowed = {"score", "streak", "total_correct", "last_active"}
        to_set = {k: v for k, v in fields.items() if k in allowed}
        if not to_set:
            # still touch last_active
            to_set["last_active"] = time.time()
        else:
            to_set["last_active"] = time.time()
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                # build SQL dynamically and safely
                cols = ", ".join([f"{k} = ?" for k in to_set.keys()])
                vals = list(to_set.values())
                vals.append(user_id)
                cur.execute(f"UPDATE users SET {cols} WHERE user_id = ?", vals)
                if cur.rowcount == 0:
                    # if not existing, create
                    self.create_user(user_id, **to_set)

    def increment_score(self, user_id: str, delta: int):
        """
        Increase (or decrease) user's score by delta; score never goes below 0.
        """
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                # Ensure user exists
                cur.execute("INSERT OR IGNORE INTO users(user_id, score, streak, total_correct, last_active) VALUES (?, ?, ?, ?, ?)",
                            (user_id, 0, 0, 0, time.time()))
                # update score
                cur.execute("SELECT score FROM users WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                current = int(row["score"]) if row else 0
                new = max(0, current + int(delta))
                cur.execute("UPDATE users SET score = ?, last_active = ? WHERE user_id = ?", (new, time.time(), user_id))

    def award_badge(self, user_id: str, badge_name: str):
        """
        Insert badge if not present. Uses primary key constraint to avoid duplicates.
        """
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("INSERT OR IGNORE INTO badges(user_id, badge_name, awarded_at) VALUES (?, ?, ?)",
                            (user_id, badge_name, time.time()))

    def _get_badges(self, user_id: str) -> List[str]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT badge_name FROM badges WHERE user_id = ?", (user_id,))
            rows = cur.fetchall()
            return [r["badge_name"] for r in rows] if rows else []

    def get_leaderboard(self, top_n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id, score, streak FROM users ORDER BY score DESC LIMIT ?", (top_n,))
                rows = cur.fetchall()
                return [{"user_id": r["user_id"], "score": int(r["score"]), "streak": int(r["streak"])} for r in rows]

    def delete_user(self, user_id: str):
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM badges WHERE user_id = ?", (user_id,))
                cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    def list_users(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.cursor()
                if limit is None:
                    cur.execute("SELECT * FROM users")
                else:
                    cur.execute("SELECT * FROM users LIMIT ?", (limit,))
                rows = cur.fetchall()
                return [self._row_to_user_dict(r) for r in rows]
