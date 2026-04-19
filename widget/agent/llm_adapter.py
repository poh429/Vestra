"""Thin adapter layer for structured LLM invocations.

Responsible for:
- Provider connection details
- Retry / Timeout behavior
- JSON extraction and repair
- Fallback mechanics on parse failure
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Add project root to sys.path to access internal llm_core
_root = Path(__file__).resolve().parents[2] 
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from llm_core import call_openrouter, call_google_sdk, call_nvidia_nim, initialize_services
    print(f"  [Vestra-Adapter] Successfully loaded internal llm_core from: {_root}")
except ImportError as e:
    # Error diagnostic
    print(f"  ❌ [Vestra-Adapter] FAILED to load llm_core from: {_root}")
    print(f"  Trace: {e}")
    # Safe fallback if run out of root context
    call_openrouter = None
    call_google_sdk = None
    call_nvidia_nim = None
    initialize_services = lambda: None


class StructuredLLMAdapter:
    """Handles communications with the underlying LLM provider for structured JSON responses."""

    def __init__(self, config: Optional[dict[str, Any]] = None, mock: bool = False):
        self.config = config or {}
        self.mock = mock

    def invoke(self, prompt: str) -> dict[str, Any]:
        """
        Invokes the actual LLM via llm_core openrouter calls unless mock=True.
        """
        if self.mock or not call_openrouter:
            # V1.4-c isolation capability
            try:
                raw_text = self._mock_call(prompt)
                return self._safe_parse(raw_text)
            except TimeoutError:
                return {"verdict": "unknown", "llm_status": "timeout", "reason_codes": ["PROVIDER_TIMEOUT"], "notes": ["LLM Adapter Error: Request timed out."]}
            except Exception as e:
                return {"verdict": "unknown", "llm_status": "error", "reason_codes": ["PROVIDER_ERROR"], "notes": [f"LLM Adapter Error: {e}"]}

        # Production Execution
        try:
            # 1. Environment Setup: Automap keys for Google SDK stability
            if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
                os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")
            
            # 2. Ensure services are initialized with current environment
            if initialize_services:
                initialize_services()

            # 3. Track providers errors
            errors = []

            # 4. Ultra-Low Latency Provider: NVIDIA NIM (Minimax)
            if call_nvidia_nim:
                # User specifically requested minimaxai/minimax-m2.7
                res = call_nvidia_nim("minimaxai/minimax-m2.7", [
                    {"role": "system", "content": "You are a senior financial analyst. Reply strictly with raw JSON."},
                    {"role": "user", "content": prompt}
                ], temperature=0.1)
                if res:
                    return self._safe_parse(res)
                errors.append("NVIDIA NIM (Minimax) returned None.")

            # 5. Primary Provider: Direct Google SDK (Fastest & most stable)
            if call_google_sdk:
                res = call_google_sdk("gemini-2.0-flash", prompt, temperature=0.1)
                if res:
                    return self._safe_parse(res)
                errors.append("Google SDK returned None.")

            # 5. Secondary Provider: OpenRouter Multi-Model Chain (User preferred Gemma)
            if call_openrouter:
                messages = [
                    {"role": "system", "content": "You are a senior financial analyst. Reply strictly with a raw valid JSON object. No markdown blocks."},
                    {"role": "user", "content": prompt}
                ]
                # High-tier free models - Using User's requested Gemma + Gemini/Llama fallbacks
                models = [
                    "google/gemma-4-31b-it:free",
                    "google/gemma-2-9b-it:free",
                    "google/gemma-2-27b-it:free",
                    "google/gemini-2.0-flash-exp:free",
                    "meta-llama/llama-3.3-70b-instruct:free"
                ]
                res = call_openrouter(models, messages, temperature=0.1)
                if res:
                    return self._safe_parse(res)
                errors.append("OpenRouter chain failed (Likely 429/404).")

            raise Exception(f"All LLM providers failed. Log: {'; '.join(errors)}")
            
        except Exception as e:
            return {
                "verdict": "unknown",
                "llm_status": "error",
                "reason_codes": ["PROVIDER_ERROR"],
                "notes": [f"Dual-Track Engine Error: {e}"]
            }

    def _mock_call(self, prompt: str) -> str:
        """Internal mock for v1.4-c isolation testing."""
        # Force a timeout scenario
        if "MOCK_TIMEOUT" in prompt:
            raise TimeoutError("LLM Provider Timeout")

        # Force a parse failure scenario if told to
        if "MOCK_BAD_JSON" in prompt:
            return "{ bad_json: missing quotes "

        # Mixed signals -> partially_supported
        if "mixed" in prompt.lower() or "好壞參半" in prompt.lower():
            return json.dumps({
                "verdict": "partially_supported",
                "confidence": "low",
                "reason_codes": ["MIXED_SIGNALS"],
                "llm_status": "success",
                "notes": ["Evidence shows conflicting or incomplete confirmation."],
            })

        # MOCK_REPORT returns a generic coverage report output
        if "MOCK_REPORT" in prompt:
            return json.dumps({
                "overall_assessment": "Generally strong outlook but macro risk exists.",
                "market_belief_gap": "Market underestimates the gross margin potential.",
                "bull_base_bear_summary": {
                    "bull": "Expansion completes smoothly.",
                    "base": "Standard trajectory.",
                    "bear": "Delay causes customer loss."
                },
                "major_triggers": ["Next quarter earnings"],
                "red_flags": ["No new capex announced"],
                "must_watch_metrics": ["Gross margin"],
                "open_evidence_gaps": ["Lacking yield data"],
                "confidence": "high",
                "llm_status": "success"
            })

        # MOCK_SCENARIO returns a generic scenario valuation output
        if "MOCK_SCENARIO" in prompt:
            return json.dumps({
                "bull_case": {"narrative": "Everything goes well.", "assumptions": ["A1"], "implied_financials": {}, "probability": "high"},
                "base_case": {"narrative": "Status quo.", "assumptions": ["B1"], "implied_financials": {}, "probability": "medium"},
                "bear_case": {"narrative": "Melt down.", "assumptions": ["C1"], "implied_financials": {}, "probability": "low"},
                "market_implied_view": "Market currently prices base case.",
                "rerating_triggers": ["Volume up"],
                "expectation_risk": "low",
                "confidence": "high",
                "llm_status": "success"
            })

        # Weak Filing Only -> unknown
        if "weak filing" in prompt.lower() and not "strong evidence" in prompt.lower():
            return json.dumps({
                "verdict": "unknown",
                "confidence": "low",
                "reason_codes": ["WEAK_FILING_EVIDENCE"],
                "llm_status": "success",
                "notes": ["Filing insight is too weak/generic to form a strict verdict."],
            })

        # If there is a delay signal in transcript but core mechanism is intact -> delayed
        if "delay" in prompt.lower() or "延遲" in prompt.lower() or "遞延" in prompt.lower():
            if "cancel" not in prompt.lower() and "否定" not in prompt.lower():
                return json.dumps({
                    "verdict": "delayed",
                    "confidence": "medium",
                    "delayed_progress": "Mechanism intact, timing slipped.",
                    "delayed_state": "slipping",
                    "reason_codes": ["DELAY_SIGNAL_DETECTED"],
                    "llm_status": "success",
                    "notes": ["Detected delay signal in transcripts or evidence."],
                })
        
        # If there's an active contradiction
        if "contradict" in prompt.lower() or "cancel" in prompt.lower() or "否定" in prompt.lower():
            return json.dumps({
                "verdict": "contradicted",
                "confidence": "high",
                "falsification_progress": "Hit kill condition or found strong opposing evidence.",
                "falsification_state": "breached",
                "reason_codes": ["KILL_CONDITION_MET"],
                "llm_status": "success",
                "notes": ["Core assumption breached."],
            })

        # Default fallback output 
        return json.dumps({
            "verdict": "unknown",
            "confidence": "low",
            "missing_evidence_topics": ["Pending hard validation."],
            "reason_codes": ["INSUFFICIENT_EVIDENCE"],
            "llm_status": "success",
            "notes": ["Fallback to unknown due to lack of definitive directional evidence."],
            "source_summary": "Heuristic fallback evaluation applied."
        })

    def _safe_parse(self, text: str) -> dict[str, Any]:
        """Safely parse LLM JSON response with basic repair."""
        try:
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            return json.loads(clean_text)
        except json.JSONDecodeError as err:
            # Shield main flow from exploding on bad output
            # Pass back the indicator to the executor
            return {
                "verdict": "unknown", 
                "llm_status": "parse_error",
                "reason_codes": ["PARSE_FAILURE"],
                "notes": [f"LLM Adapter Parse Error: {err}"]
            }
