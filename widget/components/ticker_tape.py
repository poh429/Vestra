import tkinter as tk
from typing import Dict, Any
from widget.style import theme

class TickerTapeWindow(tk.Toplevel):
    def __init__(self, master, watchlist: list, position="top", transparent=False, direction="rtl", on_close=None, on_config=None):
        super().__init__(master)
        
        self.overrideredirect(True)
        self._transparent = transparent
        self._position = position
        self._direction = direction
        self._on_close = on_close
        self._on_config = on_config

        if self._transparent:
            # Fully transparent background via color-key
            self.configure(bg="#000001")
            self.wm_attributes("-transparentcolor", "#000001")
            canvas_bg = "#000001"
        else:
            self.configure(bg=theme.BG)
            canvas_bg = theme.BG
            try:
                self.tk.call("wm", "attributes", self._w, "-transparentcolor", "")
            except Exception:
                pass
            
        self.wm_attributes("-topmost", True)
        if not self._transparent:
            # Apply slight transparency only if not fully transparent
            self.wm_attributes("-alpha", 0.95)
        
        # Screen width & Bar dimensions
        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()
        self.bar_h = 32
        
        y_pos = 0 if self._position == "top" else (self.screen_h - self.bar_h)
        self.geometry(f"{self.screen_w}x{self.bar_h}+0+{y_pos}")
        
        self._canvas = tk.Canvas(
            self, bg=canvas_bg, height=self.bar_h, width=self.screen_w,
            highlightthickness=0, borderwidth=0
        )
        self._canvas.pack(fill="both", expand=True)
        
        self._items = []
        self._texts = []
        
        # Build state array
        for item in watchlist:
            sym = item.get("symbol", "").upper()
            if sym:
                self._items.append({
                    "symbol": sym,
                    "price": "...",
                    "change_pct": "...",
                    "color": theme.FG
                })
                
        # Scrolling parameters
        self._item_spacing = 250    # Minimum width per ticker item
        self._speed = 1.5           # Pixels to move per frame
        self._running = True
        
        # Start X position far offscreen so it scrolls in nicely
        self._base_x = self.screen_w if self._direction == "rtl" else -self.screen_w
        
        self._init_canvas()
        self._animate()
        
    def _init_canvas(self):
        self._canvas.delete("all")
        self._texts.clear()
        
        font_spec = theme.FONT_BOLD
        for i, item in enumerate(self._items):
            tid = self._canvas.create_text(
                0, self.bar_h // 2,
                text=self._format_text(item),
                anchor="w",
                font=font_spec,
                fill=item["color"]
            )
            self._texts.append(tid)

    def _format_text(self, item):
        return f"{item['symbol']}   {item['price']}  ({item['change_pct']})"

    def set_position(self, new_pos: str):
        self._position = new_pos
        y_pos = 0 if new_pos == "top" else (self.screen_h - self.bar_h)
        self.geometry(f"{self.screen_w}x{self.bar_h}+0+{y_pos}")
        
    def set_transparent(self, new_trans: bool):
        self._transparent = new_trans
        if self._transparent:
            self.configure(bg="#000001")
            self.wm_attributes("-transparentcolor", "#000001")
            self.wm_attributes("-alpha", 1.0)
            self._canvas.configure(bg="#000001")
        else:
            self.configure(bg=theme.BG)
            try:
                self.tk.call("wm", "attributes", self._w, "-transparentcolor", "")
            except Exception:
                self.wm_attributes("-transparentcolor", "")
            self.wm_attributes("-alpha", 0.95)
            self._canvas.configure(bg=theme.BG)
            
    def set_direction(self, new_dir: str):
        self._direction = new_dir
        # Reset base_x when direction changes so it enters from correct edge
        total_count = len(self._texts)
        train_w = total_count * self._item_spacing
        seamless = train_w >= self.screen_w

        if self._direction == "rtl":
            self._base_x = self.screen_w if not seamless else 0
        else:
            self._base_x = -train_w if not seamless else 0

    def update_price(self, symbol: str, data: Dict[str, Any]):
        sym = symbol.upper()
        price = data.get("price")
        change_pct = data.get("change_pct")
        
        for idx, item in enumerate(self._items):
            if item["symbol"] == sym:
                dirty = False
                if price is not None:
                    if isinstance(price, (int, float)):
                        fmt = "{:,.2f}" if price >= 1 else "{:,.4f}"
                        item["price"] = fmt.format(price)
                        dirty = True
                        
                if change_pct is not None:
                    try:
                        f_pct = float(change_pct)
                        if f_pct > 0:
                            item["change_pct"] = f"+{f_pct:.2f}%"
                            item["color"] = theme.UP
                        elif f_pct < 0:
                            item["change_pct"] = f"{f_pct:.2f}%"
                            item["color"] = theme.DOWN
                        else:
                            item["change_pct"] = "0.00%"
                            item["color"] = theme.FG
                        dirty = True
                    except ValueError:
                        pass
                
                if dirty and idx < len(self._texts):
                    self._canvas.itemconfig(
                        self._texts[idx], 
                        text=self._format_text(item), 
                        fill=item["color"]
                    )
                break

    def _animate(self):
        if not self._running:
            return
            
        total_count = len(self._texts)
        if total_count == 0:
            self.after(30, self._animate)
            return
            
        train_w = total_count * self._item_spacing
        seamless = train_w >= self.screen_w
        speed_delta = -self._speed if self._direction == "rtl" else self._speed
        self._base_x += speed_delta
        
        # Handle wrap logic for the train
        if self._direction == "rtl":
            if seamless:
                if self._base_x < -train_w:
                    self._base_x += train_w
            else:
                # Wait for entire train to exit left, then reset to right edge
                if self._base_x + train_w < 0:
                    self._base_x = self.screen_w
        else: # ltr
            if seamless:
                if self._base_x > 0:
                    self._base_x -= train_w
            else:
                # Wait for entire train to exit right, then reset to left edge
                if self._base_x > self.screen_w:
                    self._base_x = -train_w

        y = self.bar_h // 2
        for i, tid in enumerate(self._texts):
            x = self._base_x + (i * self._item_spacing)
            
            # For seamless modes, smoothly wrap individual items when they go off screen
            if seamless:
                if self._direction == "rtl" and x < -self._item_spacing:
                    x += train_w
                elif self._direction == "ltr" and x > self.screen_w:
                    x -= train_w
                
            self._canvas.coords(tid, x, y)
            
        self.after(20, self._animate)

    def close(self):
        """Called manually via right-click or remotely by WidgetManager"""
        self._running = False
        self.destroy()
        if self._on_close:
            self._on_close()
