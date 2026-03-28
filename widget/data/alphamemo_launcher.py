from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
import ctypes
import threading

ALPHAMEMO_URL = "https://www.alphamemo.ai/free-transcripts"
LOG_FILE = Path(__file__).resolve().parents[2] / "err.txt"
EDGE_USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"
CHROME_USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"


def _log(message: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{timestamp} {message}\n")
    except Exception:
        pass




def _open_browser(url: str) -> None:
    try:
        if EDGE_USER_DATA_DIR.exists():
            subprocess.Popen(["msedge", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        if CHROME_USER_DATA_DIR.exists():
            subprocess.Popen(["chrome", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    except Exception:
        pass
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception as e:
        _log(f"[AlphaMemo] webbrowser.open failed: {e}")


def open_alphamemo_with_query(query: str, keep_open: bool = True) -> None:
    """
    Open AlphaMemo directly to the transcript page via API resolution.
    If resolution fails, it gracefully falls back to the main search page.
    """
    import urllib.request
    import urllib.parse
    import json
    
    _log(f"[AlphaMemo] open request: {query}")
    
    normalized = query.split(".")[0].strip()
    target_url = ALPHAMEMO_URL
    
    anon_key = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmbGR6dGNjY3Robm5qYmViYmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE5NTIwNTMsImV4cCI6MjA1NzUyODA1M30."
        "XJDInKWn10xUag0bl0Cu3ZwQ2nQ61ZAL_ClajR22t_I"
    )
    
    try:
        encoded_exact = urllib.parse.quote(normalized)
        
        # Keep query perfectly simple to avoid PostgREST syntax errors causing 401.
        api_url = (
            f"https://api.alphamemo.ai/rest/v1/free_transcripts"
            f"?select=id,stock_name,audio_date"
            f"&stock_number=eq.{encoded_exact}"
            f"&order=audio_date.desc"
            f"&limit=1"
        )
        
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}"
        })
        
        # Timeout quickly to avoid UI freeze if internet is spotty
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and len(data) > 0 and "id" in data[0]:
                transcript_id = data[0]["id"]
                audio_date = data[0].get("audio_date", "")
                target_url = f"{ALPHAMEMO_URL}/{transcript_id}"
                _log(f"[AlphaMemo] resolved {normalized} to {transcript_id} ({audio_date})")
            else:
                _log(f"[AlphaMemo] no transcript found for {normalized}, using fallback")
                
    except Exception as e:
        _log(f"[AlphaMemo] API lookup failed for {normalized}: {e}")
        
    # 3. Open browser (separated logic)
    _open_browser(target_url)
    _log("[AlphaMemo] navigation complete")
