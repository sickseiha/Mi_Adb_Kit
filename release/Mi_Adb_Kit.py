import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import sys

installed_cache = None
uninstalled_cache = None
system_all_cache = None
user_all_cache = None
search_after_id1 = None
search_after_id2 = None
last_adb_state = None

def check_adb_installed():
    adb_path = os.path.join(os.path.dirname(sys.executable), "adb.exe")
    if os.path.exists(adb_path):
        subprocess.run([adb_path, "start-server"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    try:
        result = subprocess.run(['adb', '--version'], capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0
    except:
        return False

def check_adb_connection():
    try:
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
        return len(result.stdout.strip().split('\n')) > 1
    except:
        return False

def run_adb_cmd(cmd):
    allowed_cmds = ['pm list packages', 'pm list packages -u', 'pm uninstall -k --user 0',
                    'pm uninstall --user 0', 'cmd package install-existing', 'getprop ro.product.brand',
                    'getprop ro.product.model', 'getprop ro.product.device',
                    'getprop ro.system.build.version.incremental', 'wm size',
                    'wm density', 'settings get secure miui_refresh_rate', 'settings get secure user_refresh_rate', 
                    'which su', 'getprop ro.boot.verifiedbootstate', 'cat /proc/version']
    if not any(cmd.startswith(allowed) for allowed in allowed_cmds):
        return ["Error: Invalid command"]
    if not check_adb_connection():
        return ["Error: No device connected"]
    try:
        result = subprocess.run(['adb', 'shell', cmd], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.stdout.strip().split('\n')
    except:
        return ["Error: ADB failed"]

def get_installed():
    global installed_cache
    if installed_cache is None:
        installed_cache = [line.replace('package:', '') for line in run_adb_cmd('pm list packages') if line.startswith('package:')]
    return installed_cache

def get_uninstalled():
    global uninstalled_cache
    if uninstalled_cache is None:
        all_pkgs = set(line.replace('package:', '') for line in run_adb_cmd('pm list packages -u') if line.startswith('package:'))
        installed = set(get_installed())
        uninstalled_cache = sorted(all_pkgs - installed)
    return uninstalled_cache

def get_system_all():
    global system_all_cache
    if system_all_cache is None:
        system_all_cache = set(line.replace('package:', '') for line in run_adb_cmd('pm list packages -s -u') if line.startswith('package:'))
    return system_all_cache

def get_user_all():
    global user_all_cache
    if user_all_cache is None:
        user_all_cache = set(line.replace('package:', '') for line in run_adb_cmd('pm list packages -3 -u') if line.startswith('package:'))
    return user_all_cache

def update_display_tab():
    original_res, current_res = get_resolution()
    res_original_label.config(text=f"Original: {original_res}")
    res_current_label.config(text=f"Current: {current_res}")
    original_dpi, current_dpi = get_dpi()
    dpi_original_label.config(text=f"Original: {original_dpi}")
    dpi_current_label.config(text=f"Current: {current_dpi}")
    fps_system_label.config(text=f"System: {get_fps()}")
    fps_user_label.config(text=f"User: {get_user_fps()}")

def update_device_info_tab():
    brand, model, code, version = get_device_info()
    kernel = get_kernel()
    root_status = check_root()
    bootloader_status = check_bootloader()
    device_info_labels[0].config(text=f"Brand: {brand}")
    device_info_labels[1].config(text=f"Model: {model}")
    device_info_labels[2].config(text=f"Code: {code}")
    device_info_labels[3].config(text=f"Firmware: {version}")
    device_info_labels[4].config(text=f"Kernel: {kernel}")
    root_color = "red" if root_status == "Yes" else "green" if root_status == "No" else "black"
    device_info_labels[5].config(text=root_status, foreground=root_color)
    bootloader_color = "red" if bootloader_status == "Yes" else "green" if bootloader_status == "No" else "black"
    device_info_labels[6].config(text=bootloader_status, foreground=bootloader_color)

def refresh_lists():
    global installed_cache, uninstalled_cache
    installed_packages = get_installed()
    uninstalled_packages = get_uninstalled()
    system_all = get_system_all()
    user_all = get_user_all()
    installed_system = [pkg for pkg in installed_packages if pkg in system_all]
    installed_user = [pkg for pkg in installed_packages if pkg in user_all]
    uninstalled_system = [pkg for pkg in uninstalled_packages if pkg in system_all]
    uninstalled_user = [pkg for pkg in uninstalled_packages if pkg in user_all]
    for widget in total_frame1.winfo_children():
        widget.destroy()
    total_label1 = ttk.Frame(total_frame1)
    total_label1.pack(side='right')
    ttk.Label(total_label1, text="System: ").pack(side='left')
    ttk.Label(total_label1, text=f"{len(installed_system)}", foreground="red").pack(side='left')
    if installed_user:
        ttk.Label(total_label1, text=" User: ").pack(side='left')
        ttk.Label(total_label1, text=f"{len(installed_user)}", foreground="green").pack(side='left')
    for widget in total_frame2.winfo_children():
        widget.destroy()
    total_label2 = ttk.Frame(total_frame2)
    total_label2.pack(side='right')
    ttk.Label(total_label2, text="System: ").pack(side='left')
    ttk.Label(total_label2, text=f"{len(uninstalled_system)}", foreground="red").pack(side='left')
    if uninstalled_user:
        ttk.Label(total_label2, text=" User: ").pack(side='left')
        ttk.Label(total_label2, text=f"{len(uninstalled_user)}", foreground="green").pack(side='left')
    refresh_list(canvas1, package_frame1, installed_packages, "installed", search_entry1)
    refresh_list(canvas2, package_frame2, uninstalled_packages, "uninstalled", search_entry2)

def refresh_adb(show_popup=True, force_refresh=False):
    global installed_cache, uninstalled_cache, system_all_cache, user_all_cache, last_adb_state
    current_adb_state = check_adb_connection()
    if not force_refresh and current_adb_state == last_adb_state and show_popup:
        return
    last_adb_state = current_adb_state
    if not current_adb_state:
        if show_popup:
            messagebox.showerror("Error", "No device connected")
        device_name_label.config(text="No device connected", foreground="red")
        installed_cache = []
        uninstalled_cache = []
        system_all_cache = set()
        user_all_cache = set()
        refresh_lists()
        update_display_tab()
        update_device_info_tab()
        return
    installed_cache = None
    uninstalled_cache = None
    system_all_cache = None
    user_all_cache = None
    brand, model, code, version = get_device_info()
    device_name = f"{brand} {model} ({code})" if model != "Unknown" and code != "Unknown" else "No device connected"
    device_color = "green" if model != "Unknown" and code != "Unknown" else "red"
    device_name_label.config(text=device_name, foreground=device_color)
    refresh_lists()
    update_display_tab()
    update_device_info_tab()
    if show_popup and device_color == "green":
        messagebox.showinfo("Success", f"{device_name} connected")

def uninstall_package(package, canvas, search_entry):
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    system_all = get_system_all()
    user_all = get_user_all()
    if package in system_all:
        response = messagebox.askyesnocancel("Uninstall", f"This is system app ({package}). Do you want to keep its data for future reinstall?", icon="warning")
        if response is True:
            cmd = f'pm uninstall -k --user 0 {package}'
        elif response is False:
            cmd = f'pm uninstall --user 0 {package}'
        else:
            return
    else:
        response = messagebox.askyesno("Uninstall", f"This is user app ({package}). All its data will be permanently deleted.", icon="warning")
        if not response:
            return
        cmd = f'pm uninstall --user 0 {package}'
    result = subprocess.run(['adb', 'shell', cmd], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout.strip() or result.stderr.strip()
    if "Success" in output:
        messagebox.showinfo("Success", f"Successfully uninstalled {package}")
        global installed_cache, uninstalled_cache
        installed_cache = None
        uninstalled_cache = None
        refresh_lists()
    elif "Operation not allowed" in output or "Permission denied" in output:
        messagebox.showerror("Error", f"Cannot uninstall {package}: System app protected")
    else:
        messagebox.showerror("Error", f"Failed to uninstall {package}")

def reinstall_package(package, canvas, search_entry):
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    response = messagebox.askyesno("Reinstall", f"Reinstall ({package})? This will restore the app to its previous state.", icon="warning")
    if not response:
        return
    result = subprocess.run(['adb', 'shell', f'cmd package install-existing {package}'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout.strip() or result.stderr.strip()
    if "Success" in output or "Package" in output:
        messagebox.showinfo("Success", f"Successfully reinstalled {package}")
        global installed_cache, uninstalled_cache
        installed_cache = None
        uninstalled_cache = None
        refresh_lists()
    elif "Operation not allowed" in output or "Permission denied" in output:
        messagebox.showerror("Error", f"Cannot reinstall {package}: System app protected")
    else:
        messagebox.showerror("Error", f"Failed to reinstall {package}")

def refresh_list(canvas, package_frame, packages, status, search_entry):
    for widget in package_frame.winfo_children():
        widget.destroy()
    query = search_entry.get()
    filtered = [pkg for pkg in packages if query.lower() in pkg.lower()]
    if not filtered:
        ttk.Label(package_frame, text="No matching packages found").pack(anchor='w', pady=2)
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.yview_moveto(0)
        return
    system_all = get_system_all()
    user_all = get_user_all()
    system_pkgs = [pkg for pkg in filtered if pkg in system_all]
    user_pkgs = [pkg for pkg in filtered if pkg in user_all]
    filtered = system_pkgs + user_pkgs
    for pkg in filtered:
        frame = ttk.Frame(package_frame)
        frame.pack(fill='x', pady=2)
        ttk.Label(frame, text=pkg, width=60, anchor='w').pack(side='left')
        ttk.Label(frame, text="").pack(side='left', expand=True, fill='x')
        app_type = "System" if pkg in system_all else "User" if pkg in user_all else "Unknown"
        color = "red" if app_type == "System" else "green" if app_type == "User" else "black"
        btn = ttk.Button(frame, text="Uninstall" if status == "installed" else "Reinstall",
                         command=lambda p=pkg: uninstall_package(p, canvas, search_entry) if status == "installed" else reinstall_package(p, canvas, search_entry))
        btn.pack(side='right', padx=5)
        btn.configure(style="Green.TButton" if app_type == "User" else "Red.TButton" if status == "installed" else "Green.TButton")
        ttk.Label(frame, text=app_type, foreground=color).pack(side='right', padx=5)
    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.yview_moveto(0)

def periodic_check():
    global last_adb_state
    current_adb_state = check_adb_connection()
    if current_adb_state != last_adb_state:
        refresh_adb(show_popup=True, force_refresh=True)
    root.after(2000, periodic_check)

def get_resolution():
    if not check_adb_connection():
        return "Unknown", "Unknown"
    output = run_adb_cmd('wm size')
    original = current = "Unknown"
    for line in output:
        if "Physical size" in line:
            original = line.split(': ')[1].strip()
        if "Override size" in line:
            current = line.split(': ')[1].strip()
    if current == "Unknown":
        current = original
    return original, current

def get_dpi():
    if not check_adb_connection():
        return "Unknown", "Unknown"
    output = run_adb_cmd('wm density')
    original = current = "Unknown"
    for line in output:
        if "Physical density" in line:
            original = line.split(': ')[1].strip()
        if "Override density" in line:
            current = line.split(': ')[1].strip()
    if current == "Unknown":
        current = original
    return original, current

def get_fps():
    if not check_adb_connection():
        return "Unknown"
    output = run_adb_cmd('settings get secure miui_refresh_rate')
    return output[0].strip() if output and output[0].strip().isdigit() else "Unknown"

def get_user_fps():
    if not check_adb_connection():
        return "Unknown"
    output = run_adb_cmd('settings get secure user_refresh_rate')
    return output[0].strip() if output and output[0].strip().isdigit() else "Unknown"

def get_device_info():
    if not check_adb_connection():
        return "Unknown", "Unknown", "Unknown", "Unknown"
    brand = run_adb_cmd('getprop ro.product.brand')
    model = run_adb_cmd('getprop ro.product.model')
    code = run_adb_cmd('getprop ro.product.device')
    version = run_adb_cmd('getprop ro.system.build.version.incremental')
    return (
        brand[0].strip() if brand and brand[0].strip() else "Unknown",
        model[0].strip() if model and model[0].strip() else "Unknown",
        code[0].strip() if code and code[0].strip() else "Unknown",
        version[0].strip() if version and version[0].strip() else "Unknown"
    )

def check_root():
    if not check_adb_connection():
        return "Unknown"
    output = run_adb_cmd('which su')
    return "Yes" if output and output[0].strip() and '/su' in output[0] else "No"

def check_bootloader():
    if not check_adb_connection():
        return "Unknown"
    output = run_adb_cmd('getprop ro.boot.verifiedbootstate')
    return "Yes" if output and output[0].strip() in ['orange', 'yellow'] else "No"

def get_kernel():
    if not check_adb_connection():
        return "Unknown"
    output = run_adb_cmd('cat /proc/version')
    return output[0].strip().split()[2] if output and output[0].strip() else "Unknown"

def set_resolution(width, height):
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    if not (width.isdigit() and height.isdigit() and int(width) > 0 and int(height) > 0):
        messagebox.showerror("Error", "Invalid input")
        return
    result = subprocess.run(['adb', 'shell', f'wm size {width}x{height}'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout.strip() or result.stderr.strip()
    if "override" in output.lower() or not output:
        messagebox.showinfo("Success", f"Resolution set to {width}x{height}")
        update_display_tab()
    else:
        messagebox.showerror("Error", "Failed to set resolution")

def reset_resolution():
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    original, _ = get_resolution()
    result = subprocess.run(['adb', 'shell', 'wm size reset'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout.strip() or result.stderr.strip()
    if not output or "reset" in output.lower():
        messagebox.showinfo("Success", f"Resolution reset to {original}")
        update_display_tab()
    else:
        messagebox.showerror("Error", "Failed to reset resolution")

def set_dpi(dpi):
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    if not (dpi.isdigit() and int(dpi) > 0):
        messagebox.showerror("Error", "Invalid input")
        return
    dpi_val = int(dpi)
    if dpi_val <= 200:
        response = messagebox.askyesno("DPI", f"DPI {dpi_val} may make the display appear too small. Continue?", icon="warning")
        if not response:
            return
    elif dpi_val >= 600:
        response = messagebox.askyesno("DPI", f"DPI {dpi_val} may make the display appear too large. Continue?", icon="warning")
        if not response:
            return
    result = subprocess.run(['adb', 'shell', f'wm density {dpi}'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout.strip() or result.stderr.strip()
    if "override" in output.lower() or not output:
        messagebox.showinfo("Success", f"DPI set to {dpi}")
        update_display_tab()
    else:
        messagebox.showerror("Error", "Failed to set DPI")

def reset_dpi():
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    original, _ = get_dpi()
    result = subprocess.run(['adb', 'shell', 'wm density reset'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output = result.stdout.strip() or result.stderr.strip()
    if not output or "reset" in output.lower():
        messagebox.showinfo("Success", f"DPI reset to {original}")
        update_display_tab()
    else:
        messagebox.showerror("Error", "Failed to reset DPI")

def apply_fps(fps, reset=False):
    if not check_adb_connection():
        messagebox.showerror("Error", "No device connected")
        return
    if not reset:
        if not (fps.isdigit() and int(fps) > 0):
            messagebox.showerror("Error", "Invalid input")
            return
        fps_val = int(fps)
        if fps_val not in [30, 60, 90, 120, 144, 165]:
            messagebox.showwarning("FPS", "FPS must be 30, 60, 90, 120, 144, or 165.")
            return
    else:
        fps_val = 60
    current_fps = get_fps()
    current_user_fps = get_user_fps()
    if current_fps != "Unknown" and int(current_fps) == fps_val and current_user_fps != "Unknown" and int(current_user_fps) == fps_val:
        messagebox.showinfo("Info", f"FPS is already set to {fps_val}")
        return
    result1 = subprocess.run(['adb', 'shell', f'settings put secure miui_refresh_rate {fps_val}'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    result2 = subprocess.run(['adb', 'shell', f'settings put secure user_refresh_rate {fps_val}'], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    output1 = result1.stdout.strip() or result1.stderr.strip()
    output2 = result2.stdout.strip() or result2.stderr.strip()
    if (not output1 or "success" in output1.lower()) and (not output2 or "success" in output2.lower()):
        messagebox.showinfo("Success", f"FPS {'reset to 60' if reset else f'set to {fps_val}'}")
        update_display_tab()
    else:
        messagebox.showerror("Error", "Failed to set FPS")

def open_telegram():
    webbrowser.open("https://t.me/sickseiha")

def open_github():
    webbrowser.open("https://github.com/sickseiha/Mi_Adb_Kit")

def create_debloater_tab(tab):
    global sub_nb, sub_tab1, sub_tab2, canvas1, canvas2, package_frame1, package_frame2, scrollbar1, scrollbar2, search_entry1, search_entry2, device_name_label, total_frame1, total_frame2, search_after_id1, search_after_id2
    style = ttk.Style()
    style.configure("Red.TButton", foreground="red")
    style.configure("Green.TButton", foreground="green")
    top_frame = ttk.Frame(tab)
    top_frame.pack(fill='x', padx=10, pady=5)
    ttk.Label(top_frame, text="Device Connected: ").pack(side='left')
    brand, model, code, version = get_device_info()
    device_name = f"{brand} {model} ({code})" if model != "Unknown" and code != "Unknown" else "No device connected"
    device_color = "green" if model != "Unknown" and code != "Unknown" else "red"
    device_name_label = ttk.Label(top_frame, text=device_name, foreground=device_color)
    device_name_label.pack(side='left')
    ttk.Label(top_frame, text="").pack(side='left', expand=True, fill='x')
    ttk.Button(top_frame, text="Refresh", command=lambda: refresh_adb(show_popup=True, force_refresh=True)).pack(side='right')
    sub_nb = ttk.Notebook(tab)
    sub_nb.pack(expand=True, fill='both')
    sub_tab1 = ttk.Frame(sub_nb)
    sub_nb.add(sub_tab1, text="Installed")
    search_frame1 = ttk.Frame(sub_tab1)
    search_frame1.pack(fill='x', padx=10, pady=5)
    ttk.Label(search_frame1, text="Search:").pack(side='left')
    search_entry1 = ttk.Entry(search_frame1)
    search_entry1.pack(fill='x', expand=True)
    canvas_frame1 = ttk.Frame(sub_tab1)
    canvas_frame1.pack(expand=True, fill='both', padx=10)
    canvas1 = tk.Canvas(canvas_frame1)
    scrollbar1 = ttk.Scrollbar(canvas_frame1, orient=tk.VERTICAL, command=canvas1.yview)
    canvas1.configure(yscrollcommand=scrollbar1.set)
    scrollbar1.pack(side='right', fill='y')
    canvas1.pack(side='left', expand=True, fill='both')
    package_frame1 = ttk.Frame(canvas1)
    canvas1.create_window((0, 0), window=package_frame1, anchor='nw')
    total_frame1 = ttk.Frame(sub_tab1)
    total_frame1.pack(fill='x', padx=10, pady=5)
    sub_tab2 = ttk.Frame(sub_nb)
    sub_nb.add(sub_tab2, text="Uninstalled")
    search_frame2 = ttk.Frame(sub_tab2)
    search_frame2.pack(fill='x', padx=10, pady=5)
    ttk.Label(search_frame2, text="Search:").pack(side='left')
    search_entry2 = ttk.Entry(search_frame2)
    search_entry2.pack(fill='x', expand=True)
    canvas_frame2 = ttk.Frame(sub_tab2)
    canvas_frame2.pack(expand=True, fill='both', padx=10)
    canvas2 = tk.Canvas(canvas_frame2)
    scrollbar2 = ttk.Scrollbar(canvas_frame2, orient=tk.VERTICAL, command=canvas2.yview)
    canvas2.configure(yscrollcommand=scrollbar2.set)
    scrollbar2.pack(side='right', fill='y')
    canvas2.pack(side='left', expand=True, fill='both')
    package_frame2 = ttk.Frame(canvas2)
    canvas2.create_window((0, 0), window=package_frame2, anchor='nw')
    total_frame2 = ttk.Frame(sub_tab2)
    total_frame2.pack(fill='x', padx=10, pady=5)
    package_frame1.bind('<Configure>', lambda e: canvas1.configure(scrollregion=canvas1.bbox("all")))
    package_frame2.bind('<Configure>', lambda e: canvas2.configure(scrollregion=canvas2.bbox("all")))
    canvas1.bind_all("<MouseWheel>", lambda e: canvas1.yview_scroll(int(-1 * (e.delta / 120)), "units") if sub_nb.index(sub_nb.select()) == 0 else canvas2.yview_scroll(int(-1 * (e.delta / 120)), "units"))
    canvas1.bind_all("<Button-4>", lambda e: canvas1.yview_scroll(-1, "units") if sub_nb.index(sub_nb.select()) == 0 else canvas2.yview_scroll(-1, "units"))
    canvas1.bind_all("<Button-5>", lambda e: canvas1.yview_scroll(1, "units") if sub_nb.index(sub_nb.select()) == 0 else canvas2.yview_scroll(1, "units"))
    canvas1.bind('<Configure>', lambda e: canvas1.itemconfig(canvas1.create_window((0, 0), window=package_frame1, anchor='nw'), width=e.width))
    canvas2.bind('<Configure>', lambda e: canvas2.itemconfig(canvas2.create_window((0, 0), window=package_frame2, anchor='nw'), width=e.width))
    def search1_handler(e):
        global search_after_id1
        if search_after_id1:
            root.after_cancel(search_after_id1)
        search_after_id1 = root.after(300, refresh_lists)
    def search2_handler(e):
        global search_after_id2
        if search_after_id2:
            root.after_cancel(search_after_id2)
        search_after_id2 = root.after(300, refresh_lists)
    search_entry1.bind('<KeyRelease>', search1_handler)
    search_entry2.bind('<KeyRelease>', search2_handler)
    root.after(100, lambda: refresh_adb(show_popup=False))

def create_display_tab(tab):
    global res_original_label, res_current_label, dpi_original_label, dpi_current_label, fps_system_label, fps_user_label
    style = ttk.Style()
    style.configure("Red.TButton", foreground="red")
    style.configure("Green.TButton", foreground="green")
    frame = ttk.Frame(tab)
    frame.pack(expand=True, fill='both', padx=10, pady=10)
    res_frame = ttk.Frame(frame)
    res_frame.pack(expand=True, pady=10)
    ttk.Label(res_frame, text="Resolution:", anchor='center').pack(anchor='center')
    original_res, current_res = get_resolution()
    res_original_label = ttk.Label(res_frame, text=f"Original: {original_res}", anchor='center')
    res_current_label = ttk.Label(res_frame, text=f"Current: {current_res}", anchor='center')
    res_original_label.pack(anchor='center', pady=2)
    res_current_label.pack(anchor='center', pady=2)
    res_input_frame = ttk.Frame(res_frame)
    res_input_frame.pack(anchor='center', pady=5)
    width_entry = ttk.Entry(res_input_frame, width=10)
    width_entry.pack(side='left')
    ttk.Label(res_input_frame, text=" x ").pack(side='left')
    height_entry = ttk.Entry(res_input_frame, width=10)
    height_entry.pack(side='left')
    res_button_frame = ttk.Frame(res_frame)
    res_button_frame.pack(anchor='center', pady=5)
    ttk.Button(res_button_frame, text="Apply", command=lambda: set_resolution(width_entry.get(), height_entry.get()), style="Red.TButton").pack(side='left', padx=5)
    ttk.Button(res_button_frame, text="Reset", command=reset_resolution, style="Green.TButton").pack(side='left', padx=5)
    dpi_frame = ttk.Frame(frame)
    dpi_frame.pack(expand=True, pady=10)
    ttk.Label(dpi_frame, text="DPI:", anchor='center').pack(anchor='center')
    original_dpi, current_dpi = get_dpi()
    dpi_original_label = ttk.Label(dpi_frame, text=f"Original: {original_dpi}", anchor='center')
    dpi_current_label = ttk.Label(dpi_frame, text=f"Current: {current_dpi}", anchor='center')
    dpi_original_label.pack(anchor='center', pady=2)
    dpi_current_label.pack(anchor='center', pady=2)
    dpi_input_frame = ttk.Frame(dpi_frame)
    dpi_input_frame.pack(anchor='center', pady=5)
    dpi_entry = ttk.Entry(dpi_input_frame, width=10)
    dpi_entry.pack(side='left')
    dpi_button_frame = ttk.Frame(dpi_frame)
    dpi_button_frame.pack(anchor='center', pady=5)
    ttk.Button(dpi_button_frame, text="Apply", command=lambda: set_dpi(dpi_entry.get()), style="Red.TButton").pack(side='left', padx=5)
    ttk.Button(dpi_button_frame, text="Reset", command=reset_dpi, style="Green.TButton").pack(side='left', padx=5)
    fps_frame = ttk.Frame(frame)
    fps_frame.pack(expand=True, pady=10)
    ttk.Label(fps_frame, text="FPS:", anchor='center').pack(anchor='center')
    fps_system_label = ttk.Label(fps_frame, text=f"System: {get_fps()}", anchor='center')
    fps_system_label.pack(anchor='center', pady=2)
    fps_user_label = ttk.Label(fps_frame, text=f"User: {get_user_fps()}", anchor='center')
    fps_user_label.pack(anchor='center', pady=2)
    fps_input_frame = ttk.Frame(fps_frame)
    fps_input_frame.pack(anchor='center', pady=5)
    fps_entry = ttk.Entry(fps_input_frame, width=10)
    fps_entry.pack(side='left')
    fps_button_frame = ttk.Frame(fps_frame)
    fps_button_frame.pack(anchor='center', pady=5)
    ttk.Button(fps_button_frame, text="Apply", command=lambda: apply_fps(fps_entry.get()), style="Red.TButton").pack(side='left', padx=5)
    ttk.Button(fps_button_frame, text="Reset", command=lambda: apply_fps("60", reset=True), style="Green.TButton").pack(side='left', padx=5)

def create_device_info_tab(tab):
    global device_info_labels
    frame = ttk.Frame(tab)
    frame.pack(expand=True, fill='both', padx=10, pady=10)
    brand, model, code, version = get_device_info()
    kernel = get_kernel()
    root_status = check_root()
    bootloader_status = check_bootloader()
    device_info_labels = []
    device_info_labels.append(ttk.Label(frame, text=f"Brand: {brand}", anchor='center'))
    device_info_labels[0].pack(anchor='center', pady=2)
    device_info_labels.append(ttk.Label(frame, text=f"Model: {model}", anchor='center'))
    device_info_labels[1].pack(anchor='center', pady=2)
    device_info_labels.append(ttk.Label(frame, text=f"Code: {code}", anchor='center'))
    device_info_labels[2].pack(anchor='center', pady=2)
    device_info_labels.append(ttk.Label(frame, text=f"Firmware: {version}", anchor='center'))
    device_info_labels[3].pack(anchor='center', pady=2)
    device_info_labels.append(ttk.Label(frame, text=f"Kernel: {kernel}", anchor='center'))
    device_info_labels[4].pack(anchor='center', pady=2)
    root_frame = ttk.Frame(frame)
    root_frame.pack(anchor='center', pady=2)
    ttk.Label(root_frame, text="Rooted? ", anchor='center').pack(side='left')
    root_color = "red" if root_status == "Yes" else "green" if root_status == "No" else "black"
    device_info_labels.append(ttk.Label(root_frame, text=root_status, foreground=root_color))
    device_info_labels[5].pack(side='left')
    bootloader_frame = ttk.Frame(frame)
    bootloader_frame.pack(anchor='center', pady=2)
    ttk.Label(bootloader_frame, text="Unlocked? ", anchor='center').pack(side='left')
    bootloader_color = "red" if bootloader_status == "Yes" else "green" if bootloader_status == "No" else "black"
    device_info_labels.append(ttk.Label(bootloader_frame, text=bootloader_status, foreground=bootloader_color))
    device_info_labels[6].pack(side='left')
    ttk.Label(frame, text="", anchor='center').pack(anchor='center', pady=5)
    ttk.Label(frame, text="Made with Love", anchor='center').pack(anchor='center', pady=2)
    telegram_label = ttk.Label(frame, text="t.me/sickseiha", anchor='center', foreground="blue", cursor="hand2")
    telegram_label.pack(anchor='center', pady=2)
    telegram_label.bind("<Button-1>", lambda e: open_telegram())
    ttk.Label(frame, text="GitHub Repositories", anchor='center').pack(anchor='center', pady=2)
    github_label = ttk.Label(frame, text="github.com/sickseiha/Mi_Adb_Kit", anchor='center', foreground="blue", cursor="hand2")
    github_label.pack(anchor='center', pady=2)
    github_label.bind("<Button-1>", lambda e: open_github())

if not check_adb_installed():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Error", "ADB not found. Please install ADB and ensure it is added to your system PATH.")
    root.destroy()
    sys.exit(1)

root = tk.Tk()
root.title("Mi Adb Kit")
root.geometry("800x600")
nb = ttk.Notebook(root)
nb.pack(expand=True, fill='both')
tab1 = ttk.Frame(nb)
nb.add(tab1, text="Apps")
create_debloater_tab(tab1)
tab2 = ttk.Frame(nb)
nb.add(tab2, text="Display")
create_display_tab(tab2)
tab3 = ttk.Frame(nb)
nb.add(tab3, text="Info")
create_device_info_tab(tab3)
root.after(2000, periodic_check)
root.mainloop()
