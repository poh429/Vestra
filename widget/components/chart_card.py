"""
ChartCard — tkinter Frame with matplotlib chart embedded.
Features:
  • Timeframe switcher: 日內 / 日線 / 周線 / 月線 / 全歷史
  • Chart mode toggle : Line ↔ K棒 (OHLC candlestick)
  • Optional RSI sub-panel
  • Thread-safe async data loading
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

import pandas as pd
import numpy as np

from widget.style import theme

# ── helpers ───────────────────────────────────────────────────────────────────

def _color_dir(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return theme.CHART_DOWN
    try:
        last_close = float(df["Close"].iloc[-1])
        first_open = float(df["Open"].iloc[0])
        return theme.CHART_UP if last_close >= first_open else theme.CHART_DOWN
    except Exception:
        return theme.CHART_DOWN


def _draw_line(ax, df: pd.DataFrame, color: str):
    close = df["Close"].astype(float)
    xs = mdates.date2num(df.index.to_pydatetime())
    ax.plot(xs, close, color=color, linewidth=1.4, solid_capstyle="round")
    # Gradient fill
    ax.fill_between(df.index, float(close.min()), close,
                    alpha=0.15, color=color)


def _draw_candles(ax, df: pd.DataFrame, base_color: str = None):
    for i, (idx, row) in enumerate(df.iterrows()):
        op, hi, lo, cl = row["Open"], row["High"], row["Low"], row["Close"]
        color = theme.CHART_UP if cl >= op else theme.CHART_DOWN
        # wick
        ax.plot([i, i], [lo, hi], color=color, linewidth=0.7)
        # body
        body_h = abs(cl - op) or 0.001
        rect = Rectangle((i - 0.35, min(op, cl)), 0.7, body_h,
                          color=color, zorder=2)
        ax.add_patch(rect)
    # set x-ticks to dates
    n = len(df)
    step = max(1, n // 6)
    ticks = list(range(0, n, step))
    labels = [df.index[i].strftime("%m/%d") for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=6, color=base_color or theme.FG_DIM)
    ax.set_xlim(-0.5, n - 0.5)


def _draw_ohlc(ax, df: pd.DataFrame, base_color: str = None):
    """Traditional OHLC tick bars."""
    for i, (idx, row) in enumerate(df.iterrows()):
        op, hi, lo, cl = row["Open"], row["High"], row["Low"], row["Close"]
        color = theme.CHART_UP if cl >= op else theme.CHART_DOWN
        # High-Low vertical line
        ax.plot([i, i], [lo, hi], color=color, linewidth=0.8)
        # Open tick (left)
        ax.plot([i - 0.25, i], [op, op], color=color, linewidth=0.8)
        # Close tick (right)
        ax.plot([i, i + 0.25], [cl, cl], color=color, linewidth=0.8)
    n = len(df)
    step = max(1, n // 6)
    ticks = list(range(0, n, step))
    labels = [df.index[j].strftime("%m/%d") for j in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=6, color=base_color or theme.FG_DIM)
    ax.set_xlim(-0.5, n - 0.5)


def _draw_volume(ax, main_ax, df: pd.DataFrame, is_line_mode: bool = False):
    """Volume bar chart, overlaid at the bottom of the main chart."""
    vol = df["Volume"].values
    if len(vol) == 0:
        return

    op = df["Open"].values
    cl = df["Close"].values
    colors = [theme.CHART_UP if c >= o else theme.CHART_DOWN for o, c in zip(op, cl)]

    if is_line_mode:
        # Let mpl handle the pd.DatetimeIndex alignment directly
        # Calculate an approximate width in days (e.g. 1 day = 1.0, 5 min = 5/1440)
        from pandas import Timedelta
        if len(df.index) > 1:
            diff = df.index[1] - df.index[0]
            w = max(diff.total_seconds() / 86400 * 0.7, 0.005)
        else:
            w = 0.7
        ax.bar(df.index, vol, color=colors, alpha=0.25, width=w)
    else:
        xs = np.arange(len(df))
        ax.bar(xs, vol, color=colors, alpha=0.25, width=0.7)

    # Scale so volume bars only occupy the bottom 25% of the frame
    max_v = np.nanmax(vol)
    if max_v > 0:
        ax.set_ylim(0, max_v * 4)
        
    # Sync X-axis limits to prevent cropping
    ax.set_xlim(main_ax.get_xlim())


def _style_ax(ax, custom_color: str = None):
    if custom_color:
        bg_color = theme.mix_colors(custom_color, theme.CHART_BG, 0.05)
        text_color = theme.mix_colors(custom_color, theme.FG_DIM, 0.8)
        border_color = theme.mix_colors(custom_color, theme.BORDER, 0.4)
    else:
        bg_color = theme.CHART_BG
        text_color = theme.FG_DIM
        border_color = theme.BORDER

    ax.set_facecolor(bg_color)
    ax.tick_params(colors=text_color, labelsize=6)
    for spine in ax.spines.values():
        spine.set_color(border_color)
    ax.yaxis.tick_right()
    ax.yaxis.set_tick_params(labelsize=6, labelcolor=text_color)
    ax.grid(axis="y", color=theme.CHART_GRID, linewidth=0.5, linestyle="--")


# ── ChartCard widget ──────────────────────────────────────────────────────────

class ChartCard(tk.Frame):
    """A card displaying an interactive chart with timeframe + mode controls."""

    TF_LIST   = ["日內", "日線", "周線", "月線", "全歷史"]
    MODES     = ["Line", "K棒", "OHLC"]

    def __init__(self, parent, symbol: str, label: str, category: str,
                 use_fugle: bool = True, show_rsi: bool = False,
                 show_header: bool = True, show_volume: bool = False,
                 show_fundamentals: bool = False, **kw):
        self._base_color = kw.pop("base_color", None)
        super().__init__(parent, bg=theme.BG2,
                         highlightbackground=theme.BORDER,
                         highlightthickness=1, **kw)
        self.symbol      = symbol
        self.label       = label
        self.category    = category
        self.use_fugle   = use_fugle
        self.show_rsi    = show_rsi
        self.show_volume = show_volume
        self.show_fundamentals = show_fundamentals
        self._show_header = show_header

        self._df: Optional[pd.DataFrame] = None
        self._tf   = "日線"
        self._mode = "Line"   # "Line" | "K棒" | "OHLC"
        self._ax_vol = None   # volume sub-axes

        # Placeholder labels (overwritten if header is shown)
        self._price_lbl  = None
        self._change_lbl = None
        self._arrow_lbl  = None
        self._ext_hours_lbl = None  # Built if show_header=True
        # Fundamental stat labels (populated async)
        self._fund_mktcap_lbl = None
        self._fund_pe_lbl     = None
        self._fund_eps_lbl    = None

        self.bind("<<ChartLoaded>>", lambda e: self._render())

        if show_header:
            self._build_header()
        self._build_controls()
        self._build_chart()
        if show_fundamentals:
            self._build_fundamentals()
        self._load()
        if show_fundamentals:
            import threading
            threading.Thread(target=self._fetch_fundamentals, daemon=True).start()

    # ── Fundamental Stats Bar ─────────────────────────────────────────────────

    def _build_fundamentals(self):
        """Build a compact one-row fundamental stats bar at the bottom of the card."""
        bar = tk.Frame(self, bg=theme.BG3)
        bar.pack(fill="x", padx=4, pady=(0, 3))

        label_opts = dict(font=("Segoe UI", 7), fg=theme.FG_DIM, bg=theme.BG3)
        number_opts = dict(font=("Segoe UI", 7), fg=theme.FG, bg=theme.BG3)
        value_opts = dict(font=("Segoe UI", 7, "bold"), fg=theme.FG, bg=theme.BG3)

        # Market Cap
        tk.Label(bar, text="Mkt Cap", **label_opts).pack(side="left", padx=(6, 1))
        self._fund_mktcap_lbl = tk.Label(bar, text="…", **number_opts)
        self._fund_mktcap_lbl.pack(side="left", padx=(0, 0))
        self._fund_mktcap_unit_lbl = tk.Label(bar, text="", **value_opts)
        self._fund_mktcap_unit_lbl.pack(side="left", padx=(1, 8))

        # P/E
        tk.Label(bar, text="P/E", **label_opts).pack(side="left", padx=(0, 1))
        self._fund_pe_lbl = tk.Label(bar, text="…", **value_opts)
        self._fund_pe_lbl.pack(side="left", padx=(0, 8))

        # EPS
        tk.Label(bar, text="EPS", **label_opts).pack(side="left", padx=(0, 1))
        self._fund_eps_lbl = tk.Label(bar, text="…", **value_opts)
        self._fund_eps_lbl.pack(side="left")

    def _fetch_fundamentals(self):
        """Background thread: fetch fundamentals via yfinance and update labels."""
        try:
            import yfinance as yf
            sym = self.symbol
            if self.category == "台股" and not sym.endswith(".TW"):
                sym = sym + ".TW"
            elif self.category == "Crypto":
                if sym.endswith("USDT"):
                    sym = sym[:-4] + "-USD"
                elif sym.endswith("USD") and "-" not in sym:
                    sym = sym[:-3] + "-USD"

            info = yf.Ticker(sym).info

            mkt_cap  = info.get("marketCap")
            pe       = info.get("trailingPE")
            eps      = info.get("trailingEps")
            currency = info.get("currency", "")

            def _fmt_cap(v, cur):
                if v is None:
                    return ("N/A", "")
                cur_str = f" {cur}" if cur else ""
                if v >= 1e12:
                    return (f"{v/1e12:.2f}", f"T{cur_str}")
                if v >= 1e9:
                    return (f"{v/1e9:.1f}", f"B{cur_str}")
                if v >= 1e6:
                    return (f"{v/1e6:.0f}", f"M{cur_str}")
                return (f"{v}", f"{cur_str}")

            cap_val, cap_unit = _fmt_cap(mkt_cap, currency)
            pe_str  = f"{pe:.1f}" if pe is not None else "N/A"
            eps_str = f"{eps:.2f}" if eps is not None else "N/A"

            def _update():
                try:
                    if self._fund_mktcap_lbl and self._fund_mktcap_lbl.winfo_exists():
                        self._fund_mktcap_lbl.config(text=cap_val)
                    if self._fund_mktcap_unit_lbl and self._fund_mktcap_unit_lbl.winfo_exists():
                        self._fund_mktcap_unit_lbl.config(text=cap_unit)
                    if self._fund_pe_lbl and self._fund_pe_lbl.winfo_exists():
                        self._fund_pe_lbl.config(text=pe_str)
                    if self._fund_eps_lbl and self._fund_eps_lbl.winfo_exists():
                        self._fund_eps_lbl.config(text=eps_str)
                except Exception:
                    pass

            self.after(0, _update)
        except Exception as e:
            print(f"[Fundamentals] fetch error {self.symbol}: {e}")

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=theme.BG2)
        hdr.pack(fill="x", padx=8, pady=(8, 2))

        # Left side: Label
        tk.Label(hdr, text=self.label, font=theme.FONT_BOLD,
                 fg=theme.FG, bg=theme.BG2).pack(side="left")

        # Right side: Price, Change, Extended Hours
        right_f = tk.Frame(hdr, bg=theme.BG2)
        right_f.pack(side="right", fill="y")

        # Value frame for price/change
        val_f = tk.Frame(right_f, bg=theme.BG2)
        val_f.pack(anchor="e")

        # Arrow
        self._arrow_lbl = tk.Label(val_f, text="--", font=("Segoe UI", 12, "bold"),
                                   bg=theme.BG2, fg=theme.FG_DIM)
        self._arrow_lbl.pack(side="left", padx=(0, 2))

        # Price
        self._price_lbl = tk.Label(val_f, text="---", font=("Segoe UI", 12, "bold"),
                                   bg=theme.BG2, fg=theme.FG)
        self._price_lbl.pack(side="left", padx=(0, 5))

        # Change & Pct
        self._change_lbl = tk.Label(val_f, text="---", font=("Segoe UI", 8),
                                    bg=theme.BG2, fg=theme.FG_DIM)
        self._change_lbl.pack(side="left", pady=(3, 0))

        # Extended Hours Label (Hidden by default)
        self._ext_hours_lbl = tk.Label(right_f, text="", font=("Segoe UI", 8),
                                       bg=theme.BG2, fg=theme.FG_DIM)
        self._ext_hours_lbl.pack(anchor="e", pady=(0, 2))

    # ── Controls ──────────────────────────────────────────────────────────────

    def _build_controls(self):
        ctl = tk.Frame(self, bg=theme.BG2)
        ctl.pack(fill="x", padx=8, pady=2)

        # Timeframe buttons
        self._tf_btns: dict[str, tk.Label] = {}
        for tf in self.TF_LIST:
            lbl = tk.Label(ctl, text=tf, font=theme.FONT_TINY,
                           fg=theme.FG_DIM, bg=theme.BG3,
                           padx=5, pady=1, cursor="hand2",
                           relief="flat")
            lbl.pack(side="left", padx=1)
            lbl.bind("<Button-1>", lambda e, t=tf: self._switch_tf(t))
            self._tf_btns[tf] = lbl

        # Mode toggle (right side)
        self._mode_btns: dict[str, tk.Label] = {}
        for mode in self.MODES:
            lbl = tk.Label(ctl, text=mode, font=theme.FONT_TINY,
                           fg=theme.FG_DIM, bg=theme.BG3,
                           padx=5, pady=1, cursor="hand2",
                           relief="flat")
            lbl.pack(side="right", padx=1)
            lbl.bind("<Button-1>", lambda e, m=mode: self._switch_mode(m))
            self._mode_btns[mode] = lbl

        self._refresh_btn_styles()

    # ── Chart canvas ──────────────────────────────────────────────────────────

    def _build_chart(self):
        # Determine subplot rows
        rows = 1
        height_ratios = [1]
        if self.show_rsi:
            rows += 1
            height_ratios.append(0.4)

        # Base height depends only on RSI now, Volume is overlaid
        self._fig = Figure(figsize=(3.6, 1.85 if self.show_rsi else 1.4),
                           dpi=100, facecolor=theme.CHART_BG)
        self._fig.subplots_adjust(left=0.01, right=0.88,
                                   top=0.96, bottom=0.12,
                                   hspace=0.08)

        axes = self._fig.subplots(rows, 1, gridspec_kw={"height_ratios": height_ratios}) if rows > 1 else [self._fig.add_subplot(1, 1, 1)]
        if rows == 1:
            axes = [axes] if not isinstance(axes, list) else axes

        self._ax = axes[0]
        self._ax_rsi = None
        self._ax_vol = None

        if self.show_volume:
            self._ax_vol = self._ax.twinx()

        ax_remaining = list(axes[1:])
        if self.show_rsi and ax_remaining:
            self._ax_rsi = ax_remaining.pop(0)
            _style_ax(self._ax_rsi, self._base_color)

        _style_ax(self._ax, self._base_color)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True,
                                           padx=4, pady=(2, 6))

        # ── Crosshair state ──────────────────────────────────────────
        self._ch_vline  = None   # vertical line artist
        self._ch_hline  = None   # horizontal line artist
        self._ch_annot  = None   # price+date text box
        self._ch_dot    = None   # dot on the curve

        self._canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._canvas.mpl_connect("axes_leave_event",    self._on_leave)

    # ── Data Loading ─────────────────────────────────────────────────────────

    def _load(self):
        """Kick off async history load."""
        from widget.data.history_loader import load_history_async
        self._set_loading(True)
        load_history_async(
            self.symbol, self.category, self._tf,
            callback=self._on_data,
            use_fugle=self.use_fugle,
        )

    def _on_data(self, df: Optional[pd.DataFrame]):
        """Called from background thread — trigger a safe event on the main UI thread."""
        self._df = df
        try:
            self.event_generate("<<ChartLoaded>>")
        except Exception:
            pass

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render(self):
        self._set_loading(False)
        df = self._df
        if df is None or df.empty:
            if self._price_lbl:
                self._price_lbl.config(text="N/A", fg=theme.NEUTRAL)
            return

        color = _color_dir(df)
        self._update_header(df, color)

        self._ax.cla()
        _style_ax(self._ax, self._base_color)

        if self._mode == "K棒":
            _draw_candles(self._ax, df, base_color=self._base_color)
        elif self._mode == "OHLC":
            _draw_ohlc(self._ax, df, base_color=self._base_color)
        else:
            _draw_line(self._ax, df, color)
            # x-axis date formatting for line
            if hasattr(df.index, 'to_pydatetime'):
                self._ax.xaxis.set_major_formatter(
                    mdates.DateFormatter("%m/%d"))
                self._ax.xaxis.set_major_locator(
                    mdates.AutoDateLocator(minticks=4, maxticks=6))

        self._ax.tick_params(axis="x", labelsize=6, colors=self._base_color or theme.FG_DIM)

        # Overlay Volume sub-panel
        if self._ax_vol is not None and "Volume" in df.columns:
            self._ax_vol.cla()
            # Remove all styling from twinx so it doesn't draw grid/spines over the main chart
            self._ax_vol.set_facecolor("none")
            for spine in self._ax_vol.spines.values():
                spine.set_visible(False)
            self._ax_vol.tick_params(left=False, right=False, labelleft=False, labelright=False, bottom=False)
            self._ax_vol.grid(False)
            
            is_line = self._mode not in ["K棒", "OHLC"]
            _draw_volume(self._ax_vol, self._ax, df, is_line_mode=is_line)

        # RSI sub-panel
        if self._ax_rsi is not None:
            self._ax_rsi.cla()
            _style_ax(self._ax_rsi, self._base_color)
            try:
                from widget.data.indicator_feed import compute_rsi
                rsi = compute_rsi(df["Close"])
                self._ax_rsi.plot(df.index, rsi, color=theme.ACCENT2,
                                  linewidth=0.9)
                self._ax_rsi.axhline(70, color=theme.DOWN, linewidth=0.5,
                                     linestyle="--", alpha=0.7)
                self._ax_rsi.axhline(30, color=theme.UP, linewidth=0.5,
                                     linestyle="--", alpha=0.7)
                self._ax_rsi.set_ylim(0, 100)
                self._ax_rsi.set_ylabel("RSI", fontsize=6,
                                        color=theme.FG_DIM, labelpad=2)
            except Exception:
                pass

        self._canvas.draw_idle()

    def _update_header(self, df: pd.DataFrame, color: str):
        """Update labels inside internal header (standalone mode only).
        When show_header=False we only bubble color/direction up.
        """
        last  = float(df["Close"].iloc[-1])
        first = float(df["Open"].iloc[0])
        chg   = last - first
        pct   = (chg / first * 100) if first else 0
        sign  = "+" if chg >= 0 else ""
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "—")

        if self._price_lbl:   # standalone ChartCard with its own header
            self._price_lbl.config(text=f"{last:,.2f}", fg=theme.FG)
        if self._change_lbl:
            # Show the chart-period range change, not today's change
            self._change_lbl.config(
                text=f"{arrow} {sign}{pct:.2f}%", fg=color)
        if self._arrow_lbl:
            self._arrow_lbl.config(text=arrow, fg=color)

        # Bubble only color/direction to CardWindow; CardWindow keeps its own
        # live price from the feed — do NOT overwrite it with historical data.
        if hasattr(self, '_header_cb') and self._header_cb:
            self._header_cb(arrow, color)

    def _set_loading(self, loading: bool):
        if loading and self._price_lbl:
            self._price_lbl.config(text="載入中…", fg=theme.FG_DIM)

    # ── Crosshair ─────────────────────────────────────────────────────────────

    def _clear_crosshair(self):
        for attr in ("_ch_vline", "_ch_hline", "_ch_annot", "_ch_dot"):
            artist = getattr(self, attr, None)
            if artist:
                try:
                    artist.remove()
                except Exception:
                    pass
            setattr(self, attr, None)

    def _on_leave(self, event):
        self._clear_crosshair()
        self._canvas.draw_idle()

    def _on_hover(self, event):
        valid_axes = [ax for ax in (self._ax, self._ax_vol, self._ax_rsi) if ax is not None]
        if event.inaxes not in valid_axes:
            self._clear_crosshair()
            self._canvas.draw_idle()
            return
        if self._df is None or self._df.empty:
            return

        df     = self._df
        x_pos  = event.xdata
        y_pos  = event.ydata

        # ── Snap to nearest data point ────────────────────────────
        if self._mode == "K棒":
            # candlestick x-axis is integer index
            idx = int(round(x_pos))
            idx = max(0, min(len(df) - 1, idx))
            row = df.iloc[idx]
            date_str = df.index[idx].strftime("%Y/%m/%d")
            snap_x   = idx
            snap_y   = float(row["Close"])
            label = (f"{date_str}\n"
                     f"O {float(row['Open']):,.2f}\n"
                     f"H {float(row['High']):,.2f}\n"
                     f"L {float(row['Low']):,.2f}\n"
                     f"C {float(row['Close']):,.2f}")
        else:
            # line chart: x-axis is matplotlib date number
            import matplotlib.dates as mdates
            xnums = mdates.date2num(df.index.to_pydatetime())
            diffs = abs(xnums - x_pos)
            idx   = int(diffs.argmin())
            row   = df.iloc[idx]
            snap_x = xnums[idx]
            snap_y = float(row["Close"])
            date_str = df.index[idx].strftime("%Y/%m/%d")
            label = f"{date_str}\n{snap_y:,.2f}"

        # ── Draw / update crosshair lines ─────────────────────────
        self._clear_crosshair()

        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()

        self._ch_vline = self._ax.axvline(
            x=snap_x, color="#ffffff", linewidth=0.6,
            linestyle="--", alpha=0.55, zorder=5)
        self._ch_hline = self._ax.axhline(
            y=snap_y, color="#ffffff", linewidth=0.6,
            linestyle="--", alpha=0.55, zorder=5)

        # Dot on the curve
        self._ch_dot = self._ax.plot(
            snap_x, snap_y, "o",
            color="#ffffff", markersize=4, zorder=6)[0]

        # ── Price+date annotation bubble ──────────────────────────
        # Decide left/right side of annotation
        mid_x = (xlim[0] + xlim[1]) / 2
        x_ann = xlim[0] + (xlim[1] - xlim[0]) * 0.03  \
                if snap_x > mid_x else \
                xlim[0] + (xlim[1] - xlim[0]) * 0.60
        mid_y = (ylim[0] + ylim[1]) / 2
        y_ann = ylim[0] + (ylim[1] - ylim[0]) * 0.75  \
                if snap_y < mid_y else \
                ylim[0] + (ylim[1] - ylim[0]) * 0.10

        self._ch_annot = self._ax.annotate(
            label,
            xy=(snap_x, snap_y),
            xytext=(x_ann, y_ann),
            fontsize=6.5,
            color="#ffffff",
            backgroundcolor="#1e1e2e",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#1e1e2e",
                      edgecolor="#4444aa",
                      alpha=0.88),
            zorder=10,
        )

        self._canvas.draw_idle()

    # ── Button state ─────────────────────────────────────────────────────────

    def _refresh_btn_styles(self):
        for tf, lbl in self._tf_btns.items():
            if tf == self._tf:
                lbl.config(fg=theme.FG, bg=theme.ACCENT,
                            font=(*theme.FONT_TINY[:2], "bold"))
            else:
                lbl.config(fg=theme.FG_DIM, bg=theme.BG3,
                            font=theme.FONT_TINY)

        for mode, lbl in self._mode_btns.items():
            if mode == self._mode:
                lbl.config(fg=theme.FG, bg=theme.ACCENT2,
                            font=(*theme.FONT_TINY[:2], "bold"))
            else:
                lbl.config(fg=theme.FG_DIM, bg=theme.BG3,
                            font=theme.FONT_TINY)

    def _switch_tf(self, tf: str):
        if tf == self._tf:
            return
        self._tf = tf
        self._refresh_btn_styles()
        self._load()

    def _switch_mode(self, mode: str):
        if mode == self._mode:
            return
        self._mode = mode
        self._refresh_btn_styles()
        if self._df is not None:
            self._render()

    # ── External price update (from ticker feed) ──────────────────────────────

    def update_ticker(self, data: dict):
        price  = data.get("price", 0)
        change = data.get("change", 0)
        pct    = data.get("change_pct", 0)
        color  = theme.UP if change > 0 else (theme.DOWN if change < 0 else theme.NEUTRAL)
        arrow  = "▲" if change > 0 else ("▼" if change < 0 else "—")
        sign   = "+" if change >= 0 else ""
        if self._price_lbl:
            self._price_lbl.config(text=f"{price:,.2f}", fg=theme.FG)
        if self._change_lbl:
            self._change_lbl.config(text=f"{arrow} {sign}{pct:.2f}%", fg=color)
        if self._arrow_lbl:
            self._arrow_lbl.config(text=arrow, fg=color)

        # Extended hours updates
        if self._show_header and self._ext_hours_lbl:
            pre_p = data.get("pre_price")
            pre_c = data.get("pre_change")
            post_p = data.get("post_price")
            post_c = data.get("post_change")
            
            ext_text = ""
            ext_color = theme.FG_DIM
            
            # Show pre-market if present, else post-market, ONLY if different from regular price
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
            else:
                self._ext_hours_lbl.config(text="")

        # Bubble up to parent CardWindow (only arrow and color)
        if hasattr(self, '_header_cb') and self._header_cb:
            self._header_cb(arrow, color)
