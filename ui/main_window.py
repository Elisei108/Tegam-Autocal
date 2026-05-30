"""
ui/main_window.py — TegamCAL main dashboard
customtkinter 5.x, dark theme, fixed 1280x800

Подключение к CalibrationSession:
  - _on_start()  создаёт сессию, вешает колбэки, запускает
  - _on_stop()   вызывает session.abort()
  - Колбэки обновляют UI через root.after() (безопасно из потока)
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

# Соответствие состояний сессии → шаг степпера (0-based)
from calibration.session import CalibrationSession, State, Mode

_STATE_TO_STEP = {
    State.AS_FOUND: 0,
    State.ADJUST:   1,
    State.AS_LEFT:  2,
    State.REPORT:   3,
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
        self._build_footer()
        self._build_body()

        # Сессия создаётся при нажатии Start
        self._session: CalibrationSession = None

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

        # Instrument badges — сохраняем ссылки для обновления
        self._badge_tegam   = self._badge(hdr, "Tegam 1750", "COM3")
        self._badge_arduino = self._badge(hdr, "Arduino",    "COM4")
        # Начальное состояние — серый "unknown" (не проверяли ещё)
        self.set_badge("tegam",   "unknown")
        self.set_badge("arduino", "unknown")

        ctk.CTkButton(
            hdr, text="⟳  Reconnect", width=104, height=28,
            fg_color=C["bg_card"], hover_color=C["bg_panel"],
            text_color=C["dim"], border_color=C["border"], border_width=1,
            corner_radius=4, font=ctk.CTkFont("Segoe UI", 11),
        ).pack(side="left", padx=(6, 0))

        # Session fields (right)
        sf = ctk.CTkFrame(hdr, fg_color="transparent")
        sf.pack(side="right", padx=16)

        # Сохраняем ссылки на Entry чтобы читать при старте
        self._entry_temp = self._field(sf, "TEMP",           "23.2",    72)
        self._entry_temp.pack(side="left", padx=4)

        self._entry_rh = self._field(sf, "RH %",            "48",      66)
        self._entry_rh.pack(side="left", padx=4)

        self._vsep(sf)

        self._entry_sn = self._field(sf, "INSTRUMENT S/N",  "TG-001234", 116)
        self._entry_sn.pack(side="left", padx=4)

        self._vsep(sf)

        # Список техников — заполняется из конфига при старте
        tf = ctk.CTkFrame(sf, fg_color="transparent")
        tf.pack(side="left", padx=4)
        ctk.CTkLabel(tf, text="TECHNICIAN",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C["dim"]).pack(anchor="w")
        self._tech_var = tk.StringVar(value="—")
        self._tech_menu = ctk.CTkOptionMenu(
            tf, variable=self._tech_var,
            values=["—"],
            width=154, height=28,
            fg_color=C["bg_card"], button_color=C["bg_card"],
            button_hover_color=C["bg_panel"], dropdown_fg_color=C["bg_card"],
            text_color=C["text"], font=ctk.CTkFont("Segoe UI", 12),
        )
        self._tech_menu.pack()

        # Загружаем список техников из конфига в фоне при старте окна
        self.after(200, self._load_technicians)

    def _badge(self, parent, name, port):
        """
        Создать индикатор подключения прибора.
        Возвращает dict со ссылками на виджеты для последующего обновления.
        Состояния: 'ok' (зелёный) | 'error' (красный) | 'unknown' (серый)
        """
        # Внешний фрейм — его цвет меняется
        wrap = ctk.CTkFrame(parent, fg_color=C["bg_card"],
                            border_color=C["border"],
                            border_width=1, corner_radius=6)
        wrap.pack(side="left", padx=4)
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(padx=10, pady=5)

        # Точка-индикатор
        dot_lbl = ctk.CTkLabel(row, text="●",
                               font=ctk.CTkFont("Segoe UI", 10),
                               text_color=C["dim"])
        dot_lbl.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(row, text=name,
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=C["text"]).pack(side="left")
        ctk.CTkLabel(row, text=f"  {port}",
                     font=ctk.CTkFont("Consolas", 11),
                     text_color=C["dim"]).pack(side="left")

        return {"wrap": wrap, "dot": dot_lbl}

    def set_badge(self, instrument: str, status: str):
        """
        Обновить индикатор подключения.
        instrument : 'tegam' | 'arduino'
        status     : 'ok' | 'error' | 'unknown'

        'ok'      — зелёный  (подключён, ответил)
        'error'   — красный  (ошибка связи, не отвечает)
        'unknown' — серый    (ещё не проверяли)
        """
        badge = self._badge_tegam if instrument == "tegam" else self._badge_arduino
        if badge is None:
            return

        if status == "ok":
            fg_color  = C["green_bg"]
            bdr_color = C["green_bdr"]
            dot_color = C["green"]
        elif status == "error":
            fg_color  = C["red_bg"]
            bdr_color = C["red_bdr"]
            dot_color = C["red"]
        else:  # unknown
            fg_color  = C["bg_card"]
            bdr_color = C["border"]
            dot_color = C["dim"]

        badge["wrap"].configure(fg_color=fg_color, border_color=bdr_color)
        badge["dot"].configure(text_color=dot_color)

    def _field(self, parent, label, default, width):
        """Создать поле ввода. Возвращает фрейм (pack снаружи)."""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text=label, font=ctk.CTkFont("Segoe UI", 9),
                     text_color=C["dim"]).pack(anchor="w")
        e = ctk.CTkEntry(f, width=width, height=28,
                         fg_color=C["bg_card"], border_color=C["border"],
                         text_color=C["text"], font=ctk.CTkFont("Consolas", 12))
        e.insert(0, default)
        e.pack()
        # Сохраняем ссылку на Entry внутри фрейма для удобного чтения
        f._entry = e
        return f

    def _vsep(self, parent):
        ctk.CTkFrame(parent, width=1, height=36,
                     fg_color=C["border"]).pack(side="left", padx=10)

    def _load_technicians(self):
        """Загрузить список техников из config.xlsx в выпадающий список."""
        try:
            from config.config_loader import load_config
            cfg = load_config()
            names = cfg.get_technician_names()
            if names:
                self._tech_menu.configure(values=names)
                self._tech_var.set(names[0])
        except Exception as e:
            self.log("WARN", f"Could not load technicians from config: {e}")

    # ── Stepper ───────────────────────────────────────────────────────────────

    def _build_stepper(self):
        bar = ctk.CTkFrame(self, height=50, fg_color=C["bg_panel"], corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self._stepper_row = ctk.CTkFrame(bar, fg_color="transparent")
        self._stepper_row.place(relx=0.5, rely=0.5, anchor="center")

        # Начальное состояние: все future
        self._step_states = ["future", "future", "future", "future"]
        self._redraw_stepper()

    def _redraw_stepper(self):
        """Перерисовать степпер с текущими состояниями шагов."""
        for w in self._stepper_row.winfo_children():
            w.destroy()

        for i, (label, state) in enumerate(zip(self.STEPS, self._step_states)):
            self._step_item(self._stepper_row, i + 1, label, state).pack(side="left")
            if i < len(self.STEPS) - 1:
                ctk.CTkFrame(self._stepper_row, width=96, height=1,
                             fg_color=C["border"]).pack(side="left", padx=10)

    def set_step(self, step_index: int, state: str):
        """
        Установить состояние шага степпера.
        step_index: 0=As Found, 1=Adjust, 2=As Left, 3=Report
        state: 'active' | 'done' | 'skipped' | 'future'
        """
        if 0 <= step_index < len(self._step_states):
            self._step_states[step_index] = state
            self._redraw_stepper()

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

        self._table_title_var = tk.StringVar(value="MEASUREMENTS — AS FOUND")
        tk.Label(outer, textvariable=self._table_title_var,
                 font=("Segoe UI", 10, "bold"),
                 fg=C["dim"], bg=C["bg_card"],
                 anchor="w", padx=8, pady=7).pack(fill="x")
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

        # Кнопки справа налево
        tk.Button(hdr, text="Clear ✕", font=("Segoe UI", 10),
                  fg=C["dim"], bg=C["bg_card"],
                  activeforeground=C["red"], activebackground=C["bg_card"],
                  relief="flat", bd=0, cursor="hand2",
                  command=self._clear_log).pack(side="right", padx=(4, 10))

        tk.Button(hdr, text="📄 Export", font=("Segoe UI", 10),
                  fg=C["dim"], bg=C["bg_card"],
                  activeforeground=C["cyan"], activebackground=C["bg_card"],
                  relief="flat", bd=0, cursor="hand2",
                  command=self._export_log).pack(side="right", padx=4)

        tk.Button(hdr, text="📋 Copy", font=("Segoe UI", 10),
                  fg=C["dim"], bg=C["bg_card"],
                  activeforeground=C["cyan"], activebackground=C["bg_card"],
                  relief="flat", bd=0, cursor="hand2",
                  command=self._copy_log).pack(side="right", padx=4)

        tk.Frame(outer, height=1, bg=C["border"]).pack(fill="x")

        self._log_widget = tk.Text(outer, bg=C["bg_panel"], fg=C["text"],
                            font=("Consolas", 11), relief="flat", bd=0,
                            state="disabled", cursor="arrow",
                            selectbackground=C["bg_card"], height=4)
        self._log_widget.pack(fill="both", expand=True, padx=8, pady=4)

        self._log_widget.tag_config("ts",   foreground="#505b6e")
        self._log_widget.tag_config("INFO", foreground=C["dim"])
        self._log_widget.tag_config("PASS", foreground=C["green"])
        self._log_widget.tag_config("FAIL", foreground=C["red"])
        self._log_widget.tag_config("WARN", foreground=C["yellow"])
        self._log_widget.tag_config("ERR",  foreground=C["red"])
        self._log_widget.tag_config("msg",  foreground=C["text"])

        self.log("INFO", "TegamCAL started — waiting for operator input")

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self):
        ftr = ctk.CTkFrame(self, height=60, fg_color=C["bg_header"], corner_radius=0)
        ftr.pack(fill="x", side="bottom")
        ftr.pack_propagate(False)
        tk.Frame(ftr, height=1, bg=C["border"]).pack(fill="x")

        row = ctk.CTkFrame(ftr, fg_color="transparent")
        row.place(relx=0.5, rely=0.55, anchor="center")

        self._progress_var = tk.StringVar(value="Ready — press Start to begin As Found")
        ctk.CTkLabel(row, textvariable=self._progress_var,
                     font=ctk.CTkFont("Consolas", 12),
                     text_color=C["dim"]).pack(side="left", padx=(0, 20))

        # Дропдаун режима — на одном уровне со Start
        self._mode_var = tk.StringVar(value=Mode.FULL.value)
        self._mode_menu = ctk.CTkOptionMenu(
            row,
            variable=self._mode_var,
            values=[Mode.FULL.value, Mode.VERIFICATION.value, Mode.ADJUST_ONLY.value],
            width=170, height=38,
            fg_color=C["bg_card"], button_color=C["bg_card"],
            button_hover_color=C["bg_panel"], dropdown_fg_color=C["bg_card"],
            text_color=C["text"], font=ctk.CTkFont("Segoe UI", 12),
        )
        self._mode_menu.pack(side="left", padx=(0, 12))

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

        # Кнопки ADJUST — скрыты по умолчанию, появляются при состоянии ADJUST
        # Сохраняем ссылку на row чтобы потом показать/спрятать
        self._footer_row = row

        self._btn_confirm = ctk.CTkButton(
            row, text="✓   Confirm Adjust",
            width=160, height=38,
            fg_color=C["green"], hover_color="#6FAF73",
            text_color="#0A1F0B",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            corner_radius=6, command=self._on_confirm_adjust,
        )

        self._btn_skip = ctk.CTkButton(
            row, text="↼   Skip Adjust",
            width=140, height=38,
            fg_color="transparent", hover_color="#3a2a10",
            text_color=C["yellow"], border_color=C["yellow"], border_width=1,
            corner_radius=6, command=self._on_skip_adjust,
        )
        # Изначально не пакуем — покажем в _show_adjust_buttons()

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_start(self):
        """Нажата кнопка Start — собираем данные из полей и запускаем сессию."""
        if self._session and self._session.state != State.IDLE:
            self.log("WARN", "Session already running")
            return

        # Читаем поля из заголовка
        operator    = self._tech_var.get()
        serial_no   = self._entry_sn._entry.get().strip()
        temperature = self._entry_temp._entry.get().strip()
        humidity    = self._entry_rh._entry.get().strip()

        # Читаем выбранный режим из dropdown
        mode_str = self._mode_var.get()
        mode = next((m for m in Mode if m.value == mode_str), Mode.FULL)

        # Минимальная валидация
        if operator == "—" or not operator:
            self.log("WARN", "Select a technician before starting")
            return
        if not serial_no:
            self.log("WARN", "Enter instrument serial number before starting")
            return

        # Блокируем кнопку Start, разблокируем Stop
        self._btn_start.configure(state="disabled", fg_color=C["bg_card"],
                                  text_color=C["dim"])
        self._btn_stop.configure(state="normal")

        # Сбрасываем таблицу в исходное состояние
        self._reset_table()

        # Переводим баджи в "unknown" перед новым подключением
        self.set_badge("tegam",   "unknown")
        self.set_badge("arduino", "unknown")

        # Создаём и настраиваем сессию
        self._session = CalibrationSession()
        self._session.ui_root              = self
        self._session.on_state_change      = self._cb_state_change
        self._session.on_measurement       = self._cb_measurement
        self._session.on_point_done        = self._cb_point_done
        self._session.on_phase_done        = self._cb_phase_done
        self._session.on_error             = self._cb_error
        self._session.on_log               = self.log
        self._session.on_instrument_status = self._cb_instrument_status

        self.log("INFO",
            f"Starting session | Mode: {mode.value} | Operator: {operator} | "
            f"S/N: {serial_no} | T={temperature}°C RH={humidity}%")

        self._session.start_session(
            operator    = operator,
            serial_no   = serial_no,
            temperature = temperature,
            humidity    = humidity,
            mode        = mode,
        )

    def _on_stop(self):
        """Нажата кнопка Stop."""
        if self._session:
            self._session.abort()
            self.log("WARN", "Calibration aborted by operator")
        self._hide_adjust_buttons()
        self._restore_start_button()
        self.set_badge("tegam",   "unknown")
        self.set_badge("arduino", "unknown")
        self.set_progress("Stopped — press Start to begin again")

    def _on_confirm_adjust(self):
        """Нажата кнопка Confirm Adjust — прибор подстроен, продолжаем."""
        if self._session:
            self._session.confirm_adjust()
            self.log("INFO", "Adjustment confirmed by operator — continuing to AS LEFT")
        self._hide_adjust_buttons()

    def _on_skip_adjust(self):
        """Нажата кнопка Skip Adjust — пропускаем подстройку."""
        if self._session:
            self._session.skip_adjust()
            self.log("WARN", "Adjustment skipped by operator")
        self._hide_adjust_buttons()

    def _show_adjust_buttons(self):
        """Показать кнопки Confirm/Skip (вход в ADJUST)."""
        self._btn_confirm.pack(side="left", padx=(20, 8))
        self._btn_skip.pack(side="left")

    def _hide_adjust_buttons(self):
        """Спрятать кнопки Confirm/Skip (выход из ADJUST)."""
        self._btn_confirm.pack_forget()
        self._btn_skip.pack_forget()

    # ── Session callbacks (вызываются из потока через root.after) ─────────────

    def _cb_state_change(self, state: State):
        """Сессия перешла в новое состояние → обновляем степпер и статус."""
        # Определяем режим от текущей сессии (если есть)
        mode = self._session.session_data.mode if self._session else None

        if state == State.AS_FOUND:
            # Сбрасываем все шаги, активируем первый
            # Для Verification: Adjust и As Left сразу skipped
            if mode == Mode.VERIFICATION:
                self._step_states = ["active", "skipped", "skipped", "future"]
            else:
                self._step_states = ["active", "future", "future", "future"]
            self._redraw_stepper()
            self.set_progress(f"AS FOUND — measuring... ({mode.value if mode else ''})")
            self._table_title_var.set("MEASUREMENTS — AS FOUND")

        elif state == State.ADJUST:
            # ADJUST_ONLY — начинаем сразу с ADJUST, As Found и As Left пропущены
            if mode == Mode.ADJUST_ONLY:
                self._step_states = ["skipped", "active", "skipped", "skipped"]
                self.set_progress("ADJUST ONLY — manual relay control, press Stop when done")
                self.log("WARN", "Manual adjust mode — click points in left panel to switch relays")
            else:
                self._step_states = ["done", "active", "future", "future"]
                self.set_progress("ADJUST — adjust instrument, then press Confirm")
                self.log("WARN", "Manual adjustment required — adjust instrument and press Confirm (or Skip)")
            self._redraw_stepper()
            self._show_adjust_buttons()

        elif state == State.AS_LEFT:
            # Если ADJUST был — помечаем его done, иначе skipped
            adjust_state = "done" if (self._session and
                                      self._session.session_data.adjust_done) else "skipped"
            self._step_states = ["done", adjust_state, "active", "future"]
            self._redraw_stepper()
            self.set_progress("AS LEFT — measuring...")
            self._table_title_var.set("MEASUREMENTS — AS LEFT")
            self._reset_table()

        elif state == State.REPORT:
            # Схлопываем степпер по режиму
            if mode == Mode.VERIFICATION:
                self._step_states = ["done", "skipped", "skipped", "active"]
            else:
                self._step_states = ["done", self._step_states[1], "done", "active"]
            self._redraw_stepper()
            self.set_progress("Complete — calibration finished ✓")
            self._restore_start_button()
            self.log("PASS", "Calibration complete — ready for report")
            # Автоматически закрываем сессию — сбрасываем в IDLE
            # чтобы повторный Start не давал "Session already running"
            if self._session:
                self._session.finish_session()

        elif state == State.ABORTED:
            self._step_states = ["future", "future", "future", "future"]
            self._redraw_stepper()
            self._restore_start_button()

        elif state == State.IDLE:
            pass   # финальный сброс после finish_session()

    def _cb_measurement(self, pt_idx: int, meas_idx: int,
                         value: float, unit: str):
        """Пришло одно показание → записать в ячейку таблицы."""
        # Определяем количество знаков по единице
        dec = {"mOhm": 1, "Ohm": 3, "KOhm": 4, "MOhm": 4}.get(unit, 3)
        text = f"{value:.{dec}f}"
        self.set_cell(pt_idx, meas_idx, text, "running")
        # Подсвечиваем активную точку в левой панели
        self.set_point_state(pt_idx, "active")

    def _cb_point_done(self, pt_idx: int, result):
        """Точка полностью измерена → заполнить Mean, U, Status."""
        import math
        dec = {"mOhm": 1, "Ohm": 3, "KOhm": 4, "MOhm": 4}.get(result.display_unit, 3)

        # Если данных нет (NaN) — точка FAIL из-за отсутствия показаний
        if math.isnan(result.display_value):
            self.set_cell(pt_idx, "mean", "NO DATA",   "fail")
            self.set_cell(pt_idx, "u",    "—",          "fail")
            self.set_cell(pt_idx, "status", "FAIL",     "fail")
            self.set_point_state(pt_idx, "fail")
            return

        self.set_cell(pt_idx, "mean",
                      f"{result.display_value:.{dec}f} {result.display_unit}",
                      "pass" if result.passed else "fail")

        self.set_cell(pt_idx, "u",
                      f"±{result.display_u:.{dec}f}",
                      "")

        status_text = "PASS" if result.passed else "FAIL"
        self.set_cell(pt_idx, "status", status_text,
                      "pass" if result.passed else "fail")

        # Цвет точки в левой панели
        self.set_point_state(pt_idx, "done" if result.passed else "fail")

    def _cb_phase_done(self, phase: str, results):
        """Фазовый прогон завершён → логируем итог."""
        passed = sum(1 for r in results if r.passed)
        total  = len(results)
        level  = "PASS" if passed == total else "WARN"
        self.log(level,
            f"{phase} complete: {passed}/{total} PASS"
            + ("" if passed == total else
               f" — FAIL on point(s): "
               f"{[r.point_num for r in results if not r.passed]}"))

    def _cb_error(self, message: str):
        """Критическая ошибка сессии."""
        self.log("ERR", f"Session error: {message}")
        self.set_progress(f"ERROR: {message[:60]}")
        self._restore_start_button()

    def _cb_instrument_status(self, instrument: str, status: str):
        """Сессия сообщает о состоянии подключения прибора → обновляем badge."""
        self.set_badge(instrument, status)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reset_table(self):
        """Сбросить все ячейки таблицы в начальное состояние."""
        for r in range(len(self.CAL_POINTS)):
            for m in range(self.N_MEAS):
                self.set_cell(r, m, "—", "")
            self.set_cell(r, "mean",   "—", "")
            self.set_cell(r, "u",      "—", "")
            self.set_cell(r, "status", "—", "")
            self.set_point_state(r, "idle")

    def _restore_start_button(self):
        """Вернуть кнопку Start в активное состояние."""
        self._btn_start.configure(state="normal", fg_color=C["cyan"],
                                  text_color="#071419")

    def _get_log_text(self) -> str:
        """Получить весь текст лога в виде обычной строки (plain text, без тегов)"""
        return self._log_widget.get("1.0", "end").strip()

    def _clear_log(self):
        self._log_widget.configure(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.configure(state="disabled")

    def _copy_log(self):
        """Скопировать содержимое лога в буфер обмена (Clipboard)."""
        text = self._get_log_text()
        if not text:
            self.log("WARN", "Log is empty — nothing to copy")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("INFO", f"Log copied to clipboard ({len(text.splitlines())} lines)")

    def _export_log(self):
        """Сохранить лог в .txt файл через диалог сохранения."""
        from tkinter import filedialog
        import os

        text = self._get_log_text()
        if not text:
            self.log("WARN", "Log is empty — nothing to export")
            return

        # Имя файла по умолчанию: TegamCAL_log_YYYY-MM-DD_HH-MM.txt
        default_name = datetime.now().strftime("TegamCAL_log_%Y-%m-%d_%H-%M.txt")

        path = filedialog.asksaveasfilename(
            title="Export Event Log",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )

        if not path:   # оператор нажал Cancel
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                # Заголовок файла
                sn = self._entry_sn._entry.get().strip() or "unknown"
                op = self._tech_var.get()
                f.write(f"TegamCAL Event Log\n")
                f.write(f"Exported : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Instrument S/N : {sn}\n")
                f.write(f"Operator : {op}\n")
                f.write("-" * 60 + "\n")
                f.write(text)
                f.write("\n")
            self.log("INFO", f"Log exported → {os.path.basename(path)}")
        except Exception as e:
            self.log("ERR", f"Export failed: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, level: str, message: str):
        """Добавить цветную строку в лог."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_widget.configure(state="normal")
        self._log_widget.insert("end", f"[{ts}] ", "ts")
        self._log_widget.insert("end", f"{level:<5}", level.upper()[:4])
        self._log_widget.insert("end", f"  {message}\n", "msg")
        self._log_widget.see("end")
        self._log_widget.configure(state="disabled")

    def set_progress(self, text: str):
        """Обновить строку статуса в футере."""
        self._progress_var.set(text)

    def set_cell(self, point: int, meas, value: str, status: str = ""):
        """
        Обновить ячейку таблицы измерений.
        point  : 0-based строка (0..3)
        meas   : 0..4 для показаний, или 'mean' / 'u' / 'status'
        status : 'pass' | 'fail' | 'warn' | 'running' | ''
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
        """Перерисовать строку точки в левой панели (idle/active/done/fail)."""
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
