import sys
import json
import os
from pathlib import Path
from typing import Any, Optional, Dict, List, Callable
import threading
from concurrent.futures import ThreadPoolExecutor

# Add project root to sys.path for step35_firecrawl_tool
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.append(str(_root))

from .llm_adapter import StructuredLLMAdapter
from .models import EvidenceRecord, NumericFact
from .evidence_ledger import EvidenceLedgerStore

try:
    from step35_firecrawl_tool import firecrawl_tool
except ImportError:
    # Fallback if not in standard layout
    firecrawl_tool = None


class SearchAgent:
    """Agent responsible for performing deep web research to fill evidence gaps."""

    def __init__(self, model_name: str = "gpt-4o"):
        self.llm = StructuredLLMAdapter()
        self.ledger = EvidenceLedgerStore()
        self._lock = threading.Lock()

    def run_deep_research(
        self, 
        symbol: str, 
        missing_topics: List[str], 
        context: str = "",
        on_progress: Optional[Callable[[str], None]] = None
    ) -> List[EvidenceRecord]:
        """Entry point for deep research with telemetry callback."""
        if not missing_topics:
            return []
        
        def report(msg: str):
            with self._lock:
                if on_progress:
                    on_progress(msg)
                print(f"[SearchAgent] {msg}")

        report(f"Analyzing {len(missing_topics)} evidence gaps for {symbol}...")

        # 1. Generate specific search queries
        queries = self._generate_queries(symbol, missing_topics, context)
        
        all_new_evidence: List[EvidenceRecord] = []
        
        # 2. Parallelize Execute searches and extract (v1.9.8)
        max_workers = min(len(queries), 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            def process_query(idx_query):
                i, query = idx_query
                report(f"Searching [{i}/{max_workers}]: '{query}'...")
                search_results = self._search_and_scrape(query)
                
                if search_results:
                    report(f"Scrape successful for '{query}'. Extracting evidence...")
                    extracted = self._extract_evidence(symbol, query, search_results)
                    report(f"Extracted {len(extracted)} units from query {i}.")
                    return extracted
                else:
                    report(f"No usable content found for query {i}.")
                    return []

            # Run in parallel
            results = list(executor.map(process_query, enumerate(queries[:max_workers], start=1)))
            for r in results:
                all_new_evidence.extend(r)
        
        # 4. Append to ledger for permanence
        if all_new_evidence:
            self.ledger.append_many(symbol, all_new_evidence)
            
        return all_new_evidence

    def _generate_queries(self, symbol: str, topics: List[str], context: str) -> List[str]:
        prompt = f"""
目標公司: {symbol}
研究背景: {context}
缺失資訊: {", ".join(topics)}

請為這間公司生成 3 個精確的 Google 搜尋關鍵字，目的是找到能填補這項缺失資訊的最新證據（如：法說會新聞、財報分析、產業趨勢報告）。
關鍵字應包含公司名稱、年份以及具體主題。

輸出格式：
["query1", "query2", "query3"]
"""
        try:
            resp_dict = self.llm.invoke(prompt)
            if isinstance(resp_dict, list):
                return resp_dict
            return []
        except Exception as e:
            print(f"[SearchAgent] Failed to generate queries: {e}")
            return [f"{symbol} {t} 2024" for t in topics[:3]]

    def _search_and_scrape(self, query: str) -> str:
        if not firecrawl_tool or not firecrawl_tool.app:
            return ""
            
        try:
            from firecrawl import Firecrawl
            client: Firecrawl = firecrawl_tool.app
            search_data = client.search(query, limit=1)
            
            if search_data and "data" in search_data and search_data["data"]:
                top_url = search_data["data"][0].get("url")
                if top_url:
                    return firecrawl_tool.scrape_url(top_url)
        except Exception as e:
            print(f"[SearchAgent] Search/Scrape failed: {e}")
        return ""

    def _extract_evidence(self, symbol: str, query: str, content: str) -> List[EvidenceRecord]:
        """Parse raw markdown into structured EvidenceRecord objects."""
        if len(content) < 200:
            return []

        prompt = f"""
以下為從網路搜尋中抓取到的關於 {symbol} 的內容（搜尋字串：{query}）。
請從中提取出具有「強大證據力」的訊息，並轉換成 JSON 格式。

要求：
1. direction 必須為 bullish, bearish 或 unknown。
2. 提取具體的數據事實（NumericFact）。
3. claim 必須簡明扼要。

內文內容：
{content[:8000]}
"""
        try:
            data_list = self.llm.invoke(prompt)
            if not isinstance(data_list, list):
                return []
            
            records = []
            for d in data_list:
                d["symbol"] = symbol
                d["source_type"] = "deep_search"
                d["verification_status"] = "verified_ai"
                if "numeric_facts" in d:
                    from .models import NumericFact
                    d["numeric_facts"] = [NumericFact.from_dict(nf) for nf in d["numeric_facts"]]
                records.append(EvidenceRecord.from_dict(d))
            return records
        except Exception as e:
            print(f"[SearchAgent] Failed to extract evidence: {e}")
            return []
