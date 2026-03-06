"""
Settings panel — tkinter Toplevel for watchlist management + rate limits.
"""

import json
import os
import tkinter as tk
from tkinter import messagebox

from widget.style import theme

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "widget_config.json")
CATEGORIES  = ["Crypto", "美股", "ETF", "台股"]
DISPLAYS    = ["ticker", "chart"]


class SettingsPanel(tk.Toplevel):
    """Settings window: manage watchlist + control rate limits."""

    def __init__(self, parent, config: dict, on_save=None):
        super().__init__(parent)
        self.config_data = config
        self.on_save_cb  = on_save
        self.title("⚙ Stock Widget 設定")
        self.resizable(False, False)
        self.configure(bg=theme.BG)
        self._build()
        self.grab_set()   # modal

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        pw = tk.PanedWindow(self, orient="horizontal", bg=theme.BG,
                             sashwidth=1)
        pw.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: watchlist
        left = tk.Frame(pw, bg=theme.BG)
        pw.add(left, width=320)
        self._build_watchlist_section(left)

        # Right: rate limit settings
        right = tk.Frame(pw, bg=theme.BG)
        pw.add(right, width=240)
        self._build_rate_section(right)

        # Bottom buttons
        btn_row = tk.Frame(self, bg=theme.BG)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        self._mk_btn(btn_row, "✅ 儲存", self._save).pack(side="right", padx=4)
        self._mk_btn(btn_row, "✕ 取消", self.destroy).pack(side="right")

    # ── Watchlist section ─────────────────────────────────────────────────────

    def _build_watchlist_section(self, parent):
        tk.Label(parent, text="追蹤清單", font=theme.FONT_LARGE,
                 fg=theme.FG, bg=theme.BG).pack(anchor="w", pady=(0, 6))

        # Listbox with scrollbar
        frame = tk.Frame(parent, bg=theme.BG)
        frame.pack(fill="both", expand=True)

        sb = tk.Scrollbar(frame)
        sb.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            frame, yscrollcommand=sb.set,
            bg=theme.BG2, fg=theme.FG,
            selectbackground=theme.ACCENT,
            font=theme.FONT_SMALL, bd=0,
            highlightbackground=theme.BORDER, highlightthickness=1,
            activestyle="none",
        )
        self._listbox.pack(fill="both", expand=True)
        sb.config(command=self._listbox.yview)
        self._reload_list()

        self._mk_btn(parent, "🗑 移除選取", self._remove_selected).pack(
            anchor="w", pady=(4, 10))

        # Add new item
        tk.Label(parent, text="─── 新增標的 ───", font=theme.FONT_SMALL,
                 fg=theme.FG_DIM, bg=theme.BG).pack(anchor="w")

        fields = [("代號 (如 AAPL / 2330.TW / BTCUSDT)", "sym"),
                  ("顯示名稱（留空同代號）",            "label")]
        self._vars = {}
        for hint, key in fields:
            tk.Label(parent, text=hint, font=theme.FONT_TINY,
                     fg=theme.FG_DIM, bg=theme.BG).pack(anchor="w", pady=(4, 0))
            v = tk.StringVar()
            self._vars[key] = v
            ent = tk.Entry(parent, textvariable=v, font=theme.FONT_SMALL,
                           bg=theme.BG3, fg=theme.FG,
                           insertbackground=theme.FG, bd=0,
                           highlightbackground=theme.BORDER,
                           highlightthickness=1)
            ent.pack(fill="x")

        # Category
        tk.Label(parent, text="分類：", font=theme.FONT_TINY,
                 fg=theme.FG_DIM, bg=theme.BG).pack(anchor="w", pady=(4, 0))
        self._cat_var = tk.StringVar(value=CATEGORIES[0])
        cat_menu = tk.OptionMenu(parent, self._cat_var, *CATEGORIES)
        self._style_menu(cat_menu)
        cat_menu.pack(fill="x")

        # Display type
        tk.Label(parent, text="顯示方式：", font=theme.FONT_TINY,
                 fg=theme.FG_DIM, bg=theme.BG).pack(anchor="w", pady=(4, 0))
        self._disp_var = tk.StringVar(value="ticker")
        disp_menu = tk.OptionMenu(parent, self._disp_var, *DISPLAYS)
        self._style_menu(disp_menu)
        disp_menu.pack(fill="x")

        self._mk_btn(parent, "➕ 新增", self._add_item).pack(
            anchor="w", pady=(6, 0))

    # ── Rate limit section ────────────────────────────────────────────────────

    def _build_rate_section(self, parent):
        rl = self.config_data.get("rate_limits", {})

        tk.Label(parent, text="速率限制設定", font=theme.FONT_LARGE,
                 fg=theme.FG, bg=theme.BG).pack(anchor="w", pady=(0, 10))

        # Crypto WS toggle
        self._crypto_ws = tk.BooleanVar(value=rl.get("crypto_ws", True))
        ck = tk.Checkbutton(parent, text="Crypto WebSocket (即時)",
                            variable=self._crypto_ws,
                            bg=theme.BG, fg=theme.FG,
                            selectcolor=theme.BG3,
                            activebackground=theme.BG,
                            font=theme.FONT_SMALL)
        ck.pack(anchor="w")

        # Numeric sliders
        self._rate_vars = {}
        sliders = [
            ("美股 更新間隔（秒）", "us_stock_interval_sec",  30, 300, rl.get("us_stock_interval_sec", 60)),
            ("台股 更新間隔（秒）", "tw_stock_interval_sec",  30, 300, rl.get("tw_stock_interval_sec", 90)),
            ("歷史快取（分鐘）",    "chart_history_cache_min", 5, 120, rl.get("chart_history_cache_min", 30)),
        ]
        for label, key, lo, hi, init in sliders:
            tk.Label(parent, text=label, font=theme.FONT_SMALL,
                     fg=theme.FG_DIM, bg=theme.BG).pack(anchor="w", pady=(10, 0))
            row = tk.Frame(parent, bg=theme.BG)
            row.pack(fill="x")
            v = tk.IntVar(value=init)
            self._rate_vars[key] = v
            val_lbl = tk.Label(row, textvariable=v, font=theme.FONT_BOLD,
                               fg=theme.ACCENT, bg=theme.BG, width=4)
            val_lbl.pack(side="right")
            sl = tk.Scale(row, from_=lo, to=hi, orient="horizontal",
                          variable=v, bg=theme.BG, fg=theme.FG_DIM,
                          troughcolor=theme.BG3, highlightthickness=0,
                          showvalue=False, length=150,
                          activebackground=theme.ACCENT)
            sl.pack(side="left", fill="x", expand=True)

        # Fugle intraday toggle
        self._fugle_var = tk.BooleanVar(
            value=rl.get("tw_use_fugle_intraday", True))
        ck2 = tk.Checkbutton(parent,
                             text="台股日內使用 Fugle API",
                             variable=self._fugle_var,
                             bg=theme.BG, fg=theme.FG,
                             selectcolor=theme.BG3,
                             activebackground=theme.BG,
                             font=theme.FONT_SMALL)
        ck2.pack(anchor="w", pady=(14, 0))

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _reload_list(self):
        self._listbox.delete(0, "end")
        for item in self.config_data.get("watchlist", []):
            self._listbox.insert(
                "end",
                f"[{item['category']}] {item['label']} — {item['display']}")

    def _remove_selected(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        wl  = self.config_data.get("watchlist", [])
        if 0 <= idx < len(wl):
            wl.pop(idx)
        self._reload_list()

    def _add_item(self):
        sym   = self._vars["sym"].get().strip().upper()
        label = self._vars["label"].get().strip() or sym
        cat   = self._cat_var.get()
        disp  = self._disp_var.get()
        if not sym:
            messagebox.showwarning("錯誤", "請輸入代號！", parent=self)
            return
        entry = {"symbol": sym, "label": label, "category": cat, "display": disp}
        if cat == "Crypto":
            entry["base_currency"] = "USDT"
        self.config_data.setdefault("watchlist", []).append(entry)
        self._reload_list()
        self._vars["sym"].set("")
        self._vars["label"].set("")

    def _save(self):
        # Update rate limits
        self.config_data["rate_limits"] = {
            "crypto_ws":              self._crypto_ws.get(),
            "us_stock_interval_sec":  self._rate_vars["us_stock_interval_sec"].get(),
            "tw_stock_interval_sec":  self._rate_vars["tw_stock_interval_sec"].get(),
            "chart_history_cache_min": self._rate_vars["chart_history_cache_min"].get(),
            "tw_use_fugle_intraday":  self._fugle_var.get(),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            if self.on_save_cb:
                self.on_save_cb()
            self.destroy()
        except Exception as e:
            messagebox.showerror("儲存失敗", str(e), parent=self)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mk_btn(self, parent, text: str, cmd) -> tk.Button:
        return tk.Button(parent, text=text, command=cmd,
                         bg=theme.BG3, fg=theme.FG,
                         activebackground=theme.ACCENT,
                         activeforeground=theme.FG,
                         font=theme.FONT_SMALL, bd=0,
                         relief="flat", padx=8, pady=3,
                         cursor="hand2")

    def _style_menu(self, menu: tk.OptionMenu):
        menu.configure(
            bg=theme.BG3, fg=theme.FG,
            activebackground=theme.ACCENT,
            activeforeground=theme.FG,
            font=theme.FONT_SMALL, bd=0,
            relief="flat", highlightthickness=0)
        menu["menu"].configure(
            bg=theme.BG3, fg=theme.FG,
            activebackground=theme.ACCENT,
            font=theme.FONT_SMALL)
