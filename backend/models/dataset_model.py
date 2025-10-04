# data_loader.py
from typing import List, Dict, Tuple
import csv
import os

# Basit veri temsili: tek bir light curve için dict
# {
#   "lc_id": int,
#   "time": [float,...],
#   "flux": [float,...],
#   "label": [0/1,...]  # aynı uzunlukta, 1: transit
# }

def load_csv_dataset(path: str) -> Dict[int, Dict]:
    """
    CSV beklenen formatı: LC_ID, TIME, FLUX, LABEL
    Aynı LC_ID'ye ait satırlar birleştirilir.
    Dönen yapı: { lc_id: { "lc_id": lc_id, "time": [...], "flux": [...], "label":[...] } }
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Veri bulunamadı: {path}")
    dataset = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lc = int(row['LC_ID'])
            t = float(row['TIME'])
            flux = float(row['FLUX'])
            label = int(row.get('LABEL', 0))
            if lc not in dataset:
                dataset[lc] = {"lc_id": lc, "time": [], "flux": [], "label": []}
            dataset[lc]["time"].append(t)
            dataset[lc]["flux"].append(flux)
            dataset[lc]["label"].append(label)
    return dataset

def get_lightcurve(dataset: Dict[int, Dict], lc_id: int) -> Dict:
    """
    lc_id'ye göre ışık eğrisini döndürür veya KeyError fırlatır.
    Frontend için JSON-friendly dict döndür.
    """
    if lc_id not in dataset:
        raise KeyError(f"lc_id {lc_id} yok")
    return dataset[lc_id]

def sample_random_lc_id(dataset: Dict[int, Dict]) -> int:
    """Basit: dataset'ten rastgele bir lc_id döndürür (oyun akışı için)."""
    import random
    return random.choice(list(dataset.keys()))
