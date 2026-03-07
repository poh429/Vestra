"""
CardWindow — a single independent floating Toplevel window for one asset.

Features:
 • Frameless, always-on-top, draggable, semi-transparent
 • Right-click context menu: timeframe, chart mode, lock, settings, remove
 • Double-click title to collapse / expand
 • Hosts either a ChartCard or a TickerRow
 • Saves its own position to config on drag-release
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from widget.style import theme


# ── tiny helpers ─────────────────────────────────────────────────────────────

def _mk_ctx_sep(menu: tk.Menu):
    menu.add_separator()


class CardWindow(tk.Toplevel):
    """One floating card = one Toplevel window."""

    HEADER_H = 36      # collapsed height

    def __init__(
        self,
        master,
        item_cfg: dict,           # one watchlist entry
        on_remove:  Callable,     # callback(symbol) → remove card
        on_price_update: Callable,# callback to register for updates
        use_fugle: bool = True,
    ):
        super().__init__(master)
        self._cfg        = item_cfg
        self._on_remove  = on_remove
        self._use_fugle  = use_fugle
        self._collapsed  = False
        self._locked     = item_cfg.get("locked", False)
        self._drag_x     = 0
        self._drag_y     = 0

        self.symbol   = item_cfg["symbol"]
        self.label    = item_cfg.get("label", self.symbol)
        self.category = item_cfg.get("category", "")
        self._display = item_cfg.get("display", "chart")
        self._tf      = item_cfg.get("timeframe", "日線")
        self._mode    = item_cfg.get("chart_mode", "Line")
        
        self._last_ticker_data = {}

        # Holdings — P&L simulation
        self._qty  = float(item_cfg.get("qty",  0))   # number of shares/units held
        self._cost = float(item_cfg.get("cost", 0))   # average cost per unit

        # Price alerts
        from widget.data.alert_manager import get_alert_manager
        self._alert_mgr = get_alert_manager()
        alert_above = item_cfg.get("alert_above")
        alert_below = item_cfg.get("alert_below")
        if alert_above or alert_below:
            self._alert_mgr.set_alert(
                self.symbol.upper(),
                above=float(alert_above) if alert_above else None,
                below=float(alert_below) if alert_below else None,
            )

        self._setup_window()
        self._build_ui()
        on_price_update(self.symbol.upper(), self._on_ticker_update)

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        self.overrideredirect(True)
        is_topmost = True
        if hasattr(self.master, "_cfg"):
            is_topmost = self.master._cfg.get("always_on_top", True)
        self.attributes("-topmost", is_topmost)
        alpha = self._cfg.get("alpha", 0.93)
        self.attributes("-alpha", alpha)
        self.configure(bg=theme.BG)

        w = self._cfg.get("card_width", 340)
        x = self._cfg.get("pos_x", 100)
        y = self._cfg.get("pos_y", 100)
        self.geometry(f"{w}x200+{x}+{y}")

        # Context menu
        self._ctx = tk.Menu(self, tearoff=0, bg=theme.BG2, fg=theme.FG,
                             activebackground=theme.ACCENT,
                             activeforeground=theme.FG,
                             font=theme.FONT_SMALL, bd=0,
                             relief="flat")

        if self._display == "chart":
            color_menu = tk.Menu(self._ctx, tearoff=0, bg=theme.BG2, fg=theme.FG,
                                  activebackground=theme.ACCENT,
                                  activeforeground=theme.FG,
                                  font=theme.FONT_SMALL)
            color_menu.add_command(label="背景色調", command=self._pick_bg_tint)
            color_menu.add_command(label="圖表與文字色", command=self._pick_chart_accent)
            color_menu.add_command(label="基本面文字色", command=self._pick_fund_color)
            color_menu.add_separator()
            color_menu.add_command(label="恢復預設", command=self._reset_color)
            self._ctx.add_cascade(label="🎨 顏色設定", menu=color_menu)
            self._ctx.add_command(
                label="📊 基本面資訊  " + ("✔" if self._cfg.get("show_fundamentals") else "□"),
                command=self._toggle_fundamentals)
            _mk_ctx_sep(self._ctx)

        lock_label = "🔓 解鎖移動" if self._locked else "🔒 鎖定位置"
        self._ctx.add_command(label=lock_label, command=self._toggle_lock)
        self._ctx.add_command(label="⟲ 重新載入圖表",  command=self._reload_chart)
        _mk_ctx_sep(self._ctx)
        self._ctx.add_command(label="✕ 關閉此卡片",    command=self._remove_self)

    def _on_configure(self, event):
        if event.widget == self:
            w = self.winfo_width()
            h = self.winfo_height()
            if not hasattr(self, '_last_rgn_size'):
                self._last_rgn_size = (0, 0)
            if self._last_rgn_size == (w, h):
                return
            
            def _apply_rgn():
                w = self.winfo_width()
                h = self.winfo_height()
                if self._last_rgn_size == (w, h):
                    return
                self._last_rgn_size = (w, h)
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                    rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w, h, 16, 16)
                    ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
                    # Also re-apply acrylic since rgn changes can reset it
                    self._apply_acrylic(hwnd)
                except Exception:
                    pass

            if hasattr(self, '_rgn_timer'):
                self.after_cancel(self._rgn_timer)
            self._rgn_timer = self.after(50, _apply_rgn)

    def _apply_acrylic(self, hwnd=None):
        """Apply Acrylic blur-behind to frameless windows.
        Uses SetWindowCompositionAttribute which works on overrideredirect windows.
        Win10 1903+  /  Win11 compatible.
        acrylic_mode: 'off' | 'acrylic' | 'mica'
        """
        acrylic_mode = "off"
        if hasattr(self.master, "_cfg"):
            acrylic_mode = self.master._cfg.get("acrylic_mode", "off")

        try:
            import ctypes

            if hwnd is None:
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())

            class _ACCENT(ctypes.Structure):
                _fields_ = [
                    ("AccentState",   ctypes.c_int),
                    ("AccentFlags",   ctypes.c_int),
                    ("GradientColor", ctypes.c_uint),
                    ("AnimationId",   ctypes.c_int),
                ]

            class _WCA_DATA(ctypes.Structure):
                _fields_ = [
                    ("Attribute",  ctypes.c_int),
                    ("Data",       ctypes.c_void_p),
                    ("SizeOfData", ctypes.c_size_t),
                ]

            acc = _ACCENT()
            if acrylic_mode == "off":
                acc.AccentState   = 0  # ACCENT_DISABLED
                acc.AccentFlags   = 0
                acc.GradientColor = 0
            else:
                acc.AccentState   = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
                acc.AccentFlags   = 2  # draw on all edges
                acc.GradientColor = 0x44_12_12_1a  # tint

            wca = _WCA_DATA()
            wca.Attribute   = 19      # WCA_ACCENT_POLICY
            wca.SizeOfData  = ctypes.sizeof(acc)
            wca.Data        = ctypes.cast(ctypes.pointer(acc), ctypes.c_void_p)

            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(wca))

            if acrylic_mode == "off":
                self.configure(bg=theme.BG)
                self.attributes("-alpha", self._cfg.get("alpha", 0.93))
            else:
                self.configure(bg="#12121a")
                self.attributes("-alpha", 0.92)
        except Exception:
            pass   # silently ignored on unsupported systems


    # ── UI ────────────────────────────────────────────────────────────────────

    def apply_settings(self, new_cfg: dict):
        """Update configurations and rebuild UI if display mode or chart subplots changed."""
        old_disp = self._display
        old_rsi  = self._cfg.get("show_rsi", False)
        old_vol  = self._cfg.get("show_volume", False)

        self._cfg = new_cfg
        self._display = new_cfg.get("display", "chart")
        self._tf = new_cfg.get("timeframe", "日線")
        self._mode = new_cfg.get("chart_mode", "Line")
        
        # P&L Holdings
        self._qty  = float(self._cfg.get("qty", 0))
        self._cost = float(self._cfg.get("cost", 0))

        # Alert thresholds
        # Re-initialize alert manager if it doesn't exist, otherwise update existing alerts
        from widget.data.alert_manager import get_alert_manager
        self._alert_mgr = get_alert_manager()
        alert_above = self._cfg.get("alert_above")
        alert_below = self._cfg.get("alert_below")
        if alert_above or alert_below:
            self._alert_mgr.set_alert(
                self.symbol.upper(),
                above=float(alert_above) if alert_above else None,
                below=float(alert_below) if alert_below else None,
            )
        else:
            self._alert_mgr.clear_alert(self.symbol.upper())

        self.set_alpha(new_cfg.get("alpha", 0.93))
        self._locked = new_cfg.get("locked", False)
        
        new_rsi = new_cfg.get("show_rsi", False)
        new_vol = new_cfg.get("show_volume", False)

        # Rebuild UI if display mode changed, OR if chart subplots toggled
        if self._display != old_disp or new_rsi != old_rsi or new_vol != old_vol:
            for child in self.winfo_children():
                child.destroy()
            self._build_ui()
            # Feed current price data into the new UI
            if self._last_ticker_data:
                self._on_ticker_update(self._last_ticker_data)
        else:
            if self._display == "chart" and getattr(self, "_card", None):
                if hasattr(self._card, "_switch_tf"):
                    self._card._switch_tf(self._tf)
                if hasattr(self._card, "_switch_mode"):
                    self._card._switch_mode(self._mode)
            # Just updating P&L if holdings changed without changing chart layout
            if self._last_ticker_data:
                self._on_ticker_update(self._last_ticker_data)
        
        self._setup_window()
        self._adjust_height()

    def _build_ui(self):
        bg_tint = self._cfg.get("bg_tint")
        if bg_tint:
            bg_main = theme.mix_colors(bg_tint, theme.BG, 0.08)
            bg_hdr  = theme.mix_colors(bg_tint, theme.BG2, 0.12)
        else:
            bg_main = theme.BG
            bg_hdr  = theme.BG2

        outer = tk.Frame(self, bg=bg_main, padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        self._bind_targets = [self, outer]

        if self._display == "ticker":
            # ── Compact Ticker Layout ──
            self._hdr = tk.Frame(outer, bg=bg_hdr)
            self._hdr.pack(fill="both", expand=True)
            self._body = tk.Frame(outer) # Dummy body to prevent errors
            
            left_f = tk.Frame(self._hdr, bg=bg_hdr)
            left_f.pack(side="left", padx=14, fill="both", expand=True)
            right_f = tk.Frame(self._hdr, bg=bg_hdr)
            right_f.pack(side="right", padx=14, fill="y")
            
            # Left: Large Symbol
            sym_text = self.label.split()[0] if self.category == "台股" else self.symbol.replace(".TW", "")
            
            self._sym_lbl = tk.Label(left_f, text=sym_text, font=("Segoe UI", 16, "bold"), fg=theme.FG, bg=bg_hdr)
            self._sym_lbl.pack(side="left", anchor="w")
            
            # Right: Price (top) and Change (bottom)
            price_f = tk.Frame(right_f, bg=bg_hdr)
            price_f.pack(side="top", anchor="e", pady=(6, 0))
            
            self._pl_lbl = tk.Label(price_f, text="", font=("Segoe UI", 9, "bold"), fg=theme.FG_MUTED, bg=theme.BG3, padx=6)
            self._pl_lbl.pack(side="left", padx=(0, 6))
            if self._qty <= 0 or self._cost <= 0:
                self._pl_lbl.pack_forget()

            self._price_lbl = tk.Label(price_f, text="—", font=("Segoe UI", 16, "bold"), fg=theme.FG, bg=bg_hdr)
            self._price_lbl.pack(side="left")
            
            bot_f = tk.Frame(right_f, bg=bg_hdr)
            bot_f.pack(side="bottom", anchor="e", pady=(0, 6))
            self._change_lbl = tk.Label(bot_f, text="", font=("Segoe UI", 10), fg=theme.NEUTRAL, bg=bg_hdr)
            self._change_lbl.pack(side="left")
            self._arrow_lbl = tk.Label(bot_f, text="", font=("Segoe UI", 10), fg=theme.NEUTRAL, bg=bg_hdr)
            self._arrow_lbl.pack(side="left", padx=(2,0))

            # Dummies for chart-only components
            self._cat_lbl = tk.Label(self._hdr) 
            self._status_dot = tk.Label(self._hdr)

            self._bind_targets.extend([self._hdr, left_f, right_f, self._sym_lbl, 
                                       self._price_lbl, bot_f, self._change_lbl, self._arrow_lbl])
        else:
            # ── Original Chart Layout ──
            self._hdr = tk.Frame(outer, bg=bg_hdr, height=self.HEADER_H)
            self._hdr.pack(fill="x")
            self._hdr.pack_propagate(False)

            self._arrow_lbl = tk.Label(self._hdr, text="●", font=theme.FONT_TINY,
                                        fg=theme.NEUTRAL, bg=bg_hdr, width=2)
            self._arrow_lbl.pack(side="left", padx=(6, 2))

            self._sym_lbl = tk.Label(self._hdr, text=self.label, font=theme.FONT_BOLD,
                                      fg=theme.FG, bg=bg_hdr)
            self._sym_lbl.pack(side="left")

            self._cat_lbl = tk.Label(self._hdr, text=f"  {self.category}",
                                      font=theme.FONT_TINY, fg=theme.FG_DIM, bg=bg_hdr)
            self._cat_lbl.pack(side="left")

            self._status_dot = tk.Label(self._hdr, text="●", font=("Segoe UI", 9),
                                         fg=theme.FG_MUTED, bg=bg_hdr, width=2)
            self._status_dot.pack(side="left", padx=(4, 0))

            self._price_lbl = tk.Label(self._hdr, text="—", font=theme.FONT_MONO,
                                        fg=theme.FG, bg=bg_hdr)
            self._price_lbl.pack(side="right", padx=(0, 8))

            self._pl_lbl = tk.Label(self._hdr, text="", font=("Segoe UI", 8, "bold"),
                                    fg=theme.FG_MUTED, bg=theme.BG3, padx=4)
            self._pl_lbl.pack(side="right", padx=(0, 6))
            if self._qty <= 0 or self._cost <= 0:
                self._pl_lbl.pack_forget()

            self._change_lbl = tk.Label(self._hdr, text="", font=theme.FONT_SMALL,
                                         fg=theme.NEUTRAL, bg=bg_hdr)
            self._change_lbl.pack(side="right", padx=(0, 8))

            self._update_market_status()

            # Body (collapsible)
            self._body = tk.Frame(outer, bg=bg_main)
            self._body.pack(fill="both", expand=True)

            self._bind_targets.extend([self._hdr, self._sym_lbl, self._cat_lbl, self._arrow_lbl, 
                                       self._price_lbl, self._change_lbl, self._status_dot, self._body])

        self._build_body()

        # ── Resize grip (bottom-right) ──────────────────────────────
        self._grip = tk.Label(outer, text="⠿", font=("Segoe UI", 9),
                               fg=theme.FG_MUTED, bg=theme.BG,
                               cursor="size_nw_se")
        self._grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        self._grip.bind("<Button-1>",        self._on_resize_start)
        self._grip.bind("<B1-Motion>",       self._on_resize)
        self._grip.bind("<ButtonRelease-1>", self._on_resize_end)
        self._grip.bind("<Enter>", lambda e: self._grip.config(fg=theme.FG_DIM))
        self._grip.bind("<Leave>", lambda e: self._grip.config(fg=theme.FG_MUTED))

        # Bind drag & context menu to all surfaces
        for w in self._bind_targets:
            w.bind("<Button-1>",        self._on_drag_start)
            w.bind("<B1-Motion>",       self._on_drag)
            w.bind("<ButtonRelease-1>", self._on_drag_end)
            w.bind("<Button-3>",        self._show_ctx)
            w.bind("<Double-Button-1>", self._toggle_collapse)


    def _update_market_status(self):
        try:
            from widget.data.market_status import is_market_open
            is_open = is_market_open(self.category)
            color = theme.UP if is_open else theme.FG_MUTED
            self._status_dot.config(fg=color)
        except Exception:
            pass



    def _build_body(self):
        for child in self._body.winfo_children():
            child.destroy()

        if self._display == "chart":
            from widget.components.chart_card import ChartCard
            self._card = ChartCard(
                self._body, self.symbol, self.label, self.category,
                use_fugle=self._use_fugle,
                show_rsi=self._cfg.get("show_rsi", False),
                show_volume=self._cfg.get("show_volume", False),
                show_header=False,   # CardWindow has its own header
                base_color=self._cfg.get("chart_accent"),
                show_fundamentals=self._cfg.get("show_fundamentals", False)
            )
            # Wire callback so ChartCard pushes price updates up to our header
            self._card._header_cb = self._on_chart_price
            # Override default timeframe/mode
            self._card._tf   = self._tf
            self._card._mode = self._mode
            self._card.pack(fill="both", expand=True, padx=2, pady=(0, 4))
            self._card._load()
            self._card._refresh_btn_styles()

        else:
            # Ticker mode
            tk.Label(self._body, text="─ Ticker ─",
                     font=theme.FONT_TINY, fg=theme.FG_MUTED,
                     bg=theme.BG).pack(pady=4)
            self._card = None

        self._body.bind("<Button-3>", self._show_ctx)
        self._adjust_height()

    def _on_chart_price(self, arrow: str, color: str):
        """Callback from ChartCard: only update the dot/arrow color from the chart trend.
        Price and % remain from the live feed (or '—' if no feed yet)."""
        self._arrow_lbl.config(text=arrow, fg=color)


    def _adjust_height(self):
        """Resize the window to fit content."""
        self.update_idletasks()
        if self._collapsed:
            self.geometry(f"{self._cfg.get('card_width', 340)}x{self.HEADER_H + 4}")
            return
        if self._display == "chart":
            h = 230 if not self._cfg.get("show_rsi") else 310
            if self._cfg.get("show_fundamentals"):
                h += 28
        else:
            h = 66
        self.geometry(f"{self._cfg.get('card_width', 340)}x{h}")

    # ── Price update (called from feed threads via after()) ───────────────────

    def _on_ticker_update(self, data: dict):
        self._last_ticker_data = data
        price  = data.get("price", 0)
        change = data.get("change", 0)
        pct    = data.get("change_pct", 0)
        
        color = theme.UP if change > 0 else (theme.DOWN if change < 0 else theme.NEUTRAL)
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "—")
            
        sign   = "+" if change >= 0 else ""

        self._price_lbl.config(text=f"{price:,.2f}", fg=theme.FG)
        if self._display == "ticker":
            self._change_lbl.config(text=f"{sign}{change:,.2f} ({sign}{pct:.2f}%)", fg=color)
        else:
            self._change_lbl.config(text=f"{arrow} {sign}{pct:.2f}%", fg=color)
        self._arrow_lbl.config(text=arrow, fg=color)

        # ── Price Alert ─────────────────────────────────────────────────────
        if hasattr(self, "_alert_mgr") and price > 0:
            self._alert_mgr.check(self.symbol.upper(), price)

        # ── P&L (Holdings Simulation) ────────────────────────────────────────
        if getattr(self, "_pl_lbl", None) and self._pl_lbl.winfo_exists() and self._qty > 0 and self._cost > 0 and price > 0:
            pl_val = (price - self._cost) * self._qty
            pl_pct = (price / self._cost - 1) * 100
            
            # SWISH style embedded tag (dark muted green/red base)
            bg_color = "#1e3a29" if pl_val >= 0 else "#4a1c1c"
            fg_color = theme.UP if pl_val >= 0 else theme.DOWN
            
            self._pl_lbl.config(
                text=f"P/L: {pl_pct:+.2f}%",
                fg=fg_color,
                bg=bg_color
            )

        if hasattr(self._card, "update_ticker"):
            self._card.update_ticker(data)
        elif hasattr(self._card, "update_data"):
            self._card.update_data(data)

    # ── Context menu actions ──────────────────────────────────────────────────

    def _toggle_fundamentals(self):
        current = self._cfg.get("show_fundamentals", False)
        self._cfg["show_fundamentals"] = not current
        self.after(50, self._rebuild_all)

    def _rebuild_all(self):
        for w in self.winfo_children():
            w.destroy()
        self._setup_window()
        self._build_ui()
        if self._last_ticker_data:
            self._on_ticker_update(self._last_ticker_data)

    def _pick_bg_tint(self):
        from tkinter import colorchooser
        current = self._cfg.get("bg_tint", theme.ACCENT)
        _, hex_color = colorchooser.askcolor(initialcolor=current, title="選擇背景色調", parent=self)
        if hex_color:
            self._cfg["bg_tint"] = hex_color
            self.after(50, self._rebuild_all)
            
    def _pick_chart_accent(self):
        from tkinter import colorchooser
        current = self._cfg.get("chart_accent", theme.ACCENT)
        _, hex_color = colorchooser.askcolor(initialcolor=current, title="選擇圖表與文字色", parent=self)
        if hex_color:
            self._cfg["chart_accent"] = hex_color
            self.after(50, self._rebuild_all)
            
    def _pick_fund_color(self):
        from tkinter import colorchooser
        current = self._cfg.get("fund_color", theme.FG)
        _, hex_color = colorchooser.askcolor(initialcolor=current, title="選擇基本面文字色", parent=self)
        if hex_color:
            self._cfg["fund_color"] = hex_color
            self.after(50, self._rebuild_all)
                
    def _reset_color(self):
        changed = False
        if "bg_tint" in self._cfg:
            del self._cfg["bg_tint"]
            changed = True
        if "chart_accent" in self._cfg:
            del self._cfg["chart_accent"]
            changed = True
        if "fund_color" in self._cfg:
            del self._cfg["fund_color"]
            changed = True
        if changed:
            self.after(50, self._rebuild_all)

    def _set_tf(self, tf: str):
        self._tf = tf
        self._cfg["timeframe"] = tf
        if hasattr(self, "_card") and hasattr(self._card, "_switch_tf"):
            self._card._switch_tf(tf)
        # Rebuild context menu to update checkmarks
        self._setup_window()

    def _set_mode(self, mode: str):
        self._mode = mode
        self._cfg["chart_mode"] = mode
        if hasattr(self, "_card") and hasattr(self._card, "_switch_mode"):
            self._card._switch_mode(mode)
        self._setup_window()

    def _toggle_lock(self):
        self._locked = not self._locked
        self._cfg["locked"] = self._locked
        self._setup_window()   # rebuild menu so label updates

    def _reload_chart(self):
        if hasattr(self, "_card") and hasattr(self._card, "_load"):
            self._card._load()

    def _remove_self(self):
        self._on_remove(self.symbol)
        self.destroy()

    def _show_ctx(self, event):
        try:
            self._ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx.grab_release()

    # ── Collapse / expand ─────────────────────────────────────────────────────

    def _toggle_collapse(self, event=None):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._body.pack_forget()
        else:
            self._body.pack(fill="both", expand=True)
        self._adjust_height()

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _on_drag_start(self, event):
        if self._locked:
            return
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag(self, event):
        if self._locked:
            return
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _on_drag_end(self, event):
        if self._locked:
            return
        self._cfg["pos_x"] = self.winfo_x()
        self._cfg["pos_y"] = self.winfo_y()

    # ── Resize ────────────────────────────────────────────────────────────────

    def _on_resize_start(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.winfo_width()
        self._resize_start_h = self.winfo_height()

    def _on_resize(self, event):
        MIN_W, MAX_W = 220, 700
        MIN_H, MAX_H = self.HEADER_H + 40, 600
        dw = event.x_root - self._resize_start_x
        dh = event.y_root - self._resize_start_y
        new_w = max(MIN_W, min(MAX_W, self._resize_start_w + dw))
        new_h = max(MIN_H, min(MAX_H, self._resize_start_h + dh))
        x = self.winfo_x()
        y = self.winfo_y()
        self.geometry(f"{new_w}x{new_h}+{x}+{y}")

    def _on_resize_end(self, event):
        self._cfg["card_width"] = self.winfo_width()
        # Save height so it persists
        self._cfg["card_height"] = self.winfo_height()

    # ── Opacity ───────────────────────────────────────────────────────────────

    def set_alpha(self, alpha: float):
        self.attributes("-alpha", max(0.1, min(1.0, alpha)))
