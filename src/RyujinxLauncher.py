import sys
import os
import json
import subprocess
import tkinter as tk
from tkinter import messagebox
import ctypes
import xml.etree.ElementTree as ET
import copy
import re
import time

# --- 1. HI-DPI FIX ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except: pass

# --- 2. SETUP & PATH LOGIC ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
base_path = current_script_dir

# Default to current directory
ryujinx_dir = base_path 

# 1. READ CONFIG FIRST
path_config_file = os.path.join(current_script_dir, "RyujinxPath.config")
if os.path.exists(path_config_file):
    try:
        with open(path_config_file, "r") as f:
            custom_path = f.readline().strip().replace('"', '') 
            if os.path.exists(custom_path):
                ryujinx_dir = custom_path
    except: pass

# 2. NOW TELL PYSDL2 WHERE TO LOOK
# We point it to the Ryujinx directory we just found, NOT just the script dir
os.environ["PYSDL2_DLL_PATH"] = ryujinx_dir

# --- 3. PLATFORM CONFIG ---
if sys.platform == "win32":
    DEFAULT_LIB = "SDL2.dll"
    TARGET_EXE = "Ryujinx.exe"
    portable_config = os.path.join(ryujinx_dir, "portable", "Config.json")
    appdata_config = os.path.join(os.getenv('APPDATA'), "Ryujinx", "Config.json")

    if os.path.exists(portable_config): CONFIG_FILE = portable_config
    elif os.path.exists(os.path.join(ryujinx_dir, "Config.json")): CONFIG_FILE = os.path.join(ryujinx_dir, "Config.json")
    else: CONFIG_FILE = appdata_config
elif sys.platform == "darwin": 
    DEFAULT_LIB = "libSDL2.dylib"
    TARGET_EXE = "Ryujinx"
    CONFIG_FILE = os.path.expanduser("~/.config/Ryujinx/Config.json")
else: 
    DEFAULT_LIB = "libSDL2-2.0.so.0"
    TARGET_EXE = "Ryujinx"
    CONFIG_FILE = os.path.expanduser("~/.config/Ryujinx/Config.json")

# --- 4. DRIVER CHECK ---
# (PySDL2 will now auto-find the DLL because of the environ variable above,
# but we keep this XML logic just to find the library name if needed)
xml_config_path = os.path.join(ryujinx_dir, "Ryujinx.SDL2.Common.dll.config")
lib_name = None
if os.path.exists(xml_config_path):
    try:
        tree = ET.parse(xml_config_path)
        root = tree.getroot()
        current_os_xml = {"win32": "windows", "darwin": "osx", "linux": "linux"}.get(sys.platform, "linux")
        for child in root.findall('dllmap'):
            if child.get('dll') == "SDL2" and child.get('os') == current_os_xml:
                lib_name = child.get('target')
                break
    except: pass
if not lib_name: lib_name = DEFAULT_LIB

try:
    import sdl2
    import sdl2.ext
except ImportError:
    messagebox.showerror("Error", "PySDL2 not installed.\nRun: pip install pysdl2")
    sys.exit(1)
except Exception as e:
    # If it still fails, it means the DLL is missing from the Ryujinx folder
    messagebox.showerror("DLL Error", f"Could not find {lib_name} in:\n{ryujinx_dir}\n\nError: {e}")
    sys.exit(1)

# --- MAPPING TEMPLATE (A=A, B=B) ---
FALLBACK_TEMPLATE = {
    "version": 1, "backend": "GamepadSDL2", "id": "", "name": "", "controller_type": "ProController", "player_index": "",
    "deadzone_left": 0.1, "deadzone_right": 0.1, "range_left": 1, "range_right": 1, "trigger_threshold": 0.5,
    "left_joycon_stick": {"joystick": "Left", "invert_stick_x": False, "invert_stick_y": False, "rotate90_cw": False, "stick_button": "LeftStick"},
    "right_joycon_stick": {"joystick": "Right", "invert_stick_x": False, "invert_stick_y": False, "rotate90_cw": False, "stick_button": "RightStick"},
    "motion": {"motion_backend": "GamepadDriver", "sensitivity": 100, "gyro_deadzone": 1, "enable_motion": True},
    "rumble": {"strong_rumble": 1, "weak_rumble": 1, "enable_rumble": True},
    "led": {"enable_led": False, "turn_off_led": False, "use_rainbow": False, "led_color": 0},
    "left_joycon": {
        "button_minus": "Back", 
        "button_l": "LeftShoulder", 
        "button_zl": "LeftTrigger", 
        "button_sl": "SingleLeftTrigger0", 
        "button_sr": "SingleRightTrigger0", 
        "dpad_up": "DpadUp", 
        "dpad_down": "DpadDown", 
        "dpad_left": "DpadLeft", 
        "dpad_right": "DpadRight"
    },
    "right_joycon": {
        "button_plus": "Start", 
        "button_r": "RightShoulder", 
        "button_zr": "RightTrigger", 
        "button_sl": "SingleLeftTrigger1", 
        "button_sr": "SingleRightTrigger1", 
        "button_x": "X", 
        "button_b": "B", 
        "button_y": "Y", 
        "button_a": "A"
    }
}

# --- SWITCH THEME COLORS ---
COLOR_BG_DARK = "#0F0F0F"       # Main Background
COLOR_BG_CARD = "#1A1A1A"       # Empty/Active Card BG
COLOR_NEON_BLUE = "#0AB9E6"     # Neon Blue (Border / Name)
COLOR_NEON_RED = "#FF3C28"      # Neon Red (Disconnect)
COLOR_TEXT_WHITE = "#EDEDED"    # Soft White
COLOR_TEXT_DIM = "#666666"      # Neutral Gray for Inactive

class RyujinxLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ryujinx Launcher")
        
        self.root.configure(bg=COLOR_BG_DARK) 
        self.root.attributes('-fullscreen', True) 
        
        # KEYBOARD BINDINGS
        self.root.bind("<Return>", lambda e: self.handle_enter_key())
        self.root.bind("<Escape>", lambda e: self.handle_esc_key())
        
        # Scaling
        screen_height = self.root.winfo_screenheight()
        self.scale = max(1.0, screen_height / 1080.0)
        s = self.scale

        try:
            sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
        except Exception as e:
            messagebox.showerror("Driver Error", f"Failed to load SDL2 driver.\n{e}")
        
        self.controllers = {} 
        self.assignments = [] # [(path_str, display_name), ...]
        self.hardware_map = {} # {instance_id: (path_str, display_name)}
        self.alert_mode = None
        self.alert_frame = None
        self.ryujinx_process = None
        self.toast_job = None
        self.returning_to_launcher = False

        self.master_template = self.load_config_data(CONFIG_FILE)
        if self.master_template == FALLBACK_TEMPLATE:
             backup_path = os.path.join(os.path.dirname(CONFIG_FILE), "Config_Main.json")
             if os.path.exists(backup_path):
                 self.master_template = self.load_config_data(backup_path)

        # --- LAYOUT CONTAINER ---
        self.main_container = tk.Frame(root, bg=COLOR_BG_DARK)
        self.main_container.pack(expand=True, fill="both", padx=int(50*s), pady=int(50*s))

        # 1. HEADER
        mode_prefix = "GAME" if len(sys.argv) > 1 else "RYUJINX"
        title_text = f"{mode_prefix} CONTROLLER SETUP"
        
        self.lbl_title = tk.Label(self.main_container, text=title_text, font=("Segoe UI", int(32*s), "bold"), bg=COLOR_BG_DARK, fg=COLOR_TEXT_WHITE)
        self.lbl_title.pack(pady=(int(20*s), int(30*s))) 
        
        # 2. PLAYER GRID
        self.grid_frame = tk.Frame(self.main_container, bg=COLOR_BG_DARK)
        self.grid_frame.pack()
        
        self.slot_cards = []
        for i in range(8):
            row = i // 2  
            col = i % 2   
            
            c_w = int(420 * s)
            c_h = int(90 * s) 
            pad_x = int(20 * s)
            pad_y = int(12 * s)
            
            # Use highlightthickness for the border
            card = tk.Frame(self.grid_frame, bg=COLOR_BG_CARD, width=c_w, height=c_h, 
                            highlightbackground=COLOR_BG_CARD, highlightthickness=int(2*s)) 
            card.pack_propagate(False) 
            card.grid(row=row, column=col, padx=pad_x, pady=pad_y)
            
            # P# Label (Top Left)
            lbl_num = tk.Label(card, text=f"P{i+1}", font=("Segoe UI", int(12*s), "bold"), bg=COLOR_BG_CARD, fg="#444444")
            lbl_num.place(x=int(15*s), y=int(10*s))
            
            # Status Label (Center)
            lbl_status = tk.Label(card, text="PRESS Ⓐ CONNECT", font=("Segoe UI", int(12*s), "bold"), bg=COLOR_BG_CARD, fg=COLOR_TEXT_DIM)
            lbl_status.place(relx=0.5, rely=0.5, anchor="center")
            
            # Disconnect Label (Bottom Middle - Hidden initially)
            lbl_disc = tk.Label(card, text="Ⓑ DISCONNECT", font=("Segoe UI", int(10*s), "bold"), bg=COLOR_BG_CARD, fg=COLOR_NEON_RED)
            
            self.slot_cards.append((card, lbl_num, lbl_status, lbl_disc))

        # 3. SMART FOOTER
        self.footer_frame = tk.Frame(root, bg="#111111", height=int(80*s))
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.pack_propagate(False)

        launch_target = "GAME" if len(sys.argv) > 1 else "RYUJINX"
        separator_text = "|"
        launch_text = f"☰ LAUNCH {launch_target}"
        quit_text = f"⧉ QUIT"

        gap_offset = int(15 * s)

        self.separator_text = tk.Label(self.footer_frame, text=separator_text, font=("Segoe UI", int(14*s), "bold"), bg="#111111", fg=COLOR_TEXT_WHITE)
        self.launch_text = tk.Label(self.footer_frame, text=launch_text, font=("Segoe UI", int(14*s), "bold"), bg="#111111", fg=COLOR_TEXT_WHITE)
        self.quit_text = tk.Label(self.footer_frame, text=quit_text, font=("Segoe UI", int(14*s), "bold"), bg="#111111", fg=COLOR_TEXT_WHITE)

        self.separator_text.place(relx=0.5, rely=0.5, anchor="center")
        self.launch_text.place(relx=0.5, rely=0.5, anchor="e", x=-gap_offset)
        self.quit_text.place(relx=0.5, rely=0.5, anchor="w", x=gap_offset)

        # NEW: Toast Notification Label
        self.lbl_toast = tk.Label(self.main_container, text="", font=("Segoe UI", int(12*s), "bold"), bg=COLOR_BG_DARK, fg=COLOR_NEON_RED)
        self.lbl_toast.place(relx=0.5, rely=0.9, anchor="center")
        self.lbl_toast.place_forget()

        self.update_loop() 

    def load_config_data(self, file_path):
        template = FALLBACK_TEMPLATE
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                if "input_config" in data and isinstance(data["input_config"], list):
                    for entry in data["input_config"]:
                        if entry.get("backend") == "GamepadSDL2" and entry.get("controller_type") == "ProController":
                            template = copy.deepcopy(entry)
                            break
            except: pass
        return template

    def ryujinx_guid_fix(self, raw_hex):
        if len(raw_hex) < 32: return raw_hex 
        bus_id = raw_hex[:2] 
        part1 = f"000000{bus_id}"
        part2 = raw_hex[10:12] + raw_hex[8:10]
        part3 = raw_hex[14:16] + raw_hex[12:14]
        part4_a = raw_hex[16:20]
        part4_b = raw_hex[20:]
        return f"{part1}-{part2}-{part3}-{part4_a}-{part4_b}"

    def show_toast(self, message):
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.lbl_toast.config(text=message)
        self.lbl_toast.place(relx=0.5, rely=0.9, anchor="center")
        self.toast_job = self.root.after(2000, lambda: self.lbl_toast.place_forget())

    # --- KEYBOARD HANDLERS ---
    def handle_enter_key(self):
        if self.alert_mode == "LAUNCH": self.force_launch()
        elif self.alert_mode == "EXIT": self.root.destroy()
        elif self.alert_mode == "KILL_CONFIRM": self.kill_and_quit()

    def handle_esc_key(self):
        if self.alert_mode: self.close_alert()
        else: self.show_exit_confirmation()

    def perform_kill(self):
        if self.ryujinx_process:
            self.ryujinx_process.kill()
        self.root.quit()
        sys.exit()

    # --- NEW HELPERS FOR KILL MENU ---
    def kill_and_quit(self):
        if self.ryujinx_process:
            self.ryujinx_process.kill()
        self.root.quit()
        sys.exit()

    def kill_and_restart(self):
        self.returning_to_launcher = True

        time.sleep(0.1)

        if self.ryujinx_process:
            self.ryujinx_process.kill()
        self.ryujinx_process = None

        # --- RESET STATE ---
        self.assignments = [] # Wipe everything
        self.refresh_grid()
        self.close_alert()
        self.root.deiconify()
        self.root.state('normal') # Ensure window is back
    # ---------------------------------

    def update_loop(self):
        # --- BACKGROUND MONITORING ---
        if self.ryujinx_process and not self.alert_mode:
            if self.ryujinx_process.poll() is not None:
                # Ryujinx closed normally, Reset State
                if self.returning_to_launcher:
                    print("[SYSTEM] Ryujinx Closed. Resetting.")
                    self.assignments = [] # Wipe assignments
                    self.refresh_grid()
                    self.root.deiconify()
                    self.root.state('normal')
                    self.ryujinx_process = None
                else:
                    # Ryujinx closed externally (Quit or Crashed)
                    print("[SYSTEM] Ryujinx Closed Externally. Terminating Launcher.")
                    self.root.quit()
                    sys.exit()

            # --- GLOBAL KILL SWITCH (ANY CONTROLLER) ---
            kill_combo = False
            for ctrl in self.controllers.values():
                if (sdl2.SDL_GameControllerGetButton(ctrl, sdl2.SDL_CONTROLLER_BUTTON_BACK) and
                    sdl2.SDL_GameControllerGetButton(ctrl, sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER) and
                    sdl2.SDL_GameControllerGetButton(ctrl, sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)):
                    kill_combo = True
                    break # Trigger found, stop searching

            if kill_combo:
                self.root.deiconify()
                self.show_alert("KILL_CONFIRM")
                self.root.after(50, self.update_loop)
                return
        # -----------------------------

        num_joysticks = sdl2.SDL_NumJoysticks()
        self.hardware_map.clear()
        
        # Build Map
        for i in range(num_joysticks):
            if not sdl2.SDL_IsGameController(i): continue
            ctrl = sdl2.SDL_GameControllerOpen(i)
            if ctrl:
                joy = sdl2.SDL_GameControllerGetJoystick(ctrl)
                instance_id = sdl2.SDL_JoystickInstanceID(joy)
                if instance_id not in self.controllers:
                    self.controllers[instance_id] = ctrl
                
                raw_name = sdl2.SDL_GameControllerName(ctrl).decode()
                
                # GET HID PATH (The Source of Truth)
                try:
                    path_bytes = sdl2.SDL_GameControllerPath(ctrl)
                    hid_path = path_bytes.decode() if path_bytes else f"UNK_{instance_id}"
                except:
                    hid_path = f"UNK_{instance_id}"

                self.hardware_map[instance_id] = (hid_path, raw_name)

        # --- MENU MODE (ALWAYS ACTIVE) ---
        new_assignments = []
        dropped_names = []

        current_connected_paths = set()
        for inst_id in self.hardware_map:
            path, _ = self.hardware_map[inst_id]
            current_connected_paths.add(path)

        # Remove disconnected, Slide Up
        for path, name in self.assignments:
            if path in current_connected_paths:
                new_assignments.append((path, name))
            else:
                dropped_names.append(name)

        if len(new_assignments) != len(self.assignments):
            self.assignments = new_assignments
            self.refresh_grid()
            if dropped_names:
                self.show_toast(f"⚠ {dropped_names[0]} Disconnected")

        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                if self.alert_mode:
                    if self.alert_mode == "KILL_CONFIRM":
                        if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                            self.kill_and_restart()
                        elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_Y:
                            self.kill_and_quit()
                        elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                            self.close_alert()
                            self.root.withdraw() # Cancel: Go back to hiding
                    else:
                        if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                            if self.alert_mode == "LAUNCH": self.force_launch()
                            elif self.alert_mode == "EXIT": self.root.destroy()
                            elif self.alert_mode == "KILL_CONFIRM": self.perform_kill()
                        elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                            self.close_alert()
                else:
                    if self.ryujinx_process: continue

                    if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                        self.assign_player(event.cbutton.which)
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                        self.remove_player(event.cbutton.which)
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_START:
                        self.check_launch()
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_BACK:
                        self.show_exit_confirmation()

            elif event.type == sdl2.SDL_QUIT:
                self.root.destroy()
        
        self.root.after(50, self.update_loop)

    def assign_player(self, instance_id):
        if instance_id not in self.hardware_map: return

        target_path, display_name = self.hardware_map[instance_id]

        # Check duplicate
        for path, _ in self.assignments:
            if path == target_path: return

        if len(self.assignments) >= 8: return 

        self.assignments.append((target_path, display_name))
        self.refresh_grid()

    def remove_player(self, instance_id):
        if instance_id not in self.hardware_map: return
        target_path, _ = self.hardware_map[instance_id]

        found_index = -1
        for i, (path, _) in enumerate(self.assignments):
            if path == target_path:
                found_index = i
                break
        if found_index != -1:
            self.assignments.pop(found_index)
            self.refresh_grid()

    def refresh_grid(self):
        s = self.scale
        for i in range(8):
            card, lbl_num, lbl_status, lbl_disc = self.slot_cards[i]
            
            if i < len(self.assignments):
                # --- ACTIVE SLOT ---
                _, display_name = self.assignments[i]
                
                # Clean name (remove index for display)
                clean_name = re.sub(r'\s*\(\d+\)$', '', display_name)

                card.config(bg=COLOR_BG_CARD, highlightbackground=COLOR_NEON_BLUE, highlightcolor=COLOR_NEON_BLUE)
                lbl_num.config(bg=COLOR_BG_CARD, fg=COLOR_NEON_BLUE)
                
                lbl_status.place(relx=0.5, rely=0.25, anchor="center")
                lbl_status.config(text=clean_name, bg=COLOR_BG_CARD, fg=COLOR_NEON_BLUE, font=("Segoe UI", int(12*s), "bold"))
                
                lbl_disc.place(relx=0.5, rely=0.75, anchor="center")
                lbl_disc.config(bg=COLOR_BG_CARD, fg=COLOR_NEON_RED)
                
            else:
                # --- INACTIVE SLOT ---
                card.config(bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_CARD, highlightcolor=COLOR_BG_CARD)
                lbl_num.config(bg=COLOR_BG_CARD, fg="#444444")
                
                lbl_status.place(relx=0.5, rely=0.5, anchor="center")
                lbl_status.config(text="PRESS Ⓐ CONNECT", bg=COLOR_BG_CARD, fg=COLOR_TEXT_DIM, font=("Segoe UI", int(12*s), "bold"))
                
                # Hide Disconnect Hint
                lbl_disc.place_forget()

    def check_launch(self):
        if len(self.assignments) == 0:
            self.show_alert("LAUNCH")
        else:
            self.force_launch()

    def show_exit_confirmation(self):
        self.show_alert("EXIT")

    def show_alert(self, mode):
        self.alert_mode = mode
        s = self.scale
        
        self.alert_frame = tk.Frame(self.root, bg="#000000")
        self.alert_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        box_w = int(600 * s)
        box_h = int(320 * s)
        box = tk.Frame(self.alert_frame, bg="#1E1E1E", bd=2, relief="solid")
        box.place(relx=0.5, rely=0.5, anchor="center", width=box_w, height=box_h)
        
        if mode == "LAUNCH":
            launch_target = "GAME" if len(sys.argv) > 1 else "RYUJINX"
            tk.Label(box, text="⚠️ NO CONTROLLERS", font=("Segoe UI", int(26*s), "bold"), bg="#1E1E1E", fg="#FFCC00").pack(pady=(int(40*s), int(10*s)))
            tk.Label(box, text="Ryujinx will launch with default inputs.", font=("Segoe UI", int(14*s)), bg="#1E1E1E", fg="#BBBBBB").pack(pady=int(5*s))
            btn_frame = tk.Frame(box, bg="#1E1E1E")
            btn_frame.pack(pady=int(40*s))
            tk.Label(btn_frame, text=f"Ⓐ LAUNCH {launch_target}", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg=COLOR_NEON_BLUE).pack(side="left", padx=int(20*s))
            tk.Label(btn_frame, text="Ⓑ BACK", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg=COLOR_NEON_RED).pack(side="left", padx=int(20*s))
            
        elif mode == "EXIT":
            tk.Label(box, text="EXIT LAUNCHER?", font=("Segoe UI", int(26*s), "bold"), bg="#1E1E1E", fg=COLOR_TEXT_WHITE).pack(pady=(int(40*s), int(10*s)))
            tk.Label(box, text="Are you sure you want to quit?", font=("Segoe UI", int(14*s)), bg="#1E1E1E", fg="#BBBBBB").pack(pady=int(5*s))
            btn_frame = tk.Frame(box, bg="#1E1E1E")
            btn_frame.pack(pady=int(40*s))
            tk.Label(btn_frame, text="Ⓐ YES", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg=COLOR_NEON_BLUE).pack(side="left", padx=int(20*s))
            tk.Label(btn_frame, text="Ⓑ NO", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg=COLOR_NEON_RED).pack(side="left", padx=int(20*s))

        elif mode == "KILL_CONFIRM":
            tk.Label(box, text="KILL GAME?", font=("Segoe UI", int(26*s), "bold"), bg="#1E1E1E", fg=COLOR_TEXT_WHITE).pack(pady=(int(40*s), int(10*s)))
            tk.Label(box, text="How would you like to proceed?", font=("Segoe UI", int(14*s)), bg="#1E1E1E", fg="#BBBBBB").pack(pady=int(5*s))

            btn_frame = tk.Frame(box, bg="#1E1E1E")
            btn_frame.pack(pady=int(30*s))

            # RESTART (LAUNCHER)
            tk.Label(btn_frame, text="Ⓐ LAUNCHER", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg=COLOR_NEON_BLUE).pack(side="left", padx=int(15*s))
            # EXIT (DESKTOP)
            tk.Label(btn_frame, text="Ⓨ DESKTOP", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg="#FFCC00").pack(side="left", padx=int(15*s))
            # CANCEL
            tk.Label(btn_frame, text="Ⓑ CANCEL", font=("Segoe UI", int(12*s), "bold"), bg="#1E1E1E", fg=COLOR_NEON_RED).pack(side="left", padx=int(15*s))

    def close_alert(self):
        self.alert_mode = None
        if self.alert_frame:
            self.alert_frame.destroy()
            self.alert_frame = None

    def save_config(self):
        # 1. FLUSH AND RESCAN to match OS Order
        for c in self.controllers.values():
            sdl2.SDL_GameControllerClose(c)
        self.controllers.clear()

        sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
        sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)

        # 2. Build New Map from FRESH Scan
        final_hw_list = []
        num = sdl2.SDL_NumJoysticks()
        guid_counters = {}

        for i in range(num):
            if not sdl2.SDL_IsGameController(i): continue
            ctrl = sdl2.SDL_GameControllerOpen(i)
            if ctrl:
                # We need GUID and Path
                joy = sdl2.SDL_GameControllerGetJoystick(ctrl)

                # Get GUID
                guid_obj = sdl2.SDL_JoystickGetGUID(joy)
                psz_guid = (ctypes.c_char * 33)()
                sdl2.SDL_JoystickGetGUIDString(guid_obj, psz_guid, 33)
                raw_guid_str = psz_guid.value.decode()
                base_guid = self.ryujinx_guid_fix(raw_guid_str)

                # Get Path (Key)
                try:
                    p = sdl2.SDL_GameControllerPath(ctrl)
                    path = p.decode() if p else ""
                except: path = ""

                # Calculate Index
                idx = guid_counters.get(base_guid, 0)
                final_id = f"{idx}-{base_guid}"
                guid_counters[base_guid] = idx + 1

                final_hw_list.append({
                    "path": path,
                    "ryu_id": final_id,
                    "name": sdl2.SDL_GameControllerName(ctrl).decode()
                })
                sdl2.SDL_GameControllerClose(ctrl)

        # 3. Match Assignments (Paths) -> New Configs
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f: data = json.load(f)
        except: return

        new_input = []
        for i, (assigned_path, _) in enumerate(self.assignments):
            # Find this path in the FRESH list
            matched_hw = next((x for x in final_hw_list if x["path"] == assigned_path), None)

            if matched_hw:
                entry = copy.deepcopy(self.master_template)
                entry["id"] = matched_hw["ryu_id"]
                entry["name"] = matched_hw["name"]
                entry["player_index"] = f"Player{i+1}"
                entry["backend"] = "GamepadSDL2"
                entry["controller_type"] = "ProController"
                new_input.append(entry)

        data["input_config"] = new_input
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False) 
        except: pass

    def force_launch(self):
        self.save_config()
        self.root.withdraw()
        self.returning_to_launcher = False
        
        exe_path = os.path.join(ryujinx_dir, TARGET_EXE)
        if not os.path.exists(exe_path):
             exe_path = os.path.join(os.path.dirname(ryujinx_dir), TARGET_EXE)

        if os.path.exists(exe_path):
            try:
                cmd_args = [exe_path] + sys.argv[1:]
                self.ryujinx_process = subprocess.Popen(cmd_args)
            except Exception as e:
                messagebox.showerror("Launch Error", f"Failed to start Ryujinx.\n{e}")
                sys.exit()
        else:
            messagebox.showerror("Missing File", f"Could not find {TARGET_EXE}")
            sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = RyujinxLauncherApp(root)
    root.mainloop()