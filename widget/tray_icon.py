"""
System tray icon manager using pystray + Pillow.
Runs in a background thread alongside the tkinter window.
"""

import threading
from typing import Callable

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as Item, Menu


def _make_icon(size: int = 64) -> Image.Image:
    """Draw a simple stock-chart icon in the widget accent color."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # Background circle
    d.ellipse([2, 2, size - 2, size - 2], fill="#7c6fff")

    # Simple bar-chart shape
    bars = [
        (10, 44, 18, 54),   # short bar
        (20, 34, 28, 54),   # medium bar
        (30, 24, 38, 54),   # tall bar
        (40, 30, 48, 54),   # medium bar
        (50, 18, 58, 54),   # tallest bar (green = up)
    ]
    colors = ["#00e676", "#00e676", "#00e676", "#ff4d4d", "#00e676"]
    for (x1, y1, x2, y2), c in zip(bars, colors):
        d.rectangle([x1, y1, x2, y2], fill=c)

    return img


class TrayIconManager:
    """Manages a pystray system tray icon running on its own thread."""

    def __init__(
        self,
        show_cb:    Callable,
        hide_cb:    Callable,
        settings_cb: Callable,
        quit_cb:    Callable,
    ):
        self.show_cb    = show_cb
        self.hide_cb    = hide_cb
        self.settings_cb = settings_cb
        self.quit_cb    = quit_cb
        self._icon: pystray.Icon | None = None

    def start(self):
        """Start the tray icon on a daemon thread."""
        icon_img = _make_icon()
        menu = Menu(
            Item("◈ 顯示 Widget",   self._show,     default=True),
            Item("隱藏",             self._hide),
            Menu.SEPARATOR,
            Item("⚙ 設定",          self._settings),
            Item("🔄 重新整理",     self._refresh),
            Menu.SEPARATOR,
            Item("✕ 關閉",          self._quit),
        )
        self._icon = pystray.Icon(
            name="StockWidget",
            icon=icon_img,
            title="Stock Widget",
            menu=menu,
        )
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()

    def stop(self):
        if self._icon:
            self._icon.stop()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _show(self, icon, item):
        self.show_cb()

    def _hide(self, icon, item):
        self.hide_cb()

    def _settings(self, icon, item):
        self.settings_cb()

    def _refresh(self, icon, item):
        # Refresh is handled by calling show (window rebuilds on next show)
        self.show_cb()

    def _quit(self, icon, item):
        self.stop()
        self.quit_cb()
