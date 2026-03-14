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


def _copy_to_clipboard(text: str) -> None:
    """
    Copies text to the system clipboard using PowerShell.
    """
    try:
        # Use PowerShell to set clipboard to avoid extra dependencies like pyperclip
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $Input"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        process.communicate(input=text)
        _log(f"[Clipboard] successfully copied text (len={len(text)})")
    except Exception as e:
        _log(f"[Clipboard] copy failed: {e}")


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
    Open AlphaMemo for manual search.
    """
    _log(f"[AlphaMemo] open request: {query}")
    _open_browser(ALPHAMEMO_URL)
    _log("[AlphaMemo] opened AlphaMemo for manual input")
