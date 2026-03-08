import tkinter as tk
from typing import Dict, Any
from widget.style import theme

class TickerTapeWindow(tk.Toplevel):
    def __init__(self, master, watchlist: list, on_close=None):
        super().__init__(master)
        
        self.overrideredirect(True)
        self.configure(bg=theme.BG)
        self.wm_attributes("-topmost", True)
        # Apply slight transparency
        self.wm_attributes("-alpha", 0.95)
        
        # Screen width & Bar dimensions
        # Position at the top, slightly padded or at very top (0)
        self.screen_w = self.winfo_screenwidth()
        self.bar_h = 32
        self.geometry(f"{self.screen_w}x{self.bar_h}+0+0")
        
        self._on_close = on_close
        
        self._canvas = tk.Canvas(
            self, bg=theme.BG, height=self.bar_h, width=self.screen_w,
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
        
        # Start X position far offscreen to the right so it scrolls in nicely
        self._base_x = self.screen_w
        
        self._init_canvas()
        self._animate()
        
        # Context menu
        self.bind("<Button-3>", self._context_menu)
        
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

    def _context_menu(self, event):
        ctx = tk.Menu(self, tearoff=0, bg=theme.BG_L3, fg=theme.FG)
        ctx.add_command(label="✕ 關閉跑馬燈 (返回卡片模式)", command=self.close)
        ctx.tk_popup(event.x_root, event.y_root)

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
            
        # Move everything to the left
        self._base_x -= self._speed
        
        # If the leading item goes too far off left, we shift it to the back
        # Which effectively means we push the 'base_x' forward by one unit 
        # to keep the illusion seamless
        if self._base_x < -self._item_spacing * total_count:
            self._base_x += self._item_spacing * total_count

        y = self.bar_h // 2
        for i, tid in enumerate(self._texts):
            # calculate logical X position
            x = self._base_x + (i * self._item_spacing)
            
            # If the item falls off the left side of the screen, wrap it to the right 
            # side of the train
            if x < -self._item_spacing:
                x += total_count * self._item_spacing
                
            self._canvas.coords(tid, x, y)
            
        self.after(20, self._animate)

    def close(self):
        """Called manually via right-click or remotely by WidgetManager"""
        self._running = False
        self.destroy()
        if self._on_close:
            self._on_close()
