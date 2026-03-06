"""
AlertManager — price alert system for Stock Desktop Widget.
Stores per-symbol alert thresholds and fires desktop notifications
when they are crossed.

Usage:
    mgr = AlertManager()
    mgr.set_alert("NVDA", above=150.0)
    mgr.set_alert("BTC-USD", below=60000.0)
    mgr.check("NVDA", 151.0)   # fires notification if threshold crossed
"""

import threading
from typing import Dict, Optional


class AlertManager:
    """Singleton-ish price alert tracker."""

    def __init__(self):
        self._alerts: Dict[str, dict] = {}   # symbol → {above, below, fired_above, fired_below}
        self._lock = threading.Lock()

    # ── Configuration ──────────────────────────────────────────────────────────

    def set_alert(self, symbol: str, above: Optional[float] = None,
                  below: Optional[float] = None) -> None:
        """Set alert thresholds for a symbol. Pass None to clear a threshold."""
        with self._lock:
            entry = self._alerts.setdefault(symbol.upper(), {
                "above": None, "below": None,
                "fired_above": False, "fired_below": False,
            })
            if above is not None:
                entry["above"] = above
                entry["fired_above"] = False   # reset so it can fire again
            if below is not None:
                entry["below"] = below
                entry["fired_below"] = False
            if above is None and below is None:
                # explicit clear
                self._alerts.pop(symbol.upper(), None)

    def clear_alert(self, symbol: str) -> None:
        with self._lock:
            self._alerts.pop(symbol.upper(), None)

    def get_alert(self, symbol: str) -> dict:
        with self._lock:
            return dict(self._alerts.get(symbol.upper(), {}))

    # ── Runtime check ──────────────────────────────────────────────────────────

    def check(self, symbol: str, price: float) -> None:
        """Call on every price update. Fires notification if threshold crossed."""
        with self._lock:
            entry = self._alerts.get(symbol.upper())
            if not entry:
                return

            above = entry.get("above")
            below = entry.get("below")

            if above is not None and price >= above and not entry["fired_above"]:
                entry["fired_above"] = True
                threading.Thread(
                    target=self._notify,
                    args=(symbol, f"📈 {symbol} 突破 {above:,.2f}！現價 {price:,.2f}"),
                    daemon=True,
                ).start()

            elif above is not None and price < above:
                entry["fired_above"] = False   # reset when price drops back

            if below is not None and price <= below and not entry["fired_below"]:
                entry["fired_below"] = True
                threading.Thread(
                    target=self._notify,
                    args=(symbol, f"📉 {symbol} 跌破 {below:,.2f}！現價 {price:,.2f}"),
                    daemon=True,
                ).start()

            elif below is not None and price > below:
                entry["fired_below"] = False   # reset when price rises back

    # ── Notification ───────────────────────────────────────────────────────────

    def _notify(self, symbol: str, message: str) -> None:
        """Fire a desktop notification. Uses plyer if available, else print."""
        try:
            from plyer import notification
            notification.notify(
                title=f"Stock Widget — {symbol}",
                message=message,
                app_name="Stock Widget",
                timeout=8,
            )
        except Exception:
            # plyer not installed or OS error — fallback to terminal
            print(f"[Alert] {message}")


# Module-level singleton
_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    return _manager
