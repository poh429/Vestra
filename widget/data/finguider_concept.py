import json
import os
import requests
import time
from typing import Dict, List, Optional, Any

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
_CONCEPT_LIST_CACHE = os.path.join(_CACHE_DIR, "finguider_concepts.json")
_CONCEPT_STOCKS_CACHE = os.path.join(_CACHE_DIR, "finguider_concept_stocks_{}.json")

_CONCEPT_LIST_TTL = 24 * 3600   # 24 hours
_CONCEPT_STOCKS_TTL = 6 * 3600  # 6 hours

def _ensure_cache_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)

def _load_cache(path: str, ttl: int) -> Optional[dict]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        fetched_at = cached.get("_fetched_at", 0)
        if time.time() - fetched_at > ttl:
            return None
        return cached
    except Exception:
        return None

def _save_cache(path: str, data: dict):
    _ensure_cache_dir()
    data["_fetched_at"] = time.time()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[FinGuider] cache write error: {e}")

def fetch_concept_list(force: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch US concept categories from FinGuider.
    Returns: [{"id": "C0054", "name": "AI 資料中心", "ret_1m": 0.03}, ...]
    """
    if not force:
        cached = _load_cache(_CONCEPT_LIST_CACHE, _CONCEPT_LIST_TTL)
        if cached and "concepts" in cached:
            return cached["concepts"]

    try:
        resp = requests.post('https://finguider.cc/Api/us_stock_list_concept_preview/', timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        concepts = []
        for item in data:
            if not isinstance(item, dict):
                continue
            lid = item.get("list_id")
            name = item.get("list_name")
            if not lid or not name:
                continue
            
            concepts.append({
                "id": lid,
                "name": name,
                "ret_1m": item.get("acc_ret_1m")
            })
            
        if concepts:
            _save_cache(_CONCEPT_LIST_CACHE, {"concepts": concepts})
            return concepts
    except Exception as e:
        print(f"[FinGuider] Error fetching concept list: {e}")
        
    # Try expired cache as fallback
    try:
        if os.path.exists(_CONCEPT_LIST_CACHE):
            with open(_CONCEPT_LIST_CACHE, "r", encoding="utf-8") as f:
                return json.load(f).get("concepts", [])
    except Exception:
        pass
        
    return []

def fetch_concept_stocks(concept_id: str, force: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch constituent stocks for a US concept from FinGuider.
    Returns: [{"code": "NVDA", "name": "NVDA", "ret_1m": 0.05, "industry": "Semiconductor"}, ...]
    """
    cache_path = _CONCEPT_STOCKS_CACHE.format(concept_id)
    
    if not force:
        cached = _load_cache(cache_path, _CONCEPT_STOCKS_TTL)
        if cached and "stocks" in cached:
            return cached["stocks"]

    try:
        resp = requests.post(
            'https://finguider.cc/Api/us_stock_list_concept/', 
            json={"list_id": concept_id},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        stocks = []
        for item in data:
            sym = item.get("symbol")
            if not sym:
                continue
            stocks.append({
                "code": sym,
                "name": sym, # FinGuider doesn't return names consistently in this endpoint, use symbol
                "ret_1m": item.get("acc_ret_1m"),
                "industry": item.get("industry")
            })
            
        if stocks:
            _save_cache(cache_path, {"stocks": stocks})
            return stocks
    except Exception as e:
        print(f"[FinGuider] Error fetching concept stocks for {concept_id}: {e}")
        
    try:
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f).get("stocks", [])
    except Exception:
        pass
        
    return []

if __name__ == "__main__":
    cl = fetch_concept_list(force=True)
    print(f"Total FinGuider concepts: {len(cl)}")
    if cl:
        test_id = cl[0]['id']
        stocks = fetch_concept_stocks(test_id, force=True)
        print(f"Stocks in {cl[0]['name']}: {len(stocks)}")
        for s in stocks[:5]:
            ret = s.get('ret_1m') or 0
            print(f"  {s['code']}: {ret*100:+.2f}%")
