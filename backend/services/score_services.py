# score_services.py
from typing import Dict, Any
from data_loader import get_lightcurve
from user_store import InMemoryUserStore
from model_wrapper import ModelWrapper

# Levels
LEVELS = [
    ("Novice Seeker", 0),
    ("Certified Hunter", 500),
    ("Guild Master", 2500),
]

# Badge rules declared here; keys are badge names and values are rule descriptors.
BADGE_RULES = {
    "Rare Candidate": {"streak_min": 7},
    "Consistent": {"total_hits_min": 50}, 
}


def compute_level(score: int) -> str:
    """Return the highest level whose threshold <= score."""
    cur = LEVELS[0][0]
    for name, thresh in LEVELS:
        if score >= thresh:
            cur = name
    return cur


class ScoreService:

    def __init__(self, store: InMemoryUserStore, model: ModelWrapper, dataset: Dict[int, Dict],
                 base_points: int = 10, penalty: int = 5):
        self.store = store
        self.model = model
        self.dataset = dataset
        self.base_points = base_points
        self.penalty = penalty

        # Optional per-user statistics (e.g. total_correct_hits) could be stored in store
        # or tracked here. We'll store cumulative correct hits in store under "total_correct".
        # Ensure backward compatibility with stores that don't have this field.
    
    def _ensure_user_fields(self, user_id: str):
        """Make sure store user entry has fields we rely on."""
        u = self.store.get_user(user_id)
        if "total_correct" not in u:
            self.store.update_user(user_id, total_correct=0)

    def _award_badges(self, user_id: str):

        user = self.store.get_user(user_id)
        streak = user.get("streak", 0)
        total_correct = user.get("total_correct", 0)

        # Rare Candidate
        rc = BADGE_RULES.get("Rare Candidate", {})
        rc_min = rc.get("streak_min", None)
        if rc_min is not None and streak >= rc_min:
            self.store.award_badge(user_id, "Rare Candidate")

        # Consistent
        cons = BADGE_RULES.get("Consistent", {})
        cons_min = cons.get("total_hits_min", None)
        if cons_min is not None and total_correct >= cons_min:
            self.store.award_badge(user_id, "Consistent")

    def process_user_click(self, user_id: str, lc_id: int, click_index: int) -> Dict[str, Any]:

        # 1) load lightcurve (this will raise if lc_id invalid)
        lc = get_lightcurve(self.dataset, lc_id)

        # check click_index in range
        if click_index < 0 or click_index >= len(lc["label"]):
            raise ValueError(f"click_index {click_index} out of range for lc_id {lc_id}")

        # Ensure user has auxiliary fields
        self._ensure_user_fields(user_id)

        # 2) correctness
        is_correct = bool(lc["label"][click_index])

        # 3) update streak and score
        user = self.store.get_user(user_id)
        if is_correct:
            user['streak'] += 1
            gained = self.base_points * user['streak']
            self.store.increment_score(user_id, gained)
            # track total_correct
            new_total = user.get("total_correct", 0) + 1
            self.store.update_user(user_id, total_correct=new_total)
        else:
            user['streak'] = 0
            self.store.increment_score(user_id, -self.penalty)

        # 4) compute new level and award badges
        updated_user = self.store.get_user(user_id)
        new_level = compute_level(updated_user['score'])
        self._award_badges(user_id)

        # 5) update ML model with the labeled example (human-in-the-loop)
        # label = 1 if correct else 0
        label = 1 if is_correct else 0
        try:
            self.model.partial_fit(lc["time"], lc["flux"], click_index, label)
        except Exception as e:
            # Keep user flow intact even on model failure
            # In production, log this exception properly
            print("Model partial_fit failed:", e)

        # 6) prepare result
        final_user = self.store.get_user(user_id)
        result = {
            "is_correct": bool(is_correct),
            "new_score": int(final_user['score']),
            "streak": int(final_user['streak']),
            "level": new_level,
            "badges": list(final_user.get("badges", [])),
            "total_correct": int(final_user.get("total_correct", 0)),
        }
        return result
