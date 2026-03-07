"""
Theme constants for Stock Desktop Widget V2 (tkinter + matplotlib).
"""

# ── Window ────────────────────────────────────────────────────────────────────
BG          = "#07070a"
BG2         = "#0c0c10"
BG3         = "#13131a"
BORDER      = "#22222d"
ACCENT      = "#7c6fff"
ACCENT2     = "#4fc3f7"

# ── Text ─────────────────────────────────────────────────────────────────────
FG          = "#ffffff"    # pure white — maximum legibility
FG_DIM      = "#a0a0b8"    # medium-light, used for secondary labels
FG_MUTED    = "#5a5a72"    # very dim, only for decorative/hint text

# ── Semantic ─────────────────────────────────────────────────────────────────
UP          = "#00e676"
DOWN        = "#ff4d4d"
NEUTRAL     = "#8888aa"    # neutral arrows / unchanged values

# ── Chart ─────────────────────────────────────────────────────────────────────
CHART_BG    = "#07070a"
CHART_GRID  = "#171720"
CHART_UP    = "#00e676"
CHART_DOWN  = "#ff4d4d"

# ── Fonts (tkinter font tuples) ────────────────────────────────────────────
# Prefer 'Segoe UI Variable Display' on Windows 11 for much better scaling and smoothing. Fallback to 'Segoe UI'.
_BASE_FONT = "Segoe UI Variable Display"

FONT        = (_BASE_FONT, 11)
FONT_BOLD   = (_BASE_FONT, 11, "bold")
FONT_LARGE  = (_BASE_FONT, 14, "bold")
FONT_MONO   = ("Consolas", 12, "bold")
FONT_MONO_L = ("Consolas", 18, "bold")
FONT_SMALL  = (_BASE_FONT,  9)
FONT_TINY   = (_BASE_FONT,  8)

# ── Sizes ─────────────────────────────────────────────────────────────────────
CARD_PAD    = 10
CARD_RADIUS = 8

# ── Timeframes ────────────────────────────────────────────────────────────────
TIMEFRAMES = ["日內", "日線", "周線", "月線", "全歷史"]

TF_PARAMS = {
    "日內":   {"period": "1d",  "interval": "5m"},
    "日線":   {"period": "3mo", "interval": "1d"},
    "周線":   {"period": "1y",  "interval": "1wk"},
    "月線":   {"period": "5y",  "interval": "1mo"},
    "全歷史": {"period": "max", "interval": "1mo"},
}

# ── Categories ────────────────────────────────────────────────────────────────
CATEGORIES  = ["全部", "Crypto", "美股", "ETF", "台股"]


# ── Color Mixing Utilities ────────────────────────────────────────────────────

def hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def mix_colors(color1: str, color2: str, weight: float) -> str:
    """Mix color1 with color2. weight is 0.0 to 1.0. 1.0 means 100% color1."""
    c1 = hex_to_rgb(color1)
    c2 = hex_to_rgb(color2)
    r = int(c1[0] * weight + c2[0] * (1 - weight))
    g = int(c1[1] * weight + c2[1] * (1 - weight))
    b = int(c1[2] * weight + c2[2] * (1 - weight))
    return _hex(r, g, b)


# ── Dynamic brightness ────────────────────────────────────────────────────────

def _hex(r: int, g: int, b: int) -> str:
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def set_lightness(v: int) -> None:
    """
    Apply a global brightness to the theme colours.
    v = 0   → dark theme  (#0e0e12 family)
    v = 100 → light theme (#f5f5f8 family)
    """
    import sys
    module = sys.modules[__name__]

    # Dark-mode anchor colours (v=0)
    dark = dict(
        BG=(14, 14, 18), BG2=(22, 22, 28), BG3=(28, 28, 36), BORDER=(42, 42, 54)
    )
    # Light-mode anchor colours (v=100)
    light = dict(
        BG=(245, 245, 248), BG2=(232, 232, 238), BG3=(218, 218, 228), BORDER=(180, 180, 200)
    )

    t = v / 100.0   # 0.0 → dark, 1.0 → light

    for key in ("BG", "BG2", "BG3", "BORDER"):
        dr, dg, db = dark[key]
        lr, lg, lb = light[key]
        nr = int(dr + (lr - dr) * t)
        ng = int(dg + (lg - dg) * t)
        nb = int(db + (lb - db) * t)
        setattr(module, key, _hex(nr, ng, nb))

    # Text: white on dark → near-black on light
    fg_r = int(255 - 230 * t)      # 255 → 25
    fg_d = int(160 - 100 * t)      # 160 → 60
    fg_m = int(90  - 50  * t)      # 90  → 40
    setattr(module, "FG",       _hex(fg_r, fg_r, min(fg_r + 20, 255)))
    setattr(module, "FG_DIM",   _hex(fg_d, fg_d, int(fg_d * 1.1)))
    setattr(module, "FG_MUTED", _hex(fg_m, fg_m, int(fg_m * 1.2)))

    # Sync chart background colours
    setattr(module, "CHART_BG",   getattr(module, "BG"))
    setattr(module, "CHART_GRID", getattr(module, "BG2"))


def apply_lightness_from_config(cfg: dict) -> None:
    """Called at startup so the theme respects a saved brightness value."""
    v = cfg.get("bg_lightness", 0)
    if v != 0:
        set_lightness(v)
