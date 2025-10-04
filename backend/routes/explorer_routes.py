# explorer_route.py
from typing import Dict, Any, Optional
from dataset_model import sample_random_lc_id, get_lightcurve
from model_wrapper import ModelWrapper
from user_model import InMemoryUserStore
from score_services import ScoreService


class ExplorerEngine:

    def __init__(self, model: ModelWrapper, store: InMemoryUserStore, dataset: Dict[int, Dict],
                 score_service: Optional[ScoreService] = None):
        self.model = model
        self.store = store
        self.dataset = dataset
        # If a ScoreService instance is not provided, create one.
        self.score_service = score_service or ScoreService(store, model, dataset)

    def get_lightcurve_for_frontend(self, lc_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Return a lightcurve dict suitable for sending to the frontend.
        """
        if lc_id is None:
            lc_id = sample_random_lc_id(self.dataset)
        lc = get_lightcurve(self.dataset, lc_id)
        return {
            "lc_id": lc["lc_id"],
            "time": list(lc["time"]),
            "flux": list(lc["flux"]),
            "data_length": len(lc["time"]),
        }

    def get_ai_hint(self, lc_id: int, click_index: int) -> Dict[str, Any]:

        lc = get_lightcurve(self.dataset, lc_id)
        # validate click index range
        if click_index < 0 or click_index >= len(lc["time"]):
            raise ValueError("click_index out of range")
        prob = self.model.predict_proba(lc["time"], lc["flux"], click_index)
        pred = 1 if prob >= 0.5 else 0
        return {"ai_probability": float(prob), "ai_prediction": int(pred)}

    def submit_click(self, user_id: str, lc_id: int, click_index: int) -> Dict[str, Any]:
        # ScoreService will validate lc_id and click_index and raise well-defined exceptions
        result = self.score_service.process_user_click(user_id, lc_id, click_index)
        # Explorer may want to augment result with a fresh AI probability for the same click (post-update),
        # but careful: after partial_fit the probability may change. If you want pre-update AI hint,
        # call get_ai_hint BEFORE submit_click in the route.
        return result

