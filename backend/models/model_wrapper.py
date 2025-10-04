# model_wrapper.py
from typing import Sequence, List
import numpy as np
from sklearn.linear_model import SGDClassifier
import joblib
import os

class ModelWrapper:
    """
    Çok basit bir wrapper:
    - predict_proba(line) gibi tek-birim tahminler,
    - partial_fit ile insan etiketleri geldikçe güncelleme (online learning)
    Not: küçük demo veri için SGDClassifier uygun; productionda değiştirilir.
    """

    def __init__(self, classes=(0,1), model_path: str | None = None):
        self.classes = classes
        self.model_path = model_path
        # SGDClassifier ile online eğitim desteği var
        self.model = SGDClassifier(loss='log', max_iter=1000, tol=1e-3)
        # model'u ilk kez eğitmemişsek partial_fit çağrılana kadar hata verebileceği için None bırakıyoruz.
        self._initialized = False

        # Eğer model dosyası varsa yükle
        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)
            self._initialized = True

    def featurize(self, time: Sequence[float], flux: Sequence[float], index: int) -> List[float]:
        """
        Tek bir nokta için özellik üretir. Burada çok basit: flux değeri ve komşu farkları.
        - index: tıklanan örneğin index'i
        Dönen vektör: [flux[index], flux[index]-flux[index-1], flux[index+1]-flux[index], local_std]
        """
        arr = np.array(flux)
        n = len(arr)
        val = arr[index]
        prev = arr[index-1] if index-1 >= 0 else val
        nxt = arr[index+1] if index+1 < n else val
        local = arr[max(0,index-3):min(n,index+4)]
        local_std = float(np.std(local))
        return [float(val), float(val - prev), float(nxt - val), local_std]

    def predict_proba(self, time: Sequence[float], flux: Sequence[float], index: int) -> float:
        """1 sınıfı için olasılık döndürür (prob of transit)."""
        x = np.array(self.featurize(time, flux, index)).reshape(1, -1)
        if not self._initialized:
            # model eğitilmediğinde default belirsiz olasılık 0.5 döndür
            return 0.5
        p = self.model.predict_proba(x)[0]
        # p[1] transit olma olasılığı
        return float(p[1])

    def predict(self, time, flux, index, threshold=0.5) -> int:
        return 1 if self.predict_proba(time, flux, index) >= threshold else 0

    def partial_fit(self, time, flux, index, label: int):
        """
        İnsan etiketi geldiğinde küçük bir güncelleme uygula.
        Eğer model ilk defa eğitiliyorsa partial_fit ile classes parametresi gerekiyor.
        """
        x = np.array(self.featurize(time, flux, index)).reshape(1, -1)
        y = np.array([label])
        if not self._initialized:
            self.model.partial_fit(x, y, classes=self.classes)
            self._initialized = True
        else:
            self.model.partial_fit(x, y)
        # opsiyonel: modeli diske kaydet
        if self.model_path:
            joblib.dump(self.model, self.model_path)
