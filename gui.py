#!/usr/bin/env python3
"""星図生成プログラム GUI launcher — uv run gui.py"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
import types

# ── Direction mapping ──────────────────────────────────────────────────────────
_DIR_LABELS = ["（全天）", "北", "北東", "東", "南東", "南", "南西", "西", "北西"]
_DIR_VALUES = {
    "（全天）": "", "北": "北", "北東": "北東", "東": "東", "南東": "南東",
    "南": "南", "南西": "南西", "西": "西", "北西": "北西",
}

# Timezones shown in the dropdown
_TIMEZONES = [
    "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai", "Asia/Singapore",
    "Asia/Kolkata", "Australia/Sydney",
    "Europe/London", "Europe/Paris", "Europe/Berlin",
    "America/New_York", "America/Chicago", "America/Los_Angeles",
    "America/Honolulu", "UTC",
]


# ── Progress capture ───────────────────────────────────────────────────────────
class _StdoutCapture:
    """Forwards print() calls to a callback on the main thread."""
    encoding = "utf-8"
    errors   = "replace"

    def __init__(self, on_line):
        self._cb = on_line

    def write(self, text):
        text = text.strip()
        if text:
            self._cb(text)

    def flush(self):
        pass

    def reconfigure(self, **_):
        pass


# ── Main GUI class ─────────────────────────────────────────────────────────────
class StarChartGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("星図生成プログラム")
        self.root.minsize(980, 660)

        self._generating  = False
        self._preview_ref = None   # keep PhotoImage alive

        self._import_main()
        self._build_ui()
        self._on_city_changed()    # initialize field states

    # ── Bootstrap ──────────────────────────────────────────────────────────────
    def _import_main(self):
        try:
            import main as _m
            self._m = _m
        except Exception as exc:
            messagebox.showerror("起動エラー", f"main.py を読み込めません:\n{exc}")
            self.root.destroy()
            raise SystemExit(1)

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        m = self._m

        # ── PanedWindow: left (settings) | right (preview) ───────────────────
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── Left: scrollable settings panel ──────────────────────────────────
        left_outer = ttk.Frame(paned, width=340)
        left_outer.pack_propagate(False)
        paned.add(left_outer, weight=0)

        cv = tk.Canvas(left_outer, highlightthickness=0)
        sb = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sf = ttk.Frame(cv)
        sf.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=sf, anchor="nw")
        cv.bind_all("<MouseWheel>",
                    lambda e: cv.yview_scroll(-1 * (e.delta // 120), "units"))

        P = 6   # padding constant

        # ── Section: 観測地 ───────────────────────────────────────────────────
        lf = ttk.LabelFrame(sf, text="観測地", padding=P)
        lf.pack(fill=tk.X, padx=P, pady=(P, 2))

        # City preset
        ttk.Label(lf, text="都市:").grid(row=0, column=0, sticky="w")
        self._city_var = tk.StringVar()
        city_names = ["（手動入力）"] + [c for c in m.CITIES]
        self._city_cb = ttk.Combobox(lf, textvariable=self._city_var,
                                      values=city_names, state="readonly", width=22)
        self._city_cb.set("東京")
        self._city_cb.grid(row=0, column=1, columnspan=2, sticky="we", padx=(4, 0))
        self._city_cb.bind("<<ComboboxSelected>>", lambda e: self._on_city_changed())

        # Lat / Lon
        ttk.Label(lf, text="緯度:").grid(row=1, column=0, sticky="w", pady=2)
        self._lat_var = tk.StringVar(value="35.6762")
        self._lat_ent = ttk.Entry(lf, textvariable=self._lat_var, width=12)
        self._lat_ent.grid(row=1, column=1, sticky="we", padx=(4, 0))

        ttk.Label(lf, text="経度:").grid(row=2, column=0, sticky="w", pady=2)
        self._lon_var = tk.StringVar(value="139.6503")
        self._lon_ent = ttk.Entry(lf, textvariable=self._lon_var, width=12)
        self._lon_ent.grid(row=2, column=1, sticky="we", padx=(4, 0))

        ttk.Label(lf, text="標高(m):").grid(row=3, column=0, sticky="w", pady=2)
        self._elev_var = tk.StringVar(value="0")
        ttk.Entry(lf, textvariable=self._elev_var, width=8).grid(
            row=3, column=1, sticky="w", padx=(4, 0))

        ttk.Label(lf, text="地名:").grid(row=4, column=0, sticky="w", pady=2)
        self._locname_var = tk.StringVar()
        ttk.Entry(lf, textvariable=self._locname_var, width=22).grid(
            row=4, column=1, columnspan=2, sticky="we", padx=(4, 0))

        lf.columnconfigure(1, weight=1)

        # ── Section: 日時 ─────────────────────────────────────────────────────
        lf2 = ttk.LabelFrame(sf, text="日時", padding=P)
        lf2.pack(fill=tk.X, padx=P, pady=2)

        now = datetime.now()
        self._year_var  = tk.StringVar(value=str(now.year))
        self._month_var = tk.StringVar(value=f"{now.month:02d}")
        self._day_var   = tk.StringVar(value=f"{now.day:02d}")
        self._hour_var  = tk.StringVar(value=f"{now.hour:02d}")
        self._min_var   = tk.StringVar(value=f"{now.minute:02d}")

        # Date row: year / month / day spinboxes
        ttk.Label(lf2, text="日付:").grid(row=0, column=0, sticky="w")
        date_f = ttk.Frame(lf2)
        date_f.grid(row=0, column=1, columnspan=2, sticky="w", padx=(4, 0))
        ttk.Spinbox(date_f, textvariable=self._year_var,
                    from_=1900, to=2200, width=5).pack(side=tk.LEFT)
        ttk.Label(date_f, text="年").pack(side=tk.LEFT)
        ttk.Spinbox(date_f, textvariable=self._month_var,
                    from_=1, to=12, width=3, wrap=True,
                    format="%02.0f").pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(date_f, text="月").pack(side=tk.LEFT)
        ttk.Spinbox(date_f, textvariable=self._day_var,
                    from_=1, to=31, width=3, wrap=True,
                    format="%02.0f").pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(date_f, text="日").pack(side=tk.LEFT)

        # Time row: hour / minute spinboxes + 現在 button
        ttk.Label(lf2, text="時刻:").grid(row=1, column=0, sticky="w", pady=2)
        time_f = ttk.Frame(lf2)
        time_f.grid(row=1, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=2)
        ttk.Spinbox(time_f, textvariable=self._hour_var,
                    from_=0, to=23, width=3, wrap=True,
                    format="%02.0f").pack(side=tk.LEFT)
        ttk.Label(time_f, text="時").pack(side=tk.LEFT)
        ttk.Spinbox(time_f, textvariable=self._min_var,
                    from_=0, to=59, width=3, wrap=True,
                    format="%02.0f").pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(time_f, text="分").pack(side=tk.LEFT)
        ttk.Button(time_f, text="現在", width=4,
                   command=self._set_now).pack(side=tk.LEFT, padx=(10, 0))

        # Timezone
        ttk.Label(lf2, text="タイムゾーン:").grid(row=2, column=0, sticky="w", pady=2)
        self._tz_var = tk.StringVar(value="Asia/Tokyo")
        ttk.Combobox(lf2, textvariable=self._tz_var,
                     values=_TIMEZONES, width=20).grid(
            row=2, column=1, columnspan=2, sticky="we", padx=(4, 0))

        lf2.columnconfigure(1, weight=1)

        # ── Section: 表示設定 ─────────────────────────────────────────────────
        lf3 = ttk.LabelFrame(sf, text="表示設定", padding=P)
        lf3.pack(fill=tk.X, padx=P, pady=2)

        # Language
        ttk.Label(lf3, text="言語:").grid(row=0, column=0, sticky="w")
        self._lang_var = tk.StringVar(value="ja")
        lang_f = ttk.Frame(lf3)
        lang_f.grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Radiobutton(lang_f, text="日本語",  variable=self._lang_var, value="ja").pack(side=tk.LEFT)
        ttk.Radiobutton(lang_f, text="English", variable=self._lang_var, value="en").pack(side=tk.LEFT, padx=(8, 0))

        # Direction
        ttk.Label(lf3, text="方向:").grid(row=1, column=0, sticky="w", pady=2)
        self._dir_var = tk.StringVar(value="（全天）")
        ttk.Combobox(lf3, textvariable=self._dir_var,
                     values=_DIR_LABELS, state="readonly", width=10).grid(
            row=1, column=1, sticky="w", padx=(4, 0))

        # Min magnitude
        ttk.Label(lf3, text="限界等級:").grid(row=2, column=0, sticky="w", pady=2)
        self._mag_var = tk.StringVar(value="5.5")
        ttk.Spinbox(lf3, textvariable=self._mag_var,
                    from_=1.0, to=7.0, increment=0.5, width=6,
                    format="%.1f").grid(row=2, column=1, sticky="w", padx=(4, 0))

        # Toggle checkboxes (2-column grid)
        self._mw_var  = tk.BooleanVar(value=True)
        self._cl_var  = tk.BooleanVar(value=True)
        self._cn_var  = tk.BooleanVar(value=True)
        self._sn_var  = tk.BooleanVar(value=True)
        self._pn_var  = tk.BooleanVar(value=True)
        self._ast_var = tk.BooleanVar(value=True)

        chk = ttk.Frame(lf3)
        chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        items = [
            ("天の川",      self._mw_var),
            ("星座線",      self._cl_var),
            ("星座名",      self._cn_var),
            ("恒星名",      self._sn_var),
            ("惑星名",      self._pn_var),
            ("季節の大図形", self._ast_var),
        ]
        for idx, (lbl, var) in enumerate(items):
            ttk.Checkbutton(chk, text=lbl, variable=var).grid(
                row=idx // 2, column=idx % 2, sticky="w", padx=(0, 12), pady=1)

        lf3.columnconfigure(1, weight=1)

        # ── Section: 出力 ─────────────────────────────────────────────────────
        lf4 = ttk.LabelFrame(sf, text="出力", padding=P)
        lf4.pack(fill=tk.X, padx=P, pady=2)

        # File name — empty = auto-generate
        ttk.Label(lf4, text="ファイル名:").grid(row=0, column=0, sticky="w")
        self._out_var = tk.StringVar(value="")
        out_ent = ttk.Entry(lf4, textvariable=self._out_var, width=16,
                            foreground="#aaaaaa")
        out_ent.grid(row=0, column=1, sticky="we", padx=(4, 0))
        ttk.Button(lf4, text="…", width=3,
                   command=self._browse_output).grid(row=0, column=2, padx=(4, 0))
        # Placeholder behaviour: grey hint when empty
        def _out_focus_in(_):
            if self._out_var.get() == "":
                out_ent.config(foreground=out_ent.cget("foreground"))
        def _out_changed(*_):
            out_ent.config(foreground="#aaaaaa" if not self._out_var.get() else "")
        out_ent.bind("<FocusIn>", _out_focus_in)
        self._out_var.trace_add("write", _out_changed)
        ttk.Label(lf4, text="空欄で自動生成", foreground="#888888",
                  font=("", 8)).grid(row=0, column=3, sticky="w", padx=(4, 0))

        # Format — PNG / JPG
        ttk.Label(lf4, text="形式:").grid(row=1, column=0, sticky="w", pady=2)
        self._fmt_var = tk.StringVar(value="PNG")
        fmt_f = ttk.Frame(lf4)
        fmt_f.grid(row=1, column=1, columnspan=2, sticky="w", padx=(4, 0))
        ttk.Radiobutton(fmt_f, text="PNG", variable=self._fmt_var, value="PNG").pack(side=tk.LEFT)
        ttk.Radiobutton(fmt_f, text="JPG", variable=self._fmt_var, value="JPG").pack(side=tk.LEFT, padx=(10, 0))

        # DPI
        ttk.Label(lf4, text="DPI:").grid(row=2, column=0, sticky="w", pady=2)
        self._dpi_var = tk.StringVar(value="150")
        ttk.Combobox(lf4, textvariable=self._dpi_var,
                     values=["72", "96", "150", "200", "300"],
                     width=6).grid(row=2, column=1, sticky="w", padx=(4, 0))

        lf4.columnconfigure(1, weight=1)

        # ── Generate button + progress bar ────────────────────────────────────
        btn_frame = ttk.Frame(sf)
        btn_frame.pack(fill=tk.X, padx=P, pady=(8, 2))
        self._gen_btn = ttk.Button(btn_frame, text="★  星図を生成",
                                    command=self._on_generate)
        self._gen_btn.pack(fill=tk.X)

        self._progress = ttk.Progressbar(sf, mode="indeterminate", length=200)
        self._progress.pack(fill=tk.X, padx=P, pady=(2, 2))

        self._status_var = tk.StringVar(value="準備完了")
        ttk.Label(sf, textvariable=self._status_var, foreground="#555555",
                  wraplength=300, justify=tk.LEFT).pack(
            padx=P, pady=(0, P), anchor="w")

        # ── Right: preview ────────────────────────────────────────────────────
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        prev_lf = ttk.LabelFrame(right, text="プレビュー", padding=4)
        prev_lf.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._preview_lbl = ttk.Label(prev_lf,
                                       text="「星図を生成」ボタンを押すと\nここにプレビューが表示されます",
                                       anchor="center", justify="center")
        self._preview_lbl.pack(fill=tk.BOTH, expand=True)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _set_now(self):
        now = datetime.now()
        self._year_var.set(str(now.year))
        self._month_var.set(f"{now.month:02d}")
        self._day_var.set(f"{now.day:02d}")
        self._hour_var.set(f"{now.hour:02d}")
        self._min_var.set(f"{now.minute:02d}")

    def _on_city_changed(self, *_):
        city = self._city_var.get()
        manual = (city == "（手動入力）" or city == "")
        state = "normal" if manual else "readonly"
        self._lat_ent.config(state=state)
        self._lon_ent.config(state=state)

        if not manual and city in self._m.CITIES:
            lat, lon, tz = self._m.CITIES[city]
            self._lat_var.set(str(lat))
            self._lon_var.set(str(lon))
            self._tz_var.set(tz)
            # Auto-fill location name only if it's currently another city name or empty
            cur = self._locname_var.get()
            if not cur or cur in self._m.CITIES:
                self._locname_var.set(city)

    def _browse_output(self):
        is_jpg = self._fmt_var.get() == "JPG"
        ext    = ".jpg" if is_jpg else ".png"
        ftypes = ([("JPEG 画像", "*.jpg *.jpeg"), ("すべてのファイル", "*.*")]
                  if is_jpg else
                  [("PNG 画像", "*.png"), ("すべてのファイル", "*.*")])
        cur = self._out_var.get().strip()
        init = Path(cur).stem if cur else "starchart"
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=ftypes,
            initialfile=init + ext,
        )
        if path:
            self._out_var.set(path)

    def _resolve_output(self) -> str:
        ext = ".jpg" if self._fmt_var.get() == "JPG" else ".png"
        out = self._out_var.get().strip()
        if out:
            p = Path(out)
            # If the extension doesn't match the selected format, replace it
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                out = str(p.with_suffix(ext))
            return out
        # Auto-generate: starchart_{city}_{YYYYMMDD}_{HHMM}.ext
        city = self._city_var.get()
        loc  = city if city not in ("（手動入力）", "") else "custom"
        dt   = (f"{self._year_var.get()}"
                f"{self._month_var.get().zfill(2)}"
                f"{self._day_var.get().zfill(2)}"
                f"_{self._hour_var.get().zfill(2)}"
                f"{self._min_var.get().zfill(2)}")
        return f"starchart_{loc}_{dt}{ext}"

    # ── Generation ─────────────────────────────────────────────────────────────
    def _on_generate(self):
        if self._generating:
            return
        self._generating = True
        self._gen_btn.config(state="disabled")
        self._progress.start(12)
        self._status_var.set("生成中…")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            args = self._build_args()
            old_stdout = sys.stdout
            sys.stdout = _StdoutCapture(
                lambda msg: self.root.after(0, lambda m=msg: self._status_var.set(m))
            )
            try:
                self._m.generate_chart(args)
            finally:
                sys.stdout = old_stdout
            self.root.after(0, self._done, args.output)
        except Exception as exc:
            self.root.after(0, self._error, str(exc))

    def _build_args(self):
        city = self._city_var.get()
        loc_name = self._locname_var.get().strip()
        if not loc_name and city not in ("（手動入力）", ""):
            loc_name = city

        # Build datetime string from individual spinboxes
        try:
            yr = int(self._year_var.get())
            mo = int(self._month_var.get())
            dy = int(self._day_var.get())
            hr = int(self._hour_var.get())
            mn = int(self._min_var.get())
            dt_raw = f"{yr:04d}-{mo:02d}-{dy:02d}T{hr:02d}:{mn:02d}:00"
        except ValueError:
            dt_raw = ""

        return types.SimpleNamespace(
            city="",                              # already resolved below
            lat=float(self._lat_var.get()),
            lon=float(self._lon_var.get()),
            elevation=float(self._elev_var.get() or "0"),
            location_name=loc_name,
            datetime=dt_raw,
            timezone=self._tz_var.get(),
            lang=self._lang_var.get(),
            direction=_DIR_VALUES.get(self._dir_var.get(), ""),
            min_mag=float(self._mag_var.get()),
            no_milky_way=not self._mw_var.get(),
            no_constellation_lines=not self._cl_var.get(),
            no_constellation_names=not self._cn_var.get(),
            no_star_names=not self._sn_var.get(),
            no_planet_names=not self._pn_var.get(),
            no_asterisms=not self._ast_var.get(),
            output=self._resolve_output(),
            title="",
            dpi=int(self._dpi_var.get()),
            force_refresh=False,
        )

    def _done(self, path: str):
        self._generating = False
        self._gen_btn.config(state="normal")
        self._progress.stop()
        self._status_var.set(f"完了: {path}")
        self._load_preview(path)

    def _error(self, msg: str):
        self._generating = False
        self._gen_btn.config(state="normal")
        self._progress.stop()
        self._status_var.set(f"エラー: {msg}")
        messagebox.showerror("生成エラー", msg)

    def _load_preview(self, path: str):
        try:
            img = tk.PhotoImage(file=path)
            pw = max(self._preview_lbl.winfo_width(),  200)
            ph = max(self._preview_lbl.winfo_height(), 200)
            factor = max(1, max(img.width() // pw, img.height() // ph) + 1)
            if factor > 1:
                img = img.subsample(factor, factor)
            self._preview_ref = img          # prevent GC
            self._preview_lbl.config(image=img, text="")
        except Exception as exc:
            self._status_var.set(f"プレビュー読込エラー: {exc}")


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    try:
        # Use a modern ttk theme if available
        style = ttk.Style()
        for theme in ("vista", "clam", "alt"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
    except Exception:
        pass
    StarChartGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
