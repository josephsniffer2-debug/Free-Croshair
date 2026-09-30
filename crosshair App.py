"""
Crosshair - a click-through crosshair overlay for Windows.

Run:  python crosshair.py
Press F8 any time to show/hide the crosshair.
Your settings are saved automatically when you close the window
(in crosshair_settings.json next to this file).
Works on windowed / borderless games, not exclusive fullscreen.
Images: PNG/GIF work out of the box (transparent PNGs work best).
For JPG/WEBP/BMP, run once:  pip install pillow
"""
import colorsys
import ctypes
import json
import math
import os
import time
import tkinter as tk
from fractions import Fraction
from tkinter import colorchooser, filedialog

TRANS = "#010101"   # this exact color becomes see-through
SIZE = 400          # overlay window is SIZE x SIZE
STYLES = ["Cross", "T-shape", "X", "Cross + Dot", "Dot", "Circle", "Circle + Dot", "Image"]
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crosshair_settings.json")
DEFAULTS = {"style": "Cross", "color": "#00ff66", "arm": 14, "thick": 2, "gap": 5,
            "dot": 2, "opacity": 100, "offx": 0, "offy": 0, "outline": True,
            "image_path": "", "image_size": 100,
            "ui_mode": "Rainbow", "ui_speed": 8, "ui_color": "#7c5cff"}
TABS = ["Shape", "Image & Position", "Interface"]
MODES = ["Rainbow", "Breathing", "Static"]
BG, FG, DIM, BTN, TRACK = "#0e1018", "#f2f4ff", "#7d849c", "#1c2030", "#2a3048"
user32 = ctypes.windll.user32


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE) as f:
            s.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except Exception:
        pass
    return s


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

    def load_image(self, path, pct):
        """Loads and scales an image. Uses Pillow if installed (any format), else PNG/GIF only."""
        try:
            from PIL import Image, ImageTk
            if path not in self.cache:
                self.cache[path] = Image.open(path).convert("RGBA")
            im = self.cache[path]
            k = min(pct / 100, SIZE / im.width, SIZE / im.height)
            im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except ImportError:
            if path not in self.cache:
                self.cache[path] = tk.PhotoImage(file=path)   # PNG / GIF only
            im = self.cache[path]
            k = min(pct / 100, SIZE / im.width(), SIZE / im.height())
            f = Fraction(k).limit_denominator(8)
            num, den = max(1, f.numerator), max(1, f.denominator)
            return im.zoom(num, num).subsample(den, den)

    def draw_image(self, s):
        path = s["image_path"]
        if not path:
            self.error = "No image chosen yet."
            return
        try:
            self.img = self.load_image(path, s["image_size"])   # keep a reference or it vanishes
            self.cv.create_image(SIZE // 2, SIZE // 2, image=self.img)
        except Exception:
            self.cache.pop(path, None)
            self.error = "Couldn't load that image. Without Pillow only PNG/GIF work."

    def draw(self, s):
        cv, c = self.cv, SIZE // 2
        cv.delete("all")
        self.error = ""
        if s["style"] == "Image":
            self.draw_image(s)
            return
        style, col, arm, t, gap, out = s["style"], s["color"], s["arm"], s["thick"], s["gap"], s["outline"]
        h = t / 2

        def rect(x1, y1, x2, y2):
            if out:
                cv.create_rectangle(x1 - 1, y1 - 1, x2 + 1, y2 + 1, fill="black", outline="black")
            cv.create_rectangle(x1, y1, x2, y2, fill=col, outline=col)

        if style in ("Cross", "T-shape", "Cross + Dot"):
            rect(c - gap - arm, c - h, c - gap, c + h)           # left
            rect(c + gap, c - h, c + gap + arm, c + h)           # right
            if style != "T-shape":
                rect(c - h, c - gap - arm, c + h, c - gap)       # top
            rect(c - h, c + gap, c + h, c + gap + arm)           # bottom
        if style == "X":
            k = math.sqrt(0.5)
            for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                p = (c + dx * gap * k, c + dy * gap * k, c + dx * (gap + arm) * k, c + dy * (gap + arm) * k)
                if out:
                    cv.create_line(*p, fill="black", width=t + 2)
                cv.create_line(*p, fill=col, width=t)
        if style in ("Circle", "Circle + Dot"):
            r = gap + arm / 2
            if out:
                cv.create_oval(c - r, c - r, c + r, c + r, outline="black", width=t + 2)
            cv.create_oval(c - r, c - r, c + r, c + r, outline=col, width=t)
        if style in ("Dot", "Cross + Dot", "Circle + Dot"):
            r = s["dot"]
            if out:
                cv.create_oval(c - r - 1, c - r - 1, c + r + 1, c + r + 1, fill="black", outline="black")
            cv.create_oval(c - r, c - r, c + r, c + r, fill=col, outline=col)


class Slider(tk.Canvas):
    """A custom slider that can glow in the UI accent color."""
    def __init__(self, parent, lo, hi, val, command, width=200):
        super().__init__(parent, width=width, height=24, bg=BG, highlightthickness=0, cursor="hand2")
        self.lo, self.hi, self.val, self.command, self.w = lo, hi, val, command, width
        self.end = width - 44
        self.accent = "#7c5cff"
        self.bind("<Button-1>", self.on_mouse)
        self.bind("<B1-Motion>", self.on_mouse)
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
        self.draw()

    def draw(self):
        self.delete("all")
        f = (self.val - self.lo) / (self.hi - self.lo)
        x = 8 + f * (self.end - 8)
        self.create_line(8, 12, self.end, 12, fill=TRACK, width=5, capstyle="round")
        self.create_line(8, 12, x, 12, fill=self.accent, width=5, capstyle="round")
        self.create_oval(x - 8, 4, x + 8, 20, fill=self.accent, outline=BG, width=2)
        self.create_text(self.w, 12, text=str(self.val), fill=FG, anchor="e", font=("Segoe UI", 9, "bold"))


def hex_to_rgb(c):
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def shade(c, k):
    r, g, b = hex_to_rgb(c)
    return rgb_to_hex(r * k, g * k, b * k)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Crosshair")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        s = load_settings()
        self.color, self.image_path, self.ui_color = s["color"], s["image_path"], s["ui_color"]
        self.ready, self.visible, self.f8_was_down = False, True, False
        self.t0 = time.time()
        self.style_var = tk.StringVar(value=s["style"])
        self.outline_var = tk.BooleanVar(value=s["outline"])
        self.mode_var = tk.StringVar(value=s["ui_mode"])
        self.overlay = Overlay(self)
        self.sliders, self.accent_btns = {}, []
        self.tab_frames, self.tab_labels, self.tab_lines = {}, {}, {}

        # animated RGB window border
        self.border = tk.Frame(self, bg="#7c5cff", padx=3, pady=3)
        self.border.pack()
        body = tk.Frame(self.border, bg=BG, padx=18, pady=14)
        body.pack()

        # header with flowing RGB bar
        self.header = tk.Canvas(body, width=340, height=54, bg=BG, highlightthickness=0)
        self.header.pack()
        self.header.create_text(0, 18, anchor="w", text="CROSSHAIR", fill=FG, font=("Segoe UI", 20, "bold"))
        self.header.create_text(340, 22, anchor="e", text="F8 = show / hide", fill=DIM, font=("Segoe UI", 8))
        self.bar = [self.header.create_rectangle(i * 6, 46, i * 6 + 7, 50, width=0, fill=BG) for i in range(57)]

        # tabs
        tabbar = tk.Frame(body, bg=BG)
        tabbar.pack(fill="x", pady=(8, 6))
        holder = tk.Frame(body, bg=BG, width=340, height=320)
        holder.pack()
        holder.pack_propagate(False)
        for name in TABS:
            cell = tk.Frame(tabbar, bg=BG)
            cell.pack(side="left", padx=(0, 6))
            lbl = tk.Label(cell, text=name, bg=BG, fg=DIM, font=("Segoe UI", 10, "bold"), padx=6, pady=3,
                           cursor="hand2")
            lbl.pack()
            lbl.bind("<Button-1>", lambda e, n=name: self.show_tab(n))
            line = tk.Frame(cell, bg=BG, height=2)
            line.pack(fill="x")
            self.tab_labels[name], self.tab_lines[name] = lbl, line
            self.tab_frames[name] = tk.Frame(holder, bg=BG)

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
        self.color_btn.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        tk.Checkbutton(t, text="Black outline", variable=self.outline_var, command=self.redraw, bg=BG, fg=FG,
                       selectcolor=BTN, activebackground=BG, activeforeground=FG, font=("Segoe UI", 9)
                       ).grid(row=6, column=0, columnspan=2, sticky="w")

        # --- Image & Position tab ---
        t = self.tab_frames["Image & Position"]
        b = self.button(t, "Choose image...", self.choose_image, accent=True)
        b.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 2))
        self.img_lbl = tk.Label(t, text="", bg=BG, fg=DIM, font=("Segoe UI", 8), wraplength=320)
        self.img_lbl.grid(row=1, column=0, columnspan=2, pady=(0, 6))
        self.add_slider(t, 2, "Image size %", "image_size", 10, 300, s["image_size"])
        self.add_slider(t, 3, "Opacity %", "opacity", 20, 100, s["opacity"])
        self.add_slider(t, 4, "Left / right", "offx", -300, 300, s["offx"])
        self.add_slider(t, 5, "Up / down", "offy", -300, 300, s["offy"])

        # --- Interface tab (RGB settings for this window only) ---
        t = self.tab_frames["Interface"]
        self.label(t, 0, "RGB mode")
        self.menu(t, 0, self.mode_var, MODES, lambda: None)
        self.add_slider(t, 1, "RGB speed", "ui_speed", 1, 30, s["ui_speed"])
        b = self.button(t, "Pick interface color", self.pick_ui_color)
        b.config(bg=self.ui_color, fg="black")
        b.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        self.ui_color_btn = b
        tk.Label(t, text="Rainbow cycles through every color. Breathing and Static use the color\n"
                         "above. These only change this window, never the crosshair.",
                 bg=BG, fg=DIM, font=("Segoe UI", 8), justify="left").grid(row=3, column=0, columnspan=2,
                                                                          sticky="w", pady=(6, 0))

        # bottom buttons
        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill="x", pady=(12, 0))
        self.toggle_btn = self.button(bottom, "Hide crosshair", self.toggle, accent=True)
        self.toggle_btn.pack(side="left", fill="x", expand=True)
        self.button(bottom, "Reset", self.reset).pack(side="left", padx=(8, 0))

        self.show_tab("Shape")
        self.ready = True
        self.redraw()
        self.tick()
        self.poll_hotkey()
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ---- small UI helpers ----
    def label(self, parent, row, text):
        tk.Label(parent, text=text, bg=BG, fg=FG, font=("Segoe UI", 9), width=12, anchor="w").grid(
            row=row, column=0, sticky="w", pady=4)

    def menu(self, parent, row, var, values, command):
        m = tk.OptionMenu(parent, var, *values, command=lambda _: command())
        m.config(bg=BTN, fg=FG, relief="flat", bd=0, highlightthickness=0, activebackground=TRACK,
                 activeforeground=FG, font=("Segoe UI", 9), width=16)
        m["menu"].config(bg=BTN, fg=FG, activebackground=TRACK, activeforeground=FG)
        m.grid(row=row, column=1, sticky="e", pady=4)

    def button(self, parent, text, command, accent=False):
        b = tk.Button(parent, text=text, command=command, relief="flat", bd=0, bg=BTN, fg=FG,
                      activebackground=TRACK, activeforeground=FG, font=("Segoe UI", 10, "bold"),
                      padx=10, pady=7, cursor="hand2")
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
        self.tab_frames[name].pack(fill="x")
        self.active_tab = name

    # ---- RGB animation (interface only) ----
    def accent(self, t, offset=0.0):
        mode = self.mode_var.get()
        speed = self.sliders["ui_speed"].get()
        if mode == "Rainbow":
            r, g, b = colorsys.hsv_to_rgb((t * speed * 0.02 + offset) % 1, 0.65, 1.0)
            return rgb_to_hex(r * 255, g * 255, b * 255)
        if mode == "Breathing":
            k = 0.5 + 0.5 * (math.sin(t * speed * 0.25) + 1) / 2
            return shade(self.ui_color, k * (1 - offset * 0.6))
        return shade(self.ui_color, 1 - offset * 0.6)

    def tick(self):
        t = time.time() - self.t0
        acc = self.accent(t)
        self.border.config(bg=acc)
        for i, item in enumerate(self.bar):
            self.header.itemconfig(item, fill=self.accent(t, i / 57 * 0.6))
        for b in self.accent_btns:
            b.config(fg=acc)
        for w in self.sliders.values():
            if w.winfo_ismapped():
                w.set_accent(acc)
        for n in TABS:
            on = n == self.active_tab
            self.tab_labels[n].config(fg=FG if on else DIM)
            self.tab_lines[n].config(bg=acc if on else BG)
        self.after(40, self.tick)

    # ---- crosshair logic ----
    def settings(self):
        s = {k: w.get() for k, w in self.sliders.items()}
        s.update(style=self.style_var.get(), color=self.color, outline=self.outline_var.get(),
                 image_path=self.image_path, ui_mode=self.mode_var.get(), ui_color=self.ui_color)
        return s

    def redraw(self):
        if not self.ready:
            return
        s = self.settings()
        self.overlay.place_at(s["offx"], s["offy"])
        self.overlay.attributes("-alpha", s["opacity"] / 100)
        self.overlay.draw(s)
        if s["style"] == "Image":
            self.img_lbl.config(text=self.overlay.error or os.path.basename(self.image_path))
        else:
            self.img_lbl.config(text="")

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

    def choose_image(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose a crosshair image",
            filetypes=[("Images", "*.png *.gif *.jpg *.jpeg *.bmp *.webp"), ("All files", "*.*")])
        if path:
            self.image_path = path
            self.style_var.set("Image")
            self.redraw()

    def reset(self):
        for k, w in self.sliders.items():
            if not k.startswith("ui_"):
                w.set(DEFAULTS[k])
        self.style_var.set(DEFAULTS["style"])
        self.outline_var.set(DEFAULTS["outline"])
        self.color = DEFAULTS["color"]
        self.image_path = ""
        self.color_btn.config(bg=self.color)
        self.redraw()

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.overlay.deiconify()
            self.overlay.make_click_through()
        else:
            self.overlay.withdraw()
        self.toggle_btn.config(text="Hide crosshair" if self.visible else "Show crosshair")

    def poll_hotkey(self):
        down = bool(user32.GetAsyncKeyState(0x77) & 0x8000)   # F8
        if down and not self.f8_was_down:
            self.toggle()
        self.f8_was_down = down
        self.after(40, self.poll_hotkey)

    def close(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings(), f, indent=2)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
