import sys
import threading
import tkinter as tk
from widget import theme
import webbrowser

class AIDialog(tk.Toplevel):
    def __init__(self, parent, symbol: str, news_text: str, stream_generator=None):
        super().__init__(parent)
        self.symbol = symbol
        self.news_text = news_text
        self.stream_generator = stream_generator
        
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.config(bg=theme.BG2)
        
        # Center horizontally, position slightly down from top
        w, h = 450, 500
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Add thin border to match theme
        self.frame = tk.Frame(self, bg=theme.BG, bd=1, relief="solid", highlightbackground=theme.ACCENT, highlightcolor=theme.ACCENT, highlightthickness=1)
        self.frame.pack(fill="both", expand=True)
        
        self._build_ui()
        
        # Start the stream if provided
        if self.stream_generator:
            self._start_stream()

    def _build_ui(self):
        # Header area
        hdr = tk.Frame(self.frame, bg=theme.BG_HDR)
        hdr.pack(fill="x", side="top")
        
        lbl = tk.Label(hdr, text=f"🤖 AI 情報分析 - {self.symbol}", font=theme.FONT_BOLD, fg=theme.FG_HDR, bg=theme.BG_HDR)
        lbl.pack(side="left", padx=10, pady=8)
        
        close_btn = tk.Label(hdr, text="✕", font=theme.FONT, fg=theme.FG_DIM, bg=theme.BG_HDR, cursor="hand2")
        close_btn.pack(side="right", padx=10, pady=8)
        close_btn.bind("<Button-1>", lambda e: self.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#FF4444"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=theme.FG_DIM))
        
        # Main text area
        self.text_area = tk.Text(self.frame, font=("Segoe UI", 10), bg=theme.BG, fg=theme.FG, bd=0, wrap="word", padx=15, pady=15, state="disabled")
        self.text_area.pack(fill="both", expand=True)
        
        # Action bar at bottom
        self.action_bar = tk.Frame(self.frame, bg=theme.BG_HDR, pady=10)
        self.action_bar.pack(fill="x", side="bottom")
        
        # Fallback button
        self.btn_fallback = tk.Label(self.action_bar, text="🌐 打開瀏覽器詢問 Gemini (已複製指令)", font=("Segoe UI", 10, "bold"), fg=theme.FG_HDR, bg=theme.ACCENT, padx=12, pady=6, cursor="hand2")
        self.btn_fallback.pack(pady=5)
        
        self.btn_fallback.bind("<Button-1>", self._on_fallback_clicked)
        self.btn_fallback.bind("<Enter>", lambda e: self.btn_fallback.config(bg=theme.UP))
        self.btn_fallback.bind("<Leave>", lambda e: self.btn_fallback.config(bg=theme.ACCENT))
        
        # Make the window draggable via header
        def start_drag(e):
            self.x = e.x
            self.y = e.y
        def drag(e):
            new_x = self.winfo_x() + e.x - self.x
            new_y = self.winfo_y() + e.y - self.y
            self.geometry(f"+{new_x}+{new_y}")
            
        hdr.bind("<Button-1>", start_drag)
        hdr.bind("<B1-Motion>", drag)
        lbl.bind("<Button-1>", start_drag)
        lbl.bind("<B1-Motion>", drag)

    def _append_text(self, text: str):
        self.text_area.config(state="normal")
        self.text_area.insert("end", text)
        self.text_area.see("end")
        self.text_area.config(state="disabled")

    def _start_stream(self):
        self._append_text("正在分析最新情報...\n\n")
        
        def worker():
            try:
                for chunk in self.stream_generator(self.symbol, self.news_text):
                    self.after(0, self._append_text, chunk)
            except Exception as e:
                self.after(0, self._append_text, f"\n\n分析發生錯誤: {e}")
                
        threading.Thread(target=worker, daemon=True).start()

    def _on_fallback_clicked(self, event):
        prompt = f"""請幫我分析以下關於 {self.symbol} 的近期新聞與資訊，並嚴格遵循以下格式使用繁體中文輸出：

1. 🔥 近期多方動能 (利多):
(列出 1~3 點最重要的好消息)

2. 🧊 潛在空方風險 (利空):
(列出 1~3 點需要注意的壞消息或隱憂)

3. 📝 總結判定:
(以一句話總結當前短線情緒，例如：整體情緒偏多/中立/偏空/狂熱/恐慌)

新聞資訊如下：
{self.news_text}
"""
        # Copy to clipboard
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.update() # Keep it in clipboard
        
        self.btn_fallback.config(text="✅ 已複製並打開瀏覽器！")
        self.after(2000, lambda: self.btn_fallback.config(text="🌐 打開瀏覽器詢問 Gemini (已複製指令)"))
        
        webbrowser.open("https://gemini.google.com/app")
        
def show_ai_dialog(parent, symbol, fetch_news_fn, stream_summary_fn):
    """
    Helper function to wrap the background fetching of news and spawning of the dialog.
    """
    def _worker():
        news_text = fetch_news_fn(symbol)
        def _spawn():
            dlg = AIDialog(parent, symbol, news_text, stream_summary_fn)
            dlg.focus_set()
        parent.after(0, _spawn)
        
    threading.Thread(target=_worker, daemon=True).start()
