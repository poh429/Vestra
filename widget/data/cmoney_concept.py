# --- cmoney_concept.py — CMoney 概念股資料抓取 ---
"""
Fetches concept stock categories and their constituent stocks from CMoney.
Features:
- Parse concept list from https://www.cmoney.tw/forum/concept
- Parse stock constituents from each concept detail page
- Batch resolve Chinese names via CMoney API
- In-memory + disk cache with configurable TTL
- Fallback to industry_logic.json if CMoney is unreachable
"""
import json
import os
import re
import ssl
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple

# SSL context — some Windows installs reject CMoney's cert chain
_SSL_CTX = ssl.create_default_context()
try:
    _SSL_CTX.load_default_certs()
except Exception:
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Constants ─────────────────────────────────────────────────────────────────
_CONCEPT_LIST_URL = "https://www.cmoney.tw/forum/concept"
_CONCEPT_DETAIL_URL = "https://www.cmoney.tw/forum/concept/{concept_id}"
_STOCK_INFO_API = "https://www.cmoney.tw/api/web-business/webbusiness-service/api/Stock/AdditionalInformation"

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
_CONCEPT_LIST_CACHE = os.path.join(_CACHE_DIR, "cmoney_concepts.json")
_CONCEPT_STOCKS_CACHE = os.path.join(_CACHE_DIR, "cmoney_concept_stocks_{}.json")

_CONCEPT_LIST_TTL = 24 * 3600   # 24 hours
_CONCEPT_STOCKS_TTL = 6 * 3600  # 6 hours

# Hot concepts to pin at top of UI
HOT_CONCEPTS = [
    "AI人工智慧", "CoWoS", "HBM", "GB200", "GB300", "散熱模組",
    "電動車", "5G", "PCB", "光通訊", "ASIC", "記憶體",
    "AI PC", "ChatGPT", "次世代半導體", "FOPLP扇出型封裝",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_cache_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch URL content with error handling."""
    try:
        import requests, urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[CMoney] fetch error {url}: {e}")
        return None


def _post_json(url: str, data, timeout: int = 10) -> Optional[dict]:
    """POST JSON data and return parsed response."""
    try:
        import requests, urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = requests.post(url, json=data, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[CMoney] POST error {url}: {e}")
        return None


def _load_cache(path: str, ttl: int) -> Optional[dict]:
    """Load cached JSON if file exists and is within TTL."""
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        fetched_at = cached.get("_fetched_at", 0)
        if time.time() - fetched_at > ttl:
            return None  # expired
        return cached
    except Exception:
        return None


def _save_cache(path: str, data: dict):
    """Save data to cache with timestamp."""
    _ensure_cache_dir()
    data["_fetched_at"] = time.time()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CMoney] cache write error: {e}")


# ── Core API ──────────────────────────────────────────────────────────────────

def fetch_concept_list(force: bool = False) -> List[Dict[str, str]]:
    """
    Fetch all concept categories from CMoney.
    
    Returns:
        List of dicts: [{"id": "C50909", "name": "CoWoS"}, ...]
    """
    # Check cache
    if not force:
        cached = _load_cache(_CONCEPT_LIST_CACHE, _CONCEPT_LIST_TTL)
        if cached and "concepts" in cached:
            return cached["concepts"]

    html = _fetch_url(_CONCEPT_LIST_URL)
    if not html:
        # Try cache even if expired
        try:
            if os.path.exists(_CONCEPT_LIST_CACHE):
                with open(_CONCEPT_LIST_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f).get("concepts", [])
        except Exception:
            pass
        return _fallback_concept_list()

    # Parse concept links: /forum/concept/C50909
    pattern = r'/forum/concept/(C\d+)'
    # Also capture names from link text
    # Pattern: [概念名](url) or just the href with adjacent text
    link_pattern = r'href="[^"]*?/forum/concept/(C\d+)"[^>]*>([^<]+)<'
    matches = re.findall(link_pattern, html)
    
    seen = set()
    concepts = []
    for cid, name in matches:
        name = name.strip()
        if cid not in seen and name and not name.startswith("http"):
            seen.add(cid)
            concepts.append({"id": cid, "name": name})

    if not concepts:
        # Fallback: simpler regex
        simple_matches = re.findall(
            r'\[([^\]]+)\]\(https://www\.cmoney\.tw/forum/concept/(C\d+)\)',
            html
        )
        for name, cid in simple_matches:
            name = name.strip()
            if cid not in seen and name:
                seen.add(cid)
                concepts.append({"id": cid, "name": name})

    if concepts:
        _save_cache(_CONCEPT_LIST_CACHE, {"concepts": concepts})
        print(f"[CMoney] Fetched {len(concepts)} concept categories")
    else:
        print("[CMoney] Warning: parsed 0 concepts, using fallback")
        return _fallback_concept_list()

    return concepts


def fetch_concept_stocks(concept_id: str, force: bool = False) -> List[Dict[str, str]]:
    """
    Fetch constituent stocks for a given concept.
    
    Args:
        concept_id: CMoney concept ID (e.g. "C50909")
        
    Returns:
        List of dicts: [{"code": "2330", "name": "台積電"}, ...]
    """
    cache_path = _CONCEPT_STOCKS_CACHE.format(concept_id)
    
    # Check cache
    if not force:
        cached = _load_cache(cache_path, _CONCEPT_STOCKS_TTL)
        if cached and "stocks" in cached:
            return cached["stocks"]

    url = _CONCEPT_DETAIL_URL.format(concept_id=concept_id)
    html = _fetch_url(url)
    if not html:
        # Try expired cache
        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("stocks", [])
        except Exception:
            pass
        return []

    # ── Strategy 1: Parse Nuxt SSR state for stockList ──
    # window.__NUXT__ contains data[0].stockList with all stocks
    nuxt_match = re.search(r'window\.__NUXT__\s*=\s*\(function\(', html)
    if nuxt_match:
        # Extract stockId/stockName pairs from the SSR state
        # Pattern: {stockId:"2330",stockName:"台積電"} or similar
        stock_pairs = re.findall(
            r'stockId["\s:]+["\']?(\d{4,6})["\']?[,}].*?stockName["\s:]+["\']?([^"\',}]+)["\']?',
            html, re.DOTALL
        )
        if stock_pairs:
            seen = set()
            stocks = []
            for code, name in stock_pairs:
                if code not in seen:
                    seen.add(code)
                    stocks.append({"code": code, "name": name.strip()})
            if stocks:
                _save_cache(cache_path, {"stocks": stocks, "concept_id": concept_id})
                print(f"[CMoney] Fetched {len(stocks)} stocks for concept {concept_id} (via Nuxt SSR)")
                return stocks

    # ── Strategy 2: Parse <a class="table__stock"> links ──
    # These are specific to the concept's stock table
    table_stock_pattern = r'class="table__stock"[^>]*href="[^"]*?/forum/stock/(\d{4,6})"'
    table_codes = re.findall(table_stock_pattern, html)
    
    if not table_codes:
        # Broader fallback: find stock links near concept content
        # Use a more specific pattern to avoid sidebar
        table_stock_pattern2 = r'href="/forum/stock/(\d{4,6})"[^>]*class="[^"]*table__stock'
        table_codes = re.findall(table_stock_pattern2, html)

    if not table_codes:
        # Last resort: parse all stock links but filter out known sidebar codes
        stock_pattern = r'/forum/stock/(\d{4,6})'
        all_codes = re.findall(stock_pattern, html)
        sidebar_codes = {
            "0050", "0056", "00878", "00919", "009816",
            "2330", "2337", "2605", "3715", "2317",  # hot stocks in sidebar
        }
        table_codes = [c for c in all_codes if c not in sidebar_codes]

    # Deduplicate preserving order
    seen = set()
    codes = []
    for code in table_codes:
        if code not in seen:
            seen.add(code)
            codes.append(code)
    
    if not codes:
        return []

    # Resolve names via Fugle (CMoney API requires auth)
    stocks = _resolve_stock_names(codes)
    
    if stocks:
        _save_cache(cache_path, {"stocks": stocks, "concept_id": concept_id})
        print(f"[CMoney] Fetched {len(stocks)} stocks for concept {concept_id}")

    return stocks


def _resolve_stock_names(codes: List[str]) -> List[Dict[str, str]]:
    """
    Resolve stock codes to names using CMoney's AdditionalInformation API.
    Falls back to code-only if API fails.
    """
    result = _post_json(_STOCK_INFO_API, codes)
    
    if result and "data" in result:
        name_map = {}
        for item in result["data"]:
            sid = item.get("id", "")
            name = item.get("name", "")
            if sid and name:
                name_map[sid] = name
        
        stocks = []
        for code in codes:
            stocks.append({
                "code": code,
                "name": name_map.get(code, code),
            })
        return stocks
    
    # API failed — also try Fugle as backup for names
    stocks = []
    for code in codes:
        stocks.append({"code": code, "name": code})
    
    # Try Fugle for names in bulk
    try:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv())
        api_key = os.getenv("FUGLE_API_KEY")
        if api_key:
            from fugle_marketdata import RestClient
            client = RestClient(api_key=api_key)
            for stock in stocks:
                try:
                    info = client.stock.intraday.ticker(symbol=stock["code"])
                    name = info.get("name") or info.get("nameZhTw")
                    if name:
                        stock["name"] = name
                except Exception:
                    pass
    except Exception:
        pass
    
    return stocks


# ── Fallback ──────────────────────────────────────────────────────────────────

def _fallback_concept_list() -> List[Dict[str, str]]:
    """
    Fallback: parse industry_logic.json for concept names.
    Returns in the same format as fetch_concept_list().
    """
    try:
        cfg_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "configs", "industry_logic.json"
        )
        if not os.path.exists(cfg_path):
            # Try alternative path
            cfg_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "configs", "industry_logic.json"
            )
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        concepts = []
        for k, v in data.items():
            aliases = v.get("alias", [])
            if not aliases:
                continue
            name = aliases[0]
            syms = [str(a) for a in aliases if re.match(r'^\d{4}$', str(a))]
            if len(syms) >= 2:
                concepts.append({
                    "id": f"local_{k}",
                    "name": name,
                    "_local_stocks": syms,
                })
        return concepts
    except Exception as e:
        print(f"[CMoney] Fallback also failed: {e}")
        return []


def get_fallback_stocks(concept: dict) -> List[Dict[str, str]]:
    """Get stocks from a local/fallback concept entry."""
    local_syms = concept.get("_local_stocks", [])
    return [{"code": code, "name": code} for code in local_syms]


# ── Module test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== CMoney Concept Fetcher Test ===\n")
    
    concepts = fetch_concept_list(force=True)
    print(f"Total concepts: {len(concepts)}")
    for c in concepts[:10]:
        print(f"  {c['id']}: {c['name']}")
    
    if concepts:
        test_id = None
        for c in concepts:
            if "CoWoS" in c["name"]:
                test_id = c["id"]
                break
        if not test_id:
            test_id = concepts[0]["id"]
        
        print(f"\n--- Stocks for {test_id} ---")
        stocks = fetch_concept_stocks(test_id, force=True)
        for s in stocks:
            print(f"  {s['name']} {s['code']}")
