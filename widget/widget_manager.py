"""
WidgetManager — orchestrates all CardWindows and data feeds.

Responsibilities:
 • Create one CardWindow per watchlist item
 • Manage Crypto / US / TW feeds and route price updates to each card
 • Provide global layout operations (arrange grid, show all, hide all)
 • System tray integration
 • Persist positions back to widget_config.json on exit
"""

import json
import os
import tkinter as tk
from typing import Callable, Dict, List, Optional

from widget.style import theme
from widget.card_window import CardWindow
from widget.tray_icon import TrayIconManager
from widget.data.crypto_feed import CryptoFeed
from widget.data.us_stock_feed import USStockFeed
from widget.data.tw_stock_feed import TWStockFeed

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "widget_config.json")


class WidgetManager(tk.Tk):
    """
    Hidden root Tk window that owns all CardWindow Toplevels.
    The root window itself is never visible — only the cards are.
    """

    GRID_COLS   = 3      # default columns for auto-arrange
    GRID_GAP_X  = 10     # horizontal gap between cards
    GRID_GAP_Y  = 10     # vertical gap
    GRID_START_X = 80
    GRID_START_Y = 80

    def __init__(self):
        super().__init__()
        self.withdraw()               # root is invisible
        self.title("StockWidgetRoot")

        # Set universal application icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo_nobackground.png")
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, img)
            except Exception:
                pass

        self._cfg: dict = {}
        self._cards: Dict[str, CardWindow] = {}   # symbol.upper() → CardWindow
        # price-update listeners per symbol
        self._listeners: Dict[str, List[Callable]] = {}
        self._feeds = []

        self._load_config()
        # Apply saved brightness before building cards
        from widget.style.theme import apply_lightness_from_config
        apply_lightness_from_config(self._cfg)
        self._build_cards()
        self._build_feeds()
        self._setup_tray()

        # Save config when app is closing
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self._cfg = json.load(f)
        except Exception:
            self._cfg = {"watchlist": [], "rate_limits": {}}

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Manager] Config save error: {e}")

    # ── Cards ─────────────────────────────────────────────────────────────────

    def _build_cards(self):
        rl = self._cfg.get("rate_limits", {})
        use_fugle = rl.get("tw_use_fugle_intraday", True)

        for item in self._cfg.get("watchlist", []):
            sym = item["symbol"].upper()
            self._listeners[sym] = []

            card = CardWindow(
                master=self,
                item_cfg=item,
                on_remove=self._remove_card,
                on_price_update=lambda s, cb: self._listeners.setdefault(s, []).append(cb),
                use_fugle=use_fugle,
            )
            self._cards[sym] = card

    def _remove_card(self, symbol: str):
        sym = symbol.upper()
        self._cards.pop(sym, None)
        self._listeners.pop(sym, None)
        # Remove from config watchlist
        self._cfg["watchlist"] = [
            i for i in self._cfg.get("watchlist", [])
            if i["symbol"].upper() != sym
        ]
        self._save_config()

    # ── Data feeds ────────────────────────────────────────────────────────────

    def _build_feeds(self):
        wl  = self._cfg.get("watchlist", [])
        rl  = self._cfg.get("rate_limits", {})

        crypto_syms = [i["symbol"] for i in wl if i["category"] == "Crypto"]
        us_syms     = [i["symbol"] for i in wl if i["category"] in ("美股", "ETF")]
        tw_syms     = [i["symbol"] for i in wl if i["category"] == "台股"]

        if crypto_syms and rl.get("crypto_ws", True):
            f = CryptoFeed(
                crypto_syms,
                callback=lambda s, d: self.after(0, self._dispatch_price, s, d),
            )
            f.start()
            self._feeds.append(f)

        if us_syms:
            f = USStockFeed(
                us_syms,
                callback=lambda s, d: self.after(0, self._dispatch_price, s, d),
                interval_sec=rl.get("us_stock_interval_sec", 60),
            )
            f.start()
            self._feeds.append(f)

        if tw_syms:
            f = TWStockFeed(
                tw_syms,
                callback=lambda s, d: self.after(0, self._dispatch_price, s, d),
                interval_sec=rl.get("tw_stock_interval_sec", 90),
                use_fugle=rl.get("tw_use_fugle_intraday", True),
            )
            f.start()
            self._feeds.append(f)

    def _stop_feeds(self):
        for f in self._feeds:
            try:
                f.stop()
            except Exception:
                pass
        self._feeds.clear()

    def _dispatch_price(self, symbol: str, data: dict):
        """Route a price update to all registered listeners for this symbol."""
        import tkinter as tk
        dead = []
        for cb in list(self._listeners.get(symbol.upper(), [])):
            try:
                cb(data)
            except tk.TclError:
                # Widget was destroyed — mark for removal
                dead.append(cb)
            except Exception as e:
                print(f"[Manager] Dispatch error {symbol}: {e}")
        # Clean up dead listeners
        if dead:
            self._listeners[symbol.upper()] = [
                cb for cb in self._listeners.get(symbol.upper(), [])
                if cb not in dead
            ]

    # ── Global layout ─────────────────────────────────────────────────────────

    def arrange_grid(self, cols: int = None):
        """Arrange all visible cards in a neat grid."""
        cols  = cols or self.GRID_COLS
        cards = list(self._cards.values())
        col_w = cards[0]._cfg.get("card_width", 340) + self.GRID_GAP_X if cards else 350
        col   = 0
        row   = 0
        row_h = 0

        for card in cards:
            h  = card.winfo_height() or 240
            x  = self.GRID_START_X + col * col_w
            y  = self.GRID_START_Y + row * (h + self.GRID_GAP_Y)
            card.geometry(f"+{x}+{y}")
            card._cfg["pos_x"] = x
            card._cfg["pos_y"] = y
            row_h = max(row_h, h)
            col  += 1
            if col >= cols:
                col   = 0
                row  += 1
                row_h = 0

        self._save_config()

    def show_all(self):
        is_top = self._cfg.get("always_on_top", True)
        for card in self._cards.values():
            card.deiconify()
            card.attributes("-topmost", is_top)

    def hide_all(self):
        for card in self._cards.values():
            card.withdraw()

    # ── Settings (global) ─────────────────────────────────────────────────────

    def open_manager_panel(self):
        """Open the centralized Swish Finance-style management panel."""
        from widget.manager_panel import ManagerPanel

        def _on_save():
            self._load_config()
            self._stop_feeds()
            for card in list(self._cards.values()):
                card.destroy()
            self._cards.clear()
            self._listeners.clear()
            self._build_cards()
            self._build_feeds()

        ManagerPanel(
            parent=self,
            config=self._cfg,
            cards=self._cards,
            on_save=_on_save,
            on_arrange=lambda: self.arrange_grid(3),
            on_rebuild=_on_save,
        )

    # keep old name as alias for SettingsPanel callers
    def open_global_settings(self):
        self.open_manager_panel()

    # ── Tray icon ─────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self._tray = TrayIconManager(
            show_cb=    lambda: self.after(0, self.show_all),
            hide_cb=    lambda: self.after(0, self.hide_all),
            settings_cb=lambda: self.after(0, self.open_global_settings),
            quit_cb=    lambda: self.after(0, self._quit),
        )
        # Add extra tray menu items via monkey-patch before starting
        _orig_start = self._tray.start

        def _patched_start():
            import pystray
            from pystray import MenuItem as Item, Menu

            icon_img = __import__("widget.tray_icon", fromlist=["_make_icon"])._make_icon()
            menu = pystray.Menu(
                Item("◈ 顯示全部",   lambda i, it: self.after(0, self.show_all), default=True),
                Item("隱藏全部",     lambda i, it: self.after(0, self.hide_all)),
                pystray.Menu.SEPARATOR,
                Item("▣ 管理面板",      lambda i, it: self.after(0, self.open_manager_panel)),
                pystray.Menu.SEPARATOR,
                Item("⊞ 整齊排列 (2欄)", lambda i, it: self.after(0, lambda: self.arrange_grid(2))),
                Item("⊞ 整齊排列 (3欄)", lambda i, it: self.after(0, lambda: self.arrange_grid(3))),
                pystray.Menu.SEPARATOR,
                Item("✕ 關閉",        lambda i, it: self.after(0, self._quit)),
            )
            self._tray._icon = pystray.Icon(
                name="StockWidget", icon=icon_img,
                title="Stock Widget", menu=menu,
            )
            import threading
            threading.Thread(target=self._tray._icon.run, daemon=True).start()

        self._tray.start = _patched_start
        self._tray.start()

    # ── Quit ─────────────────────────────────────────────────────────────────

    def _quit(self):
        self._save_config()
        self._stop_feeds()
        try:
            self._tray.stop()
        except Exception:
            pass
        self.destroy()
