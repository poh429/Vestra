"""LLM Core Provider Layer.

Centralized interface for multiple LLM providers:
- OpenRouter (multi-model fallback chain)
- Google SDK (Gemini direct access)
- NVIDIA NIM (Minimax ultra-low latency)

Handles API key management, rate limiting, and response normalization.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Global state for initialized services
_services_initialized = False


def initialize_services() -> None:
    """Initialize API keys and validate configuration."""
    global _services_initialized
    
    if _services_initialized:
        return
    
    # Auto-map common environment variable names
    if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")
    
    if not os.getenv("OPENROUTER_API_KEY") and os.getenv("OPENAI_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = os.getenv("OPENAI_API_KEY")
    
    # NVIDIA NIM uses OPENAI_API_KEY format
    if not os.getenv("NVIDIA_API_KEY") and os.getenv("OPENAI_API_KEY"):
        os.environ["NVIDIA_API_KEY"] = os.getenv("OPENAI_API_KEY")
    
    _services_initialized = True
    logger.info("[LLM Core] Services initialized")


def _check_rate_limit(response: requests.Response) -> bool:
    """Check if response indicates rate limiting."""
    return response.status_code in [429, 503]


def _extract_json_from_response(text: str) -> str:
    """Extract JSON from markdown blocks or raw text."""
    clean = text.strip()
    
    # Remove markdown code blocks
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    
    return clean.strip()


def call_openrouter(
    models: List[str],
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_retries: int = 3,
    timeout: int = 30,
) -> Optional[str]:
    """
    Call OpenRouter with model fallback chain.
    
    Args:
        models: List of model IDs to try in order
        messages: Chat completion messages
        temperature: Sampling temperature
        max_retries: Number of retry attempts per model
        timeout: Request timeout in seconds
    
    Returns:
        Response text or None if all models fail
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("[OpenRouter] API key not found")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vestra-ai",
        "X-Title": "Vestra Analyst OS",
    }
    
    for model in models:
        for attempt in range(max_retries):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 2048,
                }
                
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        logger.info(f"[OpenRouter] Success with model: {model}")
                        return _extract_json_from_response(content)
                
                elif _check_rate_limit(response):
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"[OpenRouter] Rate limited on {model}, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                else:
                    logger.warning(f"[OpenRouter] Model {model} failed: {response.status_code}")
                    break  # Try next model
                    
            except requests.exceptions.Timeout:
                logger.warning(f"[OpenRouter] Timeout on {model}, attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"[OpenRouter] Error on {model}: {e}")
                break
    
    logger.error("[OpenRouter] All models in chain failed")
    return None


def call_google_sdk(
    model: str,
    prompt: str,
    temperature: float = 0.1,
    max_retries: int = 3,
    timeout: int = 30,
) -> Optional[str]:
    """
    Call Google Gemini via direct SDK or REST API.
    
    Args:
        model: Model name (e.g., "gemini-2.0-flash")
        prompt: User prompt
        temperature: Sampling temperature
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        Response text or None if failed
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("[Google SDK] API key not found")
        return None
    
    # Try using google-generativeai package if available
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        
        for attempt in range(max_retries):
            try:
                gemini_model = genai.GenerativeModel(model)
                response = gemini_model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": 2048,
                    },
                    request_options={"timeout": timeout},
                )
                
                if response.text:
                    logger.info(f"[Google SDK] Success with model: {model}")
                    return _extract_json_from_response(response.text)
                    
            except Exception as e:
                if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"[Google SDK] Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                logger.error(f"[Google SDK] Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
        
        return None
        
    except ImportError:
        # Fallback to REST API
        logger.info("[Google SDK] Using REST API fallback")
        return _call_google_rest(model, prompt, temperature, max_retries, timeout)


def _call_google_rest(
    model: str,
    prompt: str,
    temperature: float = 0.1,
    max_retries: int = 3,
    timeout: int = 30,
) -> Optional[str]:
    """Call Google Gemini via REST API."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048,
        },
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if content:
                    logger.info(f"[Google REST] Success with model: {model}")
                    return _extract_json_from_response(content)
            
            elif _check_rate_limit(response):
                wait_time = (attempt + 1) * 2
                logger.warning(f"[Google REST] Rate limited, waiting {wait_time}s")
                time.sleep(wait_time)
                continue
            
            else:
                logger.warning(f"[Google REST] Failed: {response.status_code}")
                break
                
        except requests.exceptions.Timeout:
            logger.warning(f"[Google REST] Timeout, attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
        except Exception as e:
            logger.error(f"[Google REST] Error: {e}")
            break
    
    return None


def call_nvidia_nim(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_retries: int = 3,
    timeout: int = 30,
) -> Optional[str]:
    """
    Call NVIDIA NIM endpoint (supports Minimax and other NIM models).
    
    Args:
        model: Model ID (e.g., "minimaxai/minimax-m2.7")
        messages: Chat completion messages
        temperature: Sampling temperature
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        Response text or None if failed
    """
    # NVIDIA NIM uses OpenAI-compatible API
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[NVIDIA NIM] API key not found")
        return None
    
    # Map model name to NIM endpoint
    # For Minimax specifically, use the NIM catalog endpoint
    base_url = "https://integrate.api.nvidia.com/v1"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    for attempt in range(max_retries):
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 2048,
                "stream": False,
            }
            
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    logger.info(f"[NVIDIA NIM] Success with model: {model}")
                    return _extract_json_from_response(content)
            
            elif _check_rate_limit(response):
                wait_time = (attempt + 1) * 2
                logger.warning(f"[NVIDIA NIM] Rate limited, waiting {wait_time}s")
                time.sleep(wait_time)
                continue
            
            else:
                logger.warning(f"[NVIDIA NIM] Failed: {response.status_code} - {response.text[:200]}")
                break
                
        except requests.exceptions.Timeout:
            logger.warning(f"[NVIDIA NIM] Timeout, attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
        except Exception as e:
            logger.error(f"[NVIDIA NIM] Error: {e}")
            break
    
    return None


# Convenience function for quick testing
if __name__ == "__main__":
    import sys
    
    # Quick sanity check
    initialize_services()
    
    print("LLM Core Status:")
    print(f"  OPENROUTER_API_KEY: {'✓' if os.getenv('OPENROUTER_API_KEY') else '✗'}")
    print(f"  GOOGLE_API_KEY: {'✓' if os.getenv('GOOGLE_API_KEY') else '✗'}")
    print(f"  NVIDIA_API_KEY: {'✓' if os.getenv('NVIDIA_API_KEY') else '✗'}")
    
    if len(sys.argv) > 1:
        test_prompt = " ".join(sys.argv[1:])
        print(f"\nTesting with prompt: {test_prompt}")
        
        result = call_google_sdk("gemini-2.0-flash", test_prompt)
        if result:
            print(f"\nGoogle SDK Response:\n{result}")
        else:
            print("\nGoogle SDK failed, trying OpenRouter...")
            result = call_openrouter(
                ["google/gemma-2-9b-it:free"],
                [{"role": "user", "content": test_prompt}]
            )
            if result:
                print(f"\nOpenRouter Response:\n{result}")
