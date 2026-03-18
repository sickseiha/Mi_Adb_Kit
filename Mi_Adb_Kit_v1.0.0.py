import tkinter as tk
from tkinter import font
import subprocess
import threading
import re
import sys
import time
from queue import Queue, Empty


def resource_path(relative):
    import os
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _adb():
    import os
    path = resource_path(os.path.join("bin", "adb.exe"))
    return path if os.path.isfile(path) else "adb"


class DarkWindow:
    COLORS = {
        "dark": "#0d0d0d",
        "white": "#ffffff",
        "text_light": "#e0e0e0",
        "text_dim": "#aaaaaa",
        "dot_inactive": "#555555",
        "usb_green": "#28a745",
        "wifi_cyan": "#17a2b8",
        "reconnect_yellow": "#e0a800",
        "error_red": "#dc3545",
        "separator": "#2a2a2a"
    }

    INTERFACES = ["wlan0", "wlan1", "rmnet_data0", "eth0"]
    PLATFORM_FLAGS = 0x08000000 if sys.platform.startswith("win") else 0

    def __init__(self, root):
        self.root = root
        self.root.geometry("600x600")
        try:
            self.root.iconbitmap(resource_path("Mi_Adb_Kit_v1.0.0.ico"))
        except Exception:
            pass
        self.root.overrideredirect(True)
        self.root.configure(bg=self.COLORS["white"])
        self.root.resizable(False, False)
        self.offset_x = 0
        self.offset_y = 0
        self.is_dragging = False
        self._setup_state()
        self._setup_ui()
        self._setup_bindings()

    def _setup_state(self):
        self.state_lock = threading.Lock()
        self.adb_mode = None
        self.wifi_serial = None
        self.last_ip = None
        self.tcpip_set = False
        self._setting_up_wifi = False
        self.app_running = True
        self.ui_queue = Queue()
        self._last_fetched_device = None
        self._all_installed = []
        self._all_uninstalled = []
        self._search_after_installed = None
        self._search_after_uninstalled = None

    def _setup_ui(self):
        main_container = tk.Frame(self.root, bg=self.COLORS["white"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        inner_frame = tk.Frame(main_container, bg=self.COLORS["dark"])
        inner_frame.pack(fill=tk.BOTH, expand=True)
        self._create_titlebar(inner_frame)
        self._create_content(inner_frame)

    def _create_titlebar(self, parent):
        self.titlebar = tk.Frame(parent, bg=self.COLORS["dark"], height=25)
        self.titlebar.pack(fill="x")
        tk.Frame(parent, bg=self.COLORS["white"], height=1).pack(fill="x")
        self.title_label = tk.Label(
            self.titlebar, text="",
            bg=self.COLORS["dark"], fg=self.COLORS["white"],
            font=font.Font(family="Segoe UI", size=10), padx=10
        )
        self.title_label.pack(side="left", pady=3)
        button_frame = tk.Frame(self.titlebar, bg=self.COLORS["dark"])
        button_frame.pack(side="right")
        tk.Frame(button_frame, bg=self.COLORS["white"], width=1).pack(side="left", fill="y")
        self.min_btn = tk.Button(
            button_frame, text="−", font=("Segoe UI", 14),
            bg=self.COLORS["dark"], fg=self.COLORS["white"],
            activebackground=self.COLORS["white"], activeforeground="black",
            bd=0, padx=6, pady=0, width=2, height=1,
            cursor="hand2", command=self.minimize_window
        )
        self.min_btn.pack(side="left")
        tk.Frame(button_frame, bg=self.COLORS["white"], width=1).pack(side="left", fill="y")
        self.close_btn = tk.Button(
            button_frame, text="✕", font=("Segoe UI", 14),
            bg=self.COLORS["dark"], fg="#ff6b6b",
            activebackground="#ff6b6b", activeforeground="black",
            bd=0, padx=6, pady=0, width=2, height=1,
            cursor="hand2", command=self.close_window
        )
        self.close_btn.pack(side="left")

    def _create_content(self, parent):
        self.content_frame = tk.Frame(parent, bg=self.COLORS["dark"])
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        info_frame = tk.Frame(self.content_frame, bg=self.COLORS["dark"], height=28)
        info_frame.pack(fill="x")
        info_frame.pack_propagate(False)

        conn_frame = tk.Frame(info_frame, bg=self.COLORS["dark"])
        conn_frame.pack(side="left", fill="y", padx=(4, 0))
        tk.Label(conn_frame, text="Connection", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9)).pack(side="left")
        self.dot = tk.Label(conn_frame, text="●", bg=self.COLORS["dark"],
                            fg=self.COLORS["dot_inactive"], font=("Segoe UI", 12))
        self.dot.pack(side="left", padx=(6, 4))
        self.conn_label = tk.Label(conn_frame, text="Checking...",
                                   bg=self.COLORS["dark"], fg=self.COLORS["text_dim"],
                                   font=("Segoe UI", 9))
        self.conn_label.pack(side="left")

        disp_frame = tk.Frame(info_frame, bg=self.COLORS["dark"])
        disp_frame.pack(side="right", fill="y", padx=(0, 4))
        self.change_btn = tk.Label(disp_frame, text="⚙", bg=self.COLORS["dark"],
                                   fg=self.COLORS["text_dim"], font=("Segoe UI", 11),
                                   cursor="hand2", padx=4)
        self.change_btn.pack(side="right")
        self.change_btn.bind("<Button-1>", lambda e: self._toggle_display_popup())
        self._display_popup = None
        self.dpi_label = tk.Label(disp_frame, text="", bg=self.COLORS["dark"],
                                  fg=self.COLORS["white"], font=("Segoe UI", 9))
        self.dpi_label.pack(side="right", padx=(0, 2))
        tk.Label(disp_frame, text="Dpi", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9)).pack(side="right")
        self.res_label = tk.Label(disp_frame, text="", bg=self.COLORS["dark"],
                                  fg=self.COLORS["white"], font=("Segoe UI", 9))
        self.res_label.pack(side="right", padx=(0, 2))
        tk.Label(disp_frame, text="Resolution", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9)).pack(side="right", padx=(8, 0))

        device_frame = tk.Frame(info_frame, bg=self.COLORS["dark"])
        device_frame.pack(side="left", fill="both", expand=True)
        center = tk.Frame(device_frame, bg=self.COLORS["dark"])
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text="Device", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.device_label = tk.Label(center, text="No device",
                                     bg=self.COLORS["dark"], fg=self.COLORS["white"],
                                     font=("Segoe UI", 9))
        self.device_label.pack(side="left")

        tk.Frame(self.content_frame, bg=self.COLORS["separator"], height=1).pack(fill="x")

        split_frame = tk.Frame(self.content_frame, bg=self.COLORS["dark"])
        split_frame.pack(fill=tk.BOTH, expand=True)
        split_frame.columnconfigure(0, weight=1, uniform="half")
        split_frame.columnconfigure(2, weight=1, uniform="half")
        split_frame.rowconfigure(0, weight=1)

        left_panel = tk.Frame(split_frame, bg=self.COLORS["dark"])
        left_panel.grid(row=0, column=0, sticky="nsew")
        tk.Label(left_panel, text="INSTALLED", bg=self.COLORS["dark"],
                 fg=self.COLORS["white"],
                 font=font.Font(family="Segoe UI", size=9, weight="bold")).pack(pady=(4, 4))
        tk.Frame(left_panel, bg=self.COLORS["separator"], height=1).pack(fill="x")

        sf_l = tk.Frame(left_panel, bg="#1a1a1a", highlightthickness=1,
                        highlightbackground=self.COLORS["separator"])
        sf_l.pack(fill="x", padx=10, pady=(4, 4))
        tk.Label(sf_l, text="⌕", bg="#1a1a1a", fg=self.COLORS["text_dim"],
                 font=("Segoe UI", 11)).pack(side="left", padx=(4, 2))
        self._sv_installed = tk.StringVar()
        self.search_installed = tk.Entry(sf_l, textvariable=self._sv_installed,
                                         bg="#1a1a1a", fg=self.COLORS["text_light"],
                                         insertbackground=self.COLORS["white"],
                                         relief="flat", bd=0, font=("Segoe UI", 9),
                                         highlightthickness=0)
        self.search_installed.pack(side="left", fill="x", expand=True, ipady=4)
        self._clear_btn_installed = tk.Label(sf_l, text="×", bg="#1a1a1a",
                                             fg=self.COLORS["text_dim"],
                                             font=("Segoe UI", 11), cursor="hand2", padx=4)
        self._clear_btn_installed.bind("<Button-1>", lambda e: self._sv_installed.set(""))

        def _trace_installed(*_):
            if self._sv_installed.get():
                self._clear_btn_installed.pack(side="right", padx=(0, 2))
            else:
                self._clear_btn_installed.pack_forget()
            self._on_search_installed()
        self._sv_installed.trace_add("write", _trace_installed)

        self.panel_installed = tk.Frame(left_panel, bg=self.COLORS["dark"])
        self.panel_installed.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.panel_installed, text="No packages", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 10)).pack(expand=True)

        tk.Frame(split_frame, bg=self.COLORS["separator"], width=1).grid(row=0, column=1, sticky="ns")

        right_panel = tk.Frame(split_frame, bg=self.COLORS["dark"])
        right_panel.grid(row=0, column=2, sticky="nsew")
        tk.Label(right_panel, text="UNINSTALLED", bg=self.COLORS["dark"],
                 fg=self.COLORS["white"],
                 font=font.Font(family="Segoe UI", size=9, weight="bold")).pack(pady=(4, 4))
        tk.Frame(right_panel, bg=self.COLORS["separator"], height=1).pack(fill="x")

        sf_r = tk.Frame(right_panel, bg="#1a1a1a", highlightthickness=1,
                        highlightbackground=self.COLORS["separator"])
        sf_r.pack(fill="x", padx=10, pady=(4, 4))
        tk.Label(sf_r, text="⌕", bg="#1a1a1a", fg=self.COLORS["text_dim"],
                 font=("Segoe UI", 11)).pack(side="left", padx=(4, 2))
        self._sv_uninstalled = tk.StringVar()
        self.search_uninstalled = tk.Entry(sf_r, textvariable=self._sv_uninstalled,
                                           bg="#1a1a1a", fg=self.COLORS["text_light"],
                                           insertbackground=self.COLORS["white"],
                                           relief="flat", bd=0, font=("Segoe UI", 9),
                                           highlightthickness=0)
        self.search_uninstalled.pack(side="left", fill="x", expand=True, ipady=4)
        self._clear_btn_uninstalled = tk.Label(sf_r, text="×", bg="#1a1a1a",
                                               fg=self.COLORS["text_dim"],
                                               font=("Segoe UI", 11), cursor="hand2", padx=4)
        self._clear_btn_uninstalled.bind("<Button-1>", lambda e: self._sv_uninstalled.set(""))

        def _trace_uninstalled(*_):
            if self._sv_uninstalled.get():
                self._clear_btn_uninstalled.pack(side="right", padx=(0, 2))
            else:
                self._clear_btn_uninstalled.pack_forget()
            self._on_search_uninstalled()
        self._sv_uninstalled.trace_add("write", _trace_uninstalled)

        self.panel_uninstalled = tk.Frame(right_panel, bg=self.COLORS["dark"])
        self.panel_uninstalled.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.panel_uninstalled, text="No packages", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 10)).pack(expand=True)

    def _setup_bindings(self):
        self.titlebar.bind("<Button-1>", self.start_drag)
        self.titlebar.bind("<B1-Motion>", self.drag_window)
        self.titlebar.bind("<ButtonRelease-1>", self.stop_drag)
        self.root.bind("<Map>", self.on_restore)
        self.root.bind("<FocusOut>", self._on_focus_out)
        self.search_installed.bind("<KeyRelease>", self._on_search_installed)
        self.search_uninstalled.bind("<KeyRelease>", self._on_search_uninstalled)

    def _on_focus_out(self, event):
        self.root.after(100, self._check_focus)

    def _check_focus(self):
        if not self.app_running:
            return
        focused = self.root.focus_get()
        if focused is not None:
            return
        try:
            fw = self.root.tk.call("focus")
            if fw and str(fw).startswith(str(self.root)):
                return
        except Exception:
            pass
        try:
            mx = self.root.winfo_pointerx()
            my = self.root.winfo_pointery()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                self._close_display_popup()
                return
        except Exception:
            pass
        self._close_display_popup()
        self.minimize_window()

    def _on_search_installed(self, event=None):
        if self._search_after_installed:
            self.root.after_cancel(self._search_after_installed)
        self._search_after_installed = self.root.after(300, self._filter_installed)

    def _on_search_uninstalled(self, event=None):
        if self._search_after_uninstalled:
            self.root.after_cancel(self._search_after_uninstalled)
        self._search_after_uninstalled = self.root.after(300, self._filter_uninstalled)

    def _filter_installed(self):
        query = self._sv_installed.get().lower().strip()
        filtered = [p for p in self._all_installed if query in p.lower()] if query else self._all_installed
        self._build_scroll_panel(self.panel_installed, filtered, mode="installed")

    def _filter_uninstalled(self):
        query = self._sv_uninstalled.get().lower().strip()
        filtered = [p for p in self._all_uninstalled if query in p.lower()] if query else self._all_uninstalled
        self._build_scroll_panel(self.panel_uninstalled, filtered, mode="uninstalled")

    def start_drag(self, event):
        self.is_dragging = True
        self.offset_x = event.x_root - self.root.winfo_x()
        self.offset_y = event.y_root - self.root.winfo_y()

    def drag_window(self, event):
        if self.is_dragging:
            self.root.geometry(f"+{event.x_root - self.offset_x}+{event.y_root - self.offset_y}")

    def stop_drag(self, event):
        self.is_dragging = False

    def minimize_window(self):
        self.root._minimized = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def on_restore(self, event):
        if not self.app_running:
            return
        if getattr(self.root, '_minimized', False):
            self.root.after(10, self._reapply_overrideredirect)

    def _reapply_overrideredirect(self):
        if not self.app_running:
            return
        if self.root.state() == "normal":
            self.root._minimized = False
            self.root.overrideredirect(True)
            self.root.lift()
        else:
            self.root.after(50, self._reapply_overrideredirect)

    def _run(self, cmd):
        try:
            return subprocess.check_output(
                cmd,
                creationflags=self.PLATFORM_FLAGS,
                stderr=subprocess.STDOUT,
                timeout=5
            ).decode(errors="ignore")
        except Exception:
            return ""

    def _run_with_device(self, cmd, device=None):
        try:
            full_cmd = [_adb(), "-s", device] + cmd if device else [_adb(), "-d"] + cmd
            return subprocess.check_output(
                full_cmd,
                creationflags=self.PLATFORM_FLAGS,
                stderr=subprocess.STDOUT,
                timeout=5
            ).decode(errors="ignore")
        except Exception:
            return ""

    def _run_s(self, cmd):
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=self.PLATFORM_FLAGS,
                timeout=10
            )
        except Exception:
            pass

    def _get_ip_for(self, serial):
        for iface in self.INTERFACES:
            out = self._run_with_device(["shell", "ip", "addr", "show", iface], serial)
            if out:
                match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out)
                if match:
                    ip = match.group(1)
                    if ip.startswith(("192.", "10.", "172.")):
                        return ip
        return None

    def _get_device_info(self, device=None):
        marketname = (
            self._run_with_device(["shell", "getprop", "ro.product.marketname"], device).strip() or
            self._run_with_device(["shell", "getprop", "ro.product.vendor.marketname"], device).strip()
        )
        if marketname:
            return marketname
        brand = self._run_with_device(["shell", "getprop", "ro.product.brand"], device).strip()
        model = self._run_with_device(["shell", "getprop", "ro.product.model"], device).strip()
        if brand or model:
            return f"{brand or 'Unknown'} {model or 'Unknown'}"
        return None

    def _is_connected(self):
        with self.state_lock:
            return self.adb_mode is not None

    def _get_active_device(self):
        with self.state_lock:
            if self.adb_mode == "usb":
                return None
            if self.adb_mode == "wifi" and self.wifi_serial:
                return self.wifi_serial
        return None

    def _fetch_packages(self, device_key):
        raw_all = self._run_with_device(["shell", "pm", "list", "packages", "-u"], device_key)
        raw_inst = self._run_with_device(["shell", "pm", "list", "packages"], device_key)
        all_pkgs = {l.replace("package:", "").strip() for l in raw_all.splitlines() if l.startswith("package:")}
        inst_pkgs = {l.replace("package:", "").strip() for l in raw_inst.splitlines() if l.startswith("package:")}
        self.ui_queue.put(("installed_list", sorted(inst_pkgs)))
        self.ui_queue.put(("uninstalled_list", sorted(all_pkgs - inst_pkgs)))

    def _build_scroll_panel(self, parent, packages, mode="installed"):
        for w in parent.winfo_children():
            w.destroy()

        if not packages:
            tk.Label(parent, text="No packages", bg=self.COLORS["dark"],
                     fg=self.COLORS["text_dim"], font=("Segoe UI", 10)).pack(expand=True)
            return

        TRACK_W = 6
        THUMB_COLOR = "#444444"
        THUMB_HOVER = "#666666"

        canvas = tk.Canvas(parent, bg=self.COLORS["dark"], highlightthickness=0)
        canvas.pack(side="left", fill=tk.BOTH, expand=True)
        sb = tk.Canvas(parent, bg=self.COLORS["dark"], highlightthickness=0, width=TRACK_W)
        sb.pack(side="right", fill="y")

        list_frame = tk.Frame(canvas, bg=self.COLORS["dark"])
        win_id = canvas.create_window((0, 0), window=list_frame, anchor="nw")

        action = self._do_uninstall if mode == "installed" else self._do_reinstall
        for pkg in packages:
            lbl = tk.Label(list_frame, text=pkg, bg=self.COLORS["dark"],
                           fg=self.COLORS["text_light"], font=("Segoe UI", 10),
                           anchor="w", pady=3, cursor="hand2")
            lbl.pack(fill="x", padx=8)
            lbl.bind("<Enter>", lambda e, l=lbl: l.config(bg="#1e1e1e", fg=self.COLORS["white"]))
            lbl.bind("<Leave>", lambda e, l=lbl: l.config(bg=self.COLORS["dark"], fg=self.COLORS["text_light"]))
            lbl.bind("<Button-1>", lambda e, p=pkg: action(p))

        state = {"drag_y": 0, "drag_top": 0.0}

        def _thumb_geom():
            total = list_frame.winfo_reqheight()
            visible = canvas.winfo_height()
            track = sb.winfo_height()
            if total <= visible or track <= 0:
                return None
            h = max(20, int(track * visible / total))
            y = min(int(canvas.yview()[0] * track), track - h)
            return y, h

        def _draw_thumb(color=THUMB_COLOR):
            sb.delete("thumb")
            geom = _thumb_geom()
            if geom:
                y, h = geom
                sb.create_rectangle(1, y, TRACK_W - 1, y + h, fill=color, outline="", tags="thumb")

        def _sb_press(e):
            geom = _thumb_geom()
            if not geom:
                return
            y, h = geom
            if y <= e.y <= y + h:
                state["drag_y"] = e.y
                state["drag_top"] = canvas.yview()[0]
                sb.bind("<B1-Motion>", _sb_drag)
                sb.bind("<ButtonRelease-1>", _sb_release)
            else:
                canvas.yview_moveto(e.y / sb.winfo_height())

        def _sb_drag(e):
            track = sb.winfo_height()
            if track > 0:
                canvas.yview_moveto(state["drag_top"] + (e.y - state["drag_y"]) / track)

        def _sb_release(e):
            sb.unbind("<B1-Motion>")
            sb.unbind("<ButtonRelease-1>")

        sb.bind("<ButtonPress-1>", _sb_press)
        sb.bind("<Enter>", lambda e: _draw_thumb(THUMB_HOVER))
        sb.bind("<Leave>", lambda e: _draw_thumb(THUMB_COLOR))
        sb.bind("<Configure>", lambda e: _draw_thumb())

        list_frame.bind("<Configure>", lambda e: (canvas.configure(scrollregion=canvas.bbox("all")), _draw_thumb()))
        canvas.bind("<Configure>", lambda e: (canvas.itemconfig(win_id, width=e.width), _draw_thumb()))
        canvas.configure(yscrollcommand=lambda first, last: _draw_thumb())

        def _scroll(delta):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(delta, "units")
                    _draw_thumb()
            except Exception:
                pass

        def _on_enter(e):
            canvas.bind_all("<MouseWheel>", lambda ev: _scroll(int(-1 * (ev.delta / 120))))
            canvas.bind_all("<Button-4>", lambda ev: _scroll(-1))
            canvas.bind_all("<Button-5>", lambda ev: _scroll(1))

        def _on_leave(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)
        canvas.bind("<Destroy>", _on_leave)

    def _show_popup(self, title, message, buttons):
        try:
            if self.root.state() == "iconic":
                return
        except Exception:
            return
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=self.COLORS["white"])
        try:
            popup.grab_set()
        except Exception:
            pass
        inner = tk.Frame(popup, bg=self.COLORS["dark"])
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Label(inner, text=title, bg=self.COLORS["dark"], fg=self.COLORS["white"],
                 font=("Segoe UI", 10, "bold"), padx=16).pack(anchor="w", pady=(12, 4))
        tk.Frame(inner, bg=self.COLORS["separator"], height=1).pack(fill="x")
        tk.Label(inner, text=message, bg=self.COLORS["dark"], fg=self.COLORS["text_light"],
                 font=("Segoe UI", 9), wraplength=320, justify="left",
                 padx=16, pady=12).pack(anchor="w")
        btn_frame = tk.Frame(inner, bg=self.COLORS["dark"])
        btn_frame.pack(fill="x", padx=16, pady=(0, 14))
        for label, color, cb in reversed(buttons):
            def _make_cmd(callback, p=popup):
                def _cmd():
                    p.destroy()
                    if callback:
                        callback()
                return _cmd
            tk.Button(btn_frame, text=label, bg=self.COLORS["dark"], fg=color,
                      activebackground=color, activeforeground=self.COLORS["dark"],
                      font=("Segoe UI", 9), relief="flat", bd=0, padx=14, pady=6,
                      cursor="hand2", highlightthickness=1, highlightbackground=color,
                      command=_make_cmd(cb)).pack(side="right", padx=(8, 0))
        popup.update_idletasks()
        pw, ph = popup.winfo_width(), popup.winfo_height()
        popup.geometry(f"+{self.root.winfo_x() + (self.root.winfo_width() - pw) // 2}"
                       f"+{self.root.winfo_y() + (self.root.winfo_height() - ph) // 2}")

    def _do_uninstall(self, package):
        if not self._is_connected():
            self._show_popup("Error", "No device connected.", [("OK", self.COLORS["error_red"], None)])
            return
        device = self._get_active_device()

        def _check_and_show():
            raw = self._run_with_device(["shell", "pm", "list", "packages", "-s"], device)
            system_pkgs = {l.replace("package:", "").strip() for l in raw.splitlines() if l.startswith("package:")}
            self.ui_queue.put(("show_uninstall_popup", package, device, package in system_pkgs))

        threading.Thread(target=_check_and_show, daemon=True).start()

    def _do_reinstall(self, package):
        if not self._is_connected():
            self._show_popup("Error", "No device connected.", [("OK", self.COLORS["error_red"], None)])
            return
        device = self._get_active_device()

        def _exec():
            result = self._run_with_device(["shell", "cmd", "package", "install-existing", package], device)
            if "Success" in result or "Package" in result:
                self.ui_queue.put(("popup_ok", f"Successfully reinstalled\n{package}"))
                with self.state_lock:
                    self._last_fetched_device = None
                self._fetch_packages(device)
            elif "Operation not allowed" in result or "Permission denied" in result:
                self.ui_queue.put(("popup_err", f"Cannot reinstall {package}:\nSystem app protected"))
            else:
                self.ui_queue.put(("popup_err", f"Failed to reinstall\n{package}"))

        self._show_popup("Reinstall", f"{package}\n\nRestore this app to its previous state?", [
            ("Reinstall", self.COLORS["usb_green"], lambda: threading.Thread(target=_exec, daemon=True).start()),
            ("Cancel", self.COLORS["text_dim"], None),
        ])

    def _toggle_display_popup(self):
        if self._display_popup and self._display_popup.winfo_exists():
            self._close_display_popup()
            return
        if not self._is_connected():
            return
        self._open_display_popup()

    def _open_display_popup(self):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=self.COLORS["white"])
        self._display_popup = popup

        inner = tk.Frame(popup, bg=self.COLORS["dark"])
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        header = tk.Frame(inner, bg=self.COLORS["dark"])
        header.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(header, text="Display", bg=self.COLORS["dark"],
                 fg=self.COLORS["white"], font=("Segoe UI", 9, "bold")).pack(side="left")
        close_x = tk.Label(header, text="✕", bg=self.COLORS["dark"],
                           fg=self.COLORS["text_dim"], font=("Segoe UI", 9), cursor="hand2")
        close_x.pack(side="right")
        close_x.bind("<Button-1>", lambda e: self._close_display_popup())

        tk.Frame(inner, bg=self.COLORS["separator"], height=1).pack(fill="x")

        res_row = tk.Frame(inner, bg=self.COLORS["dark"])
        res_row.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(res_row, text="Resolution", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9), width=9, anchor="w").pack(side="left")
        w_var = tk.StringVar()
        h_var = tk.StringVar()
        cur = self.res_label.cget("text")
        for sep in ["×", "x", "X"]:
            if sep in cur:
                parts = cur.split(sep)
                w_var.set(parts[0].strip())
                h_var.set(parts[1].strip())
                break
        w_entry = tk.Entry(res_row, textvariable=w_var, width=6,
                           bg="#1a1a1a", fg=self.COLORS["text_light"],
                           insertbackground=self.COLORS["white"],
                           relief="flat", font=("Segoe UI", 9),
                           highlightthickness=1, highlightbackground=self.COLORS["separator"])
        w_entry.pack(side="left", ipady=2)
        tk.Label(res_row, text="×", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9)).pack(side="left", padx=2)
        h_entry = tk.Entry(res_row, textvariable=h_var, width=6,
                           bg="#1a1a1a", fg=self.COLORS["text_light"],
                           insertbackground=self.COLORS["white"],
                           relief="flat", font=("Segoe UI", 9),
                           highlightthickness=1, highlightbackground=self.COLORS["separator"])
        h_entry.pack(side="left", ipady=2)

        dpi_row = tk.Frame(inner, bg=self.COLORS["dark"])
        dpi_row.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(dpi_row, text="Dpi", bg=self.COLORS["dark"],
                 fg=self.COLORS["text_dim"], font=("Segoe UI", 9), width=9, anchor="w").pack(side="left")
        dpi_var = tk.StringVar(value=self.dpi_label.cget("text").strip())
        dpi_entry = tk.Entry(dpi_row, textvariable=dpi_var, width=6,
                             bg="#1a1a1a", fg=self.COLORS["text_light"],
                             insertbackground=self.COLORS["white"],
                             relief="flat", font=("Segoe UI", 9),
                             highlightthickness=1, highlightbackground=self.COLORS["separator"])
        dpi_entry.pack(side="left", ipady=2)

        tk.Frame(inner, bg=self.COLORS["separator"], height=1).pack(fill="x")

        btn_row = tk.Frame(inner, bg=self.COLORS["dark"])
        btn_row.pack(fill="x", padx=10, pady=(6, 10))
        tk.Button(btn_row, text="Apply", bg=self.COLORS["dark"], fg=self.COLORS["error_red"],
                  activebackground=self.COLORS["error_red"], activeforeground=self.COLORS["dark"],
                  relief="flat", bd=0, font=("Segoe UI", 9), padx=14, pady=4, cursor="hand2",
                  highlightthickness=1, highlightbackground=self.COLORS["error_red"],
                  command=lambda: self._apply_all(w_var.get(), h_var.get(), dpi_var.get())).pack(side="left", expand=True)
        tk.Button(btn_row, text="Reset", bg=self.COLORS["dark"], fg=self.COLORS["usb_green"],
                  activebackground=self.COLORS["usb_green"], activeforeground=self.COLORS["dark"],
                  relief="flat", bd=0, font=("Segoe UI", 9), padx=14, pady=4, cursor="hand2",
                  highlightthickness=1, highlightbackground=self.COLORS["usb_green"],
                  command=self._reset_all).pack(side="left", expand=True)

        popup.update_idletasks()
        bx = self.change_btn.winfo_rootx()
        by = self.change_btn.winfo_rooty() + self.change_btn.winfo_height() + 4
        pw = popup.winfo_width()
        x = min(bx, self.root.winfo_x() + self.root.winfo_width() - pw - 4)
        popup.geometry(f"+{x}+{by}")

        def _on_root_click(e):
            if not self._display_popup or not self._display_popup.winfo_exists():
                self.root.unbind("<Button-1>")
                return
            wx = self._display_popup.winfo_rootx()
            wy = self._display_popup.winfo_rooty()
            ww = self._display_popup.winfo_width()
            wh = self._display_popup.winfo_height()
            if not (wx <= e.x_root <= wx + ww and wy <= e.y_root <= wy + wh):
                self._close_display_popup()

        self.root.after(100, lambda: self.root.bind("<Button-1>", _on_root_click))

    def _close_display_popup(self):
        if self._display_popup and self._display_popup.winfo_exists():
            self._display_popup.destroy()
        self._display_popup = None
        self.root.unbind("<Button-1>")

    def _apply_all(self, w, h, dpi):
        if not (w.isdigit() and h.isdigit() and int(w) > 0 and int(h) > 0):
            return
        if not (dpi.isdigit() and int(dpi) > 0):
            return
        device = self._get_active_device()
        self._close_display_popup()

        def _exec():
            self._run_with_device(["shell", "wm", "size", f"{w}x{h}"], device)
            self._run_with_device(["shell", "wm", "density", dpi], device)
            self._fetch_display_info(device)

        threading.Thread(target=_exec, daemon=True).start()

    def _reset_all(self):
        device = self._get_active_device()
        self._close_display_popup()

        def _exec():
            self._run_with_device(["shell", "wm", "size", "reset"], device)
            self._run_with_device(["shell", "wm", "density", "reset"], device)
            self._fetch_display_info(device)

        threading.Thread(target=_exec, daemon=True).start()

    def _fetch_display_info(self, device):
        out_size = self._run_with_device(["shell", "wm", "size"], device)
        out_density = self._run_with_device(["shell", "wm", "density"], device)
        res = dpi = ""
        for line in out_size.splitlines():
            if "Override size" in line:
                res = line.split(": ")[1].strip()
                break
            if "Physical size" in line:
                res = line.split(": ")[1].strip()
        for line in out_density.splitlines():
            if "Override density" in line:
                dpi = line.split(": ")[1].strip()
                break
            if "Physical density" in line:
                dpi = line.split(": ")[1].strip()
        self.ui_queue.put(("display_info", res, dpi))

    def _set_status(self, text, color):
        self.ui_queue.put(("status", text, color))

    def _set_device(self, text):
        self.ui_queue.put(("device", text))

    def _process_ui_queue(self):
        if not self.app_running:
            return
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                if msg[0] == "status":
                    self.dot.config(fg=msg[2])
                    self.conn_label.config(text=msg[1], fg=msg[2])
                elif msg[0] == "device":
                    self.device_label.config(text=msg[1])
                elif msg[0] == "display_info":
                    self.res_label.config(text=msg[1] if msg[1] else "–")
                    self.dpi_label.config(text=msg[2] if msg[2] else "–")
                elif msg[0] == "installed_list":
                    self._all_installed = msg[1]
                    self._filter_installed()
                elif msg[0] == "uninstalled_list":
                    self._all_uninstalled = msg[1]
                    self._filter_uninstalled()
                elif msg[0] == "popup_ok":
                    self._show_popup("Success", msg[1], [("OK", self.COLORS["usb_green"], None)])
                elif msg[0] == "popup_err":
                    self._show_popup("Error", msg[1], [("OK", self.COLORS["error_red"], None)])
                elif msg[0] == "show_uninstall_popup":
                    _, package, device, is_system = msg

                    def _run_uninstall(pkg=package, dev=device):
                        def _exec():
                            result = self._run_with_device(["shell", "pm", "uninstall", "--user", "0", pkg], dev)
                            if "Success" in result:
                                self.ui_queue.put(("popup_ok", f"Successfully uninstalled\n{pkg}"))
                                with self.state_lock:
                                    self._last_fetched_device = None
                                self._fetch_packages(dev)
                            elif "Operation not allowed" in result or "Permission denied" in result:
                                self.ui_queue.put(("popup_err", f"Cannot uninstall {pkg}:\nSystem app protected"))
                            else:
                                self.ui_queue.put(("popup_err", f"Failed to uninstall\n{pkg}"))
                        threading.Thread(target=_exec, daemon=True).start()

                    title = "Uninstall System App" if is_system else "Uninstall"
                    msg_text = (f"{package}\n\nThis is a system app. Are you sure?" if is_system
                                else f"{package}\n\nAll app data will be permanently deleted.")
                    self._show_popup(title, msg_text, [
                        ("Uninstall", self.COLORS["error_red"], _run_uninstall),
                        ("Cancel", self.COLORS["text_dim"], None),
                    ])
        except Empty:
            pass
        except Exception:
            pass
        if self.app_running:
            self.root.after(100, self._process_ui_queue)

    def check_connection(self):
        if not self.app_running:
            return
        if self.is_dragging:
            self.root.after(2000, self.check_connection)
            return

        def _poll():
            try:
                out = self._run([_adb(), "devices"])
                if not out:
                    self._set_status("ADB tidak tersedia", self.COLORS["error_red"])
                    self._set_device("No device")
                else:
                    lines = [l for l in out.strip().splitlines()[1:] if l.strip() and not l.startswith("*")]
                    usb_devices = [l.split()[0] for l in lines if len(l.split()) >= 2 and l.split()[1] == "device" and ":" not in l.split()[0]]
                    wifi_devices = [l.split()[0] for l in lines if len(l.split()) >= 2 and l.split()[1] == "device" and ":" in l.split()[0]]
                    usb = usb_devices[0] if usb_devices else None
                    wifi = wifi_devices[0] if wifi_devices else None
                    if usb:
                        self._handle_usb(usb)
                    elif wifi:
                        self._handle_wifi(wifi)
                    else:
                        self._handle_no_device()
            except Exception:
                self._set_status("ADB error", self.COLORS["error_red"])
                self._set_device("No device")
            if self.app_running:
                self.root.after(2000, self.check_connection)

        threading.Thread(target=_poll, daemon=True).start()

    def _handle_usb(self, usb_serial):
        with self.state_lock:
            self.adb_mode = "usb"
            self.wifi_serial = None
            changed = self._last_fetched_device != usb_serial
            if changed:
                self._last_fetched_device = usb_serial
            do_setup_wifi = not self.tcpip_set
            if do_setup_wifi:
                self.tcpip_set = True
                self._setting_up_wifi = True

        self._set_status("USB Connected", self.COLORS["usb_green"])
        self._set_device(self._get_device_info(usb_serial) or "Device connected")

        if changed:
            threading.Thread(target=lambda: self._fetch_packages(usb_serial), daemon=True).start()
            threading.Thread(target=lambda: self._fetch_display_info(usb_serial), daemon=True).start()

        if do_setup_wifi:
            def _setup_wifi(serial=usb_serial):
                time.sleep(3)
                self._run_s([_adb(), "-s", serial, "tcpip", "5555"])
                time.sleep(2)
                ip = self._get_ip_for(serial)
                if ip:
                    with self.state_lock:
                        self.last_ip = ip
                    self._run_s([_adb(), "connect", f"{ip}:5555"])
                with self.state_lock:
                    self._setting_up_wifi = False
            threading.Thread(target=_setup_wifi, daemon=True).start()

    def _handle_wifi(self, wifi_serial):
        with self.state_lock:
            self.adb_mode = "wifi"
            self.wifi_serial = wifi_serial
            changed = self._last_fetched_device != wifi_serial
            if changed:
                self._last_fetched_device = wifi_serial

        self._set_status(f"Wi-Fi  {wifi_serial}", self.COLORS["wifi_cyan"])
        self._set_device(self._get_device_info(wifi_serial) or wifi_serial)

        if changed:
            threading.Thread(target=lambda: self._fetch_packages(wifi_serial), daemon=True).start()
            threading.Thread(target=lambda: self._fetch_display_info(wifi_serial), daemon=True).start()

    def _handle_no_device(self):
        with self.state_lock:
            if self._setting_up_wifi:
                return
            self.adb_mode = None
            self.wifi_serial = None
            self._last_fetched_device = None
            self._all_installed = []
            self._all_uninstalled = []
            ip = self.last_ip
        self._set_device("No device")
        self.ui_queue.put(("installed_list", []))
        self.ui_queue.put(("uninstalled_list", []))
        self.ui_queue.put(("display_info", "", ""))
        if ip:
            self._set_status(f"Reconnecting  {ip}\u2026", self.COLORS["reconnect_yellow"])
            def _try_reconnect():
                self._run_s([_adb(), "connect", f"{ip}:5555"])
                time.sleep(1)
                out = self._run([_adb(), "devices"])
                connected = any(":" in l.split()[0] and len(l.split()) >= 2 and l.split()[1] == "device"
                                for l in out.strip().splitlines()[1:] if l.strip() and not l.startswith("*"))
                if not connected:
                    with self.state_lock:
                        self.last_ip = None
                        self.tcpip_set = False
            threading.Thread(target=_try_reconnect, daemon=True).start()
        else:
            with self.state_lock:
                self.tcpip_set = False
            self._set_status("No device detected", self.COLORS["error_red"])

    def set_title(self, title):
        self.root.title(title)
        self.title_label.config(text=title)

    def close_window(self):
        self.app_running = False
        self._close_display_popup()
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = DarkWindow(root)
    app.set_title("Mi Adb Kit")
    app.root.after(0, app._process_ui_queue)
    app.root.after(50, app.check_connection)
    root.mainloop()
