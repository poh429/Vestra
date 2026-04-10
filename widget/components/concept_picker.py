import tkinter as tk
from tkinter import messagebox
import threading

from widget.style import theme
from widget.data.cmoney_concept import fetch_concept_list as fetch_tw_concepts, fetch_concept_stocks as fetch_tw_stocks
from widget.data.finguider_concept import fetch_concept_list as fetch_us_concepts, fetch_concept_stocks as fetch_us_stocks

class ConceptPickerDialog(tk.Toplevel):
    def __init__(self, parent, on_add_callback, existing_symbols):
        """
        on_add_callback: func(concept_name, selected_stocks_list) -> None
        existing_symbols: list of currently tracked symbols (to skip or disable)
        """
        super().__init__(parent)
        self.title("🏷 概念股瀏覽器")
        self.geometry("450x550")
        self.minsize(450, 550)
        self.configure(bg=theme.BG)
        self.attributes("-topmost", True)
        self.resizable(True, True)
        
        self.on_add_callback = on_add_callback
        self.existing_symbols = set(existing_symbols)
        
        self._current_tab = "TW" # "TW" or "US"
        self._concepts_tw = []
        self._concepts_us = []
        
        self._current_concept = None
        self._stocks = []
        self._checkbox_vars = {}
        
        self._setup_ui()
        self._load_concepts()

    def _bind_mousewheel(self, widget, canvas):
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        widget.bind("<Enter>", lambda _: widget.bind_all("<MouseWheel>", _on_mousewheel))
        widget.bind("<Leave>", lambda _: widget.unbind_all("<MouseWheel>"))

    def _setup_ui(self):
        # Top Tabs
        self.tab_frame = tk.Frame(self, bg=theme.BORDER)
        self.tab_frame.pack(fill="x")
        
        self.btn_tab_tw = tk.Button(self.tab_frame, text="台股 (CMoney)", font=theme.FONT_BOLD, 
                                    bg=theme.BG2, fg=theme.FG, bd=0, relief="flat",
                                    command=lambda: self._switch_tab("TW"))
        self.btn_tab_tw.pack(side="left", fill="x", expand=True, ipady=4)
        
        self.btn_tab_us = tk.Button(self.tab_frame, text="美股 (FinGuider)", font=theme.FONT_BOLD, 
                                    bg=theme.BG, fg=theme.FG_DIM, bd=0, relief="flat",
                                    command=lambda: self._switch_tab("US"))
        self.btn_tab_us.pack(side="left", fill="x", expand=True, ipady=4)
        
        # Search & Concept Grid Frame
        self.concept_frame = tk.Frame(self, bg=theme.BG)
        self.concept_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.lbl_status = tk.Label(self.concept_frame, text="載入中...", font=theme.FONT_SMALL, fg=theme.FG_DIM, bg=theme.BG)
        self.lbl_status.pack(pady=10)
        
        # We use a Canvas for the concept grid to allow scrolling if many concepts
        self.c_canvas = tk.Canvas(self.concept_frame, bg=theme.BG, highlightthickness=0)
        self.c_scroll = tk.Scrollbar(self.concept_frame, orient="vertical", command=self.c_canvas.yview)
        self.c_inner = tk.Frame(self.c_canvas, bg=theme.BG)
        
        self.c_window_id = self.c_canvas.create_window((0, 0), window=self.c_inner, anchor="nw")
        self.c_canvas.configure(yscrollcommand=self.c_scroll.set)
        
        def _on_c_canvas_configure(event):
            # Make the inner frame exactly as wide as the canvas
            self.c_canvas.itemconfig(self.c_window_id, width=event.width)
            self.c_canvas.configure(scrollregion=self.c_canvas.bbox("all"))

        self.c_canvas.bind("<Configure>", _on_c_canvas_configure)
        self.c_inner.bind("<Configure>", lambda e: self.c_canvas.configure(scrollregion=self.c_canvas.bbox("all")))
        self._bind_mousewheel(self.c_canvas, self.c_canvas)
        self._bind_mousewheel(self.c_inner, self.c_canvas)
        
        # Details Frame (Stocks Checklist)
        self.detail_frame = tk.Frame(self, bg=theme.BG, highlightbackground=theme.BORDER, highlightthickness=1)
        
        # Header for detail
        self.detail_header = tk.Frame(self.detail_frame, bg=theme.BG2)
        self.detail_header.pack(fill="x")
        self.lbl_concept_title = tk.Label(self.detail_header, text="請選擇概念", font=theme.FONT_BOLD, fg=theme.FG, bg=theme.BG2)
        self.lbl_concept_title.pack(side="left", padx=10, pady=6)
        
        self.btn_select_all = tk.Button(self.detail_header, text="全選", font=theme.FONT_TINY,
                                        bg=theme.BG3, fg=theme.FG_DIM, bd=0, relief="flat",
                                        command=self._select_all)
        self.btn_select_all.pack(side="right", padx=10, pady=6)
        
        self.btn_deselect_all = tk.Button(self.detail_header, text="全不選", font=theme.FONT_TINY,
                                          bg=theme.BG3, fg=theme.FG_DIM, bd=0, relief="flat",
                                          command=self._deselect_all)
        self.btn_deselect_all.pack(side="right", padx=0, pady=6)
        
        # Stocks Canvas
        self.s_canvas = tk.Canvas(self.detail_frame, bg=theme.BG, highlightthickness=0)
        self.s_scroll = tk.Scrollbar(self.detail_frame, orient="vertical", command=self.s_canvas.yview)
        self.s_inner = tk.Frame(self.s_canvas, bg=theme.BG)
        
        self.s_window_id = self.s_canvas.create_window((0, 0), window=self.s_inner, anchor="nw")
        self.s_canvas.configure(yscrollcommand=self.s_scroll.set)
        
        def _on_s_canvas_configure(event):
            self.s_canvas.itemconfig(self.s_window_id, width=event.width)
            self.s_canvas.configure(scrollregion=self.s_canvas.bbox("all"))

        self.s_canvas.bind("<Configure>", _on_s_canvas_configure)
        self.s_inner.bind("<Configure>", lambda e: self.s_canvas.configure(scrollregion=self.s_canvas.bbox("all")))
        
        self.s_canvas.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.s_scroll.pack(side="right", fill="y")
        
        # Bottom Add Button
        self.bottom_frame = tk.Frame(self, bg=theme.BG)
        self.bottom_frame.pack(fill="x", side="bottom", padx=10, pady=10)
        
        self.btn_add = tk.Button(self.bottom_frame, text="✅ 加入選定標的 (0)", font=theme.FONT_BOLD,
                                 bg=theme.ACCENT, fg=theme.FG, bd=0, relief="flat",
                                 command=self._submit)

    def _switch_tab(self, tab):
        if self._current_tab == tab:
            return
        self._current_tab = tab
        if tab == "TW":
            self.btn_tab_tw.config(bg=theme.BG2, fg=theme.FG)
            self.btn_tab_us.config(bg=theme.BG, fg=theme.FG_DIM)
        else:
            self.btn_tab_us.config(bg=theme.BG2, fg=theme.FG)
            self.btn_tab_tw.config(bg=theme.BG, fg=theme.FG_DIM)
            
        self.detail_frame.pack_forget()
        self.btn_add.pack_forget()
        self.concept_frame.pack_configure(fill="both", expand=True)
        self._render_concept_grid()

    def _load_concepts(self):
        def _worker():
            self._concepts_tw = fetch_tw_concepts()
            self._concepts_us = fetch_us_concepts()
            self.after(0, self._render_concept_grid)
            
        threading.Thread(target=_worker, daemon=True).start()

    def _render_concept_grid(self):
        self.lbl_status.pack_forget()
        for w in self.c_inner.winfo_children():
            w.destroy()
            
        concepts = self._concepts_tw if self._current_tab == "TW" else self._concepts_us
        
        if not concepts:
            tk.Label(self.c_inner, text="無法載入概念清單", fg=theme.DOWN, bg=theme.BG).pack(pady=10)
            return

        self.c_canvas.pack(side="left", fill="both", expand=True)
        self.c_scroll.pack(side="right", fill="y")

        # Top concepts first
        from widget.data.cmoney_concept import HOT_CONCEPTS as CMONEY_HOT
        hot = CMONEY_HOT if self._current_tab == "TW" else ["AI 資料中心", "AI PC", "生成式AI", "半導體", "輝達", "蘋果", "電動車"]
        
        sorted_concepts = []
        hot_list = []
        normal_list = []
        for c in concepts:
            if any(h in c["name"] for h in hot):
                hot_list.append(c)
            else:
                normal_list.append(c)
                
        sorted_concepts = hot_list + normal_list
        
        col_count = 3
        # Configure columns to expand
        for i in range(col_count):
            self.c_inner.grid_columnconfigure(i, weight=1)

        for i, c in enumerate(sorted_concepts):
            lbl = c["name"]
            if self._current_tab == "US" and c.get("ret_1m") is not None:
                ret = c.get("ret_1m")
                r_str = f"{ret*100:+.1f}%"
                color = theme.UP if ret >= 0 else theme.DOWN
                # Two-line display for US concepts showing the percentage
                btn = tk.Button(self.c_inner, text=f"{lbl}\n{r_str}", font=theme.FONT_TINY, width=16, height=2,
                                bg=theme.BG3, fg=color, bd=0, relief="flat",
                                command=lambda cid=c["id"], cn=c["name"]: self._select_concept(cid, cn))
            else:
                btn = tk.Button(self.c_inner, text=lbl, font=theme.FONT_TINY, width=16, height=2,
                                bg=theme.BG3, fg=theme.FG, bd=0, relief="flat",
                                command=lambda cid=c["id"], cn=c["name"]: self._select_concept(cid, cn))
            
            # sticky="nsew" forces the button to fill the expanded grid cell
            btn.grid(row=i // col_count, column=i % col_count, padx=4, pady=4, sticky="nsew")

    def _select_concept(self, cid, cname):
        self._current_concept = cname
        self.concept_frame.pack_configure(fill="x", expand=False)
        self.c_canvas.configure(height=120)
        self.detail_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.btn_add.pack(fill="x", ipady=6)
        self.lbl_concept_title.config(text=f"載入中... {cname}")
        
        for w in self.s_inner.winfo_children():
            w.destroy()
            
        def _worker():
            if self._current_tab == "TW":
                stocks = fetch_tw_stocks(cid)
            else:
                stocks = fetch_us_stocks(cid)
            self.after(0, lambda: self._render_stocks(stocks))
            
        threading.Thread(target=_worker, daemon=True).start()

    def _render_stocks(self, stocks):
        self._stocks = stocks
        self._checkbox_vars.clear()
        
        self.lbl_concept_title.config(text=f"【{self._current_concept}】 共 {len(stocks)} 檔")
        
        if not stocks:
            tk.Label(self.s_inner, text="無成分股資料", fg=theme.FG_DIM, bg=theme.BG).pack(pady=10)
            self._update_add_btn()
            return
            
        for i, s in enumerate(stocks):
            frame = tk.Frame(self.s_inner, bg=theme.BG)
            frame.pack(fill="x", pady=2)
            
            code = s.get("code")
            name = s.get("name")
            sym = f"{code}.TW" if self._current_tab == "TW" else code
            
            # Formatted text
            disp = f"{name} ({code})" if name != code else code
            
            var = tk.BooleanVar()
            is_existing = sym in self.existing_symbols
            var.set(not is_existing) # check if not already tracked
            
            self._checkbox_vars[sym] = var
            var.trace_add("write", lambda *_: self._update_add_btn())
            
            cb = tk.Checkbutton(frame, variable=var, bg=theme.BG, activebackground=theme.BG,
                                fg=theme.FG, activeforeground=theme.FG,
                                bd=0, highlightthickness=0, selectcolor="#aaaaaa")
            cb.pack(side="left")
            
            fg_color = theme.FG_DIM if is_existing else theme.FG
            text = f"{disp} (已加入)" if is_existing else disp
            tk.Label(frame, text=text, fg=fg_color, bg=theme.BG, font=theme.FONT_SMALL).pack(side="left")
            
            if self._current_tab == "US" and s.get("ret_1m") is not None:
                ret = s.get("ret_1m")
                r_str = f"{ret*100:+.1f}%"
                r_col = theme.UP if ret >= 0 else theme.DOWN
                tk.Label(frame, text=r_str, fg=r_col, bg=theme.BG, font=theme.FONT_TINY).pack(side="right", padx=10)
                
        self._update_add_btn()

    def _select_all(self):
        for v in self._checkbox_vars.values():
            v.set(True)

    def _deselect_all(self):
        for v in self._checkbox_vars.values():
            v.set(False)

    def _update_add_btn(self):
        count = sum(v.get() for v in self._checkbox_vars.values())
        self.btn_add.config(text=f"✅ 加入選定標的 ({count})", state="normal" if count > 0 else "disabled")

    def _submit(self):
        selected = [sym for sym, var in self._checkbox_vars.items() if var.get()]
        if not selected:
            return
            
        # Call the callback
        self.on_add_callback(self._current_concept, selected, self._current_tab)
        self.destroy()

