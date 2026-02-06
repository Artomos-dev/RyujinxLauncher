"""
Ryujinx Launcher
Ryujinx Gamepad Launcher is standalone middleware designed to eliminate the Keyboard and Mouse dependency
in HTPC and Couch Gaming setups. It solves the frustration of shifting controller IDs by allowing you to
visually assign physical controllers to Player Slots (1-8) using only a gamepad immediately before launch.
With features like hot-plug detection and a controller-based "Kill Combo" for exiting, it maintains complete
immersion by removing the need to ever reach for a Mouse/Keyboard to fix configs or close the emulator.

Features:
- Gamepad-First UI: Assign up to 8 controllers without touching a Keyboard or Mouse.
- Visual Identity: Controllers are assigned persistent, unique pastel colors for easy identification.
- Joy-Con Style Interface: Clean, high-contrast UI with "Rail" indicators for active status.
- Hot-Plug Support: Connect/disconnect controllers in real-time with automatic reconnection.
- Emergency Kill Combo: Hold [Back + L + R] on *any* controller to force-kill the emulator if it freezes.
- Smart Persistence: Uses HID paths to remember specific controllers even if they reconnect in a different order.
- Frontend Ready: Seamlessly passes command-line arguments (Playnite, LaunchBox, Moonlight, Artemis).
- Portable: Single-file EXE support with embedded assets and smart directory detection.
- Cross-Platform: Compatible with Windows, Linux, and macOS.

Author: Artomos
License: CC BY-NC 4.0 (Attribution-NonCommercial)
Tested with: Ryujinx 1.3.3(Windows) (Feb 2026)
"""

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
import random

# ============================================================================
# SECTION 1: HI-DPI DISPLAY SUPPORT
# ============================================================================
# Enables proper scaling on high-resolution displays (4K, 1440p)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1+
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Windows Vista-8
    except:
        pass  # Non-Windows or unsupported

# ============================================================================
# SECTION 2: PATH DETECTION & CONFIGURATION
# ============================================================================
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        icon_path = sys._MEIPASS
    except Exception:
        icon_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(icon_path, relative_path)

# 1. Determine the "Base Path" (Where the script or .exe is located)
if getattr(sys, 'frozen', False):
    # Running as compiled .exe (PyInstaller)
    base_path = os.path.dirname(sys.executable)
else:
    # Running as .py script
    base_path = os.path.dirname(os.path.abspath(__file__))

# 2. Set Default Ryujinx Directory (Same as launcher)
ryujinx_dir = base_path

# 3. Check for Custom Path Override (RyujinxPath.config)
# We look for this file NEXT TO the launcher/script
path_config_file = os.path.join(base_path, "RyujinxPath.config")

if os.path.exists(path_config_file):
    try:
        with open(path_config_file, "r") as f:
            # clean up quotes and whitespace
            custom_path = f.readline().strip().replace('"', '')

            # verify the path actually exists before using it
            if os.path.exists(custom_path):
                ryujinx_dir = custom_path
    except Exception as e:
        # If reading fails, silently fall back to default (base_path)
        pass

# Point PySDL2 to the Ryujinx directory for SDL2.dll/dylib/so
os.environ["PYSDL2_DLL_PATH"] = ryujinx_dir

# ============================================================================
# SECTION 3: PLATFORM-SPECIFIC CONFIGURATION
# ============================================================================
# Determine correct file paths and executable names based on OS
if sys.platform == "win32":
    DEFAULT_LIB = "SDL2.dll"
    TARGET_EXE = "Ryujinx.exe"

    # Config priority: portable > local > AppData
    portable_config = os.path.join(ryujinx_dir, "portable", "Config.json")
    appdata_config = os.path.join(os.getenv('APPDATA'), "Ryujinx", "Config.json")

    if os.path.exists(portable_config):
        CONFIG_FILE = portable_config
    elif os.path.exists(os.path.join(ryujinx_dir, "Config.json")):
        CONFIG_FILE = os.path.join(ryujinx_dir, "Config.json")
    else:
        CONFIG_FILE = appdata_config

elif sys.platform == "darwin":  # macOS
    DEFAULT_LIB = "libSDL2.dylib"
    TARGET_EXE = "Ryujinx"
    CONFIG_FILE = os.path.expanduser("~/.config/Ryujinx/Config.json")

else:  # Linux
    DEFAULT_LIB = "libSDL2-2.0.so.0"
    TARGET_EXE = "Ryujinx"
    CONFIG_FILE = os.path.expanduser("~/.config/Ryujinx/Config.json")

# ============================================================================
# SECTION 4: SDL2 DRIVER DETECTION
# ============================================================================
# Read Ryujinx's XML config to find the correct SDL2 library name
xml_config_path = os.path.join(ryujinx_dir, "Ryujinx.SDL2.Common.dll.config")
lib_name = None

if os.path.exists(xml_config_path):
    try:
        tree = ET.parse(xml_config_path)
        root = tree.getroot()
        current_os_xml = {
            "win32": "windows",
            "darwin": "osx",
            "linux": "linux"
        }.get(sys.platform, "linux")

        for child in root.findall('dllmap'):
            if child.get('dll') == "SDL2" and child.get('os') == current_os_xml:
                lib_name = child.get('target')
                break
    except:
        pass  # XML parsing failed, use default

if not lib_name:
    lib_name = DEFAULT_LIB

# ============================================================================
# SECTION 5: IMPORT SDL2 LIBRARY
# ============================================================================
try:
    import sdl2
    import sdl2.ext
except ImportError:
    messagebox.showerror(
        "Error",
        "PySDL2 not installed.\nRun: pip install pysdl2"
    )
    sys.exit(1)
except Exception as e:
    messagebox.showerror(
        "DLL Error",
        f"Could not find {lib_name} in:\n{ryujinx_dir}\n\nError: {e}"
    )
    sys.exit(1)

# ============================================================================
# SECTION 6: DEFAULT CONTROLLER MAPPING TEMPLATE
# ============================================================================
# Fallback template if no existing config found (matches Nintendo Pro Controller layout)
FALLBACK_TEMPLATE = {
    "version": 1,
    "backend": "GamepadSDL2",
    "id": "",
    "name": "",
    "controller_type": "ProController",
    "player_index": "",
    "deadzone_left": 0.1,
    "deadzone_right": 0.1,
    "range_left": 1,
    "range_right": 1,
    "trigger_threshold": 0.5,
    "left_joycon_stick": {
        "joystick": "Left",
        "invert_stick_x": False,
        "invert_stick_y": False,
        "rotate90_cw": False,
        "stick_button": "LeftStick"
    },
    "right_joycon_stick": {
        "joystick": "Right",
        "invert_stick_x": False,
        "invert_stick_y": False,
        "rotate90_cw": False,
        "stick_button": "RightStick"
    },
    "motion": {
        "motion_backend": "GamepadDriver",
        "sensitivity": 100,
        "gyro_deadzone": 1,
        "enable_motion": True
    },
    "rumble": {
        "strong_rumble": 1,
        "weak_rumble": 1,
        "enable_rumble": True
    },
    "led": {
        "enable_led": False,
        "turn_off_led": False,
        "use_rainbow": False,
        "led_color": 0
    },
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

# ============================================================================
# SECTION 7: VISUAL THEME (NINTENDO SWITCH INSPIRED)
# ============================================================================
COLOR_BG_DARK = "#0F0F0F"       # Main background
COLOR_BG_CARD = "#1A1A1A"       # Card background (empty/active slots)
COLOR_NEON_BLUE = "#0AB9E6"     # Highlight color (active controllers)
COLOR_NEON_RED = "#FF3C28"      # Warning color (disconnect/remove)
COLOR_TEXT_WHITE = "#EDEDED"    # Primary text
COLOR_TEXT_DIM = "#666666"      # Inactive/placeholder text

PASTEL_POOL = [
    "#00FF00", "#32CD32", "#98FB98", "#006400", "#FFFF00",  # Lime, LimeGreen, Mint, Forest, Yellow
    "#FFD700", "#F0E68C", "#FFA500", "#FF8C00", "#D2691E",  # Gold, Khaki, Orange, DarkOrange, Chocolate
    "#FFDAB9", "#800080", "#DA70D6", "#9400D3", "#FF00FF",  # Peach, Purple, Orchid, Violet, Magenta
    "#FF69B4", "#FFC0CB", "#FFFFFF", "#00FFFF", "#808080"   # HotPink, SoftPink, White, Cyan, Gray
]

# ============================================================================
# SECTION 8: MAIN APPLICATION CLASS
# ============================================================================
class RyujinxLauncherApp:
    """
    Main application class for the Ryujinx Gamepad Launcher.

    Manages controller detection, assignment, and Ryujinx process lifecycle.
    """

    def __init__(self, root):
        """Initialize the launcher UI and controller subsystem."""
        self.root = root
        self.root.title("Ryujinx Launcher")
        self.root.configure(bg=COLOR_BG_DARK)
        self.root.attributes('-fullscreen', True)

        # Update 1: Define the specific filenames from your assets folder
        ico_path = resource_path(os.path.join("assets", "RyujinxLauncherIcon.ico"))
        png_path = resource_path(os.path.join("assets", "RyujinxLauncherPNG.png"))

        # Update 2: Robust Icon Loading
        # Windows prefers .ico for the taskbar
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(default=ico_path)
            except Exception:
                pass

        # Linux/macOS often prefer .png (iconphoto)
        # We try this if the .ico didn't work, or as a secondary measure
        elif os.path.exists(png_path):
            try:
                # Use the PNG for the window icon if on Linux/macOS
                icon_img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, icon_img)
            except Exception:
                pass

        # Keyboard shortcuts for accessibility
        self.root.bind("<Return>", lambda e: self.handle_enter_key())
        self.root.bind("<Escape>", lambda e: self.handle_esc_key())

        # Calculate UI scaling based on screen resolution
        screen_height = self.root.winfo_screenheight()
        self.scale = max(1.0, screen_height / 1080.0)
        s = self.scale

        # Initialize SDL2 controller subsystem
        try:
            sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
        except Exception as e:
            messagebox.showerror("Driver Error", f"Failed to load SDL2 driver.\n{e}")

        # State management
        self.controllers = {}               # {instance_id: SDL_GameController}
        self.assignments = []               # [(hid_path, display_name), ...] - Player order
        self.hardware_map = {}              # {instance_id: (hid_path, display_name)} - Currently connected
        self.color_pool = list(PASTEL_POOL) # Copy the pool to modify it locally
        random.shuffle(self.color_pool)     # Shuffle the color pool
        self.hid_colors = {}                # Dictionary to remember {hid_path: color_hex}
        self.alert_mode = None              # Current alert type (if any)
        self.alert_frame = None             # Alert dialog container
        self.ryujinx_process = None         # Ryujinx subprocess handle
        self.toast_job = None               # Toast notification timer
        self.returning_to_launcher = False  # Flag for kill→restart flow

        # Load existing controller mapping template from Config.json
        self.master_template = self.load_config_data(CONFIG_FILE)
        if self.master_template == FALLBACK_TEMPLATE:
            # Try backup config if available
            backup_path = os.path.join(os.path.dirname(CONFIG_FILE), "Config_Main.json")
            if os.path.exists(backup_path):
                self.master_template = self.load_config_data(backup_path)

        # ====================================================================
        # UI LAYOUT CONSTRUCTION
        # ====================================================================
        self.main_container = tk.Frame(root, bg=COLOR_BG_DARK)
        self.main_container.pack(expand=True, fill="both", padx=int(50*s), pady=int(50*s))

        # Header: Title
        mode_prefix = "GAME" if len(sys.argv) > 1 else "RYUJINX"
        title_text = f"{mode_prefix} CONTROLLER SETUP"

        self.lbl_title = tk.Label(
            self.main_container,
            text=title_text,
            font=("Segoe UI", int(32*s), "bold"),
            bg=COLOR_BG_DARK,
            fg=COLOR_TEXT_WHITE
        )
        self.lbl_title.pack(pady=(int(20*s), int(30*s)))

        # Player grid: 8 slots in 4x2 layout
        self.grid_frame = tk.Frame(self.main_container, bg=COLOR_BG_DARK)
        self.grid_frame.pack()

        self.slot_cards = []
        for i in range(8):
            row = i // 2  # 0-3
            col = i % 2   # 0-1

            c_w = int(420 * s)
            c_h = int(90 * s)
            pad_x = int(20 * s)
            pad_y = int(12 * s)

            # Card frame with border highlight
            card = tk.Frame(
                self.grid_frame,
                bg=COLOR_BG_CARD,
                width=c_w,
                height=c_h,
                highlightbackground=COLOR_BG_CARD,
                highlightthickness=int(2*s)
            )
            card.pack_propagate(False)
            card.grid(row=row, column=col, padx=pad_x, pady=pad_y)

            # Player number label (top-left corner)
            lbl_num = tk.Label(
                card,
                text=f"P{i+1}",
                font=("Segoe UI", int(12*s), "bold"),
                bg=COLOR_BG_CARD,
                fg="#444444"
            )
            lbl_num.place(x=int(15*s), y=int(10*s))

            # Status/name label (center)
            lbl_status = tk.Label(
                card,
                text="PRESS Ⓐ CONNECT",
                font=("Segoe UI", int(12*s), "bold"),
                bg=COLOR_BG_CARD,
                fg=COLOR_TEXT_DIM
            )
            lbl_status.place(relx=0.5, rely=0.5, anchor="center")

            # Disconnect hint label (bottom, initially hidden)
            lbl_disc = tk.Label(
                card,
                text="Ⓑ DISCONNECT",
                font=("Segoe UI", int(10*s), "bold"),
                bg=COLOR_BG_CARD,
                fg=COLOR_NEON_RED
            )

            self.slot_cards.append((card, lbl_num, lbl_status, lbl_disc))

        # Footer: Button hints
        self.footer_frame = tk.Frame(root, bg="#111111", height=int(80*s))
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.pack_propagate(False)

        launch_target = "GAME" if len(sys.argv) > 1 else "RYUJINX"
        separator_text = "|"
        launch_text = f"☰ LAUNCH {launch_target}"
        quit_text = f"⧉ QUIT"

        gap_offset = int(15 * s)

        self.separator_text = tk.Label(
            self.footer_frame,
            text=separator_text,
            font=("Segoe UI", int(14*s), "bold"),
            bg="#111111",
            fg=COLOR_TEXT_WHITE
        )
        self.launch_text = tk.Label(
            self.footer_frame,
            text=launch_text,
            font=("Segoe UI", int(14*s), "bold"),
            bg="#111111",
            fg=COLOR_TEXT_WHITE
        )
        self.quit_text = tk.Label(
            self.footer_frame,
            text=quit_text,
            font=("Segoe UI", int(14*s), "bold"),
            bg="#111111",
            fg=COLOR_TEXT_WHITE
        )

        self.separator_text.place(relx=0.5, rely=0.5, anchor="center")
        self.launch_text.place(relx=0.5, rely=0.5, anchor="e", x=-gap_offset)
        self.quit_text.place(relx=0.5, rely=0.5, anchor="w", x=gap_offset)

        # Toast notification label (hidden by default)
        self.lbl_toast = tk.Label(
            self.main_container,
            text="",
            font=("Segoe UI", int(12*s), "bold"),
            bg=COLOR_BG_DARK,
            fg=COLOR_NEON_RED
        )
        self.lbl_toast.place(relx=0.5, rely=0.9, anchor="center")
        self.lbl_toast.place_forget()

        # Start main event loop
        self.update_loop()

    # ========================================================================
    # CONFIGURATION MANAGEMENT
    # ========================================================================
    def load_config_data(self, file_path):
        """
        Load existing controller mapping template from Ryujinx Config.json.

        Returns:
            dict: Controller configuration template, or FALLBACK_TEMPLATE if not found
        """
        template = FALLBACK_TEMPLATE
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                if "input_config" in data and isinstance(data["input_config"], list):
                    for entry in data["input_config"]:
                        if (entry.get("backend") == "GamepadSDL2" and
                            entry.get("controller_type") == "ProController"):
                            template = copy.deepcopy(entry)
                            break
            except:
                pass  # Corrupted config, use fallback
        return template

    def ryujinx_guid_fix(self, raw_hex):
        """
        Convert SDL2 GUID format to Ryujinx's expected format.

        Ryujinx uses a specific GUID structure:
        000000XX-YYZZ-AABB-CCCC-DDDDDDDDDDDD

        Args:
            raw_hex (str): Raw 32-character hex GUID from SDL2

        Returns:
            str: Reformatted GUID for Ryujinx
        """
        if len(raw_hex) < 32:
            return raw_hex  # Invalid GUID, return as-is

        bus_id = raw_hex[:2]
        part1 = f"000000{bus_id}"
        part2 = raw_hex[10:12] + raw_hex[8:10]   # Endian swap
        part3 = raw_hex[14:16] + raw_hex[12:14]  # Endian swap
        part4_a = raw_hex[16:20]
        part4_b = raw_hex[20:]

        return f"{part1}-{part2}-{part3}-{part4_a}-{part4_b}"

    # ========================================================================
    # UI FEEDBACK METHODS
    # ========================================================================
    def show_toast(self, message):
        """
        Display a temporary notification message.

        Args:
            message (str): Text to display (automatically hides after 2 seconds)
        """
        if self.toast_job:
            self.root.after_cancel(self.toast_job)

        self.lbl_toast.config(text=message)
        self.lbl_toast.place(relx=0.5, rely=0.9, anchor="center")
        self.toast_job = self.root.after(2000, lambda: self.lbl_toast.place_forget())

    # ========================================================================
    # KEYBOARD INPUT HANDLERS
    # ========================================================================
    def handle_enter_key(self):
        """Handle Enter key press (confirm action in alerts)."""
        if self.alert_mode == "LAUNCH":
            self.force_launch()
        elif self.alert_mode == "EXIT":
            self.root.destroy()
        elif self.alert_mode == "KILL_CONFIRM":
            self.kill_and_quit()

    def handle_esc_key(self):
        """Handle Escape key press (cancel/back action)."""
        if self.alert_mode:
            self.close_alert()
        else:
            self.show_exit_confirmation()

    # ========================================================================
    # PROCESS MANAGEMENT
    # ========================================================================
    def kill_and_quit(self):
        """Kill Ryujinx process and exit launcher (used by kill menu → Desktop option)."""
        if self.ryujinx_process:
            self.ryujinx_process.kill()
        self.root.quit()
        sys.exit()

    def kill_and_restart(self):
        """
        Kill Ryujinx process and return to launcher (used by kill menu → Launcher option).

        Sets flag to prevent automatic exit when process terminates.
        """
        self.returning_to_launcher = True
        time.sleep(0.1)  # Brief delay for flag to propagate

        if self.ryujinx_process:
            self.ryujinx_process.kill()
        self.ryujinx_process = None

        # Reset launcher state for fresh assignment
        self.assignments = []
        self.refresh_grid()
        self.close_alert()
        self.root.deiconify()
        self.root.state('normal')

    # ========================================================================
    # MAIN EVENT LOOP
    # ========================================================================
    def update_loop(self):
        """
        Main event processing loop (runs every 50ms).

        Handles:
        - Ryujinx process monitoring
        - Kill combo detection
        - Controller hot-plug detection
        - Gamepad button events
        """

        # ====================================================================
        # RYUJINX PROCESS MONITORING
        # ====================================================================
        if self.ryujinx_process and not self.alert_mode:
            # Check if Ryujinx has exited
            if self.ryujinx_process.poll() is not None:
                if self.returning_to_launcher:
                    # User chose "Launcher" from kill menu - reset and show UI
                    self.assignments = []
                    self.refresh_grid()
                    self.root.deiconify()
                    self.root.state('normal')
                    self.ryujinx_process = None
                    self.returning_to_launcher = False
                else:
                    # Ryujinx closed normally or crashed - exit launcher
                    self.root.quit()
                    sys.exit()

            # ================================================================
            # GLOBAL KILL COMBO DETECTION (ANY CONTROLLER)
            # ================================================================
            # Checks all connected controllers for Back+L+R press
            # Global approach allows recovery if Player 1's controller fails
            kill_combo = False
            for ctrl in self.controllers.values():
                if (sdl2.SDL_GameControllerGetButton(ctrl, sdl2.SDL_CONTROLLER_BUTTON_BACK) and
                    sdl2.SDL_GameControllerGetButton(ctrl, sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER) and
                    sdl2.SDL_GameControllerGetButton(ctrl, sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)):
                    kill_combo = True
                    break

            if kill_combo:
                self.root.deiconify()  # Bring launcher to foreground
                self.show_alert("KILL_CONFIRM")
                self.root.after(50, self.update_loop)
                return

        # ====================================================================
        # CONTROLLER HARDWARE DETECTION (HOT-PLUG SUPPORT)
        # ====================================================================
        num_joysticks = sdl2.SDL_NumJoysticks()
        self.hardware_map.clear()

        # Scan all connected controllers and build current hardware map
        for i in range(num_joysticks):
            if not sdl2.SDL_IsGameController(i):
                continue  # Skip non-gamepad devices (e.g., flight sticks)

            ctrl = sdl2.SDL_GameControllerOpen(i)
            if ctrl:
                joy = sdl2.SDL_GameControllerGetJoystick(ctrl)
                instance_id = sdl2.SDL_JoystickInstanceID(joy)

                # Cache controller handle for button polling
                if instance_id not in self.controllers:
                    self.controllers[instance_id] = ctrl

                raw_name = sdl2.SDL_GameControllerName(ctrl).decode()

                # Get HID path (hardware-specific, persists across reconnects)
                try:
                    path_bytes = sdl2.SDL_GameControllerPath(ctrl)
                    hid_path = path_bytes.decode() if path_bytes else f"UNK_{instance_id}"
                except:
                    hid_path = f"UNK_{instance_id}"  # Fallback for unsupported platforms

                self.hardware_map[instance_id] = (hid_path, raw_name)

        # ====================================================================
        # HOT-PLUG DISCONNECT DETECTION
        # ====================================================================
        # Compare current hardware against assigned controllers
        # Remove assignments for disconnected controllers
        new_assignments = []
        dropped_names = []

        current_connected_paths = set(path for path, _ in self.hardware_map.values())

        for path, name in self.assignments:
            if path in current_connected_paths:
                new_assignments.append((path, name))  # Still connected, keep assignment
            else:
                dropped_names.append(name)  # Disconnected, remove assignment

        # Update state if any controllers were removed
        if len(new_assignments) != len(self.assignments):
            self.assignments = new_assignments
            self.refresh_grid()

            # Show toast notification for first disconnected controller
            if dropped_names:
                self.show_toast(f"⚠ {dropped_names[0]} Disconnected")

        # ====================================================================
        # GAMEPAD BUTTON EVENT PROCESSING
        # ====================================================================
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                # ============================================================
                # ALERT MODE HANDLERS
                # ============================================================
                if self.alert_mode:
                    if self.alert_mode == "KILL_CONFIRM":
                        # Three-option kill menu
                        if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                            self.kill_and_restart()  # Return to launcher
                        elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_Y:
                            self.kill_and_quit()  # Exit to desktop
                        elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                            self.close_alert()
                            self.root.withdraw()  # Cancel, resume game
                    else:
                        # Standard two-option alerts (launch/exit confirmations)
                        if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                            if self.alert_mode == "LAUNCH":
                                self.force_launch()
                            elif self.alert_mode == "EXIT":
                                self.root.destroy()
                        elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                            self.close_alert()

                # ============================================================
                # NORMAL MODE HANDLERS
                # ============================================================
                else:
                    # Ignore input if game is running (prevent mid-game reassignment)
                    if self.ryujinx_process:
                        continue

                    if event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_A:
                        self.assign_player(event.cbutton.which)  # Assign controller
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_B:
                        self.remove_player(event.cbutton.which)  # Remove assignment
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_START:
                        self.check_launch()  # Launch Ryujinx
                    elif event.cbutton.button == sdl2.SDL_CONTROLLER_BUTTON_BACK:
                        self.show_exit_confirmation()  # Exit launcher

            elif event.type == sdl2.SDL_QUIT:
                self.root.destroy()

        # Schedule next update in 50ms
        self.root.after(50, self.update_loop)

    # ========================================================================
    # CONTROLLER ASSIGNMENT LOGIC
    # ========================================================================
    def assign_player(self, instance_id):
        """
        Assign a controller to the next available player slot.

        Args:
            instance_id (int): SDL2 instance ID of the controller
        """
        if instance_id not in self.hardware_map:
            return  # Controller disconnected before assignment

        target_path, display_name = self.hardware_map[instance_id]

        # Prevent duplicate assignments (same controller can't be multiple players)
        for path, _ in self.assignments:
            if path == target_path:
                return

        # Enforce 8-player maximum
        if len(self.assignments) >= 8:
            return

        self.assignments.append((target_path, display_name))
        self.refresh_grid()

    def remove_player(self, instance_id):
        """
        Remove a controller's player assignment.

        Args:
            instance_id (int): SDL2 instance ID of the controller to remove
        """
        if instance_id not in self.hardware_map:
            return

        target_path, _ = self.hardware_map[instance_id]

        # Find and remove assignment by HID path
        found_index = -1
        for i, (path, _) in enumerate(self.assignments):
            if path == target_path:
                found_index = i
                break

        if found_index != -1:
            self.assignments.pop(found_index)
            self.refresh_grid()

    # ========================================================================
    # UI UPDATE METHODS
    # ========================================================================
    def get_assigned_color(self, hid_path):
        """
        Returns the persistent color for a specific controller HID.
        If the controller hasn't been seen before, assigns a new color from the pool.
        """
        # 1. Check if we already assigned a color to this HID earlier in the session
        if hid_path in self.hid_colors:
            return self.hid_colors[hid_path]

        # 2. If the pool is empty (more than 20 controllers?), recycle the list
        if not self.color_pool:
            self.color_pool = list(PASTEL_POOL)

        # 3. Assign the next available color
        new_color = self.color_pool.pop(0)
        self.hid_colors[hid_path] = new_color
        return new_color

    def refresh_grid(self):
        """Update all player slot cards to reflect current assignments."""
        s = self.scale

        for i in range(8):
            card, lbl_num, lbl_status, lbl_disc = self.slot_cards[i]

            if i < len(self.assignments):
                # ============================================================
                # ACTIVE SLOT (Controller assigned)
                # ============================================================
                hid_path, display_name = self.assignments[i]

                # --- NEW: Get the sticky pastel color ---
                active_color = self.get_assigned_color(hid_path)
                # ----------------------------------------

                # Remove trailing index suffix
                clean_name = re.sub(r'\s*\(\d+\)$', '', display_name)

                # Update Card Border (Use active_color)
                card.config(
                    bg=COLOR_BG_CARD,
                    highlightbackground=active_color,  # Changed from NEON_BLUE
                    highlightcolor=active_color        # Changed from NEON_BLUE
                )

                # Update Player Number Color (Use active_color)
                lbl_num.config(bg=COLOR_BG_CARD, fg=active_color)

                # Update Name Text Color (Use active_color)
                lbl_status.place(relx=0.5, rely=0.25, anchor="center")
                lbl_status.config(
                    text=clean_name,
                    bg=COLOR_BG_CARD,
                    fg=active_color,                   # Changed from NEON_BLUE
                    font=("Segoe UI", int(12*s), "bold")
                )

                # Show disconnect hint (Keep Red for "Danger/Action")
                lbl_disc.place(relx=0.5, rely=0.75, anchor="center")
                lbl_disc.config(bg=COLOR_BG_CARD, fg=COLOR_NEON_RED)

            else:
                # ============================================================
                # INACTIVE SLOT (No controller assigned)
                # ============================================================
                # (This part remains exactly the same as your original code)
                card.config(
                    bg=COLOR_BG_CARD,
                    highlightbackground=COLOR_BG_CARD,
                    highlightcolor=COLOR_BG_CARD
                )
                lbl_num.config(bg=COLOR_BG_CARD, fg="#444444")
                lbl_status.place(relx=0.5, rely=0.5, anchor="center")
                lbl_status.config(
                    text="PRESS Ⓐ CONNECT",
                    bg=COLOR_BG_CARD,
                    fg=COLOR_TEXT_DIM,
                    font=("Segoe UI", int(12*s), "bold")
                )
                lbl_disc.place_forget()

    # ========================================================================
    # ALERT DIALOG SYSTEM
    # ========================================================================
    def check_launch(self):
        """Validate assignment state before launching Ryujinx."""
        if len(self.assignments) == 0:
            self.show_alert("LAUNCH")  # Warn about no controllers
        else:
            self.force_launch()

    def show_exit_confirmation(self):
        """Show confirmation dialog before exiting launcher."""
        self.show_alert("EXIT")

    def show_alert(self, mode):
        """
        Display a modal alert dialog.

        Args:
            mode (str): Alert type - "LAUNCH", "EXIT", or "KILL_CONFIRM"
        """
        self.alert_mode = mode
        s = self.scale

        # Fullscreen overlay
        self.alert_frame = tk.Frame(self.root, bg="#000000")
        self.alert_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Dialog box
        box_w = int(600 * s)
        box_h = int(320 * s)
        box = tk.Frame(
            self.alert_frame,
            bg="#1E1E1E",
            bd=2,
            relief="solid"
        )
        box.place(relx=0.5, rely=0.5, anchor="center", width=box_w, height=box_h)

        if mode == "LAUNCH":
            # ================================================================
            # NO CONTROLLERS WARNING
            # ================================================================
            launch_target = "GAME" if len(sys.argv) > 1 else "RYUJINX"

            tk.Label(
                box,
                text="⚠️ NO CONTROLLERS",
                font=("Segoe UI", int(26*s), "bold"),
                bg="#1E1E1E",
                fg="#FFCC00"
            ).pack(pady=(int(40*s), int(10*s)))

            tk.Label(
                box,
                text="Ryujinx will launch with default inputs.",
                font=("Segoe UI", int(14*s)),
                bg="#1E1E1E",
                fg="#BBBBBB"
            ).pack(pady=int(5*s))

            btn_frame = tk.Frame(box, bg="#1E1E1E")
            btn_frame.pack(pady=int(40*s))

            tk.Label(
                btn_frame,
                text=f"Ⓐ LAUNCH {launch_target}",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_NEON_BLUE
            ).pack(side="left", padx=int(20*s))

            tk.Label(
                btn_frame,
                text="Ⓑ BACK",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_NEON_RED
            ).pack(side="left", padx=int(20*s))

        elif mode == "EXIT":
            # ================================================================
            # EXIT CONFIRMATION
            # ================================================================
            tk.Label(
                box,
                text="EXIT LAUNCHER?",
                font=("Segoe UI", int(26*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_TEXT_WHITE
            ).pack(pady=(int(40*s), int(10*s)))

            tk.Label(
                box,
                text="Are you sure you want to quit?",
                font=("Segoe UI", int(14*s)),
                bg="#1E1E1E",
                fg="#BBBBBB"
            ).pack(pady=int(5*s))

            btn_frame = tk.Frame(box, bg="#1E1E1E")
            btn_frame.pack(pady=int(40*s))

            tk.Label(
                btn_frame,
                text="Ⓐ YES",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_NEON_BLUE
            ).pack(side="left", padx=int(20*s))

            tk.Label(
                btn_frame,
                text="Ⓑ NO",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_NEON_RED
            ).pack(side="left", padx=int(20*s))

        elif mode == "KILL_CONFIRM":
            # ================================================================
            # KILL GAME MENU (THREE OPTIONS)
            # ================================================================
            tk.Label(
                box,
                text="KILL GAME?",
                font=("Segoe UI", int(26*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_TEXT_WHITE
            ).pack(pady=(int(40*s), int(10*s)))

            tk.Label(
                box,
                text="How would you like to proceed?",
                font=("Segoe UI", int(14*s)),
                bg="#1E1E1E",
                fg="#BBBBBB"
            ).pack(pady=int(5*s))

            btn_frame = tk.Frame(box, bg="#1E1E1E")
            btn_frame.pack(pady=int(30*s))

            # Option 1: Return to launcher for controller reconfiguration
            tk.Label(
                btn_frame,
                text="Ⓐ LAUNCHER",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_NEON_BLUE
            ).pack(side="left", padx=int(15*s))

            # Option 2: Exit to desktop
            tk.Label(
                btn_frame,
                text="Ⓨ DESKTOP",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg="#FFCC00"
            ).pack(side="left", padx=int(15*s))

            # Option 3: Cancel and resume game
            tk.Label(
                btn_frame,
                text="Ⓑ CANCEL",
                font=("Segoe UI", int(12*s), "bold"),
                bg="#1E1E1E",
                fg=COLOR_NEON_RED
            ).pack(side="left", padx=int(15*s))

    def close_alert(self):
        """Dismiss the current alert dialog."""
        self.alert_mode = None
        if self.alert_frame:
            self.alert_frame.destroy()
            self.alert_frame = None

    # ========================================================================
    # CONFIG GENERATION & LAUNCH
    # ========================================================================
    def save_config(self):
        """
        Generate Ryujinx controller configuration from current assignments.

        Critical: This performs a FRESH SDL2 scan to get correct GUID indices
        in the OS enumeration order that Ryujinx will see.
        """
        # ====================================================================
        # STEP 1: RESET SDL2 SUBSYSTEM
        # ====================================================================
        # Close all existing controller handles
        for c in self.controllers.values():
            sdl2.SDL_GameControllerClose(c)
        self.controllers.clear()

        # Reinitialize SDL2 for fresh enumeration
        sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
        sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)

        # ====================================================================
        # STEP 2: BUILD HARDWARE LIST WITH CORRECT GUID INDICES
        # ====================================================================
        final_hw_list = []
        num = sdl2.SDL_NumJoysticks()
        guid_counters = {}  # Track index per unique GUID

        for i in range(num):
            if not sdl2.SDL_IsGameController(i):
                continue

            ctrl = sdl2.SDL_GameControllerOpen(i)
            if ctrl:
                joy = sdl2.SDL_GameControllerGetJoystick(ctrl)

                # Extract GUID
                guid_obj = sdl2.SDL_JoystickGetGUID(joy)
                psz_guid = (ctypes.c_char * 33)()
                sdl2.SDL_JoystickGetGUIDString(guid_obj, psz_guid, 33)
                raw_guid_str = psz_guid.value.decode()
                base_guid = self.ryujinx_guid_fix(raw_guid_str)

                # Extract HID path (for matching with assignments)
                try:
                    p = sdl2.SDL_GameControllerPath(ctrl)
                    path = p.decode() if p else ""
                except:
                    path = ""

                # Calculate index (e.g., "0-GUID", "1-GUID" for duplicate GUIDs)
                idx = guid_counters.get(base_guid, 0)
                final_id = f"{idx}-{base_guid}"
                guid_counters[base_guid] = idx + 1

                final_hw_list.append({
                    "path": path,
                    "ryu_id": final_id,
                    "name": sdl2.SDL_GameControllerName(ctrl).decode()
                })

                sdl2.SDL_GameControllerClose(ctrl)

        # ====================================================================
        # STEP 3: MATCH ASSIGNMENTS TO HARDWARE BY HID PATH
        # ====================================================================
        if not os.path.exists(CONFIG_FILE):
            return  # No config file to modify

        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
        except:
            return  # Corrupted config

        new_input = []

        for i, (assigned_path, _) in enumerate(self.assignments):
            # Find hardware entry matching this assignment's HID path
            matched_hw = next(
                (x for x in final_hw_list if x["path"] == assigned_path),
                None
            )

            if matched_hw:
                # Create controller config entry
                entry = copy.deepcopy(self.master_template)
                entry["id"] = matched_hw["ryu_id"]      # Correct GUID with index
                entry["name"] = matched_hw["name"]
                entry["player_index"] = f"Player{i+1}"
                entry["backend"] = "GamepadSDL2"
                entry["controller_type"] = "ProController"
                new_input.append(entry)

        # Write updated config
        data["input_config"] = new_input
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except:
            pass  # Write failed, Ryujinx will use old config

    def force_launch(self):
        """
        Save controller configuration and launch Ryujinx process.

        Passes any command-line arguments (e.g., game path from Playnite) to Ryujinx.
        """
        self.save_config()
        self.root.withdraw()  # Hide launcher window
        self.returning_to_launcher = False  # Clear restart flag

        # Locate Ryujinx executable
        exe_path = os.path.join(ryujinx_dir, TARGET_EXE)
        if not os.path.exists(exe_path):
            # Try parent directory (if launcher is in subdirectory)
            exe_path = os.path.join(os.path.dirname(ryujinx_dir), TARGET_EXE)

        if os.path.exists(exe_path):
            try:
                # Launch Ryujinx with all arguments passed to launcher
                cmd_args = [exe_path] + sys.argv[1:]
                self.ryujinx_process = subprocess.Popen(cmd_args)
            except Exception as e:
                messagebox.showerror(
                    "Launch Error",
                    f"Failed to start Ryujinx.\n{e}"
                )
                sys.exit()
        else:
            messagebox.showerror(
                "Missing File",
                f"Could not find {TARGET_EXE}"
            )
            sys.exit()

# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = RyujinxLauncherApp(root)
    root.mainloop()