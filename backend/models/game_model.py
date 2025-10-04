# game_logic.py
from typing import Dict, Any
from model_wrapper import ModelWrapper
from user_store import InMemoryUserStore
from data_loader import get_lightcurve

# Seviye eşiği tablosu (istediğin gibi genişlet)
LEVELS = [
    ("Çırak Kaşif", 0),
    ("Sertifikalı Avcı", 500),
    ("Lonca Üstadı", 2500),
]

def compute_level(score: int) -> str:
    """
    Basit: en yüksek eşik geçildiğinde o seviye verilir.
    """
    cur = LEVELS[0][0]
    for name, thresh in LEVELS:
        if score >= thresh:
            cur = name
    return cur

class GameEngine:
    """
    Oyun mantığını yöneten sınıf.
    - model: ModelWrapper örneği
    - store: InMemoryUserStore veya DB adaptörü
    - dataset: data_loader.load_csv_dataset tarafından sağlanan dict
    """

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
        """
        Kullanıcı bir yer tıkladığında çağrılacak ana fonksiyon.
        - is_correct: doğru/taklit
        - ai_prediction: modelin transit olasılığı (0..1)
        - new_score, streak, level: güncel kullanıcı durumu
        Adım adım:
          1) label kontrolü
          2) model tahmini al
          3) kullanıcıya puan ver/ceza uygula
          4) modeli partial_fit ile güncelle (human-in-the-loop)
        """
        # 1) tahmin/prob
        lc = get_lightcurve(self.dataset, lc_id)
        ai_prob = self.model.predict_proba(lc["time"], lc["flux"], click_index)
        ai_pred = 1 if ai_prob >= 0.5 else 0

        # 2) doğru/yanlış kontrolü
        is_correct = self.check_label(lc_id, click_index)

        # 3) kullanıcı durumunu güncelle
        user = self.store.get_user(user_id)
        if is_correct:
            user['streak'] += 1
            gained = 10 * user['streak']   # base_points=10, çarpan: streak
            self.store.increment_score(user_id, gained)
        else:
            user['streak'] = 0
            self.store.increment_score(user_id, -5)  # penalty 5 puan
        # 4) seviye kontrolü
        new_user = self.store.get_user(user_id)
        new_level = compute_level(new_user['score'])
        # badge örneği: streak 7+ ise "Nadir Aday" badge
        if new_user['streak'] >= 7:
            self.store.award_badge(user_id, "Nadir Aday")

        # 5) ML modelini insan verisiyle güncelle
        # Label integer 0/1 olmalı
        label = 1 if is_correct else 0
        try:
            self.model.partial_fit(lc["time"], lc["flux"], click_index, label)
        except Exception as e:
            # model güncellemesi başarısız olsa bile oyunun akışını bozma
            # logger yerine print (basit demo)
            print("Model güncellemesi hatası:", e)

        result = {
            "is_correct": bool(is_correct),
            "ai_prediction": float(ai_prob),
            "new_score": int(new_user['score']),
            "streak": int(new_user['streak']),
            "level": new_level
        }
        return result
