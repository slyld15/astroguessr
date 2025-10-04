# game_logic.py
from typing import Dict, Any
from model_wrapper import ModelWrapper
from user_model import InMemoryUserStore
from dataset_model import get_lightcurve

# Levels chart
LEVELS = [
    ("Beginner", 0),
    ("Apprentice", 500),
    ("Master", 2500),
]

def compute_level(score: int) -> str:
    cur = LEVELS[0][0]
    for name, thresh in LEVELS:
        if score >= thresh:
            cur = name
    return cur

class GameEngine:

    def __init__(self, model: ModelWrapper, store: InMemoryUserStore, dataset: Dict[int, Dict]):
        self.model = model
        self.store = store
        self.dataset = dataset

    def check_label(self, lc_id: int, click_index: int) -> bool:
        """
        Gerçek label ile karşılaştırır.
        Eğer click_index out-of-range ise False döner.
        """
        lc = get_lightcurve(self.dataset, lc_id)
        if click_index < 0 or click_index >= len(lc["label"]):
            return False
        return bool(lc["label"][click_index])

    def process_guess(self, user_id: str, lc_id: int, click_index: int) -> Dict:
        # 1) guessing
        lc = get_lightcurve(self.dataset, lc_id)
        ai_prob = self.model.predict_proba(lc["time"], lc["flux"], click_index)
        ai_pred = 1 if ai_prob >= 0.5 else 0

        # 2) right/wrong control
        is_correct = self.check_label(lc_id, click_index)

        # 3) update user status
        user = self.store.get_user(user_id)
        if is_correct:
            user['streak'] += 1
            gained = 10 * user['streak']   # base_points=10, multiplier: streak
            self.store.increment_score(user_id, gained)
        else:
            user['streak'] = 0
            self.store.increment_score(user_id, -5)  # penalty 5 points
        # 4) level control
        new_user = self.store.get_user(user_id)
        new_level = compute_level(new_user['score'])
        # example badge: if streak is at least 7, earn badge
        if new_user['streak'] >= 7:
            self.store.award_badge(user_id, "Rare Nominee")

        # 5) Update ML model with human data
        # Label integer must be 0/1
        label = 1 if is_correct else 0
        try:
            self.model.partial_fit(lc["time"], lc["flux"], click_index, label)
        except Exception as e:
            print("Model update error:", e)

        result = {
            "is_correct": bool(is_correct),
            "ai_prediction": float(ai_prob),
            "new_score": int(new_user['score']),
            "streak": int(new_user['streak']),
            "level": new_level
        }
        return result


