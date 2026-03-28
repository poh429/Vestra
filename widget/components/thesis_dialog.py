"""Tkinter dialog for editing a ThesisDefinition.

Phase 4: Research Copilot prefill — 🔍 掃描證據 button auto-collects
evidence from existing data sources and presents a review panel.
"""

from __future__ import annotations

import threading
import tkinter as tk
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


class ThesisDialog(tk.Toplevel):
    """Modal dialog for creating / editing a thesis definition."""

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
        self._result: Optional[ThesisDefinition] = None

        self.title(f"📋 投資邏輯 — {symbol}")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self.geometry("440x720")
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set()

        # Scrollable content
        canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._inner = tk.Frame(canvas, bg=theme.BG)
        self._inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_form(existing)

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
                from widget.research.evidence_prefill import collect_evidence
                summary = collect_evidence(
                    self._symbol,
                    thesis_type=self._type_var.get(),
                    store=self._store,
                    engine=self._engine,
                )
                # Schedule UI update on main thread
                self.after(0, lambda: self._show_evidence_panel(summary))
            except Exception as e:
                self.after(0, lambda: self._show_evidence_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_evidence_panel(self, summary):
        """Show compact evidence review panel."""
        from widget.research.thesis_models import EvidenceSummary
        self._evidence = summary

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
            tk.Label(
                row, text=f"[{ef.source}]", fg=theme.FG_DIM, bg=bg,
                font=("Segoe UI", 6)
            ).pack(side="right")

        # Summary line
        tk.Label(
            self._evidence_frame, text=summary.summary_text,
            fg=theme.ACCENT, bg=bg, font=("Segoe UI", 7),
            anchor="w"
        ).pack(fill="x", padx=6, pady=(2, 2))

        # Accept button
        tk.Button(
            self._evidence_frame, text="✅ 接受並預填", command=self._accept_evidence,
            bg="#2a5a3a", fg=theme.FG, font=("Segoe UI", 7, "bold"),
            relief="flat", padx=8, pady=2
        ).pack(padx=6, pady=(2, 4), anchor="w")

        # Pack the frame (insert it after section 一)
        self._evidence_frame.pack(fill="x", padx=8, pady=(0, 4), after=self._inner.winfo_children()[3])

    def _show_evidence_error(self, error_msg):
        """Show error if evidence scan fails."""
        for child in self._evidence_frame.winfo_children():
            child.destroy()
        tk.Label(
            self._evidence_frame, text=f"掃描失敗：{error_msg}",
            fg="#FF9800", bg="#1e2a1e", font=("Segoe UI", 7)
        ).pack(padx=6, pady=4)
        self._evidence_frame.pack(fill="x", padx=8, pady=(0, 4))

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

        # Flash the evidence frame to confirm acceptance
        self._evidence_frame.configure(bg="#2a4a2a")
        self.after(300, lambda: self._evidence_frame.configure(bg="#1e2a1e"))

    # ── Helpers ──────────────────────────────────────────────────────────

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
