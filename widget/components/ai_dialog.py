import ctypes
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from widget.style import theme

VK_CONTROL = 0x11
VK_ENTER = 0x0D
VK_TAB = 0x09
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

class AIDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        symbol: str,
        news_text: str,
        stream_generator=None,
        dialog_title: str = "AI 情報分析",
        context_label: str = "近期新聞與資訊",
    ):
        super().__init__(parent)
        self.symbol = symbol
        self.news_text = news_text
        self.stream_generator = stream_generator
        self.dialog_title = dialog_title
        self.context_label = context_label
        self._first_chunk_received = False
        self._fallback_triggered = False
        self._first_token_timer = None
        
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

    def _press_key(self, vk_code: int):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def _press_ctrl_combo(self, vk_code: int):
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def _paste_and_submit(self, tab_presses: int = 0, submit_twice: bool = False):
        for _ in range(tab_presses):
            self._press_key(VK_TAB)
            time.sleep(0.08)
        self._press_ctrl_combo(VK_V)
        time.sleep(0.2)
        self._press_key(VK_ENTER)
        if submit_twice:
            time.sleep(0.5)
            self._press_key(VK_ENTER)

    def _run_auto_submit(self, provider: str):
        # Browser launch/focus timing is inconsistent, so use two staggered attempts.
        attempts = []
        if provider == "gemini":
            attempts = [
                {"delay": 5.5, "tabs": 0, "double_enter": False},
                {"delay": 3.0, "tabs": 2, "double_enter": False},
            ]
        elif provider == "perplexity":
            attempts = [
                {"delay": 3.5, "tabs": 0, "double_enter": False},
                {"delay": 2.0, "tabs": 1, "double_enter": False},
            ]

        try:
            for attempt in attempts:
                time.sleep(attempt["delay"])
                self._paste_and_submit(
                    tab_presses=attempt["tabs"],
                    submit_twice=attempt["double_enter"],
                )
        except Exception as e:
            self.after(0, self._append_text, f"\n[自動送出失敗] {e}\n")

    def _open_url_and_auto_submit(self, url: str, provider: str):
        webbrowser.open(url)
        threading.Thread(
            target=self._run_auto_submit,
            args=(provider,),
            daemon=True,
        ).start()

    def _build_ui(self):
        # Header area
        hdr = tk.Frame(self.frame, bg=theme.BG2)
        hdr.pack(fill="x", side="top")
        
        lbl = tk.Label(hdr, text=f"🤖 {self.dialog_title} - {self.symbol}", font=theme.FONT_BOLD, fg=theme.FG, bg=theme.BG2)
        lbl.pack(side="left", padx=10, pady=8)
        
        close_btn = tk.Label(hdr, text="✕", font=theme.FONT, fg=theme.FG_DIM, bg=theme.BG2, cursor="hand2")
        close_btn.pack(side="right", padx=10, pady=8)
        close_btn.bind("<Button-1>", lambda e: self.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#FF4444"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=theme.FG_DIM))
        
        # Main text area
        self.text_area = tk.Text(self.frame, font=("Segoe UI", 10), bg=theme.BG, fg=theme.FG, bd=0, wrap="word", padx=15, pady=15, state="disabled")
        self.text_area.pack(fill="both", expand=True)
        
        # Action bar at bottom
        self.action_bar = tk.Frame(self.frame, bg=theme.BG2, pady=10)
        self.action_bar.pack(fill="x", side="bottom")
        
        # Fallback buttons
        self.btn_gemini = tk.Label(self.action_bar, text="🌐 開啟 Gemini (已複製指令)", font=("Segoe UI", 10, "bold"), fg=theme.FG, bg=theme.ACCENT, padx=12, pady=6, cursor="hand2")
        self.btn_gemini.pack(pady=4)

        self.btn_perplexity = tk.Label(self.action_bar, text="🧠 開啟 Perplexity (已複製指令)", font=("Segoe UI", 10, "bold"), fg=theme.FG, bg=theme.ACCENT, padx=12, pady=6, cursor="hand2")
        self.btn_perplexity.pack(pady=4)
        
        self.btn_gemini.bind("<Button-1>", self._on_gemini_clicked)
        self.btn_gemini.bind("<Enter>", lambda e: self.btn_gemini.config(bg=theme.UP))
        self.btn_gemini.bind("<Leave>", lambda e: self.btn_gemini.config(bg=theme.ACCENT))

        self.btn_perplexity.bind("<Button-1>", self._on_perplexity_clicked)
        self.btn_perplexity.bind("<Enter>", lambda e: self.btn_perplexity.config(bg=theme.UP))
        self.btn_perplexity.bind("<Leave>", lambda e: self.btn_perplexity.config(bg=theme.ACCENT))
        
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

    def _show_news_basis(self):
        self._append_text("本次資料基礎\n")
        self._append_text(f"以下是這次送進模型的 {self.context_label} 原始內容。\n\n")
        self._append_text(f"{self.news_text}\n")
        self._append_text("\n----------------------------------------\n")
        self._append_text("AI 分析結果\n\n")

    def _start_stream(self):
        self._show_news_basis()
        self._append_text("正在嘗試免費模型...\n\n")
        self._first_token_timer = self.after(8000, self._handle_no_first_token)
        
        def worker():
            try:
                for chunk in self.stream_generator(self.symbol, self.news_text):
                    self.after(0, self._on_stream_chunk, chunk)
                self.after(0, self._on_stream_end)
            except Exception as e:
                self.after(0, self._append_text, f"\n\n分析發生錯誤: {e}")
                
        threading.Thread(target=worker, daemon=True).start()

    def _on_stream_chunk(self, chunk: str):
        if not self._first_chunk_received and chunk.strip():
            self._first_chunk_received = True
            self._cancel_first_token_timer()
        self._append_text(chunk)

    def _on_stream_end(self):
        if not self._first_chunk_received:
            self._handle_no_first_token()

    def _cancel_first_token_timer(self):
        if self._first_token_timer is not None:
            try:
                self.after_cancel(self._first_token_timer)
            except Exception:
                pass
            self._first_token_timer = None

    def _handle_no_first_token(self):
        if self._fallback_triggered or self._first_chunk_received:
            return
        self._fallback_triggered = True
        self._append_text("⚠️ 未取得回覆，已自動改用 Perplexity 備案並送出問題。\n\n")
        self._open_perplexity(auto=True)

    def _build_prompt(self):
        today = datetime.now().date()
        start_date = today - timedelta(days=7)
        prompt = f"""請幫我分析以下關於 {self.symbol} 的{self.context_label}，並嚴格遵循以下格式使用繁體中文輸出：

今天日期是 {today:%Y-%m-%d}。
你只能採用 {start_date:%Y-%m-%d} 到 {today:%Y-%m-%d} 之間的資訊。
如果資料早於 {start_date:%Y-%m-%d}、日期不明，或無法確認時間，一律忽略，不得引用。
若最近 7 天資料不足，請直接明說「最近 7 天可用資訊不足」。

1. 🔥 近期多方動能 (利多):
(列出 1~3 點最重要的好消息)

2. 🧊 潛在空方風險 (利空):
(列出 1~3 點需要注意的壞消息或隱憂)

3. 📝 總結判定:
(以一句話總結當前短線情緒，例如：整體情緒偏多/中立/偏空/狂熱/恐慌)

資料如下：
{self.news_text}
"""
        return prompt

    def _copy_prompt_to_clipboard(self):
        prompt = self._build_prompt()
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.update() # Keep it in clipboard
        return prompt
        
    def _on_gemini_clicked(self, event):
        self._copy_prompt_to_clipboard()
        self.btn_gemini.config(text="✅ 已開啟 Gemini 並自動送出！")
        self.after(2000, lambda: self.btn_gemini.config(text="🌐 開啟 Gemini (已複製指令)"))
        self._append_text("已啟動 Gemini，自動貼上並送出中...\n\n")
        self._open_url_and_auto_submit("https://gemini.google.com/app", "gemini")

    def _on_perplexity_clicked(self, event):
        self._open_perplexity(auto=False)

    def _open_perplexity(self, auto: bool = False):
        prompt = self._copy_prompt_to_clipboard()
        self.btn_perplexity.config(text="✅ 已開啟 Perplexity 並自動送出！")
        self.after(2000, lambda: self.btn_perplexity.config(text="🧠 開啟 Perplexity (已複製指令)"))
        if auto:
            self.btn_gemini.config(text="🌐 開啟 Gemini (已複製指令)")
        else:
            self._append_text("已啟動 Perplexity，自動貼上並送出中...\n\n")
        query_url = "https://www.perplexity.ai/search?q=" + urllib.parse.quote(prompt)
        self._open_url_and_auto_submit(query_url, "perplexity")
        
def show_ai_dialog(
    parent,
    symbol,
    fetch_news_fn,
    stream_summary_fn,
    dialog_title="AI 情報分析",
    context_label="近期新聞與資訊",
):
    """
    Helper function to wrap the background fetching of news and spawning of the dialog.
    """
    def _worker():
        news_text = fetch_news_fn(symbol)
        def _spawn():
            dlg = AIDialog(
                parent,
                symbol,
                news_text,
                stream_summary_fn,
                dialog_title=dialog_title,
                context_label=context_label,
            )
            dlg.focus_set()
        parent.after(0, _spawn)
        
    threading.Thread(target=_worker, daemon=True).start()
