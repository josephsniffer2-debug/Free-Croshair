"""
Crosshair - a click-through crosshair overlay for Windows.

Run:  python <this file>
Press your hotkey (F8 by default) to show/hide the crosshair.
Settings are saved automatically when you close the window.
Works on windowed / borderless games, not exclusive fullscreen.
"""
import colorsys
import ctypes
import json
import math
import os
import re
import time
import tkinter as tk
import webbrowser
from fractions import Fraction
from tkinter import colorchooser, filedialog, messagebox
from tkinter import font as tkfont

# >>> Put your own Patreon page link here <<<
PATREON_URL = "https://www.patreon.com/cw/JonDear"

TRANS = "#010101"   # this exact color becomes see-through
SIZE = 400          # overlay window is SIZE x SIZE
W = 500             # width of the control window's content
HOLDER_H = 340      # height of the tab area
HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "crosshair_settings.json")
PROFILES_FILE = os.path.join(HERE, "crosshair_profiles.json")
HOTKEYS = ["F%d" % i for i in range(1, 13) if i != 11]   # F11 = full screen

STYLES = ["Cross", "Cross + Dot", "Dot", "Circle"]
TABS = ["Shape", "Position", "Interface"]
POS_TAB = "Position"
MODES = ["Static"]
TITLE = "Crosshair"
EDITION_NAME = "FREE EDITION"

DEFAULTS = {"style": "Cross", "color": "#00ff66", "arm": 14, "thick": 2, "gap": 5,
            "dot": 2, "opacity": 100, "offx": 0, "offy": 0, "outline": True,
            "image_path": "", "image_size": 100, "outline_w": 1, "rgb_cross": False,
            "rgb_speed": 8, "hotkey": "F8",
            "ui_mode": "Rainbow", "ui_speed": 8, "ui_color": "#7c5cff"}
BG, PANEL, FG, DIM, BTN, TRACK = "#090b12", "#121624", "#f2f4ff", "#7d849c", "#1d2236", "#2a3048"
user32 = ctypes.windll.user32


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE) as f:
            s.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except Exception:
        pass
    return s




def hex_to_rgb(c):
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def shade(c, k):
    r, g, b = hex_to_rgb(c)
    return rgb_to_hex(r * k, g * k, b * k)


class Overlay(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", TRANS)
        self.configure(bg=TRANS)
        self.cv = tk.Canvas(self, width=SIZE, height=SIZE, bg=TRANS, highlightthickness=0)
        self.cv.pack()
        self.img = None
        self.cache = {}
        self.error = ""
        self.place_at(0, 0)
        self.update_idletasks()
        self.make_click_through()

    def make_click_through(self):
        hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
        style = user32.GetWindowLongW(hwnd, -20)
        # layered + click-through + tool window (no taskbar button)
        user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x80)

    def place_at(self, offx, offy):
        x = (self.winfo_screenwidth() - SIZE) // 2 + offx
        y = (self.winfo_screenheight() - SIZE) // 2 + offy
        self.geometry(f"{SIZE}x{SIZE}+{x}+{y}")


    def draw(self, s):
        cv, c = self.cv, SIZE // 2
        cv.delete("all")
        self.error = ""
        style, col, arm, t, gap, out = s["style"], s["color"], s["arm"], s["thick"], s["gap"], s["outline"]
        ow = s.get("outline_w", 1)
        h = t / 2

        def rect(x1, y1, x2, y2):
            if out:
                cv.create_rectangle(x1 - ow, y1 - ow, x2 + ow, y2 + ow, fill="black", outline="black")
            cv.create_rectangle(x1, y1, x2, y2, fill=col, outline=col)

        if style in ("Cross", "T-shape", "Cross + Dot"):
            rect(c - gap - arm, c - h, c - gap, c + h)           # left
            rect(c + gap, c - h, c + gap + arm, c + h)           # right
            if style != "T-shape":
                rect(c - h, c - gap - arm, c + h, c - gap)       # top
            rect(c - h, c + gap, c + h, c + gap + arm)           # bottom
        if style in ("Circle", "Circle + Dot"):
            r = gap + arm / 2
            if out:
                cv.create_oval(c - r, c - r, c + r, c + r, outline="black", width=t + 2 * ow)
            cv.create_oval(c - r, c - r, c + r, c + r, outline=col, width=t)
        if style in ("Dot", "Cross + Dot", "Circle + Dot"):
            r = s["dot"]
            if out:
                cv.create_oval(c - r - ow, c - r - ow, c + r + ow, c + r + ow, fill="black", outline="black")
            cv.create_oval(c - r, c - r, c + r, c + r, fill=col, outline=col)


class Slider(tk.Canvas):
    """A custom slider with a glowing accent color and a hover effect."""
    def __init__(self, parent, lo, hi, val, command, width=300):
        super().__init__(parent, width=width, height=28, bg=parent["bg"], highlightthickness=0,
                         cursor="hand2")
        self.lo, self.hi, self.val, self.command, self.w = lo, hi, val, command, width
        self.end = width - 46
        self.bgc = parent["bg"]
        self.accent = "#7c5cff"
        self.hov, self.tgt = 0.0, 0.0
        self.bind("<Button-1>", self.on_mouse)
        self.bind("<B1-Motion>", self.on_mouse)
        self.bind("<Enter>", lambda e: setattr(self, "tgt", 1.0))
        self.bind("<Leave>", lambda e: setattr(self, "tgt", 0.0))
        self.draw()

    def get(self):
        return self.val

    def set(self, v):
        self.val = max(self.lo, min(self.hi, int(round(v))))
        self.draw()

    def on_mouse(self, e):
        f = max(0, min(1, (e.x - 8) / (self.end - 8)))
        self.set(self.lo + f * (self.hi - self.lo))
        self.command()

    def set_accent(self, color):
        self.accent = color
        self.hov += (self.tgt - self.hov) * 0.3      # smooth hover
        self.draw()

    def draw(self):
        self.delete("all")
        f = (self.val - self.lo) / (self.hi - self.lo)
        x = 8 + f * (self.end - 8)
        col = shade(self.accent, 1 - 0.35 * self.hov)   # gets darker on hover
        r = 8 + 2 * self.hov
        self.create_line(8, 14, self.end, 14, fill=TRACK, width=5, capstyle="round")
        self.create_line(8, 14, x, 14, fill=col, width=5, capstyle="round")
        self.create_oval(x - r, 14 - r, x + r, 14 + r, fill=col, outline=self.bgc, width=2)
        self.create_text(self.w, 14, text=str(self.val), fill=FG, anchor="e", font=("Segoe UI", 10, "bold"))


class RoundButton(tk.Canvas):
    """A button with rounded corners that smoothly darkens when the mouse is over it."""
    def __init__(self, parent, text, command, width=100, height=40, bg=BTN, fg=FG,
                 font=("Segoe UI", 10, "bold")):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0,
                         cursor="hand2")
        self.text, self.command, self.base, self.fg, self.font = text, command, bg, fg, font
        self.hov, self.tgt = 0.0, 0.0
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: setattr(self, "tgt", 1.0))
        self.bind("<Leave>", lambda e: setattr(self, "tgt", 0.0))
        self.bind("<ButtonRelease-1>", self.on_release)
        self.draw()

    def config(self, **kw):
        """Accepts bg / fg / text / font like a normal button, then redraws."""
        if "bg" in kw:
            self.base = kw.pop("bg")
        if "fg" in kw:
            self.fg = kw.pop("fg")
        if "text" in kw:
            self.text = kw.pop("text")
        if "font" in kw:
            self.font = kw.pop("font")
        if kw:
            super().config(**kw)
        self.draw()

    def on_release(self, e):
        if self.command and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.command()

    def step(self):
        if abs(self.tgt - self.hov) > 0.01:
            self.hov += (self.tgt - self.hov) * 0.3
            if abs(self.tgt - self.hov) <= 0.01:
                self.hov = self.tgt
            self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(float(self.cget("width"))), int(float(self.cget("height")))
        r = min(14, h // 2)
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
               x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
        col = shade(self.base, 1 - 0.4 * self.hov)       # darker on hover
        self.create_polygon(pts, smooth=True, fill=col, outline=col)
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg, font=self.font, justify="center")


class TabBar(tk.Canvas):
    """Tabs with a smoothly sliding underline and hover fade."""
    def __init__(self, parent, names, command, width):
        super().__init__(parent, width=width, height=40, bg=BG, highlightthickness=0, cursor="hand2")
        self.names, self.command, self.active, self.width = names, command, names[0], width
        self.font = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.pos, x = {}, 4
        for n in names:
            w = self.font.measure(n)
            self.pos[n] = (x, w)
            x += w + 30
        self.h = {n: 0.0 for n in names}
        self.hover = None
        self.ux, self.uw = self.pos[names[0]][0], self.pos[names[0]][1]
        self.bind("<Motion>", lambda e: setattr(self, "hover", self.which(e.x)))
        self.bind("<Leave>", lambda e: setattr(self, "hover", None))
        self.bind("<Button-1>", self.on_click)

    def which(self, x):
        for n, (px, w) in self.pos.items():
            if px - 12 <= x <= px + w + 12:
                return n
        return None

    def on_click(self, e):
        n = self.which(e.x)
        if n:
            self.command(n)

    def frame(self, accent):
        self.delete("all")
        tx, tw = self.pos[self.active]
        self.ux += (tx - self.ux) * 0.25      # underline glides to the active tab
        self.uw += (tw - self.uw) * 0.25
        self.create_line(0, 37, self.width, 37, fill=TRACK)
        for n, (px, w) in self.pos.items():
            self.h[n] += ((1.0 if n == self.hover else 0.0) - self.h[n]) * 0.25
            base = FG if n == self.active else DIM
            self.create_text(px, 16, text=n, anchor="w", fill=shade(base, 1 - 0.4 * self.h[n]), font=self.font)
        self.create_rectangle(self.ux, 34, self.ux + self.uw, 38, fill=accent, width=0)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)       # fades in when opened
        self.fade = 0.0

        s = load_settings()
        self.color, self.image_path, self.ui_color = s["color"], s["image_path"], s["ui_color"]
        self.live_color = None
        self.hotkey = "F8"
        self.ready, self.visible, self.key_was_down = False, True, False
        self.t0 = time.time()
        self.style_var = tk.StringVar(value=s["style"] if s["style"] in STYLES else STYLES[0])
        self.outline_var = tk.BooleanVar(value=s["outline"])
        self.mode_var = tk.StringVar(value=s["ui_mode"] if s["ui_mode"] in MODES else MODES[0])
        self.overlay = Overlay(self)
        self.sliders, self.accent_btns, self.round_btns, self.tab_frames = {}, [], [], {}
        self.fullscreen = False

        # animated RGB window border
        self.border = tk.Frame(self, bg="#7c5cff", padx=3, pady=3)
        self.border.pack(expand=True)      # stays centered in full screen
        body = tk.Frame(self.border, bg=BG, padx=22, pady=16)
        body.pack()

        # header with flowing RGB bar
        self.header = tk.Canvas(body, width=W, height=66, bg=BG, highlightthickness=0)
        self.header.pack()
        self.header.create_text(0, 24, anchor="w", text="CROSSHAIR", fill=FG, font=("Segoe UI", 26, "bold"))
        self.header.create_text(W, 30, anchor="e", text=EDITION_NAME, fill=DIM, font=("Segoe UI", 9, "bold"))
        self.bar = [self.header.create_rectangle(i * 10, 56, i * 10 + 11, 61, width=0, fill=BG)
                    for i in range(50)]

        self.tabs = TabBar(body, TABS, self.show_tab, W)
        self.tabs.pack(pady=(10, 0))
        holder = tk.Frame(body, bg=PANEL, width=W, height=HOLDER_H)
        holder.pack()
        holder.pack_propagate(False)
        for name in TABS:
            self.tab_frames[name] = tk.Frame(holder, bg=PANEL, padx=22, pady=16)

        # --- Shape tab ---
        t = self.tab_frames["Shape"]
        self.label(t, 0, "Style")
        self.menu(t, 0, self.style_var, STYLES, self.redraw)
        self.add_slider(t, 1, "Length", "arm", 2, 100, s["arm"])
        self.add_slider(t, 2, "Thickness", "thick", 1, 12, s["thick"])
        self.add_slider(t, 3, "Center gap", "gap", 0, 40, s["gap"])
        self.add_slider(t, 4, "Dot size", "dot", 1, 12, s["dot"])
        self.color_btn = self.button(t, "Pick crosshair color", self.pick_color)
        self.color_btn.config(bg=self.color, fg="black")
        self.color_btn.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 6))
        tk.Checkbutton(t, text="Black outline", variable=self.outline_var, command=self.redraw, bg=PANEL,
                       fg=FG, selectcolor=BTN, activebackground=PANEL, activeforeground=FG,
                       font=("Segoe UI", 10)).grid(row=6, column=0, columnspan=2, sticky="w")

        # --- Position tab (Image & Position in Patreon/Owner) ---
        t = self.tab_frames[POS_TAB]
        self.add_slider(t, 3, "Opacity %", "opacity", 20, 100, s["opacity"])
        self.add_slider(t, 4, "Left / right", "offx", -300, 300, s["offx"])
        self.add_slider(t, 5, "Up / down", "offy", -300, 300, s["offy"])

        # --- Interface tab (RGB settings for this window only) ---
        t = self.tab_frames["Interface"]
        self.ui_color_btn = self.button(t, "Pick interface color", self.pick_ui_color)
        self.ui_color_btn.config(bg=self.ui_color, fg="black")
        self.ui_color_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 6))
        tk.Label(t, text="Rainbow and Breathing RGB are in the Patreon version.",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 9), justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))


        # bottom buttons
        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill="x", pady=(14, 0))
        self.toggle_btn = self.button(bottom, "Hide crosshair", self.toggle, accent=True)
        self.toggle_btn.pack(side="left", fill="x", expand=True)
        self.full_btn = self.button(bottom, "Full screen", self.toggle_full, width=120)
        self.full_btn.pack(side="left", padx=(8, 0))
        self.button(bottom, "Reset", self.reset, width=90).pack(side="left", padx=(8, 0))
        self.bind("<F11>", lambda e: self.toggle_full())
        self.bind("<Escape>", lambda e: self.toggle_full() if self.fullscreen else None)
        self.hint = tk.Label(body, text="", bg=BG, fg=DIM, font=("Segoe UI", 9))
        self.hint.pack(pady=(8, 0))
        self.update_hint()

        pat = self.button(body, "GET THE PATREON VERSION\nImages, more styles & RGB interface - free to join",
                          self.open_patreon, accent=True, height=56)
        pat.config(font=("Segoe UI", 9, "bold"))
        pat.pack(fill="x", pady=(10, 0))

        self.show_tab("Shape")
        self.ready = True
        self.redraw()
        self.tick()
        self.poll_hotkey()
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ---- small UI helpers ----
    def label(self, parent, row, text):
        tk.Label(parent, text=text, bg=PANEL, fg=FG, font=("Segoe UI", 10), width=13, anchor="w").grid(
            row=row, column=0, sticky="w", pady=5)

    def menu(self, parent, row, var, values, command):
        """A rounded dropdown: click it to pick from a list."""
        b = RoundButton(parent, "", None, width=230, height=36)
        pop = tk.Menu(self, tearoff=0, bg=BTN, fg=FG, activebackground=TRACK, activeforeground=FG, bd=0,
                      font=("Segoe UI", 10))
        for v in values:
            pop.add_command(label=v, command=lambda v=v: (var.set(v), command()))

        def show():
            try:
                pop.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 2)
            finally:
                pop.grab_release()

        b.command = show
        var.trace_add("write", lambda *a: b.config(text=f"{var.get()}   \u25be"))
        b.config(text=f"{var.get()}   \u25be")
        b.grid(row=row, column=1, sticky="e", pady=4)
        self.round_btns.append(b)

    def button(self, parent, text, command, accent=False, width=100, height=40):
        b = RoundButton(parent, text, command, width=width, height=height)
        self.round_btns.append(b)
        if accent:
            self.accent_btns.append(b)
        return b

    def add_slider(self, parent, row, label, key, lo, hi, val):
        self.label(parent, row, label)
        w = Slider(parent, lo, hi, val, self.redraw)
        w.grid(row=row, column=1, sticky="e", pady=2)
        self.sliders[key] = w

    def show_tab(self, name):
        for f in self.tab_frames.values():
            f.pack_forget()
        self.tab_frames[name].pack(fill="both", expand=True)
        self.tabs.active = name

    def update_hint(self):
        self.hint.config(text=f"{self.hotkey} = show / hide crosshair    |    F11 = full screen")

    # ---- RGB animation (interface only) ----
    def accent(self, t, offset=0.0):
        return shade(self.ui_color, 1 - offset * 0.6)

    def tick(self):
        t = time.time() - self.t0
        if self.fade < 1:
            self.fade = min(1.0, self.fade + 0.07)
            self.attributes("-alpha", self.fade)
        acc = self.accent(t)
        self.border.config(bg=acc)
        for i, item in enumerate(self.bar):
            self.header.itemconfig(item, fill=self.accent(t, i / 50 * 0.6))
        for b in self.accent_btns:
            b.config(fg=acc)
        for w in self.sliders.values():
            if w.winfo_ismapped():
                w.set_accent(acc)
        self.tabs.frame(acc)
        for b in self.round_btns:                  # smooth darken on hover
            b.step()
        self.after(25, self.tick)

    # ---- crosshair logic ----
    def settings(self, save=False):
        s = {k: w.get() for k, w in self.sliders.items()}
        color = self.color if (save or self.live_color is None) else self.live_color
        s.update(style=self.style_var.get(), color=color, outline=self.outline_var.get(),
                 image_path=self.image_path, ui_mode=self.mode_var.get(), ui_color=self.ui_color)
        return s

    def apply_settings(self, d):
        for k, w in self.sliders.items():
            if k.startswith("ui_") or k not in d:
                continue
            try:
                w.set(float(d[k]))
            except (TypeError, ValueError):
                pass
        if d.get("style") in STYLES:
            self.style_var.set(d["style"])
        if "outline" in d:
            self.outline_var.set(bool(d["outline"]))
        if isinstance(d.get("color"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", d["color"]):
            self.color = d["color"]
            self.color_btn.config(bg=self.color)
        if isinstance(d.get("image_path"), str):
            self.image_path = d["image_path"]
        self.redraw()

    def redraw(self):
        if not self.ready:
            return
        s = self.settings()
        self.overlay.place_at(s["offx"], s["offy"])
        self.overlay.attributes("-alpha", s["opacity"] / 100)
        self.overlay.draw(s)

    def pick_color(self):
        _, hexcol = colorchooser.askcolor(color=self.color, parent=self)
        if hexcol:
            self.color = hexcol
            self.color_btn.config(bg=hexcol)
            self.redraw()

    def pick_ui_color(self):
        _, hexcol = colorchooser.askcolor(color=self.ui_color, parent=self)
        if hexcol:
            self.ui_color = hexcol
            self.ui_color_btn.config(bg=hexcol)


    def open_patreon(self):
        webbrowser.open(PATREON_URL)


    def reset(self):
        self.apply_settings({k: v for k, v in DEFAULTS.items() if not k.startswith("ui_")})

    def toggle_full(self):
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)
        self.full_btn.config(text="Exit full screen" if self.fullscreen else "Full screen")

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.overlay.deiconify()
            self.overlay.make_click_through()
        else:
            self.overlay.withdraw()
        self.toggle_btn.config(text="Hide crosshair" if self.visible else "Show crosshair")

    def poll_hotkey(self):
        vk = 0x70 + int(self.hotkey[1:]) - 1      # F1 = 0x70
        down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
        if down and not self.key_was_down:
            self.toggle()
        self.key_was_down = down
        self.after(40, self.poll_hotkey)

    def close(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings(save=True), f, indent=2)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
