"""
ui/main_window.py — TegamCAL main dashboard
customtkinter 5.x, dark theme, fixed 1280×800
"""

import tkinter as tk
import customtkinter as ctk
from datetime import datetime

# ── Colour palette ────────────────────────────────────────────────────────────
C = {
    "bg_main":   "#1c1f26",
    "bg_panel":  "#22262f",
    "bg_card":   "#2a2f3a",
    "bg_header": "#161920",
    "cyan":      "#00BCD4",
    "cyan_bg":   "#0c2226",
    "green":     "#81C784",
    "green_bg":  "#192e1a",
    "green_bdr": "#2e5030",
    "red":       "#E57373",
    "red_bg":    "#2e1919",
    "red_bdr":   "#5a2020",
    "yellow":    "#FFB74D",
    "text":      "#DDE3EC",
    "dim":       "#8899AA",
    "border":    "#333a47",
}

_STEP_CFG = {
    "active":  (C["cyan"],   C["cyan_bg"],  C["cyan"],   C["cyan"]),
    "done":    (C["green"],  C["green_bg"], C["green"],  C["green"]),
    "skipped": (C["yellow"], "#2e2510",     C["yellow"], C["yellow"]),
    "future":  (C["dim"],    C["bg_card"],  C["dim"],    C["border"]),
}

_POINT_CFG = {
    "done":   (C["green"],  C["green"],  C["bg_panel"], C["green"]),
    "active": (C["cyan"],   C["cyan"],   C["cyan_bg"],  C["cyan"]),
    "fail":   (C["red"],    C["red"],    C["bg_panel"], C["red"]),
    "idle":   (C["border"], C["dim"],    C["bg_panel"], C["bg_panel"]),
}


class MainWindow(ctk.CTk):
    """TegamCAL calibration dashboard."""

    CAL_POINTS = [(1, "2 Ω"), (2, "20 Ω"), (3, "200 Ω"), (4, "2 kΩ")]
    STEPS      = ["As Found", "Adjust", "As Left", "Report"]
    N_MEAS     = 5

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self._setup_window()
        self._build_header()
        self._build_stepper()
        self._build_footer()   # footer before body so expand works
        self._build_body()

    # ── Window ────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title("TegamCAL")
        self.geometry("1280x800")
        self.resizable(False, False)
        self.configure(fg_color=C["bg_main"])

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = ctk.CTkFrame(self, height=62, fg_color=C["bg_header"], corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo
        ctk.CTkLabel(hdr, text="TegamCAL",
                     font=ctk.CTkFont("Segoe UI", 18, weight="bold"),
                     text_color=C["cyan"]).pack(side="left", padx=(16, 3))
        ctk.CTkLabel(hdr, text="Stage 1",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=C["dim"]).pack(side="left", padx=(0, 12))
        self._vsep(hdr)

        # Instrument badges
        self._badge(hdr, "Tegam 1750", "COM3", ok=True)
        self._badge(hdr, "Arduino",    "COM4", ok=True)
        ctk.CTkButton(
            hdr, text="⟳  Reconnect", width=104, height=28,
            fg_color=C["bg_card"], hover_color=C["bg_panel"],
            text_color=C["dim"], border_color=C["border"], border_width=1,
            corner_radius=4, font=ctk.CTkFont("Segoe UI", 11),
        ).pack(side="left", padx=(6, 0))

        # Session fields (right)
        sf = ctk.CTkFrame(hdr, fg_color="transparent")
        sf.pack(side="right", padx=16)

        self._field(sf, "TEMP",           "23.2 °C",   72).pack(side="left", padx=4)
        self._field(sf, "RH",             "48 %",      66).pack(side="left", padx=4)
        self._vsep(sf)
        self._field(sf, "INSTRUMENT S/N", "TG-001234", 116).pack(side="left", padx=4)
        self._vsep(sf)

        tf = ctk.CTkFrame(sf, fg_color="transparent")
        tf.pack(side="left", padx=4)
        ctk.CTkLabel(tf, text="TECHNICIAN",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C["dim"]).pack(anchor="w")
        ctk.CTkOptionMenu(
            tf, values=["Иванов И.И.", "Петров П.П."],
            width=154, height=28,
            fg_color=C["bg_card"], button_color=C["bg_card"],
            button_hover_color=C["bg_panel"], dropdown_fg_color=C["bg_card"],
            text_color=C["text"], font=ctk.CTkFont("Segoe UI", 12),
        ).pack()

    def _badge(self, parent, name, port, ok=True):
        bg  = C["green_bg"]  if ok else C["red_bg"]
        bdr = C["green_bdr"] if ok else C["red_bdr"]
        dot = C["green"]     if ok else C["red"]
        wrap = ctk.CTkFrame(parent, fg_color=bg, border_color=bdr,
                            border_width=1, corner_radius=6)
        wrap.pack(side="left", padx=4)
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(padx=10, pady=5)
        ctk.CTkLabel(row, text="●", font=ctk.CTkFont("Segoe UI", 10),
                     text_color=dot).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(row, text=name, font=ctk.CTkFont("Segoe UI", 12),
                     text_color=C["text"]).pack(side="left")
        ctk.CTkLabel(row, text=f"  {port}", font=ctk.CTkFont("Consolas", 11),
                     text_color=C["dim"]).pack(side="left")

    def _field(self, parent, label, default, width):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text=label, font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C["dim"]).pack(anchor="w")
        e = ctk.CTkEntry(f, width=width, height=28,
                         fg_color=C["bg_card"], border_color=C["border"],
                         text_color=C["text"], font=ctk.CTkFont("Consolas", 12))
        e.insert(0, default)
        e.pack()
        return f

    def _vsep(self, parent):
        ctk.CTkFrame(parent, width=1, height=36,
                     fg_color=C["border"]).pack(side="left", padx=10)

    # ── Stepper ───────────────────────────────────────────────────────────────

    def _build_stepper(self):
        bar = ctk.CTkFrame(self, height=50, fg_color=C["bg_panel"], corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.place(relx=0.5, rely=0.5, anchor="center")

        step_states = ["active", "future", "future", "future"]
        for i, (label, state) in enumerate(zip(self.STEPS, step_states)):
            self._step_item(row, i + 1, label, state).pack(side="left")
            if i < len(self.STEPS) - 1:
                ctk.CTkFrame(row, width=96, height=1,
                             fg_color=C["border"]).pack(side="left", padx=10)

    def _step_item(self, parent, num, label, state):
        fg, bg, text_fg, outline = _STEP_CFG.get(state, _STEP_CFG["future"])
        f = ctk.CTkFrame(parent, fg_color="transparent")

        cv = tk.Canvas(f, width=26, height=26, bg=C["bg_panel"],
                       highlightthickness=0)
        cv.pack(side="left", padx=(0, 7))
        cv.create_oval(2, 2, 24, 24, outline=outline, fill=bg, width=2)
        sym = "✓" if state == "done" else ("—" if state == "skipped" else str(num))
        cv.create_text(13, 13, text=sym, fill=fg,
                       font=("Segoe UI", 10, "bold"))

        ctk.CTkLabel(f, text=label,
                     font=ctk.CTkFont("Segoe UI", 12,
                                      weight="bold" if state == "active" else "normal"),
                     text_color=text_fg).pack(side="left")
        return f

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color=C["bg_main"], corner_radius=0)
        body.pack(fill="both", expand=True)
        self._build_points_panel(body)
        self._build_main_panel(body)

    # ── Cal points panel (left) ───────────────────────────────────────────────

    def _build_points_panel(self, parent):
        panel = ctk.CTkFrame(parent, width=196, fg_color=C["bg_panel"], corner_radius=0)
        panel.pack(side="left", fill="y")
        panel.pack_propagate(False)

        # Right border line
        ctk.CTkFrame(panel, width=1, fg_color=C["border"]).pack(side="right", fill="y")

        ctk.CTkLabel(panel, text="CAL POINTS",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C["dim"]).pack(anchor="w", padx=16, pady=(14, 6))

        self._point_rows = []
        for num, nom in self.CAL_POINTS:
            row = self._point_row(panel, num, nom, "idle")
            row.pack(fill="x")
            self._point_rows.append(row)

    def _point_row(self, parent, num, nominal, state):
        dot, text_fg, bg, bar_fg = _POINT_CFG.get(state, _POINT_CFG["idle"])
        outer = tk.Frame(parent, bg=bg)
        tk.Frame(outer, width=3, bg=bar_fg).pack(side="left", fill="y")
        inner = tk.Frame(outer, bg=bg)
        inner.pack(side="left", fill="x", expand=True, padx=(10, 12), pady=9)
        tk.Label(inner, text="●", font=("Segoe UI", 9),
                 fg=dot, bg=bg).pack(side="left", padx=(0, 7))
        tk.Label(inner, text=f"Point {num}", font=("Segoe UI", 13),
                 fg=text_fg, bg=bg).pack(side="left")
        tk.Label(inner, text=nominal, font=("Consolas", 11),
                 fg=C["dim"], bg=bg).pack(side="right")
        return outer

    # ── Main panel (right) ────────────────────────────────────────────────────

    def _build_main_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=C["bg_main"], corner_radius=0)
        panel.pack(side="left", fill="both", expand=True)
        self._build_table(panel)
        self._build_log(panel)

    # ── Measurement table ─────────────────────────────────────────────────────

    def _build_table(self, parent):
        outer = ctk.CTkFrame(parent, fg_color=C["bg_panel"],
                             border_color=C["border"], border_width=1, corner_radius=6)
        outer.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        tk.Label(outer, text="  MEASUREMENTS — AS FOUND",
                 font=("Segoe UI", 10, "bold"),
                 fg=C["dim"], bg=C["bg_card"],
                 anchor="w", pady=7).pack(fill="x")
        tk.Frame(outer, height=1, bg=C["border"]).pack(fill="x")

        tbl = tk.Frame(outer, bg=C["bg_panel"])
        tbl.pack(fill="both", expand=True, padx=6, pady=6)

        COLS = ["Point", "#1", "#2", "#3", "#4", "#5", "Mean", "U (k=2)", "Status"]
        for c, h in enumerate(COLS):
            tk.Label(tbl, text=h,
                     font=("Segoe UI", 10, "bold"),
                     fg=C["dim"], bg=C["bg_card"],
                     anchor="w" if c == 0 else "center",
                     padx=10, pady=7,
                     ).grid(row=0, column=c, sticky="ew", padx=1, pady=(0, 2))

        self._cells = {}

        for r, (num, nom) in enumerate(self.CAL_POINTS):
            bg = C["bg_panel"]
            tk.Label(tbl, text=f"{num}  —  {nom}",
                     font=("Segoe UI", 12), fg=C["dim"], bg=bg,
                     anchor="w", padx=12, pady=9,
                     ).grid(row=r + 1, column=0, sticky="ew", padx=1, pady=1)

            for m in range(self.N_MEAS):
                lbl = tk.Label(tbl, text="—", font=("Consolas", 12),
                               fg=C["border"], bg=bg, anchor="center", pady=9)
                lbl.grid(row=r + 1, column=m + 1, sticky="ew", padx=1, pady=1)
                self._cells[(r, m)] = lbl

            for key, col in (("mean", 6), ("u", 7)):
                lbl = tk.Label(tbl, text="—",
                               font=("Consolas", 12,
                                     "bold" if key == "mean" else "normal"),
                               fg=C["border"], bg=bg, anchor="center", pady=9)
                lbl.grid(row=r + 1, column=col, sticky="ew", padx=1, pady=1)
                self._cells[(r, key)] = lbl

            lbl = tk.Label(tbl, text="—", font=("Segoe UI", 11, "bold"),
                           fg=C["dim"], bg=bg, anchor="center", pady=9)
            lbl.grid(row=r + 1, column=8, sticky="ew", padx=1, pady=1)
            self._cells[(r, "status")] = lbl

        for c in range(len(COLS)):
            tbl.columnconfigure(c, weight=1)

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_log(self, parent):
        outer = ctk.CTkFrame(parent, height=130, fg_color=C["bg_panel"],
                             border_color=C["border"], border_width=1, corner_radius=6)
        outer.pack(fill="x", padx=12, pady=(0, 10))
        outer.pack_propagate(False)

        hdr = tk.Frame(outer, bg=C["bg_card"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="  EVENT LOG", font=("Segoe UI", 9, "bold"),
                 fg=C["dim"], bg=C["bg_card"], pady=6).pack(side="left")
        tk.Button(hdr, text="View Full Log ↗", font=("Segoe UI", 10),
                  fg=C["cyan"], bg=C["bg_card"],
                  activeforeground=C["cyan"], activebackground=C["bg_card"],
                  relief="flat", bd=0, cursor="hand2").pack(side="right", padx=10)
        tk.Frame(outer, height=1, bg=C["border"]).pack(fill="x")

        self._log = tk.Text(outer, bg=C["bg_panel"], fg=C["text"],
                            font=("Consolas", 11), relief="flat", bd=0,
                            state="disabled", cursor="arrow",
                            selectbackground=C["bg_card"], height=4)
        self._log.pack(fill="both", expand=True, padx=8, pady=4)

        self._log.tag_config("ts",   foreground="#505b6e")
        self._log.tag_config("INFO", foreground=C["dim"])
        self._log.tag_config("PASS", foreground=C["green"])
        self._log.tag_config("FAIL", foreground=C["red"])
        self._log.tag_config("WARN", foreground=C["yellow"])
        self._log.tag_config("ERR",  foreground=C["red"])
        self._log.tag_config("msg",  foreground=C["text"])

        self.log("INFO", "TegamCAL started — waiting for operator input")

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self):
        ftr = ctk.CTkFrame(self, height=60, fg_color=C["bg_header"], corner_radius=0)
        ftr.pack(fill="x", side="bottom")
        ftr.pack_propagate(False)
        # Top border
        tk.Frame(ftr, height=1, bg=C["border"]).pack(fill="x")

        row = ctk.CTkFrame(ftr, fg_color="transparent")
        row.place(relx=0.5, rely=0.55, anchor="center")

        self._progress_var = tk.StringVar(value="Ready — press Start to begin As Found")
        ctk.CTkLabel(row, textvariable=self._progress_var,
                     font=ctk.CTkFont("Consolas", 12),
                     text_color=C["dim"]).pack(side="left", padx=(0, 28))

        self._btn_start = ctk.CTkButton(
            row, text="▶   Start",
            width=140, height=38,
            fg_color=C["cyan"], hover_color="#009DB8",
            text_color="#071419",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            corner_radius=6, command=self._on_start,
        )
        self._btn_start.pack(side="left", padx=(0, 10))

        self._btn_stop = ctk.CTkButton(
            row, text="■   Stop",
            width=114, height=38,
            fg_color="transparent", hover_color=C["red_bg"],
            text_color=C["red"], border_color=C["red"], border_width=1,
            corner_radius=6, command=self._on_stop,
        )
        self._btn_stop.pack(side="left")

    # ── Button stubs ──────────────────────────────────────────────────────────

    def _on_start(self):
        self.log("INFO", "Start pressed — calibration logic not yet implemented")

    def _on_stop(self):
        self.log("WARN", "Stop pressed — calibration logic not yet implemented")

    # ── Public API (used by calibration logic layer) ──────────────────────────

    def log(self, level: str, message: str):
        """Append a coloured entry to the event log."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert("end", f"[{ts}] ", "ts")
        self._log.insert("end", f"{level:<5}", level.upper()[:4])
        self._log.insert("end", f"  {message}\n", "msg")
        self._log.see("end")
        self._log.configure(state="disabled")

    def set_progress(self, text: str):
        """Update footer status line."""
        self._progress_var.set(text)

    def set_cell(self, point: int, meas, value: str, status: str = ""):
        """
        Update a measurement table cell.
        point : 0-based row (0..3)
        meas  : 0..4 for readings, or 'mean' / 'u' / 'status'
        status: 'pass' | 'fail' | 'warn' | 'running' | ''
        """
        lbl = self._cells.get((point, meas))
        if lbl is None:
            return
        fg = {"pass":    C["green"],
              "fail":    C["red"],
              "warn":    C["yellow"],
              "running": C["cyan"]}.get(status.lower(),
                         C["text"] if value != "—" else C["border"])
        lbl.configure(text=value, fg=fg)

    def set_point_state(self, point: int, state: str):
        """Rebuild one point row with a new state (idle/active/done/fail)."""
        if point < 0 or point >= len(self._point_rows):
            return
        old = self._point_rows[point]
        num, nom = self.CAL_POINTS[point]
        new = self._point_row(old.master, num, nom, state)
        new.pack(fill="x", before=old)
        old.destroy()
        self._point_rows[point] = new


def run():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    run()
