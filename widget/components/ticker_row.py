"""
TickerRow — compact tkinter Frame for large price display (no chart).
Used for simple ticker items like BTC, AAPL, etc.
"""

import tkinter as tk
from widget.style import theme


def _fmt_price(price: float, currency: str = "USD") -> str:
    if currency in ("USDT", "USD"):
        if price >= 10_000:
            return f"{price:,.2f}"
        elif price >= 100:
            return f"{price:.2f}"
        else:
            return f"{price:.4f}"
    elif currency == "TWD":
        return f"{price:,.2f}"
    return f"{price:.4f}"


class TickerRow(tk.Frame):
    """Large ticker row: symbol | price | change indicator."""

    def __init__(self, parent, symbol: str, label: str, category: str,
                 base_currency: str = "USD", **kw):
        super().__init__(parent, bg=theme.BG2,
                         highlightbackground=theme.BORDER,
                         highlightthickness=1, **kw)
        self.symbol    = symbol
        self.label     = label
        self.category  = category
        self._currency = base_currency

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.configure(padx=0, pady=0)

        # Single row layout
        row = tk.Frame(self, bg=theme.BG2)
        row.pack(fill="both", expand=True, padx=10, pady=8)

        # Left: arrow + label
        left = tk.Frame(row, bg=theme.BG2)
        left.pack(side="left", fill="y")

        self._arrow_lbl = tk.Label(left, text="●", font=theme.FONT_TINY,
                                   fg=theme.NEUTRAL, bg=theme.BG2, width=2)
        self._arrow_lbl.pack(side="left", anchor="center")

        mid = tk.Frame(left, bg=theme.BG2)
        mid.pack(side="left", padx=(2, 0))

        tk.Label(mid, text=self.label, font=theme.FONT_BOLD,
                 fg=theme.FG, bg=theme.BG2).pack(anchor="w")

        tk.Label(mid, text=self.category, font=theme.FONT_TINY,
                 fg=theme.FG_DIM, bg=theme.BG2).pack(anchor="w")

        # Right: price + change
        right = tk.Frame(row, bg=theme.BG2)
        right.pack(side="right", fill="y")

        self._price_lbl = tk.Label(right, text="—", font=theme.FONT_MONO_L,
                                   fg=theme.FG, bg=theme.BG2,
                                   anchor="e", justify="right")
        self._price_lbl.pack(anchor="e")

        self._change_lbl = tk.Label(right, text="—", font=theme.FONT,
                                    fg=theme.NEUTRAL, bg=theme.BG2,
                                    anchor="e", justify="right")
        self._change_lbl.pack(anchor="e")

        self._ext_hours_lbl = tk.Label(right, text="", font=("Segoe UI", 7),
                                       fg=theme.FG_DIM, bg=theme.BG2,
                                       anchor="e", justify="right")
        self._ext_hours_lbl.pack(anchor="e", pady=(2, 0))

    # ── Public ────────────────────────────────────────────────────────────────

    def update_data(self, data: dict):
        price  = data.get("price", 0)
        change = data.get("change", 0)
        pct    = data.get("change_pct", 0)
        cur    = data.get("currency", data.get("base_currency", self._currency))
        self._currency = cur

        sign  = "+" if change >= 0 else ""
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "—")
        color = theme.UP if change > 0 else (theme.DOWN if change < 0 else theme.NEUTRAL)

        self._price_lbl.config(text=_fmt_price(price, cur))
        self._change_lbl.config(
            text=f"{arrow}  {sign}{change:.2f}  ({sign}{pct:.2f}%)",
            fg=color)
        self._arrow_lbl.config(text=arrow, fg=color)

        # Extended hours updates
        pre_p = data.get("pre_price")
        pre_c = data.get("pre_change")
        post_p = data.get("post_price")
        post_c = data.get("post_change")
        
        ext_text = ""
        ext_color = theme.FG_DIM
        
        if pre_p is not None and pre_p != price:
            ext_text = f"Pre: {pre_p:g}"
            if pre_c is not None:
                ext_color = theme.UP if pre_c > 0 else (theme.DOWN if pre_c < 0 else theme.NEUTRAL)
                pct_c = (pre_c / (pre_p - pre_c) * 100) if (pre_p - pre_c) else 0.0
                sgn = "+" if pre_c > 0 else ""
                ext_text += f" {sgn}{pct_c:.2f}%"
        elif post_p is not None and post_p != price:
            ext_text = f"Post: {post_p:g}"
            if post_c is not None:
                ext_color = theme.UP if post_c > 0 else (theme.DOWN if post_c < 0 else theme.NEUTRAL)
                pct_c = (post_c / (post_p - post_c) * 100) if (post_p - post_c) else 0.0
                sgn = "+" if post_c > 0 else ""
                ext_text += f" {sgn}{pct_c:.2f}%"

        if ext_text:
            self._ext_hours_lbl.config(text=ext_text, fg=ext_color)
            if not self._ext_hours_lbl.winfo_viewable():
                self._ext_hours_lbl.pack(anchor="e", pady=(2, 0))
        else:
            if self._ext_hours_lbl.winfo_viewable():
                self._ext_hours_lbl.pack_forget()
