"""
ManagerPanel — Central control panel for all stock widget cards.

Layout (Swish Finance style):
  ┌─────────────────────────────────────────────────────────┐
  │  ◈ Stock Widget Manager                            [✕]  │
  ├──────────────┬──────────────────────────────────────────┤
  │  [+] 新增    │   [Selected card name]                   │
  │  [⊞] 排列    │                                          │
  │  [⚙] 速率    │   General: timeframe / mode / lock       │
  │  ─────────   │           opacity / width / show_rsi     │
  │  ● BTC/USDT  │                                          │
  │  ● NVDA      │   (empty when nothing selected)          │
  │  ● 台積電    │                                          │
  │    ...       │                                          │
  └──────────────┴──────────────────────────────────────────┘
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

from widget.style import theme

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "widget_config.json")
CATEGORIES  = ["Crypto", "美股", "ETF", "台股"]
DISPLAYS    = ["ticker", "chart"]


# ── Custom Toggle Switch ──────────────────────────────────────────────────────
class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable=None, command=None, *args, **kwargs):
        super().__init__(parent, width=44, height=24, bg=theme.BG, highlightthickness=0, *args, **kwargs)
        self.var = variable if variable else tk.BooleanVar(value=False)
        self.command = command
        
        self.bind("<Button-1>", self.toggle)
        self.var.trace_add("write", lambda *a: self.update_view())
        
        # Draw base capsule
        self.bg_id = self.create_oval(2, 2, 22, 22, fill=theme.BG3, outline="")
        self.bg_id2 = self.create_oval(22, 2, 42, 22, fill=theme.BG3, outline="")
        self.bg_rect = self.create_rectangle(12, 2, 32, 22, fill=theme.BG3, outline="")
        
        # Draw thumb
        self.thumb = self.create_oval(4, 4, 20, 20, fill=theme.FG_DIM, outline="")
        
        self.update_view()

    def toggle(self, event=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def update_view(self):
        state = self.var.get()
        # Colors
        bg_color = theme.UP if state else theme.BG3
        thumb_color = "#ffffff" if state else theme.FG_DIM
        # Animate positions natively (simple jump for now, we can animate later if needed)
        x_offset = 20 if state else 0
        
        self.itemconfig(self.bg_id, fill=bg_color)
        self.itemconfig(self.bg_id2, fill=bg_color)
        self.itemconfig(self.bg_rect, fill=bg_color)
        self.itemconfig(self.thumb, fill=thumb_color)
        self.coords(self.thumb, 4 + x_offset, 4, 20 + x_offset, 20)

# ── Style Configuration ──────────────────────────────────────────────────────
def setup_ttk_styles():
    style = ttk.Style()
    style.theme_use('default')
    
    style.configure("Modern.TNotebook", 
                    background=theme.BG, 
                    borderwidth=0, 
                    padding=0)
                    
    style.configure("Modern.TNotebook.Tab", 
                    background=theme.BG2, 
                    foreground=theme.FG_DIM,
                    padding=[12, 6], 
                    borderwidth=0,
                    font=theme.FONT_SMALL)
                    
    style.map("Modern.TNotebook.Tab",
              background=[("selected", theme.BG)],
              foreground=[("selected", theme.FG)])
              
    # Inner frames
    style.configure("Modern.TFrame", background=theme.BG)


class ManagerPanel(tk.Toplevel):
    """Centralized widget management window."""

    SIDEBAR_W = 200

    def __init__(self, parent, config: dict,
                 cards: dict,            # symbol.upper() → CardWindow
                 on_save=None,
                 on_arrange=None,
                 **kwargs):
        super().__init__(parent)
        self._cfg       = config
        self._cards     = cards
        self._on_save   = on_save
        self._on_arrange = on_arrange
        self._on_rebuild = kwargs.get("on_rebuild")   # callable() → rebuild all cards
        self._sel_sym   = None           # currently selected symbol
        self._brightness_timer = None

        self.title("◈ Stock Widget 管理")
        
        # Set custom window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo_nobackground.png")
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.iconphoto(False, img)
            except Exception:
                pass
                
        self.resizable(True, True)
        self.minsize(640, 480)
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)

        setup_ttk_styles()

        self._build()
        self.geometry("760x540")
        self._select_first()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        tbar = tk.Frame(self, bg=theme.BG2, height=40)
        tbar.pack(fill="x")
        tbar.pack_propagate(False)
        
        # Load and resize logo for title bar
        self._title_img = None
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo_nobackground.png")
        if os.path.exists(icon_path):
            try:
                from PIL import Image, ImageTk
                pil_img = Image.open(icon_path).resize((24, 24), Image.Resampling.LANCZOS)
                self._title_img = ImageTk.PhotoImage(pil_img)
            except Exception:
                pass

        if self._title_img:
            tk.Label(tbar, image=self._title_img, bg=theme.BG2).pack(side="left", padx=(12, 6))
            tk.Label(tbar, text="Stock Widget 管理",
                     font=("Segoe UI", 12, "bold"),
                     fg=theme.ACCENT, bg=theme.BG2).pack(side="left")
        else:
            tk.Label(tbar, text="◈  Stock Widget 管理",
                     font=("Segoe UI", 12, "bold"),
                     fg=theme.ACCENT, bg=theme.BG2).pack(side="left", padx=12)

        tk.Button(tbar, text="✕", command=self.destroy,
                  bg=theme.BG2, fg=theme.FG_DIM,
                  activebackground=theme.DOWN, activeforeground=theme.FG,
                  font=("Segoe UI", 12), bd=0, relief="flat",
                  padx=10, cursor="hand2").pack(side="right")

        # Main pane
        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True)

        # ── Left sidebar ───────────────────────────────────────────
        self._sidebar = tk.Frame(body, bg=theme.BG2,
                                  width=self.SIDEBAR_W,
                                  highlightbackground=theme.BORDER,
                                  highlightthickness=1)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # ── Right content ──────────────────────────────────────────
        self._right = tk.Frame(body, bg=theme.BG)
        self._right.pack(side="left", fill="both", expand=True)
        self._build_welcome()

    def _build_sidebar(self):
        for w in self._sidebar.winfo_children():
            w.destroy()

        # Action buttons
        on_top = self._cfg.get("always_on_top", True)
        top_btn_lbl = "📌 取消最上層" if on_top else "📌 總在最上層"

        acrylic = self._cfg.get("acrylic_mode", "off")
        acrylic_labels = {"off": "🪟 毛玻璃: 關閉", "acrylic": "🪟 毛玻璃: Acrylic", "mica": "🪟 毛玻璃: Mica"}
        acrylic_btn_lbl = acrylic_labels.get(acrylic, "🪟 毛玻璃: 關閉")

        actions = [
            ("➕ 新增標的",      self._open_add),
            ("⊞ 整齊排列",      self._arrange),
            ("⚡ 速率設定",      self._open_rate_settings),
            (top_btn_lbl,      self._toggle_always_on_top),
            (acrylic_btn_lbl,  self._cycle_acrylic),
        ]
        for txt, cmd in actions:
            tk.Button(self._sidebar, text=txt, command=cmd,
                      bg=theme.BG3, fg=theme.FG,
                      activebackground=theme.ACCENT,
                      activeforeground=theme.FG,
                      font=theme.FONT_SMALL, bd=0, relief="flat",
                      anchor="w", padx=12, pady=6,
                      cursor="hand2").pack(fill="x", padx=6, pady=2)

        tk.Frame(self._sidebar, bg=theme.BORDER, height=1).pack(
            fill="x", padx=6, pady=8)

        # ── Brightness slider ────────────────────────────────────────────
        bright_frame = tk.Frame(self._sidebar, bg=theme.BG2)
        bright_frame.pack(fill="x", padx=6, pady=(0, 4))

        tk.Label(bright_frame, text="☀ 亮度", font=theme.FONT_TINY,
                 fg=theme.FG_DIM, bg=theme.BG2).pack(side="left", padx=(8, 4))

        self._bright_var = tk.IntVar(value=self._cfg.get("bg_lightness", 0))

        def _on_bright_change(val):
            v = int(float(val))
            self._cfg["bg_lightness"] = v
            from widget.style.theme import set_lightness
            set_lightness(v)
            # Debounce: wait 300ms of no movement before rebuilding all cards
            if self._brightness_timer:
                self.after_cancel(self._brightness_timer)
            self._brightness_timer = self.after(300, self._do_brightness_rebuild)

        def _toggle_theme():
            current = self._bright_var.get()
            now_light = 100 if current < 50 else 0
            self._bright_var.set(now_light)
            _on_bright_change(now_light)

        theme_btn = tk.Button(bright_frame, text="黑/白", font=theme.FONT_TINY,
                              fg=theme.FG_DIM, bg=theme.BG3, bd=0, relief="flat",
                              cursor="hand2", command=_toggle_theme)
        theme_btn.pack(side="left", padx=(0, 4))

        tk.Scale(bright_frame, from_=0, to=100,
                 orient="horizontal", variable=self._bright_var,
                 command=_on_bright_change,
                 bg=theme.BG2, fg=theme.FG_DIM,
                 troughcolor=theme.BG3, highlightthickness=0,
                 showvalue=False, sliderlength=12, length=120,
                 activebackground=theme.ACCENT).pack(side="left", fill="x", expand=True)

        tk.Label(bright_frame, textvariable=self._bright_var,
                 font=theme.FONT_TINY, fg=theme.ACCENT,
                 bg=theme.BG2, width=3).pack(side="left", padx=(2, 8))

        tk.Frame(self._sidebar, bg=theme.BORDER, height=1).pack(
            fill="x", padx=6, pady=4)

        # Card list with Scrollbar
        self._list_wrapper = tk.Frame(self._sidebar, bg=theme.BG2)
        self._list_wrapper.pack(fill="both", expand=True)

        self._list_canvas = tk.Canvas(self._list_wrapper, bg=theme.BG2, highlightthickness=0)
        self._list_scrollbar = tk.Scrollbar(self._list_wrapper, orient="vertical", command=self._list_canvas.yview)
        
        self._list_frame = tk.Frame(self._list_canvas, bg=theme.BG2)
        
        self._list_canvas.configure(yscrollcommand=self._list_scrollbar.set)
        
        self._list_scrollbar.pack(side="right", fill="y")
        self._list_canvas.pack(side="left", fill="both", expand=True)
        
        self._list_window = self._list_canvas.create_window((0, 0), window=self._list_frame, anchor="nw")
        
        def _configure_list_frame(event):
            self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))
        self._list_frame.bind("<Configure>", _configure_list_frame)
        
        def _configure_canvas(event):
            self._list_canvas.itemconfig(self._list_window, width=event.width)
        self._list_canvas.bind("<Configure>", _configure_canvas)
        
        def _on_mousewheel(event):
            # Only scroll if content is taller than canvas
            if self._list_canvas.winfo_height() < self._list_frame.winfo_reqheight():
                self._list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._list_wrapper.bind("<Enter>", lambda e: self._list_wrapper.bind_all("<MouseWheel>", _on_mousewheel))
        self._list_wrapper.bind("<Leave>", lambda e: self._list_wrapper.unbind_all("<MouseWheel>"))

        self._rebuild_list()

    def _rebuild_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        cat_colors = {
            "Crypto": "#f7931a", "美股": theme.ACCENT,
            "ETF": theme.ACCENT2, "台股": "#00e676",
        }

        for item in self._cfg.get("watchlist", []):
            sym   = item["symbol"].upper()
            label = item.get("label", sym)
            cat   = item.get("category", "")
            dot_c = cat_colors.get(cat, theme.NEUTRAL)

            row = tk.Frame(self._list_frame, bg=theme.BG2, cursor="hand2")
            row.pack(fill="x")

            is_sel = sym == self._sel_sym
            bg  = theme.BG3 if is_sel else theme.BG2
            row.configure(bg=bg)

            tk.Label(row, text="●", font=theme.FONT_TINY,
                     fg=dot_c, bg=bg, width=2).pack(side="left", padx=(8, 0))
            tk.Label(row, text=label, font=theme.FONT_SMALL,
                     fg=theme.FG if is_sel else theme.FG_DIM,
                     bg=bg, anchor="w").pack(side="left", fill="x",
                                              expand=True, pady=5)

            row.bind("<Button-1>", lambda e, s=sym: self._select(s))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, s=sym: self._select(s))

    # ── Selection / right panel ───────────────────────────────────────────────

    def _select_first(self):
        wl = self._cfg.get("watchlist", [])
        if wl:
            self._select(wl[0]["symbol"].upper())

    def _select(self, symbol: str):
        self._sel_sym = symbol
        self._rebuild_list()
        item = next((i for i in self._cfg.get("watchlist", [])
                      if i["symbol"].upper() == symbol), None)
        if item:
            self._build_card_settings(item)

    def _build_welcome(self):
        for w in self._right.winfo_children():
            w.destroy()
        tk.Label(self._right,
                 text="← 請從左側選擇標的",
                 font=("Segoe UI", 13), fg=theme.FG_DIM,
                 bg=theme.BG).pack(expand=True)

    def _build_card_settings(self, item: dict):
        for w in self._right.winfo_children():
            w.destroy()

        sym   = item["symbol"].upper()
        label = item.get("label", sym)
        cat   = item.get("category", "")

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(self._right, bg=theme.BG, pady=12)
        hdr.pack(fill="x", padx=16)

        tk.Label(hdr, text=sym, font=("Consolas", 22, "bold"),
                 fg=theme.FG, bg=theme.BG).pack(anchor="w")
        tk.Label(hdr, text=label, font=("Segoe UI", 11),
                 fg=theme.FG_DIM, bg=theme.BG).pack(anchor="w")

        tk.Frame(self._right, bg=theme.BORDER, height=1).pack(
            fill="x", padx=16)

        # ── Settings Notebook (Tabs) ──────────────────────────────
        notebook = ttk.Notebook(self._right, style="Modern.TNotebook")
        notebook.pack(fill="both", expand=True, padx=16, pady=10)

        tab_gen = ttk.Frame(notebook, style="Modern.TFrame")
        tab_disp = ttk.Frame(notebook, style="Modern.TFrame")
        tab_hold = ttk.Frame(notebook, style="Modern.TFrame")

        notebook.add(tab_gen, text="一般設定")
        notebook.add(tab_disp, text="顯示")
        notebook.add(tab_hold, text="持倉與通知")

        vars_ = {}

        def row(parent_tab, label_text, widget_factory, key):
            r = tk.Frame(parent_tab, bg=theme.BG)
            r.pack(fill="x", pady=8)
            tk.Label(r, text=label_text, font=theme.FONT_SMALL,
                     fg=theme.FG_DIM, bg=theme.BG,
                     width=16, anchor="w").pack(side="left")
            w = widget_factory(r)
            w.pack(side="left", fill="x", expand=True)
            vars_[key] = w
            return w

        # === TAB: GENERAL ===
        
        # Display type
        disp_var = tk.StringVar(value=item.get("display", "ticker"))
        def mk_disp(p):
            f = tk.Frame(p, bg=theme.BG)
            for opt in DISPLAYS:
                tk.Radiobutton(f, text=opt, variable=disp_var, value=opt,
                                bg=theme.BG, fg=theme.FG,
                                selectcolor=theme.BG3,
                                activebackground=theme.BG,
                                font=theme.FONT_SMALL).pack(side="left", padx=6)
            return f
        row(tab_gen, "顯示方式", mk_disp, "display")

        # Timeframe (only for chart)
        tf_var = tk.StringVar(value=item.get("timeframe", "日線"))
        def mk_tf(p):
            om = tk.OptionMenu(p, tf_var, *theme.TIMEFRAMES)
            _style_menu(om); return om
        row(tab_gen, "時間框架", mk_tf, "timeframe")

        # Chart mode
        mode_var = tk.StringVar(value=item.get("chart_mode", "Line"))
        def mk_mode(p):
            om = tk.OptionMenu(p, mode_var, "Line", "K棒", "OHLC")
            _style_menu(om); return om
        row(tab_gen, "圖表類型", mk_mode, "chart_mode")

        # Width
        w_var = tk.IntVar(value=item.get("card_width", 340))
        def mk_width(p):
            f = tk.Frame(p, bg=theme.BG)
            sl = tk.Scale(f, from_=260, to=600, orient="horizontal",
                           variable=w_var, bg=theme.BG, fg=theme.FG_DIM,
                           troughcolor=theme.BG3, highlightthickness=0,
                           showvalue=False, length=160,
                           activebackground=theme.ACCENT)
            sl.pack(side="left")
            tk.Label(f, textvariable=w_var, font=theme.FONT_BOLD,
                      fg=theme.ACCENT, bg=theme.BG, width=4).pack(side="left")
            return f
        row(tab_gen, "卡片寬度", mk_width, "_w_var")

        # Locked
        lock_var = tk.BooleanVar(value=item.get("locked", False))
        def mk_lock(p):
            return ToggleSwitch(p, variable=lock_var)
        row(tab_gen, "鎖定位置", mk_lock, "locked")

        # === TAB: DISPLAY ===

        # Opacity
        alpha_var = tk.DoubleVar(value=item.get("alpha", 0.93))
        def mk_alpha(p):
            f = tk.Frame(p, bg=theme.BG)
            sl = tk.Scale(f, from_=0.2, to=1.0, resolution=0.01,
                           orient="horizontal", variable=alpha_var,
                           bg=theme.BG, fg=theme.FG_DIM,
                           troughcolor=theme.BG3, highlightthickness=0,
                           showvalue=False, length=160,
                           activebackground=theme.ACCENT)
            sl.pack(side="left")
            tk.Label(f, textvariable=alpha_var, font=theme.FONT_BOLD,
                      fg=theme.ACCENT, bg=theme.BG, width=4).pack(side="left")
            return f
        row(tab_disp, "透明度", mk_alpha, "_alpha_var")

        # Show RSI
        rsi_var = tk.BooleanVar(value=item.get("show_rsi", False))
        def mk_rsi(p):
            return ToggleSwitch(p, variable=rsi_var)
        row(tab_disp, "顯示 RSI", mk_rsi, "show_rsi")

        # Show Volume
        vol_var = tk.BooleanVar(value=item.get("show_volume", False))
        def mk_vol(p):
            return ToggleSwitch(p, variable=vol_var)
        row(tab_disp, "顯示 Volume", mk_vol, "show_volume")


        # === TAB: HOLDINGS & ALERTS ===
        
        def mk_num_entry(p, var):
            e = tk.Entry(p, textvariable=var, font=theme.FONT_SMALL,
                         bg=theme.BG3, fg=theme.FG,
                         insertbackground=theme.FG, bd=0,
                         highlightbackground=theme.BORDER, highlightthickness=1,
                         width=18)
            e.pack(side="left", ipady=3, ipadx=4) # better padding
            return e

        qty_var = tk.StringVar(value=str(item.get("qty", "")))
        row(tab_hold, "持股數量", lambda p: mk_num_entry(p, qty_var), "qty")

        cost_var = tk.StringVar(value=str(item.get("cost", "")))
        row(tab_hold, "成本價", lambda p: mk_num_entry(p, cost_var), "cost")

        tk.Frame(tab_hold, bg=theme.BORDER, height=1).pack(fill="x", pady=8)

        alert_above_var = tk.StringVar(value=str(item.get("alert_above", "")))
        row(tab_hold, "高於 X 時通知", lambda p: mk_num_entry(p, alert_above_var), "alert_above")

        alert_below_var = tk.StringVar(value=str(item.get("alert_below", "")))
        row(tab_hold, "低於 X 時通知", lambda p: mk_num_entry(p, alert_below_var), "alert_below")


        # ── Action buttons ─────────────────────────────────────────
        btn_row = tk.Frame(self._right, bg=theme.BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        def _apply():
            item["display"]    = disp_var.get()
            item["timeframe"]  = tf_var.get()
            item["chart_mode"] = mode_var.get()
            item["card_width"] = w_var.get()
            item["alpha"]      = round(alpha_var.get(), 2)
            item["show_rsi"]   = rsi_var.get()
            item["locked"]     = lock_var.get()
            item["show_volume"] = vol_var.get()
            # Holdings
            try: item["qty"]  = float(qty_var.get()) if qty_var.get() else 0
            except: item["qty"] = 0
            try: item["cost"] = float(cost_var.get()) if cost_var.get() else 0
            except: item["cost"] = 0
            # Alerts
            try: item["alert_above"] = float(alert_above_var.get()) if alert_above_var.get() else None
            except: item["alert_above"] = None
            try: item["alert_below"] = float(alert_below_var.get()) if alert_below_var.get() else None
            except: item["alert_below"] = None
            # Apply to live card immediately
            card = self._cards.get(sym)
            if card:
                card.apply_settings(item)
            self._save()

        def _remove():
            if messagebox.askyesno("確認移除",
                                    f"確定移除「{label}」？",
                                    parent=self):
                card = self._cards.get(sym)
                if card:
                    # Use card's own remove callback — this also clears WidgetManager._listeners
                    card._on_remove(card.symbol)
                    card.destroy()
                else:
                    # Card already gone, just clean config
                    self._cfg["watchlist"] = [
                        i for i in self._cfg["watchlist"]
                        if i["symbol"].upper() != sym
                    ]
                self._sel_sym = None
                self._save()
                self._rebuild_list()
                self._build_welcome()

        tk.Button(btn_row, text="✓ 套用", command=_apply,
                  bg=theme.ACCENT, fg=theme.FG,
                  activebackground=theme.ACCENT2,
                  font=theme.FONT_BOLD, bd=0, relief="flat",
                  padx=14, pady=5, cursor="hand2").pack(side="left", padx=(0, 6))

        tk.Button(btn_row, text="🗑 移除", command=_remove,
                  bg=theme.BG3, fg=theme.DOWN,
                  activebackground=theme.DOWN,
                  activeforeground=theme.FG,
                  font=theme.FONT_SMALL, bd=0, relief="flat",
                  padx=10, pady=5, cursor="hand2").pack(side="left")

        # Focus on live card
        card = self._cards.get(sym)
        if card:
            card.lift()

    # ── Global actions ────────────────────────────────────────────────────────

    def _arrange(self):
        if self._on_arrange:
            self._on_arrange()

    def _do_brightness_rebuild(self):
        """Called after the brightness slider settles — rebuild cards with new colors."""
        self._save()
        if self._on_rebuild:
            self._on_rebuild()
        # Refresh sidebar colors with new theme
        self._build_sidebar()

    def _cycle_acrylic(self):
        """Cycle acrylic_mode: off → acrylic → mica → off."""
        cycle = {"off": "acrylic", "acrylic": "mica", "mica": "off"}
        current = self._cfg.get("acrylic_mode", "off")
        self._cfg["acrylic_mode"] = cycle.get(current, "off")
        self._save()
        self._build_sidebar()  # update button label
        # Apply to all live cards
        for card in self._cards.values():
            try:
                card._apply_acrylic()
            except Exception:
                pass

    def _toggle_always_on_top(self):
        current = self._cfg.get("always_on_top", True)
        self._cfg["always_on_top"] = not current
        self._save()
        self._build_sidebar()  # update button text
        
        # Apply to all live cards
        is_top = self._cfg["always_on_top"]
        for card in self._cards.values():
            try:
                card.attributes("-topmost", is_top)
            except Exception:
                pass

    def _open_add(self):
        """Smart add-symbol dialog with auto-lookup."""
        import threading
        from widget.data.symbol_lookup import lookup_symbol, guess_category

        dlg = tk.Toplevel(self)
        dlg.title("新增標的")
        dlg.configure(bg=theme.BG)
        dlg.resizable(False, False)
        dlg.geometry("360x340")
        dlg.attributes("-topmost", True)

        # ── Symbol input ──────────────────────────────────────────
        tk.Label(dlg, text="代號 (如 AAPL / 2317 / BTCUSDT)",
                 font=theme.FONT_SMALL, fg=theme.FG_DIM,
                 bg=theme.BG).pack(anchor="w", padx=16, pady=(14, 0))

        sym_v = tk.StringVar()
        sym_entry = tk.Entry(dlg, textvariable=sym_v, font=("Consolas", 13),
                             bg=theme.BG3, fg=theme.FG,
                             insertbackground=theme.FG, bd=0,
                             highlightbackground=theme.BORDER,
                             highlightthickness=1)
        sym_entry.pack(fill="x", padx=16, ipady=4)
        sym_entry.focus_set()

        # ── Preview card ──────────────────────────────────────────
        preview = tk.Frame(dlg, bg=theme.BG3,
                            highlightbackground=theme.BORDER,
                            highlightthickness=1)
        preview.pack(fill="x", padx=16, pady=(10, 0))

        cat_colors = {"Crypto": "#f7931a", "美股": theme.ACCENT,
                      "ETF": theme.ACCENT2, "台股": "#00e676"}

        dot_lbl  = tk.Label(preview, text="●", font=theme.FONT_SMALL,
                             fg=theme.NEUTRAL, bg=theme.BG3, width=2)
        dot_lbl.pack(side="left", padx=(8, 0), pady=6)
        name_lbl = tk.Label(preview, text="輸入代號後自動查詢…",
                             font=theme.FONT_BOLD, fg=theme.FG_DIM,
                             bg=theme.BG3, anchor="w")
        name_lbl.pack(side="left", expand=True, fill="x")
        cat_badge = tk.Label(preview, text="", font=theme.FONT_TINY,
                              fg=theme.BG, bg=theme.NEUTRAL,
                              padx=6, pady=1)
        cat_badge.pack(side="right", padx=8)

        status_lbl = tk.Label(dlg, text="", font=theme.FONT_TINY,
                               fg=theme.FG_DIM, bg=theme.BG)
        status_lbl.pack(anchor="w", padx=16)

        # ── Editable fields (auto-filled, manually overridable) ───
        lbl_v  = tk.StringVar()
        cat_v  = tk.StringVar(value="美股")
        disp_v = tk.StringVar(value="chart")

        def mk_row(text, var, opts=None):
            r = tk.Frame(dlg, bg=theme.BG); r.pack(fill="x", padx=16, pady=(4, 0))
            tk.Label(r, text=text, font=theme.FONT_SMALL, fg=theme.FG_DIM,
                     bg=theme.BG, width=9, anchor="w").pack(side="left")
            if opts:
                om = tk.OptionMenu(r, var, *opts)
                _style_menu(om); om.pack(side="left", fill="x", expand=True)
            else:
                tk.Entry(r, textvariable=var, font=theme.FONT_SMALL,
                         bg=theme.BG3, fg=theme.FG, insertbackground=theme.FG,
                         bd=0, highlightbackground=theme.BORDER,
                         highlightthickness=1).pack(side="left", fill="x", expand=True, ipady=2)

        mk_row("顯示名稱", lbl_v)
        mk_row("分類",     cat_v,  CATEGORIES)
        mk_row("顯示方式", disp_v, DISPLAYS)

        # ── Add button ────────────────────────────────────────────
        def _ok():
            sym = sym_v.get().strip().upper()
            if not sym:
                messagebox.showwarning("錯誤", "請輸入代號！", parent=dlg); return
            # Use auto-detected sym from lookup if available
            norm_sym, _ = guess_category(sym)
            entry = {
                "symbol":    norm_sym,
                "label":     lbl_v.get().strip() or norm_sym,
                "category":  cat_v.get(),
                "display":   disp_v.get(),
                "pos_x": 200, "pos_y": 200,
                "card_width": 340, "show_rsi": False, "locked": False,
            }
            if cat_v.get() == "Crypto":
                entry["base_currency"] = "USDT"
            self._cfg.setdefault("watchlist", []).append(entry)
            self._save()
            self._rebuild_list()
            if self._on_save:
                self._on_save()
            dlg.destroy()

        tk.Button(dlg, text="➕ 新增", command=_ok,
                  bg=theme.ACCENT, fg=theme.FG,
                  activebackground=theme.ACCENT2,
                  font=theme.FONT_BOLD, bd=0, relief="flat",
                  padx=14, pady=5, cursor="hand2").pack(anchor="e", padx=16, pady=12)

        # ── Auto-lookup on typing (debounced 700ms) ───────────────
        _lookup_after = [None]
        _last_sym     = [""]

        def _do_lookup(raw: str):
            if raw == _last_sym[0]:
                return
            _last_sym[0] = raw
            status_lbl.config(text="查詢中…", fg=theme.FG_DIM)

            def _worker():
                result = lookup_symbol(raw)
                dlg.after(0, lambda: _apply_result(result))

            threading.Thread(target=_worker, daemon=True).start()

        def _apply_result(r: dict):
            try:
                # Update preview
                c  = r["category"]
                dot_lbl.config(fg=cat_colors.get(c, theme.NEUTRAL))
                name_lbl.config(text=r["label"], fg=theme.FG)
                cat_badge.config(text=c, bg=cat_colors.get(c, theme.NEUTRAL))
                # Auto-fill editable fields (user can still change)
                if not lbl_v.get():   lbl_v.set(r["label"])
                cat_v.set(c)
                status_lbl.config(
                    text="✓ 已找到" if r["found"] else "⚠ 未找到公司名稱，可手動填入",
                    fg=theme.UP if r["found"] else theme.NEUTRAL)
            except tk.TclError:
                pass   # dialog was closed

        def _on_key(*_):
            if _lookup_after[0]:
                dlg.after_cancel(_lookup_after[0])
            raw = sym_v.get().strip()
            if len(raw) < 2:
                return
            # Instant category guess (no network)
            norm, cat = guess_category(raw)
            dot_lbl.config(fg=cat_colors.get(cat, theme.NEUTRAL))
            cat_badge.config(text=cat, bg=cat_colors.get(cat, theme.NEUTRAL))
            cat_v.set(cat)
            # Debounce full lookup to 700ms
            _lookup_after[0] = dlg.after(700, lambda: _do_lookup(raw))

        sym_v.trace_add("write", _on_key)

        # Also trigger on Enter
        sym_entry.bind("<Return>", lambda e: _do_lookup(sym_v.get().strip()))


    def _open_rate_settings(self):
        from widget.components.settings_panel import SettingsPanel
        dlg = SettingsPanel(self, self._cfg, on_save=self._save)
        # Only show rate limit section — SettingsPanel already has it

    def _save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("儲存失敗", str(e), parent=self)


# ── helper ────────────────────────────────────────────────────────────────────

def _style_menu(menu: tk.OptionMenu):
    menu.configure(bg=theme.BG3, fg=theme.FG,
                    activebackground=theme.ACCENT,
                    activeforeground=theme.FG,
                    font=theme.FONT_SMALL, bd=0,
                    relief="flat", highlightthickness=0)
    menu["menu"].configure(bg=theme.BG3, fg=theme.FG,
                            activebackground=theme.ACCENT,
                            font=theme.FONT_SMALL)
