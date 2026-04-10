"""Tkinter dialog for editing a ThesisDefinition.

Phase 4: Research Copilot prefill — 🔍 掃描證據 button auto-collects
evidence from existing data sources and presents a review panel.
"""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
import tkinter.font as tkfont
from tkinter import ttk
from datetime import datetime, timezone
from typing import Callable, Optional

from widget.research.thesis_models import (
    EXPECTED_WINDOWS,
    EVIDENCE_TYPES,
    EVIDENCE_TYPE_LABELS,
    GUIDANCE_SHIFT_TYPES,
    GUIDANCE_SHIFT_LABELS,
    THESIS_TEMPLATES,
    THESIS_TYPE_LABELS,
    THESIS_TYPES,
    ThesisDefinition,
)
from widget.style import theme


class _SourcePopover:
    def __init__(self, owner: tk.Misc):
        self._owner = owner
        self._tip = None
        self._anchor_widget = None
        self._evidence_field = None
        self._fonts: dict[str, dict] = {}

    def show(self, widget, evidence_field):
        self.hide()
        if widget is None or evidence_field is None:
            return
        if not getattr(widget, "winfo_exists", lambda: False)():
            return
        self._anchor_widget = widget
        self._evidence_field = evidence_field

        tip = tk.Toplevel(self._owner)
        try:
            tip.transient(self._owner)
        except Exception:
            pass
        tip.overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass
        tip.configure(bg=theme.BG3)
        tip.bind("<Escape>", lambda _event: self.hide())
        tip.bind("<FocusOut>", lambda _event: self.hide())

        body = tk.Frame(tip, bg=theme.BG3, padx=8, pady=6)
        body.pack(fill="both", expand=True)

        for line in self._build_lines(evidence_field):
            tk.Label(
                body,
                text=line,
                justify="left",
                anchor="w",
                fg=theme.FG,
                bg=theme.BG3,
                font=("Segoe UI", 7),
            ).pack(anchor="w")

        actions = self._build_actions(evidence_field)
        if actions:
            row = tk.Frame(body, bg=theme.BG3)
            row.pack(anchor="w", pady=(6, 0))
            for label, url in actions:
                tk.Button(
                    row,
                    text=label,
                    command=lambda target=url: self._open_url(target),
                    bg=theme.ACCENT,
                    fg=theme.FG,
                    relief="flat",
                    font=("Segoe UI", 7),
                    padx=6,
                    pady=2,
                ).pack(side="left", padx=(0, 4))

        self._capture_fonts(tip)
        self._apply_scale()
        tip.update_idletasks()
        self._reposition()
        tip.deiconify()
        try:
            tip.lift(self._owner)
            tip.focus_force()
        except Exception:
            pass
        self._tip = tip

    def hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
        self._anchor_widget = None
        self._evidence_field = None
        self._fonts = {}

    def refresh(self):
        if self._tip is None:
            return
        if self._anchor_widget is None or not getattr(self._anchor_widget, "winfo_exists", lambda: False)():
            self.hide()
            return
        self._apply_scale()
        self._reposition()

    @staticmethod
    def _build_lines(evidence_field) -> list[str]:
        lines = []
        source_label = evidence_field.source_label or evidence_field.source or ""
        compare = evidence_field.source_compare or {}
        reference = evidence_field.source_reference or {}

        if source_label.lower() == "snapshot":
            lines.append("來自本地快照比較")
            current_date = _SourcePopover._short_date(compare.get("current_date"))
            previous_date = _SourcePopover._short_date(compare.get("previous_date"))
            if current_date or previous_date:
                lines.append(f"比較：{current_date or '--'} vs {previous_date or '--'}")
            if compare.get("previous_value") is not None:
                lines.append(f"前值：{_SourcePopover._fmt_number(compare.get('previous_value'))}")
            if compare.get("current_value") is not None:
                lines.append(f"現值：{_SourcePopover._fmt_number(compare.get('current_value'))}")
            if compare.get("delta_pct") is not None:
                lines.append(f"變化：{compare.get('delta_pct'):+.1f}%")
        else:
            lines.append(f"來源：{source_label or '未知'}")
            if evidence_field.source_field:
                lines.append(f"欄位：{evidence_field.source_field}")
            if evidence_field.source_date:
                lines.append(f"日期：{_SourcePopover._short_date(evidence_field.source_date)}")
            if evidence_field.source_quality:
                lines.append(f"品質：{evidence_field.source_quality}")

        if reference:
            ref_label = reference.get("label") or "原始資料"
            ref_field = reference.get("field") or ""
            ref_date = _SourcePopover._short_date(reference.get("date"))
            parts = [part for part in (ref_label, ref_field, ref_date) if part]
            if parts:
                lines.append(f"原始依據：{' / '.join(parts)}")
            if reference.get("quality"):
                lines.append(f"原始品質：{reference.get('quality')}")

        return lines

    @staticmethod
    def _build_actions(evidence_field) -> list[tuple[str, str]]:
        actions = []
        source_label = (evidence_field.source_label or evidence_field.source or "").lower()
        if evidence_field.source_url and source_label != "snapshot":
            button_text = "開啟逐字稿" if source_label == "alphamemo" else "開啟原始資料"
            actions.append((button_text, evidence_field.source_url))

        reference = evidence_field.source_reference or {}
        if reference.get("url"):
            label = reference.get("label") or "原始資料"
            actions.append((f"開啟 {label}", reference["url"]))
        return actions

    @staticmethod
    def _open_url(url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    @staticmethod
    def _fmt_number(value) -> str:
        if isinstance(value, (int, float)):
            return f"{value:,.2f}"
        return str(value)

    @staticmethod
    def _short_date(value: str) -> str:
        if not value:
            return ""
        return str(value)[5:10] if len(str(value)) >= 10 else str(value)

    def _reposition(self):
        if self._tip is None or self._anchor_widget is None:
            return
        tip = self._tip
        widget = self._anchor_widget
        tip.update_idletasks()
        tip_w = max(tip.winfo_width(), 0)
        tip_h = max(tip.winfo_height(), 0)
        owner_x = self._owner.winfo_rootx()
        owner_y = self._owner.winfo_rooty()
        owner_w = self._owner.winfo_width()
        owner_h = self._owner.winfo_height()
        screen_w = tip.winfo_screenwidth()
        screen_h = tip.winfo_screenheight()

        x = widget.winfo_rootx() + widget.winfo_width() + 4
        if x + tip_w > min(screen_w, owner_x + owner_w):
            x = max(owner_x + 8, widget.winfo_rootx() - tip_w - 4)

        y = widget.winfo_rooty() - 2
        max_y = min(screen_h - tip_h, owner_y + owner_h - tip_h - 8)
        y = max(owner_y + 8, min(y, max_y))
        tip.geometry(f"+{x}+{y}")

    def _capture_fonts(self, root):
        for widget in self._iter_widgets(root):
            key = str(widget)
            if key in self._fonts:
                continue
            if "font" not in widget.keys():
                continue
            try:
                actual = tkfont.Font(font=widget.cget("font")).actual()
            except Exception:
                continue
            size = abs(int(actual.get("size", 0) or 0))
            if size <= 0:
                continue
            self._fonts[key] = {
                "widget": widget,
                "family": actual.get("family", "Segoe UI"),
                "size": size,
                "weight": actual.get("weight", "normal"),
            }

    def _apply_scale(self):
        if self._tip is None:
            return
        default_w = getattr(self._owner, "_DEFAULT_SIZE", (440, 720))[0]
        default_h = getattr(self._owner, "_DEFAULT_SIZE", (440, 720))[1]
        width = max(self._owner.winfo_width(), default_w)
        height = max(self._owner.winfo_height(), default_h)
        scale = min(max(max(width / default_w, height / default_h), 1.0), 1.35)
        for item in list(self._fonts.values()):
            widget = item.get("widget")
            if widget is None or not getattr(widget, "winfo_exists", lambda: False)():
                continue
            new_size = max(item["size"], int(round(item["size"] * scale)))
            try:
                widget.configure(font=(item["family"], new_size, item["weight"]))
            except Exception:
                pass

    @staticmethod
    def _iter_widgets(root):
        stack = [root]
        while stack:
            widget = stack.pop()
            yield widget
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass


class ThesisDialog(tk.Toplevel):
    """Modal dialog for creating / editing a thesis definition."""

    _DEFAULT_SIZE = (440, 720)
    _ANCHOR_GAP = 8

    def __init__(
        self,
        parent: tk.Misc,
        symbol: str,
        existing: Optional[ThesisDefinition] = None,
        on_save: Optional[Callable[[ThesisDefinition], None]] = None,
        on_delete: Optional[Callable[[], None]] = None,
        store: object = None,
        engine: object = None,
    ):
        super().__init__(parent)
        self._symbol = symbol
        self._on_save = on_save
        self._on_delete = on_delete
        self._existing = existing
        self._store = store
        self._engine = engine
        self._evidence = None  # EvidenceSummary once scanned
        self._latest_evidence_records = []
        self._accepted_evidence_records = []
        self._scanned_guidance_observations = []
        self._draft = None
        self._draft_review_task = None
        self._result: Optional[ThesisDefinition] = None
        self._source_popover = _SourcePopover(self)
        self._responsive_fonts: dict[str, dict] = {}

        self.title(f"📋 投資邏輯 — {symbol}")
        self.configure(bg=theme.BG)
        self.resizable(True, True)
        self.minsize(*self._DEFAULT_SIZE)
        self.geometry(f"{self._DEFAULT_SIZE[0]}x{self._DEFAULT_SIZE[1]}")
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set()

        # Scrollable content
        canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0)
        self._canvas = canvas
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._inner = tk.Frame(canvas, bg=theme.BG)
        self._inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._canvas_window = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<Configure>", self._on_canvas_configure)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_form(existing)
        self._capture_responsive_fonts(self._inner)
        self.bind("<Configure>", self._on_resize)
        self.after_idle(self._position_beside_parent)
        self.after_idle(self._apply_responsive_scale)

    def _position_beside_parent(self):
        """Anchor beside the source widget window, with a simple on-screen fallback."""
        try:
            self.update_idletasks()
            parent = self.master
            if parent is None or not getattr(parent, "winfo_exists", lambda: False)():
                return

            dialog_w = max(self.winfo_width(), self._DEFAULT_SIZE[0])
            dialog_h = max(self.winfo_height(), self._DEFAULT_SIZE[1])
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = max(parent.winfo_width(), 0)

            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            x = parent_x + parent_w + self._ANCHOR_GAP
            if x + dialog_w > screen_w:
                x = parent_x - dialog_w - self._ANCHOR_GAP
            if x < 0:
                x = max(0, screen_w - dialog_w)

            max_y = max(0, screen_h - dialog_h)
            y = max(0, min(parent_y, max_y))
            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        except Exception:
            pass

    def _build_form(self, existing: Optional[ThesisDefinition]):
        parent = self._inner
        pad = {"padx": 8, "pady": 4}
        fg = theme.FG
        bg = theme.BG

        # ── Section: Thesis Type ─────────────────────────────────────────
        self._section_label(parent, "一、投資邏輯類型")
        self._type_var = tk.StringVar(value=existing.thesis_type if existing else THESIS_TYPES[0])
        type_frame = tk.Frame(parent, bg=bg)
        type_frame.pack(fill="x", **pad)
        self._type_combo = ttk.Combobox(
            type_frame, textvariable=self._type_var,
            values=THESIS_TYPES, state="readonly", width=22
        )
        self._type_combo.pack(side="left")
        self._type_label = tk.Label(type_frame, text="", fg=theme.ACCENT, bg=bg, font=theme.FONT_SMALL)
        self._type_label.pack(side="left", padx=6)
        self._type_var.trace_add("write", self._update_type_label)
        self._update_type_label()

        # Buttons row: template + evidence scan
        btn_row = tk.Frame(parent, bg=bg)
        btn_row.pack(fill="x", **pad)
        tk.Button(
            btn_row, text="📋 套用模板", command=self._apply_template,
            bg=theme.BG2, fg=theme.FG, font=("Segoe UI", 7),
            relief="flat", padx=6, pady=2
        ).pack(side="left")
        if self._store or self._engine:
            tk.Button(
                btn_row, text="🔍 掃描證據", command=self._scan_evidence,
                bg="#2a5a3a", fg=theme.FG, font=("Segoe UI", 7, "bold"),
                relief="flat", padx=6, pady=2
            ).pack(side="left", padx=6)
            tk.Button(
                btn_row, text="AI 建立草稿", command=self._build_ai_draft,
                bg="#36588c", fg=theme.FG, font=("Segoe UI", 7, "bold"),
                relief="flat", padx=6, pady=2
            ).pack(side="left", padx=2)

        # Expected Window
        tk.Label(parent, text="預期時間窗口", fg=fg, bg=bg, font=theme.FONT_SMALL).pack(anchor="w", **pad)
        self._window_var = tk.StringVar(value=existing.expected_window if existing else "2Q")
        ttk.Combobox(
            parent, textvariable=self._window_var,
            values=EXPECTED_WINDOWS, state="readonly", width=10
        ).pack(anchor="w", **pad)

        # ── Evidence review panel (hidden until scan) ────────────────────
        self._evidence_frame = tk.Frame(parent, bg="#1e2a1e", relief="groove", bd=1)
        # Not packed until scan completes
        self._draft_frame = tk.Frame(parent, bg="#1e2230", relief="groove", bd=1)

        # ── Section: Claims / Break / Confirm ────────────────────────────
        self._section_label(parent, "二、核心預期與條件")

        tk.Label(parent, text="核心預期（每行一條）", fg=fg, bg=bg, font=theme.FONT_SMALL).pack(anchor="w", **pad)
        self._claims_text = self._text_area(parent, 3)
        if existing and existing.primary_claims:
            self._claims_text.insert("1.0", "\n".join(existing.primary_claims))

        tk.Label(parent, text="什麼叫看錯（每行一條）", fg=fg, bg=bg, font=theme.FONT_SMALL).pack(anchor="w", **pad)
        self._break_text = self._text_area(parent, 3)
        if existing and existing.break_conditions:
            self._break_text.insert("1.0", "\n".join(existing.break_conditions))

        tk.Label(parent, text="什麼叫驗證成功（每行一條）", fg=fg, bg=bg, font=theme.FONT_SMALL).pack(anchor="w", **pad)
        self._confirm_text = self._text_area(parent, 3)
        if existing and existing.confirm_conditions:
            self._confirm_text.insert("1.0", "\n".join(existing.confirm_conditions))

        # ── Section: Guidance Tracking ───────────────────────────────────
        self._section_label(parent, "三、管理層說法追蹤")

        self._guidance_list = existing.guidance_observations.copy() if existing else []
        self._guidance_listbox = tk.Listbox(
            parent, height=3, bg=theme.BG2, fg=fg,
            font=("Segoe UI", 7), selectmode="single",
            relief="flat", bd=1
        )
        self._guidance_listbox.pack(fill="x", **pad)
        self._refresh_guidance_listbox()

        guid_frame = tk.Frame(parent, bg=bg)
        guid_frame.pack(fill="x", **pad)
        self._guid_type_var = tk.StringVar(value=GUIDANCE_SHIFT_TYPES[0])
        ttk.Combobox(
            guid_frame, textvariable=self._guid_type_var,
            values=GUIDANCE_SHIFT_TYPES, state="readonly", width=18
        ).pack(side="left")
        self._guid_note_var = tk.StringVar()
        tk.Entry(
            guid_frame, textvariable=self._guid_note_var, width=22,
            bg=theme.BG2, fg=fg, insertbackground=fg,
            font=("Segoe UI", 7), relief="flat"
        ).pack(side="left", padx=4)
        tk.Button(
            guid_frame, text="＋", command=self._add_guidance,
            bg=theme.ACCENT, fg=theme.FG, font=("Segoe UI", 7, "bold"),
            relief="flat", padx=6
        ).pack(side="left")

        # ── Section: Evidence Tracking ───────────────────────────────────
        self._section_label(parent, "四、行為證據追蹤")

        self._evidence_list = existing.evidence_observations.copy() if existing else []
        self._evidence_listbox = tk.Listbox(
            parent, height=3, bg=theme.BG2, fg=fg,
            font=("Segoe UI", 7), selectmode="single",
            relief="flat", bd=1
        )
        self._evidence_listbox.pack(fill="x", **pad)
        self._refresh_evidence_listbox()

        evid_frame = tk.Frame(parent, bg=bg)
        evid_frame.pack(fill="x", **pad)
        self._evid_type_var = tk.StringVar(value=EVIDENCE_TYPES[0])
        ttk.Combobox(
            evid_frame, textvariable=self._evid_type_var,
            values=EVIDENCE_TYPES, state="readonly", width=18
        ).pack(side="left")
        self._evid_note_var = tk.StringVar()
        tk.Entry(
            evid_frame, textvariable=self._evid_note_var, width=22,
            bg=theme.BG2, fg=fg, insertbackground=fg,
            font=("Segoe UI", 7), relief="flat"
        ).pack(side="left", padx=4)
        tk.Button(
            evid_frame, text="＋", command=self._add_evidence,
            bg=theme.ACCENT, fg=theme.FG, font=("Segoe UI", 7, "bold"),
            relief="flat", padx=6
        ).pack(side="left")

        # ── Buttons ──────────────────────────────────────────────────────
        btn_frame = tk.Frame(parent, bg=bg)
        btn_frame.pack(fill="x", pady=10, padx=8)

        tk.Button(
            btn_frame, text="💾 儲存", command=self._save,
            bg=theme.ACCENT, fg=theme.FG, font=theme.FONT_SMALL,
            relief="flat", padx=12, pady=4
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="🗑 清除邏輯", command=self._delete,
            bg="#882222", fg=theme.FG, font=theme.FONT_SMALL,
            relief="flat", padx=12, pady=4
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="取消", command=self.destroy,
            bg=theme.BG2, fg=theme.FG, font=theme.FONT_SMALL,
            relief="flat", padx=12, pady=4
        ).pack(side="right", padx=4)

    # ── Evidence Scan ────────────────────────────────────────────────────

    def _scan_evidence(self):
        """Run evidence collection in background thread, show result panel."""
        def _worker():
            try:
                from widget.agent.alphamemo_analysis import analyze_management_communication
                from widget.research.evidence_prefill import collect_evidence
                from widget.agent.evidence_pipeline import extract_and_persist_evidence
                summary = collect_evidence(
                    self._symbol,
                    thesis_type=self._type_var.get(),
                    store=self._store,
                    engine=self._engine,
                )
                records = extract_and_persist_evidence(
                    self._symbol,
                    thesis_type=self._type_var.get(),
                    summary=summary,
                    store=self._store,
                    engine=self._engine,
                )
                analysis = analyze_management_communication(
                    self._symbol,
                    snapshot=(self._engine.get_latest(self._symbol) if self._engine and hasattr(self._engine, "get_latest") else None),
                    summary=summary,
                )
                # Schedule UI update on main thread
                self.after(0, lambda: self._show_evidence_panel(summary, records, analysis))
            except Exception as e:
                self.after(0, lambda: self._show_evidence_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_evidence_panel(self, summary, records=None, analysis=None):
        """Show compact evidence review panel."""
        from widget.research.thesis_models import EvidenceSummary
        self._evidence = summary
        self._latest_evidence_records = list(records or [])
        self._scanned_guidance_observations = list(
            getattr(analysis, "guidance_observations", []) or []
        )

        # Clear and rebuild evidence frame
        for child in self._evidence_frame.winfo_children():
            child.destroy()

        bg = "#1e2a1e"
        fg = theme.FG

        # Header
        quality_colors = {"high": "#4CAF50", "partial": "#FFC107", "limited": "#FF9800"}
        quality_zh = {"high": "高", "partial": "部分", "limited": "有限"}
        q_color = quality_colors.get(summary.data_quality, fg)
        q_text = quality_zh.get(summary.data_quality, summary.data_quality)

        header = tk.Frame(self._evidence_frame, bg=bg)
        header.pack(fill="x", padx=6, pady=(4, 2))
        tk.Label(
            header, text="── 現有證據 ──", fg=theme.ACCENT, bg=bg,
            font=("Segoe UI", 7, "bold")
        ).pack(side="left")
        tk.Label(
            header, text=f"品質：{q_text}", fg=q_color, bg=bg,
            font=("Segoe UI", 7)
        ).pack(side="right")

        if getattr(summary, "panel_hint", ""):
            tk.Label(
                self._evidence_frame, text=summary.panel_hint,
                fg=theme.FG_DIM, bg=bg, font=("Segoe UI", 7),
                anchor="w"
            ).pack(fill="x", padx=6, pady=(0, 2))

        if getattr(summary, "quality_note", ""):
            tk.Label(
                self._evidence_frame, text=summary.quality_note,
                fg=theme.FG_DIM, bg=bg, font=("Segoe UI", 7),
                anchor="w"
            ).pack(fill="x", padx=6, pady=(0, 2))

        # Evidence fields
        for ef in summary.fields:
            row = tk.Frame(self._evidence_frame, bg=bg)
            row.pack(fill="x", padx=6, pady=1)
            tk.Label(
                row, text=ef.label_zh, fg=theme.FG_DIM, bg=bg,
                font=("Segoe UI", 7), width=10, anchor="w"
            ).pack(side="left")
            tk.Label(
                row, text=ef.value, fg=fg, bg=bg,
                font=("Segoe UI", 7, "bold"), anchor="w"
            ).pack(side="left", padx=4)
            source_label = ef.source_label or ef.source
            if source_label:
                badge = tk.Label(
                    row, text=f"[{source_label}]", fg=theme.FG_DIM, bg=bg,
                    font=("Segoe UI", 6), cursor="hand2"
                )
                badge.pack(side="right")
                badge.bind(
                    "<Button-1>",
                    lambda _event, widget=badge, field=ef: self._source_popover.show(widget, field),
                )

        # Summary line
        tk.Label(
            self._evidence_frame, text=summary.summary_text,
            fg=theme.ACCENT, bg=bg, font=("Segoe UI", 7),
            anchor="w"
        ).pack(fill="x", padx=6, pady=(2, 2))

        if self._scanned_guidance_observations:
            preview = " / ".join(
                obs.get("type", "")
                for obs in self._scanned_guidance_observations[:2]
                if obs.get("type")
            )
            if preview:
                tk.Label(
                    self._evidence_frame,
                    text=f"AlphaMemo: {preview}",
                    fg=theme.FG_DIM,
                    bg=bg,
                    font=("Segoe UI", 7),
                    anchor="w",
                ).pack(fill="x", padx=6, pady=(0, 2))

        # Accept button
        tk.Button(
            self._evidence_frame, text="✅ 接受並預填", command=self._accept_evidence,
            bg="#2a5a3a", fg=theme.FG, font=("Segoe UI", 7, "bold"),
            relief="flat", padx=8, pady=2
        ).pack(padx=6, pady=(2, 4), anchor="w")

        # Pack the frame (insert it after section 一)
        self._evidence_frame.pack(fill="x", padx=8, pady=(0, 4), after=self._inner.winfo_children()[3])
        self._capture_responsive_fonts(self._evidence_frame)
        self._apply_responsive_scale()

    def _show_evidence_error(self, error_msg):
        """Show error if evidence scan fails."""
        for child in self._evidence_frame.winfo_children():
            child.destroy()
        tk.Label(
            self._evidence_frame, text=f"掃描失敗：{error_msg}",
            fg="#FF9800", bg="#1e2a1e", font=("Segoe UI", 7)
        ).pack(padx=6, pady=4)
        self._evidence_frame.pack(fill="x", padx=8, pady=(0, 4))
        self._capture_responsive_fonts(self._evidence_frame)
        self._apply_responsive_scale()

    def _accept_evidence(self):
        """Prefill sections from accepted evidence."""
        if not self._evidence:
            return

        # Auto-fill template if text fields are empty
        self._apply_template()

        # Add suggested guidance note if available
        if self._evidence.suggested_guidance_note:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self._guidance_list.append({
                "date": today,
                "type": "more_specific",
                "note": self._evidence.suggested_guidance_note,
            })
            self._refresh_guidance_listbox()

        self._accepted_evidence_records = []
        for record in self._latest_evidence_records:
            record.metadata["accepted"] = True
            self._accepted_evidence_records.append(record)

        existing_keys = {
            (
                obs.get("date", ""),
                obs.get("type", ""),
                obs.get("note", ""),
            )
            for obs in self._guidance_list
        }
        for obs in self._scanned_guidance_observations:
            key = (
                obs.get("date", ""),
                obs.get("type", ""),
                obs.get("note", ""),
            )
            if key in existing_keys:
                continue
            self._guidance_list.append(dict(obs))
            existing_keys.add(key)
        self._refresh_guidance_listbox()

        # Flash the evidence frame to confirm acceptance
        self._evidence_frame.configure(bg="#2a4a2a")
        self.after(300, lambda: self._evidence_frame.configure(bg="#1e2a1e"))

    # ── Helpers ──────────────────────────────────────────────────────────

    def _build_ai_draft(self):
        def _worker():
            try:
                from widget.agent.draft_builder import build_review_task_for_draft, build_thesis_draft
                from widget.agent.draft_store import DraftStore
                from widget.agent.evidence_pipeline import read_evidence_ledger
                from widget.agent.review_queue import ReviewQueueStore

                records = list(self._accepted_evidence_records)
                if not records:
                    records = read_evidence_ledger(self._symbol)

                draft = build_thesis_draft(
                    self._symbol,
                    self._type_var.get(),
                    records,
                )
                if draft is None:
                    self.after(0, lambda: self._show_draft_error("No accepted or verified evidence available."))
                    return

                DraftStore().save(self._symbol, draft)
                task = build_review_task_for_draft(draft)
                ReviewQueueStore().upsert(task)
                self.after(0, lambda: self._show_draft_panel(draft, task, records))
            except Exception as e:
                self.after(0, lambda: self._show_draft_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_draft_panel(self, draft, task, records):
        self._draft = draft
        self._draft_review_task = task

        for child in self._draft_frame.winfo_children():
            child.destroy()

        bg = "#1e2230"
        tk.Label(
            self._draft_frame, text="AI 草稿 review",
            fg=theme.ACCENT, bg=bg, font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", padx=6, pady=(4, 2))
        tk.Label(
            self._draft_frame, text=f"Top question: {draft.top_question}",
            fg=theme.FG, bg=bg, font=("Segoe UI", 7), anchor="w", justify="left"
        ).pack(fill="x", padx=6)
        tk.Label(
            self._draft_frame, text=f"Summary: {draft.summary}",
            fg=theme.FG_DIM, bg=bg, font=("Segoe UI", 7), anchor="w", justify="left"
        ).pack(fill="x", padx=6, pady=(0, 2))
        tk.Label(
            self._draft_frame,
            text=f"Evidence review: {len(records)} eligible / {len(draft.supporting_evidence)} used",
            fg=theme.FG_DIM, bg=bg, font=("Segoe UI", 7), anchor="w"
        ).pack(fill="x", padx=6)

        for branch in draft.branches[:2]:
            tk.Label(
                self._draft_frame,
                text=f"- {branch.name}: {len(branch.leaves)} leaves",
                fg=theme.FG, bg=bg, font=("Segoe UI", 7), anchor="w"
            ).pack(fill="x", padx=10)
            for leaf in branch.leaves[:2]:
                tk.Label(
                    self._draft_frame,
                    text=f"  · {leaf.conclusion}",
                    fg=theme.FG_DIM, bg=bg, font=("Segoe UI", 7), anchor="w"
                ).pack(fill="x", padx=16)

        if draft.rerating_triggers:
            tk.Label(
                self._draft_frame,
                text=f"Rerating: {' / '.join(draft.rerating_triggers[:2])}",
                fg=theme.ACCENT, bg=bg, font=("Segoe UI", 7), anchor="w", justify="left"
            ).pack(fill="x", padx=6, pady=(2, 2))

        tk.Button(
            self._draft_frame, text="批准儲存", command=self._approve_and_save_draft,
            bg="#36588c", fg=theme.FG, font=("Segoe UI", 7, "bold"),
            relief="flat", padx=8, pady=2
        ).pack(anchor="w", padx=6, pady=(2, 4))

        self._draft_frame.pack(fill="x", padx=8, pady=(0, 4), after=self._evidence_frame)
        self._capture_responsive_fonts(self._draft_frame)
        self._apply_responsive_scale()

    def _show_draft_error(self, error_msg):
        for child in self._draft_frame.winfo_children():
            child.destroy()
        tk.Label(
            self._draft_frame,
            text=f"AI 草稿建立失敗: {error_msg}",
            fg="#FF9800", bg="#1e2230", font=("Segoe UI", 7)
        ).pack(anchor="w", padx=6, pady=4)
        self._draft_frame.pack(fill="x", padx=8, pady=(0, 4), after=self._evidence_frame)
        self._capture_responsive_fonts(self._draft_frame)
        self._apply_responsive_scale()

    def _approve_and_save_draft(self):
        if self._draft is None:
            return

        self._draft.status = "approved"
        try:
            from widget.agent.draft_store import DraftStore
            from widget.agent.review_queue import ReviewQueueStore

            DraftStore().save(self._symbol, self._draft)
            if self._draft_review_task is not None:
                self._draft_review_task.status = "approved"
                ReviewQueueStore().upsert(self._draft_review_task)
        except Exception:
            pass

        defn = self._draft.to_thesis_definition()
        if self._existing:
            defn.created_at = self._existing.created_at
        self._result = defn
        if self._on_save:
            self._on_save(defn)
        self.destroy()

    def _section_label(self, parent, text):
        tk.Label(
            parent, text=text, fg=theme.ACCENT, bg=theme.BG,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=8, pady=(8, 2))

    def _text_area(self, parent, height):
        t = tk.Text(
            parent, height=height, width=48, bg=theme.BG2, fg=theme.FG,
            insertbackground=theme.FG, font=theme.FONT_SMALL,
            relief="flat", bd=1
        )
        t.pack(fill="x", padx=8, pady=4)
        return t

    def _on_canvas_configure(self, event):
        try:
            self._canvas.itemconfigure(self._canvas_window, width=event.width)
        except Exception:
            pass

    def _on_resize(self, _event=None):
        self.after_idle(self._apply_responsive_scale)
        self.after_idle(self._source_popover.refresh)

    def _capture_responsive_fonts(self, root):
        for widget in self._iter_widgets(root):
            key = str(widget)
            if key in self._responsive_fonts:
                continue
            if "font" not in widget.keys():
                continue
            try:
                actual = tkfont.Font(font=widget.cget("font")).actual()
            except Exception:
                continue
            size = abs(int(actual.get("size", 0) or 0))
            if size <= 0:
                continue
            self._responsive_fonts[key] = {
                "widget": widget,
                "family": actual.get("family", "Segoe UI"),
                "size": size,
                "weight": actual.get("weight", "normal"),
            }

    def _apply_responsive_scale(self):
        width = max(self.winfo_width(), self._DEFAULT_SIZE[0])
        height = max(self.winfo_height(), self._DEFAULT_SIZE[1])
        scale = min(max(max(width / self._DEFAULT_SIZE[0], height / self._DEFAULT_SIZE[1]), 1.0), 1.45)

        for item in list(self._responsive_fonts.values()):
            widget = item.get("widget")
            if widget is None or not getattr(widget, "winfo_exists", lambda: False)():
                continue
            new_size = max(item["size"], int(round(item["size"] * scale)))
            try:
                widget.configure(font=(item["family"], new_size, item["weight"]))
            except Exception:
                pass

    @staticmethod
    def _iter_widgets(root):
        stack = [root]
        while stack:
            widget = stack.pop()
            yield widget
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass

    def _update_type_label(self, *_):
        val = self._type_var.get()
        label = THESIS_TYPE_LABELS.get(val, "")
        self._type_label.configure(text=label)

    def _apply_template(self):
        thesis_type = self._type_var.get()
        template = THESIS_TEMPLATES.get(thesis_type)
        if not template:
            return
        def _fill_if_empty(widget, lines):
            current = widget.get("1.0", "end").strip()
            if not current and lines:
                widget.insert("1.0", "\n".join(lines))
        _fill_if_empty(self._claims_text, template.get("default_claims", []))
        _fill_if_empty(self._break_text, template.get("default_break", []))
        _fill_if_empty(self._confirm_text, template.get("default_confirm", []))
        self._window_var.set(template.get("default_window", "2Q"))

    def _add_guidance(self):
        obs = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "type": self._guid_type_var.get(),
            "note": self._guid_note_var.get().strip(),
        }
        self._guidance_list.append(obs)
        self._guid_note_var.set("")
        self._refresh_guidance_listbox()

    def _refresh_guidance_listbox(self):
        self._guidance_listbox.delete(0, "end")
        for obs in self._guidance_list:
            label = GUIDANCE_SHIFT_LABELS.get(obs.get("type", ""), obs.get("type", ""))
            note = obs.get("note", "")
            date = obs.get("date", "")
            self._guidance_listbox.insert("end", f"{date}  {label}  {note}")

    def _add_evidence(self):
        obs = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "type": self._evid_type_var.get(),
            "note": self._evid_note_var.get().strip(),
        }
        self._evidence_list.append(obs)
        self._evid_note_var.set("")
        self._refresh_evidence_listbox()

    def _refresh_evidence_listbox(self):
        self._evidence_listbox.delete(0, "end")
        for obs in self._evidence_list:
            label = EVIDENCE_TYPE_LABELS.get(obs.get("type", ""), obs.get("type", ""))
            note = obs.get("note", "")
            date = obs.get("date", "")
            self._evidence_listbox.insert("end", f"{date}  {label}  {note}")

    def _parse_lines(self, text_widget):
        raw = text_widget.get("1.0", "end").strip()
        return [line.strip() for line in raw.split("\n") if line.strip()]

    def _save(self):
        defn = ThesisDefinition(
            thesis_type=self._type_var.get(),
            expected_window=self._window_var.get(),
            primary_claims=self._parse_lines(self._claims_text),
            break_conditions=self._parse_lines(self._break_text),
            confirm_conditions=self._parse_lines(self._confirm_text),
            guidance_observations=self._guidance_list,
            evidence_observations=self._evidence_list,
        )
        if self._existing:
            defn.created_at = self._existing.created_at
        self._result = defn
        if self._on_save:
            self._on_save(defn)
        self.destroy()

    def _delete(self):
        if self._on_delete:
            self._on_delete()
        self.destroy()
