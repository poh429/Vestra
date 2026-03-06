"""
Main tkinter window — frameless, always-on-top, draggable, scrollable.
Hosts category tabs, ticker rows and chart cards.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Dict

from widget.style import theme
from widget.components.ticker_row import TickerRow
from widget.components.chart_card import ChartCard
from widget.components.settings_panel import SettingsPanel
from widget.data.crypto_feed import CryptoFeed
from widget.data.us_stock_feed import USStockFeed
from widget.data.tw_stock_feed import TWStockFeed
from widget.tray_icon import TrayIconManager

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "widget_config.json")


class WidgetWindow(tk.Tk):
    """Main always-on-top widget window using tkinter."""

    def __init__(self):
        super().__init__()
        self._cfg        = self._load_config()
        self._cards: Dict[str, tk.Frame] = {}
        self._feeds      = []
        self._active_cat = "全部"
        self._drag_x     = 0
        self._drag_y     = 0

        self._setup_window()
        self._build_ui()
        self._build_feeds()
        self._setup_tray()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title("Stock Widget")
        self.configure(bg=theme.BG)
        self.overrideredirect(True)         # frameless
        self.attributes("-topmost", True)   # always on top
        self.attributes("-transparentcolor", "") # not needed on Win but harmless

        win = self._cfg.get("window", {})
        w   = win.get("width", 370)
        x   = win.get("x", 80)
        y   = win.get("y", 80)
        self.geometry(f"{w}x700+{x}+{y}")
        self.minsize(300, 200)

        alpha = win.get("alpha", 0.93)
        self.attributes("-alpha", alpha)

        # Dragging
        self.bind("<Button-1>",        self._on_drag_start)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._save_position)

        # Mouse-wheel opacity (Alt+scroll)
        self.bind("<Alt-MouseWheel>",  self._on_alt_scroll)

        # Resize handle (Ctrl+scroll)
        self.bind("<Control-MouseWheel>", self._on_ctrl_scroll)

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Outer container ────────────────────────────────────────
        outer = tk.Frame(self, bg=theme.BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=theme.BG)
        inner.pack(fill="both", expand=True)

        # ── Title bar ──────────────────────────────────────────────
        tbar = tk.Frame(inner, bg=theme.BG, pady=4)
        tbar.pack(fill="x", padx=8)

        tk.Label(tbar, text="◈", font=("Segoe UI", 14, "bold"),
                 fg=theme.ACCENT, bg=theme.BG).pack(side="left")

        tk.Label(tbar, text=" Stock Widget", font=theme.FONT_BOLD,
                 fg=theme.FG, bg=theme.BG).pack(side="left")

        self._ts_lbl = tk.Label(tbar, text="", font=theme.FONT_TINY,
                                 fg=theme.FG_DIM, bg=theme.BG)
        self._ts_lbl.pack(side="left", padx=8)

        # Close & settings buttons
        for txt, cmd in [("✕", self._hide), ("⚙", self._open_settings)]:
            tk.Button(tbar, text=txt, command=cmd,
                      bg=theme.BG, fg=theme.FG_DIM,
                      activebackground=theme.ACCENT,
                      activeforeground=theme.FG,
                      font=("Segoe UI", 11), bd=0,
                      relief="flat", cursor="hand2",
                      padx=4).pack(side="right", padx=1)

        # Resize grip (bottom-right drag hint)
        tk.Label(tbar, text="⠿", font=theme.FONT_TINY,
                 fg=theme.FG_MUTED, bg=theme.BG,
                 cursor="size").pack(side="right", padx=6)

        # ── Category tabs ──────────────────────────────────────────
        tab_bar = tk.Frame(inner, bg=theme.BG)
        tab_bar.pack(fill="x", padx=6, pady=(0, 4))
        self._tab_btns: Dict[str, tk.Label] = {}
        for cat in theme.CATEGORIES:
            lbl = tk.Label(tab_bar, text=cat, font=theme.FONT_SMALL,
                           padx=8, pady=2,
                           bg=theme.ACCENT if cat == self._active_cat else theme.BG3,
                           fg=theme.FG    if cat == self._active_cat else theme.FG_DIM,
                           cursor="hand2")
            lbl.pack(side="left", padx=2)
            lbl.bind("<Button-1>", lambda e, c=cat: self._switch_cat(c))
            self._tab_btns[cat] = lbl

        # ── Scrollable cards area ──────────────────────────────────
        scroll_frame = tk.Frame(inner, bg=theme.BG)
        scroll_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(scroll_frame, bg=theme.BG,
                                  highlightthickness=0, bd=0)
        vsb = tk.Scrollbar(scroll_frame, orient="vertical",
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._cards_frame = tk.Frame(self._canvas, bg=theme.BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._cards_frame, anchor="nw")

        self._cards_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>",      self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>",     self._on_scroll)
        self._cards_frame.bind("<MouseWheel>",self._on_scroll)

        # ── Status bar ─────────────────────────────────────────────
        status = tk.Frame(inner, bg=theme.BG3, height=20)
        status.pack(fill="x", padx=0, pady=0)
        self._status_lbl = tk.Label(status, text="連線中…",
                                     font=theme.FONT_TINY,
                                     fg=theme.FG_DIM, bg=theme.BG3)
        self._status_lbl.pack(side="right", padx=8)

        self._rebuild_cards()

    # ── Cards ─────────────────────────────────────────────────────────────────

    def _rebuild_cards(self):
        for card in self._cards.values():
            card.destroy()
        self._cards.clear()

        rl        = self._cfg.get("rate_limits", {})
        use_fugle = rl.get("tw_use_fugle_intraday", True)

        for item in self._cfg.get("watchlist", []):
            sym     = item["symbol"]
            label   = item.get("label", sym)
            cat     = item.get("category", "")
            display = item.get("display", "ticker")
            base_cur = item.get("base_currency", "USD")

            if display == "chart":
                card = ChartCard(
                    self._cards_frame, sym, label, cat,
                    use_fugle=use_fugle,
                )
                card.pack(fill="x", padx=4, pady=3)
            else:
                card = TickerRow(
                    self._cards_frame, sym, label, cat,
                    base_currency=base_cur,
                )
                card.pack(fill="x", padx=4, pady=3)

            card.configure(cursor="arrow")
            card.bind("<MouseWheel>", self._on_scroll)
            for child in card.winfo_children():
                child.bind("<MouseWheel>", self._on_scroll)

            card.setvar("category", cat)
            self._cards[sym.upper()] = card

        self._apply_cat_filter()

    # ── Data feeds ────────────────────────────────────────────────────────────

    def _build_feeds(self):
        wl  = self._cfg.get("watchlist", [])
        rl  = self._cfg.get("rate_limits", {})

        crypto_syms = [i["symbol"] for i in wl if i["category"] == "Crypto"]
        us_syms     = [i["symbol"] for i in wl if i["category"] in ("美股", "ETF")]
        tw_syms     = [i["symbol"] for i in wl if i["category"] == "台股"]

        if crypto_syms and rl.get("crypto_ws", True):
            f = CryptoFeed(crypto_syms,
                           callback=lambda s, d: self.after(0, self._on_price, s, d))
            f.start()
            self._feeds.append(f)

        if us_syms:
            f = USStockFeed(us_syms,
                            callback=lambda s, d: self.after(0, self._on_price, s, d),
                            interval_sec=rl.get("us_stock_interval_sec", 60))
            f.start()
            self._feeds.append(f)

        if tw_syms:
            f = TWStockFeed(tw_syms,
                            callback=lambda s, d: self.after(0, self._on_price, s, d),
                            interval_sec=rl.get("tw_stock_interval_sec", 90),
                            use_fugle=rl.get("tw_use_fugle_intraday", True))
            f.start()
            self._feeds.append(f)

    def _stop_feeds(self):
        for f in self._feeds:
            try:
                f.stop()
            except Exception:
                pass
        self._feeds.clear()

    # ── Price update callback ─────────────────────────────────────────────────

    def _on_price(self, symbol: str, data: dict):
        card = self._cards.get(symbol.upper())
        if card is None:
            return
        if isinstance(card, TickerRow):
            card.update_data(data)
        elif isinstance(card, ChartCard):
            card.update_ticker(data)

        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self._status_lbl.config(text=f"更新 {ts}  •  {symbol}")
        self._ts_lbl.config(text=ts)

    # ── Category tabs ─────────────────────────────────────────────────────────

    def _switch_cat(self, cat: str):
        self._active_cat = cat
        for name, lbl in self._tab_btns.items():
            lbl.config(
                bg=theme.ACCENT  if name == cat else theme.BG3,
                fg=theme.FG      if name == cat else theme.FG_DIM)
        self._apply_cat_filter()

    def _apply_cat_filter(self):
        for sym, card in self._cards.items():
            # retrieve category stored in the widget dict
            item_cat = next(
                (i.get("category", "") for i in self._cfg.get("watchlist", [])
                 if i["symbol"].upper() == sym),
                "")
            show = (self._active_cat == "全部") or (item_cat == self._active_cat)
            if show:
                card.pack(fill="x", padx=4, pady=3)
            else:
                card.pack_forget()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        def _on_save():
            self._cfg = self._load_config()
            self._stop_feeds()
            self._rebuild_cards()
            self._build_feeds()
        SettingsPanel(self, self._cfg, on_save=_on_save)

    # ── Scroll ───────────────────────────────────────────────────────────────

    def _on_scroll(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _save_position(self, event=None):
        self._cfg.setdefault("window", {}).update(
            {"x": self.winfo_x(), "y": self.winfo_y()})
        self._write_config()

    # ── Opacity/resize ────────────────────────────────────────────────────────

    def _on_alt_scroll(self, event):
        delta   = event.delta / 12000
        current = self.attributes("-alpha")
        new_val = max(0.2, min(1.0, current + delta))
        self.attributes("-alpha", new_val)
        self._cfg.setdefault("window", {})["alpha"] = new_val

    def _on_ctrl_scroll(self, event):
        """Ctrl+Scroll to resize width."""
        win = self._cfg.setdefault("window", {})
        w   = win.get("width", 370)
        w   = max(280, min(600, w + int(event.delta / 30)))
        win["width"] = w
        h = self.winfo_height()
        x, y = self.winfo_x(), self.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _setup_tray(self):
        """Start pystray system tray icon."""
        self._tray = TrayIconManager(
            show_cb=lambda: self.after(0, self._show_window),
            hide_cb=lambda: self.after(0, self._hide_window),
            settings_cb=lambda: self.after(0, self._open_settings),
            quit_cb=lambda: self.after(0, self.destroy),
        )
        self._tray.start()

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)

    def _hide_window(self):
        self.withdraw()

    def _hide(self):
        """Called by window's ✕ button — minimize to tray."""
        self.withdraw()

    def _write_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def destroy(self):
        self._stop_feeds()
        try:
            self._tray.stop()
        except Exception:
            pass
        super().destroy()

    @staticmethod
    def _load_config() -> dict:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"watchlist": [], "window": {}, "rate_limits": {}}
