"""AnalystPanel — Progressive disclosure viewer for Analyst OS data.

Opens from a card's right-click menu. Contains 4 tabs:
  Tab 1: Thesis Summary (Layer 2)
  Tab 2: Tree View (Layer 3)
  Tab 3: Evidence Ledger (Layer 4)
  Tab 4: Review Queue (Layer 5)

Read-only. Does NOT modify evaluator, pipeline, or scheduler logic.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import json
from datetime import datetime
from typing import Optional

from widget.style import theme
from widget.agent.coverage_workspace import CoverageWorkspace


# ── Colour Constants ────────────────────────────────────────────────────────

_TAB_BG = "#0e0e14"
_SECT_BG = "#12121a"
_ROW_BG = "#16161e"
_ROW_ALT_BG = "#1a1a24"
_BADGE_INTACT = "#4CAF50"
_BADGE_DELAYED = "#FFC107"
_BADGE_WEAKENING = "#FF9800"
_BADGE_BROKEN = "#F44336"
_BADGE_NEUTRAL = "#5a5a72"

_STATE_COLORS = {
    "intact": _BADGE_INTACT,
    "delayed": _BADGE_DELAYED,
    "weakening": _BADGE_WEAKENING,
    "broken": _BADGE_BROKEN,
}
_STATE_ZH = {
    "intact": "邏輯完好",
    "delayed": "邏輯延後",
    "weakening": "邏輯弱化",
    "broken": "邏輯已破",
}
_VERIFY_ZH = {
    "verified": "已驗證",
    "accepted": "已接受",
    "unverified": "未驗證",
    "rejected": "已拒絕",
}
_VERIFY_COLORS = {
    "verified": _BADGE_INTACT,
    "accepted": theme.ACCENT,
    "unverified": theme.FG_MUTED,
    "rejected": _BADGE_BROKEN,
}

_ANCHOR_GAP = 8


class AnalystPanel(tk.Toplevel):
    """Progressive-disclosure viewer for one symbol's Analyst OS data."""

    def __init__(
        self,
        parent: tk.Misc,
        symbol: str,
        *,
        thesis_eval=None,
        monitor_events: list | None = None,
        draft=None,
        scheduler_svc=None,
        quota_guard=None,
    ):
        super().__init__(parent)
        self._symbol = symbol
        self._thesis_eval = thesis_eval
        self._monitor_events = monitor_events or []
        self._draft = draft
        self._scheduler = scheduler_svc
        self._quota = quota_guard
        self._is_polling = True
        self._last_diagnostic_ts = 0.0

        self.title(f"📊 Analyst OS — {symbol}")
        self.configure(bg=theme.BG)
        self.resizable(True, True)
        self.minsize(480, 520)
        self.geometry("520x640")
        self.attributes("-topmost", True)
        try:
            self.transient(parent)
        except Exception:
            pass

        # Live Status Bar (v1.8)
        self._live_status_frame = tk.Frame(self, bg=theme.BG2, height=24)
        self._live_status_frame.pack(fill="x", padx=2, pady=(0, 2))
        self._live_label = tk.Label(
            self._live_status_frame, 
            text=" 📡 系統就緒 ", 
            font=("Inter", 9), 
            bg=theme.BG2, 
            fg=theme.FG_DIM
        )
        self._live_label.pack(side="left", padx=5)

        self._progress_canvas = tk.Canvas(
            self._live_status_frame, 
            height=4, 
            bg=theme.BG3, 
            highlightthickness=0
        )
        self._progress_canvas.pack(side="left", fill="x", expand=True, padx=10)
        self._progress_bar = self._progress_canvas.create_rectangle(0, 0, 0, 4, fill="#BB86FC", outline="")

        self._build_ui()
        self._add_resize_grip()
        self.after_idle(self._position_beside_parent)
        
        # Start auto-refresh polling (v1.7-c stability)
        self.after(2000, self._poll_for_updates)

    # ── Layout ──────────────────────────────────────────────────────────────

    def _position_beside_parent(self):
        try:
            self.update_idletasks()
            p = self.master
            if p is None or not getattr(p, "winfo_exists", lambda: False)():
                return
            dlg_w = self.winfo_width()
            dlg_h = self.winfo_height()
            px = p.winfo_rootx()
            py = p.winfo_rooty()
            pw = p.winfo_width()
            scr_w = self.winfo_screenwidth()
            scr_h = self.winfo_screenheight()

            x = px + pw + _ANCHOR_GAP
            if x + dlg_w > scr_w:
                x = max(0, px - dlg_w - _ANCHOR_GAP)
            y = max(0, min(py, scr_h - dlg_h))
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self):
        # ── Status bar at top ──
        self._status_bar = tk.Frame(self, bg=_SECT_BG, height=28)
        self._status_bar.pack(fill="x")
        self._status_bar.pack_propagate(False)
        self._build_status_bar()

        # ── Notebook (tabs) ──
        style = ttk.Style()
        style.configure(
            "Analyst.TNotebook",
            background=theme.BG,
            borderwidth=0,
        )
        style.configure(
            "Analyst.TNotebook.Tab",
            background=theme.BG2,
            foreground=theme.FG_DIM,
            padding=[10, 4],
            font=("Segoe UI", 8),
        )
        style.map(
            "Analyst.TNotebook.Tab",
            background=[("selected", theme.BG3)],
            foreground=[("selected", theme.FG)],
        )

        self._nb = ttk.Notebook(self, style="Analyst.TNotebook")
        self._nb.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        # We store the inner frames of each tab for refreshing
        self._tab_frames = {}

        # Tab 0: Research Flow (v1.9 Metaso style)
        tab0 = tk.Frame(self._nb, bg=theme.BG)
        self._nb.add(tab0, text="  研究進程  ")
        self._build_tab_flow(tab0)

        # Tab 1: Summary
        tab1 = self._scrollable_frame(self._nb)
        self._nb.add(tab1["outer"], text="  摘要  ")
        self._tab_frames["summary"] = tab1["inner"]
        self._build_tab_summary(tab1["inner"])

        # Tab 2: Tree
        tab2 = self._scrollable_frame(self._nb)
        self._nb.add(tab2["outer"], text="  邏輯樹  ")
        self._tab_frames["tree"] = tab2["inner"]
        self._build_tab_tree(tab2["inner"])

        # Tab 3: Evidence
        tab3 = self._scrollable_frame(self._nb)
        self._nb.add(tab3["outer"], text="  證據帳本  ")
        self._tab_frames["evidence"] = tab3["inner"]
        self._build_tab_evidence(tab3["inner"])

        # Tab 4: Review Queue
        tab4 = self._scrollable_frame(self._nb)
        self._nb.add(tab4["outer"], text="  審核佇列  ")
        self._tab_frames["review"] = tab4["inner"]
        self._build_tab_review(tab4["inner"])

        # Tab 5: Coverage Report (v1.5.2 sidecar hook)
        tab5 = self._scrollable_frame(self._nb)
        self._nb.add(tab5["outer"], text="  覆蓋報告  ")
        self._tab_frames["coverage"] = tab5["inner"]
        self._build_tab_coverage(tab5["inner"])

        # Tab 6: Live Console (v1.8)
        tab6 = tk.Frame(self._nb, bg=theme.BG)
        self._nb.add(tab6, text="  即時控制台  ")
        self._build_tab_console(tab6)

    def _build_tab_flow(self, parent: tk.Frame):
        """Metaso-style dynamic flow dashboard."""
        self._flow_container = tk.Frame(parent, bg=theme.BG)
        self._flow_container.pack(fill="both", expand=True, padx=20, pady=20)

        # ── Left: Vertical Timeline ──
        self._timeline_canvas = tk.Canvas(
            self._flow_container, 
            bg=theme.BG, 
            width=260, 
            highlightthickness=0
        )
        self._timeline_canvas.pack(side="left", fill="y")
        
        # ── Right: Live Map & Thoughts ──
        right_panel = tk.Frame(self._flow_container, bg=theme.BG)
        right_panel.pack(side="left", fill="both", expand=True, padx=(20, 0))

        # Logic Tree Map (Miniature)
        self._tree_map_label = tk.Label(
            right_panel, text="邏輯樹驗證地圖", 
            font=("Segoe UI", 9, "bold"), fg=theme.FG_DIM, bg=theme.BG, anchor="w"
        )
        self._tree_map_label.pack(fill="x", pady=(0, 5))
        
        self._tree_canvas = tk.Canvas(
            right_panel, bg=theme.BG2, height=180, 
            highlightthickness=1, highlightbackground=theme.BORDER
        )
        self._tree_canvas.pack(fill="x", pady=(0, 15))

        # Thought Ticker
        tk.Label(
            right_panel, text="實時思維鏈 (Thought Chain)", 
            font=("Segoe UI", 9, "bold"), fg=theme.FG_DIM, bg=theme.BG, anchor="w"
        ).pack(fill="x")
        
        self._thought_text = tk.Text(
            right_panel, bg=theme.BG3, fg="#888888", 
            font=("Consolas", 9), height=10, 
            borderwidth=0, highlightthickness=0, state="disabled"
        )
        self._thought_text.pack(fill="both", expand=True, pady=5)
        
        self._init_timeline()

    def _init_timeline(self):
        """Draw the initial gray timeline nodes."""
        self._timeline_nodes = {} # step_id -> (circle_id, text_id)
        steps = [
            ("framework", "架構規劃"),
            ("search", "深度數據搜尋"),
            ("leaf", "邏輯節點驗證"),
            ("valuation", "情境價值合成"),
            ("report", "撰寫研究報告"),
            ("done", "分析完成")
        ]
        
        x = 30
        y_start = 40
        y_gap = 60
        
        # Draw vertical line
        self._timeline_canvas.create_line(x, y_start, x, y_start + (len(steps)-1)*y_gap, fill=theme.BORDER, width=2)
        
        for i, (sid, label) in enumerate(steps):
            y = y_start + i * y_gap
            # Circle
            c = self._timeline_canvas.create_oval(x-6, y-6, x+6, y+6, fill=theme.BG3, outline=theme.BORDER, width=2)
            # Label
            t = self._timeline_canvas.create_text(x+20, y, text=label, fill=theme.FG_MUTED, font=("Segoe UI", 10), anchor="w")
            self._timeline_nodes[sid] = {"circle": c, "text": t, "y": y}

    def _update_flow_ui(self, step_id: str, status: str = "active", detail: str = ""):
        """status: pending | active | done | error"""
        if not hasattr(self, "_timeline_nodes"): return
        
        node = None
        # Map orchestrator steps to timeline IDs
        mapping = {
            "framework_router": "framework",
            "search_agent": "search",
            "leaf_research_executor": "leaf",
            "scenario_valuation": "valuation",
            "coverage_writer": "report",
            "review_queue_bridge": "report",
            "completed": "done"
        }
        sid = mapping.get(step_id, step_id)
        if sid not in self._timeline_nodes: return
        
        node = self._timeline_nodes[sid]
        color = {
            "active": "#BB86FC",
            "done": "#4CAF50",
            "error": "#CF6679",
            "pending": theme.BG3
        }.get(status, theme.BG3)
        
        self._timeline_canvas.itemconfig(node["circle"], fill=color, outline=color)
        self._timeline_canvas.itemconfig(node["text"], fill=theme.FG if status != "pending" else theme.FG_MUTED)
        
        if status == "active":
            self._pulse_node(sid)
            if detail:
                self._add_thought(detail)
        elif status == "error":
            if detail:
                self._add_thought(f"ERROR: {detail}")

    def _pulse_node(self, sid):
        """Simple pulsing animation for the active node."""
        if not hasattr(self, "_timeline_nodes"): return
        node = self._timeline_nodes[sid]
        
        # Toggle brightness
        current_color = self._timeline_canvas.itemcget(node["circle"], "fill")
        next_color = "#D1ADFF" if current_color == "#BB86FC" else "#BB86FC"
        self._timeline_canvas.itemconfig(node["circle"], fill=next_color)
        
        # Schedule next pulse only if still active (handled by poller setting it to done)
        # But for now we just do 1-2 cycles or let it be handled by next poll
        
    def _add_thought(self, text: str):
        if not hasattr(self, "_thought_text"): return
        self._thought_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M")
        self._thought_text.insert("end", f"[{ts}] ⚡ {text}\n")
        self._thought_text.see("end")
        self._thought_text.config(state="disabled")

    def _build_tab_console(self, parent: tk.Frame):
        """Metaso-style live log of the analysis process."""
        self._console_text = tk.Text(
            parent,
            bg=theme.BG3,
            fg="#A0A0A0",
            font=("Consolas", 10),
            padx=10,
            pady=10,
            borderwidth=0,
            highlightthickness=0,
            state="disabled",
        )
        self._console_text.pack(fill="both", expand=True)
        
        # Tag for highlights
        self._console_text.tag_config("info", foreground="#808080")
        self._console_text.tag_config("active", foreground="#BB86FC", font=("Consolas", 10, "bold"))
        self._console_text.tag_config("done", foreground="#4CAF50")
        self._console_text.tag_config("error", foreground="#CF6679")

    def _scrollable_frame(self, parent) -> dict:
        """Create a scrollable frame inside a tab."""
        outer = tk.Frame(parent, bg=_TAB_BG)
        canvas = tk.Canvas(outer, bg=_TAB_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=_TAB_BG)
        inner.dynamic_labels = []
        inner._last_w = 0

        # Robust resize logic with recursion guard:
        def _on_inner_configure(event, frame=inner, canv=canvas):
            # Only trigger reflow if width changed significantly (> 5px)
            if abs(event.width - frame._last_w) > 5:
                frame._last_w = event.width
                self._update_frame_wraplengths(frame, event.width)
            # Always update scroll region
            canv.configure(scrollregion=canv.bbox("all"))

        inner.bind("<Configure>", _on_inner_configure)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Canvas resize -> Set interior frame width
        canvas.bind("<Configure>", lambda e, cid=win_id: canvas.itemconfigure(cid, width=e.width))

        def _wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _wheel)

        return {"outer": outer, "inner": inner}

    def _update_frame_wraplengths(self, frame: tk.Frame, width: int):
        """Update wraplength of labels registered specifically to this frame."""
        new_wrap = max(200, width - 36)
        if not hasattr(frame, "dynamic_labels"):
            return
            
        # Filter existing labels
        frame.dynamic_labels = [l for l in frame.dynamic_labels if l.winfo_exists()]
        for lbl in frame.dynamic_labels:
            try:
                lbl.configure(wraplength=new_wrap)
            except Exception:
                pass

    def _register_label(self, parent: tk.Frame, label: tk.Label):
        """Register a label for dynamic reflowing. parent must be the 'inner' frame."""
        # Find the 'inner' frame in the parent hierarchy
        target = parent
        while target and not hasattr(target, "dynamic_labels"):
            target = target.master
            if target == self: # Stop at Toplevel
                break
        
        if hasattr(target, "dynamic_labels"):
            target.dynamic_labels.append(label)

    def _add_resize_grip(self):
        """Add a visual resize handle at the bottom-right corner."""
        grip = ttk.Sizegrip(self)
        # Background of sizegrip usually follows the theme
        grip.place(relx=1.0, rely=1.0, anchor="se")

    def _poll_for_updates(self):
        """Periodically check for analysis completion and refresh UI."""
        if not self.winfo_exists():
            self._is_polling = False
            return

        try:
            from widget.agent.coverage_workspace import CoverageWorkspace
            ws = CoverageWorkspace()
            diag = ws.load_run_diagnostic(self._symbol)
            
            if diag:
                status = diag.get("status")
                active_step = diag.get("active_step", "")
                active_detail = diag.get("active_detail", "")
                completed_list = diag.get("steps_completed", [])
                failed_map = diag.get("steps_failed", {})

                # v1.9 Fix: Update all nodes based on historical state
                for c_step in completed_list:
                    self._update_flow_ui(c_step, "done")
                
                for f_step, f_reason in failed_map.items():
                    self._update_flow_ui(f_step, "error", str(f_reason))

                if status == "running":
                    self._update_console(f"> [{active_step}] {active_detail}")
                    self._update_live_progress(active_step)
                    self._update_flow_ui(active_step, "active", active_detail)
                    # Auto-switch to flow tab on start
                    if self._nb.index("current") != 0:
                        self._nb.select(0)
                        
                elif status == "completed":
                    self._update_console("✅ Analysis Completed Successfully.")
                    self._update_live_progress("completed")
                    self._update_flow_ui("completed", "done")
                elif status == "failed":
                    # reason = diag.get("steps_failed", {}) # already handled in loop above
                    self._update_console(f"❌ Analysis Failed (See details in Research Flow tab)", tag="error")
                    self._update_live_progress("failed")

                # Existing polling logic
                path = ws.path_for(self._symbol, "run_diagnostic.json")
                if path.exists():
                    mtime = path.stat().st_mtime
                    if mtime > self._last_diagnostic_ts:
                        self._last_diagnostic_ts = mtime
                        # Only refresh UI if status is not 'running' (wait for it to finish)
                        if diag.get("status") != "running":
                            self.refresh_all_data()
            
        except Exception as e:
            print(f"[AnalystPanel] polling error: {e}")

        if self._is_polling:
            self.after(2000, self._poll_for_updates)

    def _update_console(self, msg: str, tag: str = "info"):
        if not hasattr(self, "_console_text") or not self._console_text.winfo_exists():
            return
        
        self._console_text.config(state="normal")
        # Check if last line is same to avoid spamming
        last_line = self._console_text.get("end-2c linestart", "end-1c")
        if msg in last_line:
            self._console_text.config(state="disabled")
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self._console_text.insert("end", f"[{timestamp}] {msg}\n", tag)
        self._console_text.see("end")
        self._console_text.config(state="disabled")

    def _update_live_progress(self, step: str):
        if not hasattr(self, "_progress_canvas") or not self._progress_canvas.winfo_exists():
            return
        
        steps = [
            "framework_router",
            "tree_builder",
            "leaf_research_executor",
            "scenario_valuation",
            "coverage_writer",
            "review_queue_bridge",
            "completed"
        ]
        try:
            idx = steps.index(step) + 1
            progress = idx / len(steps)
        except ValueError:
            progress = 0 if step != "failed" else 1.0
        
        w = self._progress_canvas.winfo_width()
        self._progress_canvas.coords(self._progress_bar, 0, 0, int(w * progress), 4)
        
        status_text = {
            "framework_router": "📡 正在規劃研究架構...",
            "tree_builder": "🌳 正在建構邏輯樹...",
            "leaf_research_executor": "🔍 正在蒐集證據...",
            "scenario_valuation": "⚖️ 正在進行情境估值...",
            "coverage_writer": "✍️ 正在撰寫覆蓋報告...",
            "review_queue_bridge": "🚀 正在發布審核任務...",
            "completed": "✅ 分析已完成",
            "failed": "❌ 分析失敗"
        }
        self._live_label.config(text=f" {status_text.get(step, '📡 系統就緒')} ", fg="#BB86FC" if step != "completed" else "#4CAF50")

    def refresh_all_data(self):
        """Reload all data from stores and refresh all tabs."""
        print(f"[AnalystPanel] Refreshing data for {self._symbol}...")
        
        # 1. Reload base data
        from widget.research.thesis_store import ThesisStore
        from widget.research.thesis_evaluator import evaluate_thesis
        from widget.research.engine import ResearchEngine
        
        # Reload evaluator result
        try:
            store = ThesisStore()
            defn = store.load(self._symbol)
            engine = ResearchEngine()
            snap, _, _ = engine.get_cached_display_data(self._symbol)
            if defn and snap:
                prev = engine._store.read_previous(self._symbol)
                self._thesis_eval = evaluate_thesis(defn, snap, prev)
        except Exception:
            pass

        # 2. Re-build Status Bar
        for child in self._status_bar.winfo_children():
            child.destroy()
        self._build_status_bar()

        # 3. Refresh Tab contents
        builders = {
            "summary": self._build_tab_summary,
            "tree": self._build_tab_tree,
            "evidence": self._build_tab_evidence,
            "review": self._build_tab_review,
            "coverage": self._build_tab_coverage,
        }

        for name, frame in self._tab_frames.items():
            if frame.winfo_exists():
                for child in frame.winfo_children():
                    child.destroy()
                builders[name](frame)
                # Ensure the scrollable frame updates its scroll region
                frame.event_generate("<Configure>")

    def _on_content_resize(self, event):
        """No longer used. Replaced by per-frame _update_frame_wraplengths."""
        pass

    # ── Status Bar ──────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = self._status_bar

        # Thesis state
        eval_ = self._thesis_eval
        if eval_:
            state = getattr(eval_, "thesis_state", "")
            color = _STATE_COLORS.get(state, _BADGE_NEUTRAL)
            zh = _STATE_ZH.get(state, state)
            tk.Label(
                bar, text="⬤", fg=color, bg=_SECT_BG,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(8, 2))
            tk.Label(
                bar, text=zh, fg=color, bg=_SECT_BG,
                font=("Segoe UI", 8, "bold"),
            ).pack(side="left")

        # Pending reviews (live queue)
        pending = self._count_pending_reviews()
        # Sidecar bridge review tasks
        sidecar_pending = self._count_sidecar_reviews()
        total_pending = pending + sidecar_pending
        if total_pending > 0:
            tk.Label(
                bar, text=f"⚠ {total_pending} 待審", fg=_BADGE_WEAKENING, bg=_SECT_BG,
                font=("Segoe UI", 8, "bold"),
            ).pack(side="left", padx=(12, 0))

        # Sidecar valuation risk indicator
        val_risk = self._load_sidecar_valuation_risk()
        if val_risk and val_risk.lower() in ("high", "critical"):
            risk_color = _BADGE_BROKEN if val_risk.lower() == "critical" else _BADGE_WEAKENING
            tk.Label(
                bar, text=f"⚡{val_risk.upper()}", fg=risk_color, bg=_SECT_BG,
                font=("Segoe UI", 7, "bold"),
            ).pack(side="left", padx=(8, 0))

        # Quota usage
        if self._quota:
            used = self._quota.used
            hard = self._quota.hard_rpd
            pct = int(used / hard * 100) if hard > 0 else 0
            q_color = _BADGE_INTACT if pct < 60 else (_BADGE_DELAYED if pct < 80 else _BADGE_BROKEN)
            tk.Label(
                bar, text=f"⟳ {used}/{hard} RPD", fg=q_color, bg=_SECT_BG,
                font=("Segoe UI", 7),
            ).pack(side="right", padx=(0, 8))

        # Scheduler subscriptions
        if self._scheduler:
            sched = self._scheduler._schedules
            subs = sum(1 for syms in sched.values() if self._symbol in syms)
            if subs > 0:
                tk.Label(
                    bar, text=f"⏱ {subs} 排程", fg=theme.FG_DIM, bg=_SECT_BG,
                    font=("Segoe UI", 7),
                ).pack(side="right", padx=(0, 8))

    # ── Tab 1: Thesis Summary (Layer 2) ─────────────────────────────────────

    def _build_tab_summary(self, parent: tk.Frame):
        draft = self._load_draft()
        eval_ = self._thesis_eval

        if not draft and not eval_:
            self._empty_label(parent, "尚未建立投資邏輯草稿。\n請先在卡片右鍵 → 📋 設定投資邏輯，\n進行掃描證據 → AI 建立草稿。")
            return

        # Thesis evaluation header
        if eval_:
            self._section(parent, "論文狀態")
            state = getattr(eval_, "thesis_state", "unknown")
            color = _STATE_COLORS.get(state, _BADGE_NEUTRAL)
            zh = _STATE_ZH.get(state, state)
            row = tk.Frame(parent, bg=_TAB_BG)
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=f"⬤ {zh}", fg=color, bg=_TAB_BG, font=("Segoe UI", 10, "bold")).pack(side="left")
            stage = getattr(eval_, "certainty_stage", "")
            if stage:
                tk.Label(row, text=f"確信階段：{stage}", fg=theme.FG_DIM, bg=_TAB_BG, font=("Segoe UI", 8)).pack(side="right")

            explanation = getattr(eval_, "explanation", "")
            if explanation:
                lbl = tk.Label(
                    parent, text=explanation, fg=theme.FG, bg=_TAB_BG,
                    font=("Segoe UI", 8), justify="left", anchor="w",
                )
                lbl.pack(fill="x", padx=12, pady=(0, 4))
                self._register_label(parent, lbl)

            action = getattr(eval_, "action_label_zh", "")
            if action:
                lbl = tk.Label(
                    parent, text=f"行動偏向：{action}", fg=theme.ACCENT, bg=_TAB_BG,
                    font=("Segoe UI", 8), anchor="w", justify="left"
                )
                lbl.pack(fill="x", padx=12, pady=(0, 6))
                self._register_label(parent, lbl)

        if draft:
            # Top question
            if draft.top_question:
                self._section(parent, "核心問題")
                self._info_row(parent, draft.top_question)

            # Summary
            if draft.summary:
                self._section(parent, "摘要")
                self._info_row(parent, draft.summary)

            # Market belief map
            mbm = draft.market_belief_map
            if mbm:
                self._section(parent, "市場認知差距")
                if mbm.consensus_view:
                    self._kv_row(parent, "共識觀點", mbm.consensus_view)
                if mbm.variant_view:
                    self._kv_row(parent, "差異認知", mbm.variant_view)
                if mbm.mispricing_hypothesis:
                    self._kv_row(parent, "錯價假說", mbm.mispricing_hypothesis)

            # Rerating triggers
            if draft.rerating_triggers:
                self._section(parent, "重估觸發條件")
                for trigger in draft.rerating_triggers:
                    self._bullet(parent, trigger)

            # Expected window & tree style
            row = tk.Frame(parent, bg=_TAB_BG)
            row.pack(fill="x", padx=12, pady=4)
            if draft.expected_window:
                tk.Label(row, text=f"時間窗口：{draft.expected_window}", fg=theme.FG_DIM, bg=_TAB_BG, font=("Segoe UI", 8)).pack(side="left")
            if draft.tree_style:
                tk.Label(row, text=f"結構：{draft.tree_style}", fg=theme.FG_MUTED, bg=_TAB_BG, font=("Segoe UI", 7)).pack(side="right")

        # Monitor events
        if self._monitor_events:
            self._section(parent, f"最近監控事件 ({len(self._monitor_events)})")
            for ev in self._monitor_events[:5]:
                sev_color = _STATE_COLORS.get(getattr(ev, "severity", ""), theme.FG_DIM)
                self._kv_row(parent, getattr(ev, "event_type", ""), getattr(ev, "summary", ""), value_fg=sev_color)

    # ── Tab 2: Tree View (Layer 3) ──────────────────────────────────────────

    def _build_tab_tree(self, parent: tk.Frame):
        draft = self._load_draft()
        if not draft or not draft.branches:
            self._empty_label(parent, "尚無邏輯樹結構。\n請先透過 AI 建立草稿來產生 branches / leaves。")
            return

        evidence_records = self._load_evidence()
        evidence_id_set = {r.evidence_id for r in evidence_records}

        for bi, branch in enumerate(draft.branches):
            # Branch header
            branch_frame = tk.Frame(parent, bg=_ROW_BG, relief="flat", bd=0)
            branch_frame.pack(fill="x", padx=8, pady=(6, 2))

            hdr = tk.Frame(branch_frame, bg=_ROW_BG)
            hdr.pack(fill="x", padx=6, pady=4)

            status_color = _BADGE_INTACT if branch.status == "open" else _BADGE_NEUTRAL
            tk.Label(hdr, text="▸", fg=theme.ACCENT, bg=_ROW_BG, font=("Segoe UI", 10, "bold")).pack(side="left")
            branch_lbl = tk.Label(
                hdr, text=f"{branch.name or f'Branch {bi+1}'}",
                fg=theme.FG, bg=_ROW_BG, font=("Segoe UI", 9, "bold"),
            )
            branch_lbl.pack(side="left", padx=(4, 0))
            self._register_label(parent, branch_lbl)
            
            tk.Label(
                hdr, text=f"{len(branch.leaves)} leaves",
                fg=theme.FG_DIM, bg=_ROW_BG, font=("Segoe UI", 7),
            ).pack(side="right")

            if branch.question:
                lbl = tk.Label(
                    branch_frame, text=branch.question,
                    fg=theme.FG_DIM, bg=_ROW_BG, font=("Segoe UI", 8),
                    justify="left", anchor="w",
                )
                lbl.pack(fill="x", padx=10, pady=(0, 2))
                self._register_label(parent, lbl)

            # Kill conditions for this branch
            if branch.kill_conditions:
                kc_frame = tk.Frame(branch_frame, bg=_ROW_BG)
                kc_frame.pack(fill="x", padx=10, pady=(0, 4))
                tk.Label(kc_frame, text="☠ Kill:", fg=_BADGE_BROKEN, bg=_ROW_BG, font=("Segoe UI", 7, "bold")).pack(side="left")
                tk.Label(
                    kc_frame, text=" · ".join(branch.kill_conditions[:3]),
                    fg=_BADGE_WEAKENING, bg=_ROW_BG, font=("Segoe UI", 7),
                ).pack(side="left", padx=(4, 0))

            # Leaves
            for li, leaf in enumerate(branch.leaves):
                leaf_bg = _ROW_ALT_BG if li % 2 == 0 else _ROW_BG
                lf = tk.Frame(branch_frame, bg=leaf_bg)
                lf.pack(fill="x", padx=12, pady=1)

                top_row = tk.Frame(lf, bg=leaf_bg)
                top_row.pack(fill="x", padx=4, pady=2)

                leaf_status_color = _BADGE_INTACT if leaf.status == "open" else _BADGE_NEUTRAL
                tk.Label(top_row, text="•", fg=leaf_status_color, bg=leaf_bg, font=("Segoe UI", 8)).pack(side="left")

                conclusion = leaf.conclusion or leaf.hypothesis or f"Leaf {li+1}"
                leaf_lbl = tk.Label(
                    top_row, text=conclusion,
                    fg=theme.FG, bg=leaf_bg, font=("Segoe UI", 8), anchor="w",
                    justify="left"
                )
                leaf_lbl.pack(side="left", padx=(4, 0), fill="x", expand=True)
                self._register_label(parent, leaf_lbl)

                # Evidence count for this leaf
                linked = sum(1 for eid in leaf.supporting_evidence_ids if eid in evidence_id_set)
                if linked > 0:
                    tk.Label(
                        top_row, text=f"📎 {linked}",
                        fg=theme.ACCENT, bg=leaf_bg, font=("Segoe UI", 7),
                    ).pack(side="right")

                # Kill condition
                kc_text = leaf.kill_condition or (leaf.kill_conditions[0] if leaf.kill_conditions else "")
                if kc_text:
                    lbl = tk.Label(
                        lf, text=f"☠ {kc_text}",
                        fg=_BADGE_WEAKENING, bg=leaf_bg, font=("Segoe UI", 7),
                        anchor="w", justify="left"
                    )
                    lbl.pack(fill="x", padx=20, pady=(0, 2))
                    self._register_label(parent, lbl)

    # ── Tab 3: Evidence Ledger (Layer 4) ────────────────────────────────────

    def _build_tab_evidence(self, parent: tk.Frame):
        records = self._load_evidence()
        if not records:
            self._empty_label(parent, "尚無證據紀錄。\n請先透過 ThesisDialog 的 🔍 掃描證據產生 EvidenceRecord。")
            return

        self._section(parent, f"證據帳本 — {len(records)} 筆")

        for i, rec in enumerate(records):
            bg = _ROW_ALT_BG if i % 2 == 0 else _ROW_BG
            card = tk.Frame(parent, bg=bg, relief="flat", bd=0)
            card.pack(fill="x", padx=8, pady=2)

            # Header row
            hdr = tk.Frame(card, bg=bg)
            hdr.pack(fill="x", padx=6, pady=(4, 0))

            direction_fg = _BADGE_INTACT if rec.direction == "bullish" else (
                _BADGE_BROKEN if rec.direction == "bearish" else theme.FG_DIM
            )
            tk.Label(hdr, text="▸", fg=direction_fg, bg=bg, font=("Segoe UI", 9)).pack(side="left")
            topic_lbl = tk.Label(
                hdr, text=rec.topic or rec.evidence_type or "Evidence",
                fg=theme.FG, bg=bg, font=("Segoe UI", 8, "bold"),
                anchor="w", justify="left"
            )
            topic_lbl.pack(side="left", padx=(4, 0), fill="x", expand=True)
            self._register_label(parent, topic_lbl)

            # Verification badge
            vs = rec.verification_status
            vs_color = _VERIFY_COLORS.get(vs, theme.FG_MUTED)
            vs_zh = _VERIFY_ZH.get(vs, vs)
            tk.Label(hdr, text=vs_zh, fg=vs_color, bg=bg, font=("Segoe UI", 7)).pack(side="right")
            if rec.created_at:
                date_short = rec.created_at[:10] if len(rec.created_at) >= 10 else rec.created_at
                tk.Label(hdr, text=date_short, fg=theme.FG_MUTED, bg=bg, font=("Segoe UI", 7)).pack(side="right", padx=(0, 6))

            # Detail frame (collapsible)
            detail = tk.Frame(card, bg=bg)
            detail.pack(fill="x", padx=10, pady=(0, 4))
            detail.pack_forget()  # Start collapsed

            def _populate_detail(frame, record):
                if record.claim:
                    self._detail_kv(frame, "主張", record.claim, bg)
                if record.why_it_matters:
                    self._detail_kv(frame, "重要性", record.why_it_matters, bg)
                if record.source_label:
                    self._detail_kv(frame, "來源", f"{record.source_label} / {record.source_field or '—'}", bg)
                if record.source_url:
                    self._detail_kv(frame, "URL", record.source_url, bg)
                if record.summary:
                    self._detail_kv(frame, "摘要", record.summary, bg)
                for qr in record.quote_refs[:2]:
                    self._detail_kv(frame, "引用", qr.get("text", ""), bg)

            # Toggle expand/collapse
            is_expanded = {"v": False}

            def _toggle(evt=None, d=detail, r=rec, expanded=is_expanded):
                if expanded["v"]:
                    d.pack_forget()
                    expanded["v"] = False
                else:
                    # Lazy populate on first expand
                    if not d.winfo_children():
                        _populate_detail(d, r)
                    d.pack(fill="x", padx=10, pady=(0, 4))
                    expanded["v"] = True

            for w in (hdr, card):
                w.bind("<Button-1>", _toggle)

    # ── Tab 4: Review Queue (Layer 5) ───────────────────────────────────────

    def _build_tab_review(self, parent: tk.Frame):
        tasks = self._load_review_tasks()
        if not tasks:
            self._empty_label(parent, "目前沒有待審核項目。")
            return

        pending = [t for t in tasks if t.status == "pending"]
        done = [t for t in tasks if t.status != "pending"]

        if pending:
            self._section(parent, f"⚠ 待審核 ({len(pending)})")
            for t in pending:
                self._review_card(parent, t)

        if done:
            self._section(parent, f"已處理 ({len(done)})")
            for t in done:
                self._review_card(parent, t, muted=True)

    def _review_card(self, parent: tk.Frame, task, muted: bool = False):
        bg = _ROW_ALT_BG
        fg = theme.FG_DIM if muted else theme.FG
        card = tk.Frame(parent, bg=bg)
        card.pack(fill="x", padx=8, pady=2)

        hdr = tk.Frame(card, bg=bg)
        hdr.pack(fill="x", padx=6, pady=4)

        prio_colors = {"high": _BADGE_WEAKENING, "critical": _BADGE_BROKEN, "normal": theme.FG_DIM, "low": theme.FG_MUTED}
        prio_color = prio_colors.get(task.priority, theme.FG_DIM)
        tk.Label(hdr, text="⬤", fg=prio_color, bg=bg, font=("Segoe UI", 8)).pack(side="left")
        title_lbl = tk.Label(hdr, text=task.title or task.task_type, fg=fg, bg=bg, font=("Segoe UI", 8, "bold"), anchor="w", justify="left")
        title_lbl.pack(side="left", padx=(4, 0), fill="x", expand=True)
        self._register_label(parent, title_lbl)
        
        tk.Label(hdr, text=task.status, fg=theme.FG_MUTED, bg=bg, font=("Segoe UI", 7)).pack(side="right")

        if task.created_at:
            date_short = task.created_at[:10] if len(task.created_at) >= 10 else task.created_at
            tk.Label(card, text=f"建立：{date_short}", fg=theme.FG_MUTED, bg=bg, font=("Segoe UI", 7), anchor="w").pack(fill="x", padx=10)

        if task.notes:
            for note in task.notes[:2]:
                lbl = tk.Label(card, text=f"  {note}", fg=theme.FG_DIM, bg=bg, font=("Segoe UI", 7), anchor="w", justify="left")
                lbl.pack(fill="x", padx=10)
                self._register_label(parent, lbl)

        if task.status == "pending":
            btn_row = tk.Frame(card, bg=bg)
            btn_row.pack(fill="x", padx=10, pady=(2, 4))

            def _approve(t=task):
                self._set_review_status(t, "approved")
                self._refresh_review_tab(parent)

            def _dismiss(t=task):
                self._set_review_status(t, "dismissed")
                self._refresh_review_tab(parent)

            tk.Button(
                btn_row, text="✅ 批准", command=_approve,
                bg="#2a5a3a", fg=theme.FG, font=("Segoe UI", 7, "bold"),
                relief="flat", padx=6, pady=1,
            ).pack(side="left", padx=(0, 4))
            tk.Button(
                btn_row, text="✕ 駁回", command=_dismiss,
                bg="#5a2a2a", fg=theme.FG, font=("Segoe UI", 7, "bold"),
                relief="flat", padx=6, pady=1,
            ).pack(side="left")

    def _set_review_status(self, task, new_status: str):
        try:
            from widget.agent.review_queue import ReviewQueueStore
            task.status = new_status
            ReviewQueueStore().upsert(task)
        except Exception:
            pass

    def _refresh_review_tab(self, parent: tk.Frame):
        for child in parent.winfo_children():
            child.destroy()
        self._build_tab_review(parent)

    # ── Tab 5: Coverage Report (v1.5.2 Sidecar Hook) ─────────────────────────

    def _build_tab_coverage(self, parent: tk.Frame):
        """Display sidecar coverage report state and valuation summary."""
        report = self._load_sidecar_report_state()
        valuation = self._load_sidecar_valuation()

        if not report and not valuation:
            self._empty_label(parent, "尚未產生覆蓋報告。\n請先完成 tree / leaf / valuation 流程。")
            return

        # ── Report State Summary ──
        if report:
            self._section(parent, "總體評估")
            assessment = report.get("overall_assessment", "")
            if assessment:
                self._info_row(parent, assessment)

            confidence = report.get("confidence", "")
            if confidence:
                conf_color = _BADGE_INTACT if confidence == "high" else (
                    _BADGE_DELAYED if confidence == "medium" else _BADGE_WEAKENING
                )
                self._kv_row(parent, "信心程度", confidence.upper(), value_fg=conf_color)

            gap = report.get("market_belief_gap", "")
            if gap:
                self._section(parent, "市場認知差距")
                self._info_row(parent, gap)

            # Bull / Base / Bear
            bbb = report.get("bull_base_bear_summary", {})
            if bbb:
                self._section(parent, "情境視角")
                for key, label in [("bull", "🟢 Bull"), ("base", "⚪ Base"), ("bear", "🔴 Bear")]:
                    text = bbb.get(key, "")
                    if text:
                        self._kv_row(parent, label, text)

            # Triggers
            triggers = report.get("major_triggers", [])
            if triggers:
                self._section(parent, "重評觸發條件")
                for t in triggers:
                    self._bullet(parent, t)

            # Red Flags
            red_flags = report.get("red_flags", [])
            if red_flags:
                self._section(parent, "☠ 紅旗警告")
                for rf in red_flags:
                    self._bullet(parent, rf)

            # Evidence Gaps
            gaps = report.get("open_evidence_gaps", [])
            if gaps:
                self._section(parent, "證據缺口")
                for g in gaps:
                    self._bullet(parent, f"☐ {g}")

            # Branch Under Question
            buq = report.get("branch_under_question", [])
            if buq:
                self._section(parent, "待確認分支")
                for b in buq:
                    self._bullet(parent, b)

        # ── Valuation Risk ──
        if valuation:
            self._section(parent, "估值側載狀態")
            mode = valuation.get("valuation_mode", "")
            risk = valuation.get("expectation_risk", "")
            miv = valuation.get("market_implied_view", "")
            if mode:
                self._kv_row(parent, "模式", mode)
            if risk:
                risk_color = _BADGE_BROKEN if risk in ("high", "critical") else _BADGE_DELAYED
                self._kv_row(parent, "期望風險", risk.upper(), value_fg=risk_color)
            if miv:
                self._kv_row(parent, "市場隱含觀點", miv)

        # ── Open Report button ──
        report_md = self._load_sidecar_report_md()
        if report_md:
            btn_frame = tk.Frame(parent, bg=_TAB_BG)
            btn_frame.pack(fill="x", padx=12, pady=(10, 4))
            tk.Button(
                btn_frame, text="📄 開啟完整報告 (Markdown)",
                command=lambda: self._show_report_popup(report_md),
                bg="#1e3a5f", fg=theme.FG, font=("Segoe UI", 8, "bold"),
                relief="flat", padx=10, pady=4,
            ).pack(side="left")

    def _show_report_popup(self, markdown_text: str):
        """Open a simple text window showing the full report.md content."""
        popup = tk.Toplevel(self)
        popup.title(f"📝 Coverage Report — {self._symbol}")
        popup.configure(bg=_TAB_BG)
        popup.geometry("640x480")
        popup.attributes("-topmost", True)

        text_widget = tk.Text(
            popup, bg=_TAB_BG, fg=theme.FG,
            font=("Consolas", 9), wrap="word",
            insertontime=0, relief="flat", padx=12, pady=8,
        )
        text_widget.insert("1.0", markdown_text)
        text_widget.config(state="disabled")
        text_widget.pack(fill="both", expand=True)

    # ── Data Loaders ────────────────────────────────────────────────────────

    def _load_draft(self):
        if self._draft is not None:
            return self._draft
        try:
            from widget.agent.draft_store import DraftStore
            return DraftStore().load(self._symbol)
        except Exception:
            return None

    def _load_evidence(self):
        try:
            from widget.agent.evidence_ledger import EvidenceLedgerStore
            return EvidenceLedgerStore().list_for_symbol(self._symbol)
        except Exception:
            return []

    def _load_review_tasks(self):
        try:
            from widget.agent.review_queue import ReviewQueueStore
            return ReviewQueueStore().list_for_symbol(self._symbol)
        except Exception:
            return []

    def _count_pending_reviews(self) -> int:
        try:
            tasks = self._load_review_tasks()
            return sum(1 for t in tasks if t.status == "pending")
        except Exception:
            return 0

    def _count_sidecar_reviews(self) -> int:
        """Count pending sidecar bridge review tasks."""
        try:
            from widget.agent.sidecar_loader import load_sidecar_review_tasks
            items = load_sidecar_review_tasks(self._symbol)
            return sum(1 for t in items if t.get("status", "pending") == "pending")
        except Exception:
            return 0

    def _load_sidecar_report_state(self) -> Optional[dict]:
        try:
            from widget.agent.sidecar_loader import load_report_state
            return load_report_state(self._symbol)
        except Exception:
            return None

    def _load_sidecar_valuation(self) -> Optional[dict]:
        try:
            from widget.agent.sidecar_loader import load_valuation
            return load_valuation(self._symbol)
        except Exception:
            return None

    def _load_sidecar_valuation_risk(self) -> Optional[str]:
        val = self._load_sidecar_valuation()
        if val:
            return val.get("expectation_risk")
        return None

    def _load_sidecar_report_md(self) -> Optional[str]:
        try:
            from widget.agent.sidecar_loader import load_report_markdown
            return load_report_markdown(self._symbol)
        except Exception:
            return None

    # ── UI Helpers ──────────────────────────────────────────────────────────

    def _section(self, parent: tk.Frame, title: str):
        f = tk.Frame(parent, bg=_SECT_BG)
        f.pack(fill="x", padx=0, pady=(8, 2))
        lbl = tk.Label(
            f, text=f"  {title}", fg=theme.ACCENT, bg=_SECT_BG,
            font=("Segoe UI", 8, "bold"), anchor="w", justify="left"
        )
        lbl.pack(fill="x", padx=4, pady=2)
        self._register_label(parent, lbl)

    def _info_row(self, parent: tk.Frame, text: str):
        lbl = tk.Label(
            parent, text=text, fg=theme.FG, bg=_TAB_BG,
            font=("Segoe UI", 8), justify="left", anchor="w",
        )
        lbl.pack(fill="x", padx=12, pady=2)
        self._register_label(parent, lbl)

    def _kv_row(self, parent: tk.Frame, key: str, value: str, value_fg=None):
        row = tk.Frame(parent, bg=_TAB_BG)
        row.pack(fill="x", padx=12, pady=1)
        tk.Label(row, text=f"{key}：", fg=theme.FG_DIM, bg=_TAB_BG, font=("Segoe UI", 8), anchor="w").pack(side="left")
        lbl = tk.Label(
            row, text=value, fg=value_fg or theme.FG, bg=_TAB_BG,
            font=("Segoe UI", 8), anchor="w", justify="left",
        )
        lbl.pack(side="left", padx=(4, 0), fill="x", expand=True)
        self._register_label(parent, lbl)

    def _bullet(self, parent: tk.Frame, text: str):
        lbl = tk.Label(
            parent, text=f"  • {text}", fg=theme.FG, bg=_TAB_BG,
            font=("Segoe UI", 8), anchor="w", justify="left"
        )
        lbl.pack(fill="x", padx=12, pady=1)
        self._register_label(parent, lbl)

    def _empty_label(self, parent: tk.Frame, text: str):
        lbl = tk.Label(
            parent, text=text, fg=theme.FG_MUTED, bg=_TAB_BG,
            font=("Segoe UI", 9), justify="center",
        )
        lbl.pack(expand=True, pady=40, fill="x")
        self._register_label(parent, lbl)

    def _detail_kv(self, parent: tk.Frame, key: str, value: str, bg: str):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=f"{key}：", fg=theme.FG_MUTED, bg=bg, font=("Segoe UI", 7), width=6, anchor="w").pack(side="left")
        lbl = tk.Label(
            row, text=value, fg=theme.FG_DIM, bg=bg,
            font=("Segoe UI", 7), anchor="w", justify="left",
        )
        lbl.pack(side="left", padx=(2, 0), fill="x", expand=True)
        self._register_label(parent, lbl)
