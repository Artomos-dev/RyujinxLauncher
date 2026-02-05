import sys
import os
import json
import subprocess
import tkinter as tk
from tkinter import messagebox
import ctypes
import xml.etree.ElementTree as ET
import copy

# --- 0. CONFIGURATION ---
DEV_MODE_PATH = r"D:\Setups\Nintendo Switch Emulator & Roms\Ryujinx" 

# --- 1. HI-DPI FIX ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except: pass

# --- 2. SETUP ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(DEV_MODE_PATH):
    # print(f"🔧 DEV MODE: pointing to {DEV_MODE_PATH}")
    base_path = DEV_MODE_PATH
else:
    base_path = current_script_dir

os.environ["PYSDL2_DLL_PATH"] = base_path

# Path Logic
path_config_file = os.path.join(current_script_dir, "RyujinxPath.config")
ryujinx_dir = base_path 

if os.path.exists(path_config_file):
    try:
        with open(path_config_file, "r") as f:
            custom_path = f.readline().strip().replace('"', '') 
            if os.path.exists(custom_path):
                ryujinx_dir = custom_path
    except: pass

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

# Driver Logic
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

driver_path = os.path.join(ryujinx_dir, lib_name)
if not os.path.exists(driver_path):
    driver_path = os.path.join(current_script_dir, lib_name)

try:
    import sdl2
    import sdl2.ext
except ImportError:
    messagebox.showerror("Error", "PySDL2 not installed.\nRun: pip install pysdl2")
    sys.exit(1)

# --- MAPPING FIX: A=A, B=B ---
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
COLOR_BG_CARD = "#1A1A1A"       # Empty/Active Card BG (Dark Gray)
COLOR_NEON_BLUE = "#0AB9E6"     # Neon Blue (Border / Name)
COLOR_NEON_RED = "#FF3C28"      # Neon Red (Disconnect)
COLOR_TEXT_WHITE = "#EDEDED"
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
        self.assignments = [] 
        self.hardware_map = {} 
        self.alert_mode = None 
        self.alert_frame = None

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
            
            # Status Label (Center - for "Waiting" or "Name")
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

        # Define the gap size (Approx 2 spaces + half the width of the separator)
        gap_offset = int(15 * s)

        # 1. DEFINE WIDGETS (Do not pack them)
        self.separator_text = tk.Label(self.footer_frame, text=separator_text, font=("Segoe UI", int(14*s), "bold"), bg="#111111", fg=COLOR_TEXT_WHITE)
        self.launch_text = tk.Label(self.footer_frame, text=launch_text, font=("Segoe UI", int(14*s), "bold"), bg="#111111", fg=COLOR_TEXT_WHITE)
        self.quit_text = tk.Label(self.footer_frame, text=quit_text, font=("Segoe UI", int(14*s), "bold"), bg="#111111", fg=COLOR_TEXT_WHITE)

        # 2. PLACE SEPARATOR (Exact Center)
        # rely=0.5 puts it vertically in the middle of the footer
        self.separator_text.place(relx=0.5, rely=0.5, anchor="center")

        # 3. PLACE LAUNCH TEXT (Left of Center)
        # anchor="e" (East) means the Right side of the text touches the coordinate.
        # x=-gap_offset shifts it slightly left to create the space.
        self.launch_text.place(relx=0.5, rely=0.5, anchor="e", x=-gap_offset)

        # 4. PLACE QUIT TEXT (Right of Center)
        # anchor="w" (West) means the Left side of the text touches the coordinate.
        # x=gap_offset shifts it slightly right to create the space.
        self.quit_text.place(relx=0.5, rely=0.5, anchor="w", x=gap_offset)


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

    # --- KEYBOARD HANDLERS ---
    def handle_enter_key(self):
        if self.alert_mode == "LAUNCH": self.force_launch()
        elif self.alert_mode == "EXIT": self.root.destroy()

    def handle_esc_key(self):
        if self.alert_mode: self.close_alert()
        else: self.show_exit_confirmation()

    def update_loop(self):
        num_joysticks = sdl2.SDL_NumJoysticks()
        guid_counters = {} 
        self.hardware_map.clear()
        
        for i in range(num_joysticks):
            if not sdl2.SDL_IsGameController(i): continue
            ctrl = sdl2.SDL_GameControllerOpen(i)
            if ctrl:
                joy = sdl2.SDL_GameControllerGetJoystick(ctrl)
                instance_id = sdl2.SDL_JoystickInstanceID(joy)
                if instance_id not in self.controllers:
                    self.controllers[instance_id] = ctrl
                
                raw_name = sdl2.SDL_GameControllerName(ctrl).decode()
                guid_obj = sdl2.SDL_JoystickGetGUID(joy)
                psz_guid = (ctypes.c_char * 33)()
                sdl2.SDL_JoystickGetGUIDString(guid_obj, psz_guid, 33)
                raw_guid_str = psz_guid.value.decode()
                base_guid = self.ryujinx_guid_fix(raw_guid_str)
                current_idx = guid_counters.get(base_guid, 0)
                final_hw_id = f"{current_idx}-{base_guid}"
                final_hw_name = f"{raw_name} ({current_idx})"
                
                self.hardware_map[instance_id] = (final_hw_id, final_hw_name)
                guid_counters[base_guid] = current_idx + 1

        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                if self.alert_mode:
                    if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                        if self.alert_mode == "LAUNCH": self.force_launch()
                        elif self.alert_mode == "EXIT": self.root.destroy()
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                        self.close_alert()
                else:
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
        for assigned_instance, _, _ in self.assignments:
            if assigned_instance == instance_id: return 
        if len(self.assignments) >= 8: return 

        if instance_id in self.hardware_map:
            ryujinx_id, display_name = self.hardware_map[instance_id]
            self.assignments.append((instance_id, ryujinx_id, display_name))
            self.refresh_grid()

    def remove_player(self, instance_id):
        found_index = -1
        for i, (assigned_instance, _, _) in enumerate(self.assignments):
            if assigned_instance == instance_id:
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
                _, _, display_name = self.assignments[i]
                
                # Active: Blue Border, Dark BG
                card.config(bg=COLOR_BG_CARD, highlightbackground=COLOR_NEON_BLUE, highlightcolor=COLOR_NEON_BLUE)
                
                # P# Label
                lbl_num.config(bg=COLOR_BG_CARD, fg=COLOR_NEON_BLUE)
                
                # Name (Centered Top Middle)
                short_name = display_name
                if len(short_name) > 25: short_name = short_name[:23] + ".."
                
                # Move Name Up (rely=0.4) and make it Big & Blue
                lbl_status.place(relx=0.5, rely=0.25, anchor="center")
                lbl_status.config(text=short_name, bg=COLOR_BG_CARD, fg=COLOR_NEON_BLUE, font=("Segoe UI", int(12*s), "bold"))
                
                # Disconnect (Centered Bottom)
                lbl_disc.place(relx=0.5, rely=0.75, anchor="center")
                lbl_disc.config(bg=COLOR_BG_CARD, fg=COLOR_NEON_RED)
                
            else:
                # --- INACTIVE SLOT ---
                # Inactive: Dark Border (Invisible)
                card.config(bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_CARD, highlightcolor=COLOR_BG_CARD)
                
                # P# Label
                lbl_num.config(bg=COLOR_BG_CARD, fg="#444444")
                
                # Status Label (Centered Middle)
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

    def close_alert(self):
        self.alert_mode = None
        if self.alert_frame:
            self.alert_frame.destroy()
            self.alert_frame = None

    def save_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f: data = json.load(f)
        except: return

        new_input = []
        for i in range(len(self.assignments)):
            _, ryujinx_id, display_name = self.assignments[i]
            entry = copy.deepcopy(self.master_template)
            entry["id"] = ryujinx_id 
            entry["name"] = display_name
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
        self.root.destroy()
        
        exe_path = os.path.join(ryujinx_dir, TARGET_EXE)
        if not os.path.exists(exe_path):
             exe_path = os.path.join(os.path.dirname(ryujinx_dir), TARGET_EXE)

        if os.path.exists(exe_path):
            try:
                cmd_args = [exe_path] + sys.argv[1:]
                subprocess.Popen(cmd_args)
            except Exception as e:
                messagebox.showerror("Launch Error", f"Failed to start Ryujinx.\n{e}")
        else:
            messagebox.showerror("Missing File", f"Could not find {TARGET_EXE}")
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = RyujinxLauncherApp(root)
    root.mainloop()