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
import customtkinter as ctk
import ctypes
import copy
import re
import time
import random
import glob

# ============================================================================
# SECTION 1: HI-DPI DISPLAY SUPPORT
# ============================================================================
# Enables proper scaling on high-resolution displays (4K, 1440p)
# 1. Stop Windows from double-scaling
if sys.platform == "win32":
    ctk.deactivate_automatic_dpi_awareness()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1+
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Windows Vista-8
        except:
            pass  # Non-Windows or unsupported
# 2. Stop Linux from double-scaling
else:
    os.environ.setdefault('GDK_SCALE', '1')
    os.environ.setdefault('GDK_DPI_SCALE', '1')

# ============================================================================
# SECTION 2: UI DESIGN VARIABLES (720p BASELINE - 1280x720)
# ============================================================================
# All measurements are for 1280x720 resolution at 100% DPI
# These will be automatically scaled for other resolutions

UI = {
    # === FONTS ===
    'FONT_FAMILY': 'Segoe UI',
    'FONT_TITLE_SIZE': 39,          # Main title
    'FONT_CARD_SIZE': 21,           # Player card text
    'FONT_FOOTER_SIZE': 22,         # Footer buttons
    'FONT_ALERT_TITLE_SIZE': 33,    # Alert dialog title
    'FONT_ALERT_TEXT_SIZE': 22,     # Alert dialog text
    'FONT_ALERT_BTN_SIZE': 21,      # Alert dialog buttons
    'FONT_TOAST_SIZE': 21,          # Toast notification

    # === SPACING ===
    'PADDING_MAIN': 40,             # Main container padding
    'PADDING_TITLE_TOP': 15,        # Title top margin
    'PADDING_TITLE_BOTTOM': 20,     # Title bottom margin

    # === PLAYER CARDS ===
    'CARD_WIDTH': 400,              # Player card width
    'CARD_HEIGHT': 85,              # Player card height
    'CARD_PADDING_X': 15,           # Horizontal gap between cards
    'CARD_PADDING_Y': 10,           # Vertical gap between cards
    'CARD_BORDER': 2,               # Card border thickness
    'CARD_CORNER_RADIUS': 12,       # Card corner radius
    'CARD_PLAYER_NUM_X': 12,        # Player number X position
    'CARD_PLAYER_NUM_Y': 8,         # Player number Y position

    # === FOOTER ===
    'FOOTER_HEIGHT': 60,            # Footer bar height
    'FOOTER_GAP': 12,               # Gap between footer elements

    # === ALERT DIALOG ===
    'ALERT_BOX_WIDTH': 500,         # Alert dialog width
    'ALERT_BOX_HEIGHT': 240,        # Alert dialog height
    'ALERT_BOX_BORDER': 2,          # Alert dialog border
    'ALERT_BOX_CORNER_RADIUS': 12,  # Alert box corner radius
    'ALERT_TITLE_PADDING_TOP': 30,  # Alert title top padding
    'ALERT_TITLE_PADDING_BOTTOM': 8,# Alert title bottom padding
    'ALERT_TEXT_PADDING': 4,        # Alert text padding
    'ALERT_BTN_PADDING_TOP': 30,    # Alert buttons top padding
    'ALERT_BTN_PADDING_X': 15,      # Alert buttons horizontal padding

    # === TOAST ===
    'TOAST_POSITION_Y': 0.95,        # Toast Y position (relative)
}

# ============================================================================
# SECTION 3: COLOR THEME
# ============================================================================
COLOR = {
    'BG_DARK': '#0F0F0F',
    'BG_CARD': '#1A1A1A',
    'NEON_BLUE': '#0AB9E6',
    'NEON_RED': '#FF3C28',
    'TEXT_WHITE': '#EDEDED',
    'TEXT_DIM': '#666666',
    'FOOTER_BG': '#111111',
    'ALERT_BG': '#000000',
    'ALERT_BOX_BG': '#1E1E1E',
    'ALERT_TEXT_DIM': '#BBBBBB',
    'ALERT_YELLOW': '#FFCC00',
}

COLOR_POOL = [
    "#00FF00", "#00FA9A", "#ADFF2F", "#7FFFD4", "#40E0D0",  # Lime, SpringGreen, GreenYellow, Aqua, Turquoise
    "#00FFFF", "#1E90FF", "#87CEFA", "#4169E1", "#00BFFF",  # Cyan, DodgerBlue, SkyBlue, RoyalBlue, DeepSkyBlue
    "#FF00FF", "#DA70D6", "#9370DB", "#FF69B4", "#D8BFD8",  # Magenta, Orchid, MedPurple, HotPink, Thistle
    "#FFFF00", "#FFD700", "#F0E68C", "#FFC200", "#FFFFFF"   # Yellow, Gold, Khaki, Amber, White
]

# set dark mode once before any window is created
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ============================================================================
# SECTION 4: PATH DETECTION & CONFIGURATION
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

# ============================================================================
# SECTION 4b: APPIMAGE DETECTION & MOUNT HELPERS (LINUX ONLY)
# ============================================================================
# For AppImage: ryujinx_dir is swapped to mount point (usr/bin) so SDL,
# version detection, and TARGET_EXE all work unchanged from the mount point.
# Mount stays alive for the entire session — only unmounted on final exit.
# PR_SET_PDEATHSIG ensures the mount process is killed even on hard crash.
mount_proc    = None  # Popen handle — terminating it unmounts the squashfs

_appimage_candidates = (
    glob.glob(os.path.join(ryujinx_dir, "[Rr]yujinx*.AppImage")) or
    glob.glob(os.path.join(ryujinx_dir, "RYUJINX*.AppImage"))
)
appimage_path = _appimage_candidates[0] if _appimage_candidates else None
is_appimage   = sys.platform not in ("win32", "darwin") and appimage_path is not None

def mount_appimage():
    """
    Mount Ryujinx.AppImage using --appimage-mount.
    PR_SET_PDEATHSIG ensures mount process is killed even on hard launcher crash.
    Returns the mount point path.
    """
    if not is_appimage:
        return

    global mount_proc

    import signal
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1

    mount_proc = subprocess.Popen(
        [appimage_path, "--appimage-mount"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        preexec_fn=lambda: libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)
    )

    mount_point = mount_proc.stdout.readline().decode().strip()

    if not mount_point or not os.path.exists(mount_point):
        messagebox.showerror(
            "AppImage Mount Failed",
            f"Could not mount Ryujinx.AppImage.\n\n"
            f"Please ensure the file is executable:\n"
            f"chmod +x {appimage_path}"
        )
        sys.exit(1)

    print(f"📦 AppImage mounted at: {mount_point}")
    return os.path.join(mount_point, "usr", "bin")

def unmount_appimage():
    """Terminate the mount process, releasing the squashfs mount."""
    global mount_proc

    if not is_appimage or not mount_proc:
        return

    mount_proc.terminate()
    mount_proc = None
    print("📦 AppImage unmounted")

# ============================================================================
# SECTION 5: PLATFORM-SPECIFIC CONFIGURATION
# ============================================================================
# Determine correct file paths and executable names based on OS
if sys.platform == "win32":
    TARGET_EXE = os.path.join(ryujinx_dir, "Ryujinx.exe")

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
    TARGET_EXE = os.path.join(ryujinx_dir, "Ryujinx")
    CONFIG_FILE = os.path.expanduser("~/.config/Ryujinx/Config.json")

else:  # Linux
    if is_appimage:
        ryujinx_dir = mount_appimage()
    TARGET_EXE = os.path.join(ryujinx_dir, "Ryujinx")
    CONFIG_FILE = os.path.expanduser("~/.config/Ryujinx/Config.json")

# ============================================================================
# SECTION 6: RYUJINX VERSION DETECTION
# ============================================================================
"""
Determines Ryujinx version.
Returns: Ryujinx version string (1.1.1403/1.3.1/1.3.2/1.3.3/or newer)
1. Windows: Reads PE metadata natively via ctypes.
2. Mac: Reads native Info.plist (CFBundleLongVersionString).
3. Linux: Binary scan for embedded version string → [ENV VAR OVERRIDE fallback].
"""

# Default to new version
ryujinx_version = "1.1.1403"
exe_path = TARGET_EXE

if os.path.exists(exe_path):
    try:
        if sys.platform == "win32":
            # --- WINDOWS METHOD (ctypes) ---
            ver_info_size = ctypes.windll.version.GetFileVersionInfoSizeW(exe_path, None)
            if ver_info_size:
                ver_info = ctypes.create_string_buffer(ver_info_size)
                ctypes.windll.version.GetFileVersionInfoW(exe_path, 0, ver_info_size, ver_info)

                lp_buffer = ctypes.c_void_p()
                lp_len = ctypes.c_uint()
                ctypes.windll.version.VerQueryValueW(
                    ver_info, "\\", ctypes.byref(lp_buffer), ctypes.byref(lp_len)
                )

                class VS_FIXEDFILEINFO(ctypes.Structure):
                    _fields_ = [
                        ("dwSignature",        ctypes.c_uint32),
                        ("dwStrucVersion",     ctypes.c_uint32),
                        ("dwFileVersionMS",    ctypes.c_uint32),
                        ("dwFileVersionLS",    ctypes.c_uint32),
                        ("dwProductVersionMS", ctypes.c_uint32),
                        ("dwProductVersionLS", ctypes.c_uint32),
                        ("dwFileFlagsMask",    ctypes.c_uint32),
                        ("dwFileFlags",        ctypes.c_uint32),
                        ("dwFileOS",           ctypes.c_uint32),
                        ("dwFileType",         ctypes.c_uint32),
                        ("dwFileSubtype",      ctypes.c_uint32),
                        ("dwFileDateMS",       ctypes.c_uint32),
                        ("dwFileDateLS",       ctypes.c_uint32),
                    ]

                ffi = VS_FIXEDFILEINFO.from_address(lp_buffer.value)
                v1 = (ffi.dwFileVersionMS >> 16) & 0xFFFF
                v2 = (ffi.dwFileVersionMS >>  0) & 0xFFFF
                v3 = (ffi.dwFileVersionLS >> 16) & 0xFFFF
                ryujinx_version = f"{v1}.{v2}.{v3}"

        elif sys.platform == "darwin":
            # --- MAC METHOD (Native Plist) ---
            import plistlib
            plist_path = os.path.abspath(os.path.join(exe_path, "..", "..", "Info.plist"))
            if os.path.exists(plist_path):
                with open(plist_path, 'rb') as f:
                    raw = plistlib.load(f).get("CFBundleLongVersionString", ryujinx_version)
                    ryujinx_version = raw.split("-")[0].strip('"')  # "1.3.3-e2143d4" → "1.3.3"
            else:
                # Ideally this should never happen because Ryujinx embeds the version string in all official builds, but we add this as a fallback just in case
                # Check for environment variable override before giving up
                env_version = os.environ.get("RL_RYUJINX_VERSION")
                if env_version:
                    ryujinx_version = env_version.strip()
                else:
                    # If we can't find the version from binary and environment variable, show an error with instructions for the user to set it manually
                    messagebox.showerror(
                        "One-Time Setup Required",
                        "Could not detect your Ryujinx version automatically.\n\n"
                        "This is a one-time setup step required when installing or upgrading Ryujinx.\n\n"
                        "echo 'export RL_RYUJINX_VERSION=1.3.3' >> ~/.zshrc && source ~/.zshrc\n\n"
                        "(Replace 1.3.3 with your actual version). Run this in Terminal."
                    )
                    sys.exit(1)

        else:
            # --- LINUX METHOD (Binary Scan) ---
            # Mimics: strings Ryujinx | grep 'Ryujinx/' | grep ':' | head -1 | cut -d '"' -f2 | cut -d '/' -f2

            # Step 1: Read binary and decode to ASCII (strips all null bytes and non-printable chars)
            with open(exe_path, 'rb') as f:
                data = f.read()
            text = data.decode('ascii', errors='ignore')

            # Step 2: Scan line by line for the embedded version string
            # Looking for a line containing: "Ryujinx/1.3.3:..."
            found_version = None
            for line in text.splitlines():
                if '"Ryujinx/' in line and ':' in line:
                    # cut -d '"' -f2 → take part inside quotes
                    # cut -d '/' -f2 → take part after the slash
                    candidate = line.split('"')[1].split('/')[1].strip()

                    # Validate format is X.X.X before accepting (e.g. 1.3.3)
                    if re.match(r'^\d+\.\d+\.\d+$', candidate):
                        found_version = candidate
                        break

            # Step 3: Apply result or fall back to env var override
            if found_version:
                ryujinx_version = found_version
            else:
                # Ideally this should never happen because Ryujinx embeds the version string in all official builds, but we add this as a fallback just in case
                # Check for environment variable override before giving up
                env_version = os.environ.get("RL_RYUJINX_VERSION")
                if env_version:
                    ryujinx_version = env_version.strip()
                else:
                    # If we can't find the version from binary and environment variable, show an error with instructions for the user to set it manually
                    messagebox.showerror(
                        "Ryujinx Version Missing",
                        "Could not detect your Ryujinx version automatically.\n\n"
                        "This is a one-time setup step required when installing or upgrading Ryujinx.\n\n"
                        "echo 'export RL_RYUJINX_VERSION=1.3.3' >> ~/.bashrc && source ~/.bashrc\n\n"
                        "(Replace 1.3.3 with your actual version). Run this in your terminal"
                    )
                    sys.exit(1)
    except Exception:
        pass  # Fall back to default "1.1.1403"

else:
    messagebox.showerror(
        "Ryujinx Missing",
        f"Could not find {TARGET_EXE} in:\n{ryujinx_dir}"
    )
    sys.exit(1)

# ============================================================================
# SECTION 7a: LINUX LAUNCH WRAPPER DETECTION
# ============================================================================
# Prefer Ryujinx.sh over the raw binary when available.
# The shell wrapper sets LANG=C.UTF-8, DOTNET_EnableAlternateStackCheck=1,
# and enables gamemoderun if installed — giving better runtime stability.
if sys.platform not in ("win32", "darwin") and os.path.exists(os.path.join(ryujinx_dir, "Ryujinx.sh")):
    TARGET_EXE = os.path.join(ryujinx_dir, "Ryujinx.sh")

# ============================================================================
# SECTION 7b: CREATE ENVIRONMENT FOR RYUJINXLAUNCHER AND RYUJINX
# ============================================================================

if ryujinx_version == "1.1.1403":
    os.environ["SDL_JOYSTICK_RAWINPUT"] = "0"

ryujinx_env = os.environ.copy()

# ============================================================================
# SECTION 8: IMPORT SDL LIBRARY
# ============================================================================

if tuple(map(int, re.findall(r'\d+', ryujinx_version))) <= tuple(map(int, re.findall(r'\d+', "1.3.205"))):
    print("🔵 Using SDL2 backend")
    print(f"🔍 Looking for SDL2 in {ryujinx_dir} ...")
    os.environ["PYSDL2_DLL_PATH"] = ryujinx_dir
    from ControllerManagerSDL2 import SDLManager
    backend_string="GamepadSDL2"
else:
    print("🟢 Using SDL3 backend")
    print(f"🔍 Looking for SDL3 in {ryujinx_dir} ...")
    os.environ["SDL_BINARY_PATH"] = ryujinx_dir
    os.environ["SDL_DOWNLOAD_BINARIES"] = "0" # Disable SDL Lib Download, "1" by default.
    os.environ["SDL_DISABLE_METADATA"] = "1" # Disable metadata method, "0" by default.
    os.environ["SDL_CHECK_BINARY_VERSION"] = "0" # Disable binary version checking, "1" by default.
    os.environ["SDL_IGNORE_MISSING_FUNCTIONS"] = "1" # Disable missing function warnings, "1" by default.
    os.environ["SDL_FIND_BINARIES"] = "1" # Search for binaries in the system libraries, "1" by default.
    from ControllerManagerSDL3 import SDLManager
    backend_string="GamepadSDL3"

# ============================================================================
# SECTION 9: DEFAULT CONTROLLER MAPPING TEMPLATE
# ============================================================================
# Fallback template if no existing config found (matches Nintendo Pro Controller layout)
FALLBACK_TEMPLATE = {
    "version": 1,
    "backend": backend_string,
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
# SECTION 10: DYNAMIC SCALING UTILITY
# ============================================================================
def calculate_scale(screen_width, screen_height):
    """
    Calculate uniform scale factor based on screen resolution.
    Baseline: 1280x720 (720p, 16:9)

    Returns uniform scale that maintains aspect ratio
    """
    BASE_WIDTH = 1280
    BASE_HEIGHT = 720

    # Calculate scale based on both dimensions
    width_scale = screen_width / BASE_WIDTH
    height_scale = screen_height / BASE_HEIGHT

    # Use the smaller scale to ensure everything fits
    scale = min(width_scale, height_scale)

    # Minimum scale for very small screens
    if scale < 0.2:
        scale = 0.2

    return scale
# ============================================================================
# SECTION 11: MAIN APPLICATION CLASS
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
        self.root.configure(fg_color=COLOR['BG_DARK'])
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
        self.root.update_idletasks()
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.scale = calculate_scale(self.screen_width, self.screen_height)
        self.resize_job = None

        ctk.set_window_scaling(self.scale)  # Scales the window size
        ctk.set_widget_scaling(self.scale)  # Scales the buttons, fonts, and elements inside

        # Bind the configure event to detect resolution/scale changes
        self.root.bind("<Configure>", self.on_window_configure)

        # Initialize SDL2/SDL3 controller subsystem
        SDLManager.SDL_Init()

        # State management
        self.controllers = {}               # {instance_id: SDL_GameController}
        self.assignments = []               # [(hid_path, display_name), ...] - Player order
        self.hardware_map = {}              # {instance_id: (hid_path, display_name)} - Currently connected
        self.color_pool = list(COLOR_POOL) # Copy the pool to modify it locally
        random.shuffle(self.color_pool)     # Shuffle the color pool
        self.hid_colors = {}                # Dictionary to remember {hid_path: color_hex}
        self.alert_mode = None              # Current alert type (if any)
        self.alert_frame = None             # Alert dialog container
        self.ryujinx_process = None         # Ryujinx subprocess handle
        self.toast_job = None               # Toast notification timer
        self.returning_to_launcher = False  # Flag for kill→restart flow

        # Load existing controller mapping template from Config.json
        self.master_template = self.load_config_data(CONFIG_FILE)

        # Build UI
        self.build_ui()

        # Start main loop
        self.update_loop()

    def on_window_configure(self, event):
        """
        Handle window resize events (resolution or scale change).
        Uses a timer (debounce) to wait for the resize to finish before rebuilding UI.
        """
        if event.widget != self.root:
            return

        new_w = self.root.winfo_screenwidth()
        new_h = self.root.winfo_screenheight()

        # Only trigger if dimensions actually changed
        if new_w != self.screen_width or new_h != self.screen_height:
            # Cancel previous timer if user is still resizing/changing settings
            if self.resize_job:
                self.root.after_cancel(self.resize_job)

            # Schedule a rebuild in 100ms
            self.resize_job = self.root.after(100, self.perform_resize)

    def perform_resize(self):
        """
        Actually rebuild the UI with the new scale factor.
        """
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # Recalculate scale
        self.scale = calculate_scale(self.screen_width, self.screen_height)

        ctk.set_window_scaling(self.scale)  # Scales the window size
        ctk.set_widget_scaling(self.scale)  # Scales the buttons, fonts, and elements inside

        # Destroy old UI
        if hasattr(self, 'main_container'):
            self.main_container.destroy()

        # Destroy footer separately as it is packed to bottom
        if hasattr(self, 'footer_frame'):
            self.footer_frame.destroy()

        # Rebuild UI elements
        self.build_ui()

        # Restore controller assignment visuals onto the new UI
        self.refresh_grid()

        if self.alert_mode:
            # 1. Capture current mode
            mode = self.alert_mode

            # 2. Destroy the old, wrongly scaled/positioned alert frame
            if self.alert_frame:
                self.alert_frame.destroy()
                self.alert_frame = None

            # 3. Re-draw the alert (This forces it to the top of the stack)
            self.show_alert(mode)

    def build_ui(self):
        """Build the entire UI using scaled values"""

        # Main container
        self.main_container = ctk.CTkFrame(
            self.root,
            fg_color=COLOR['BG_DARK'],
            corner_radius=0
        )
        self.main_container.pack(
            expand=True,
            fill="both",
            padx=(UI['PADDING_MAIN']),
            pady=(UI['PADDING_MAIN'])
        )

        # Header: Title
        mode_prefix = "GAME" if len(sys.argv) > 1 else "RYUJINX"
        title_text = f"{mode_prefix} CONTROLLER SETUP"

        self.lbl_title = ctk.CTkLabel(
            self.main_container,
            text=title_text,
            font=(UI['FONT_FAMILY'], UI['FONT_TITLE_SIZE'], "bold"),
            fg_color="transparent",
            text_color=COLOR['TEXT_WHITE']
        )
        self.lbl_title.pack(
            pady=(
                (UI['PADDING_TITLE_TOP']),
                (UI['PADDING_TITLE_BOTTOM'])
            )
        )

        # Player grid: 8 slots in 4x2 layout
        self.grid_frame = ctk.CTkFrame(self.main_container, fg_color=COLOR['BG_DARK'], corner_radius=0)
        self.grid_frame.pack()

        self.slot_cards = []
        for i in range(8):
            row = i // 2
            col = i % 2

            # Card frame with border highlight
            card = ctk.CTkFrame(
                self.grid_frame,
                fg_color=COLOR['BG_CARD'],
                width=UI['CARD_WIDTH'],
                height=UI['CARD_HEIGHT'],
                border_color=COLOR['BG_CARD'],
                border_width=UI['CARD_BORDER'],
                corner_radius=UI['CARD_CORNER_RADIUS']
            )
            card.grid_propagate(False)
            card.grid(
                row=row,
                column=col,
                padx=(UI['CARD_PADDING_X']),
                pady=(UI['CARD_PADDING_Y'])
            )

            # Player number label (top-left corner)
            lbl_num = ctk.CTkLabel(
                card,
                text=f"P{i+1}",
                font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold"),
                fg_color="transparent",
                text_color="#444444"
            )
            lbl_num.place(
                x=UI['CARD_PLAYER_NUM_X'],
                y=UI['CARD_PLAYER_NUM_Y']
            )

            # Status/name label (center)
            lbl_status = ctk.CTkLabel(
                card,
                text="PRESS Ⓐ CONNECT",
                font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['TEXT_DIM']
            )
            lbl_status.place(relx=0.5, rely=0.5, anchor="center")

            # Disconnect hint label (bottom, initially hidden)
            lbl_disc = ctk.CTkLabel(
                card,
                text="Ⓑ DISCONNECT",
                font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_RED']
            )

            self.slot_cards.append((card, lbl_num, lbl_status, lbl_disc))

        # Footer: Button hints
        self.footer_frame = ctk.CTkFrame(
            self.root,
            fg_color=COLOR['FOOTER_BG'],
            height=UI['FOOTER_HEIGHT'],
            corner_radius=0
        )
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.pack_propagate(False)

        launch_target = "GAME" if len(sys.argv) > 1 else "RYUJINX"

        self.separator_text = ctk.CTkLabel(
            self.footer_frame,
            text="|",
            font=(UI['FONT_FAMILY'], UI['FONT_FOOTER_SIZE'], "bold"),
            fg_color="transparent",
            text_color=COLOR['TEXT_WHITE']
        )
        self.launch_text = ctk.CTkLabel(
            self.footer_frame,
            text=f"☰ LAUNCH {launch_target}",
            font=(UI['FONT_FAMILY'], UI['FONT_FOOTER_SIZE'], "bold"),
            fg_color="transparent",
            text_color=COLOR['TEXT_WHITE']
        )
        self.quit_text = ctk.CTkLabel(
            self.footer_frame,
            text="⧉ QUIT",
            font=(UI['FONT_FAMILY'], UI['FONT_FOOTER_SIZE'], "bold"),
            fg_color="transparent",
            text_color=COLOR['TEXT_WHITE']
        )

        gap = UI['FOOTER_GAP']
        self.separator_text.place(relx=0.5, rely=0.5, anchor="center")
        self.launch_text.place(relx=0.5, rely=0.5, anchor="e", x=-gap)
        self.quit_text.place(relx=0.5, rely=0.5, anchor="w", x=gap)

        # Toast notification label (hidden by default)
        self.lbl_toast = ctk.CTkLabel(
            self.main_container,
            text="",
            font=(UI['FONT_FAMILY'], UI['FONT_TOAST_SIZE'], "bold"),
            fg_color="transparent",
            text_color=COLOR['NEON_RED']
        )
        self.lbl_toast.place(relx=0.5, rely=UI['TOAST_POSITION_Y'], anchor="center")
        self.lbl_toast.place_forget()

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
                        if (entry.get("backend") in ("GamepadSDL2", "GamepadSDL3") and
                            entry.get("controller_type") == "ProController"):
                            template = copy.deepcopy(entry)
                            break
            except Exception as e:
                # Corrupted config, use fallback
                messagebox.showerror(
                    "Configuration Error",
                    "Could not read Ryujinx Config file.\n\n"
                    "Please open Ryujinx manually once to generate valid configuration files.\n"
                    "Then try launching this tool again."
                )
                sys.exit(1)  # Stop the launcher immediately
        return template

    def ryujinx_guid_fix(self, raw_hex):
        """
        Convert SDL2/SDL3 GUID format to Ryujinx's expected format.

        Ryujinx uses a specific GUID structure:
        000000XX-YYZZ-AABB-CCCC-DDDDDDDDDDDD

        Args:
            raw_hex (str): Raw 32-character hex GUID from SDL2/SDL3

        Returns:
            str: Reformatted GUID for Ryujinx
        """
        if len(raw_hex) < 32:
            return raw_hex  # Invalid GUID, return as-is

        if ryujinx_version == "1.1.1403":
            # v1.1.1403: Standard endian swap of first 4 bytes (e.g. 8d930003)
            part1 = raw_hex[6:8] + raw_hex[4:6] + raw_hex[2:4] + raw_hex[:2]
        else:
            # v1.3.1/v1.3.2/v1.3.3: Bus ID masked (e.g. 00000003)
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
    def show_toast(self, message, color=COLOR['NEON_RED']):
        """
        Display a temporary notification message.

        Args:
            message (str): Text to display (automatically hides after 2 seconds)
        """
        if self.toast_job:
            self.root.after_cancel(self.toast_job)

        self.lbl_toast.configure(text_color=color)
        self.lbl_toast.configure(text=message)
        self.lbl_toast.place(relx=0.5, rely=UI['TOAST_POSITION_Y'], anchor="center")
        self.toast_job = self.root.after(2000, lambda: self.lbl_toast.place_forget())

    # ========================================================================
    # KEYBOARD INPUT HANDLERS
    # ========================================================================
    def handle_enter_key(self):
        """Handle Enter key press (confirm action in alerts)."""
        if self.alert_mode == "LAUNCH":
            self.force_launch()
        elif self.alert_mode == "EXIT":
            unmount_appimage()
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
        unmount_appimage()
        self.root.quit()
        sys.exit()

    def kill_and_restart(self):
        """
        Kill Ryujinx process and return to launcher (used by kill menu → Launcher option).

        Sets flag to prevent automatic exit when process terminates.
        """
        self.returning_to_launcher = True
        time.sleep(0.005)  # 5ms delay for flag to propagate

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
        Main event processing loop (runs every 16ms).

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
                if (SDLManager.SDL_GameControllerGetButton(ctrl, SDLManager.SDL_CONTROLLER_BUTTON_BACK) and
                    SDLManager.SDL_GameControllerGetButton(ctrl, SDLManager.SDL_CONTROLLER_BUTTON_LEFT_SHOULDER) and
                    SDLManager.SDL_GameControllerGetButton(ctrl, SDLManager.SDL_CONTROLLER_BUTTON_RIGHT_SHOULDER)):
                    kill_combo = True
                    break

            if kill_combo:
                self.root.deiconify()  # Bring launcher to foreground
                self.show_alert("KILL_CONFIRM")
                self.root.after(16, self.update_loop)
                return

        # ====================================================================
        # CONTROLLER HARDWARE DETECTION (HOT-PLUG SUPPORT)
        # ====================================================================
        self.hardware_map.clear()

        # Scan all connected controllers and build current hardware map
        for joystick_id in SDLManager.SDL_GetJoystickIDs():
            if not SDLManager.SDL_IsGameController(joystick_id):
                continue  # Skip non-gamepad devices (e.g., flight sticks)

            ctrl = SDLManager.SDL_GameControllerOpen(joystick_id)
            if ctrl:
                joy = SDLManager.SDL_GameControllerGetJoystick(ctrl)
                instance_id = SDLManager.SDL_JoystickInstanceID(joy)

                # Cache controller handle for button polling
                if instance_id not in self.controllers:
                    self.controllers[instance_id] = ctrl

                raw_name = SDLManager.SDL_GameControllerName(ctrl).decode()

                # Get HID path (hardware-specific, persists across reconnects)
                try:
                    path_bytes = SDLManager.SDL_GameControllerPath(ctrl)
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
                dropped_names.append((path,name))  # Disconnected, remove assignment

        # Update state if any controllers were removed
        if len(new_assignments) != len(self.assignments):
            self.assignments = new_assignments
            self.refresh_grid()

            # Show toast notification for first disconnected controller
            if dropped_names:
                self.show_toast(f"⚠️ {dropped_names[0][1]} Disconnected!", self.hid_colors[dropped_names[0][0]])
                for path, name in dropped_names:
                    color = self.hid_colors.pop(path, None)
                    if color:
                        self.color_pool.append(color)

        # ====================================================================
        # GAMEPAD BUTTON EVENT PROCESSING
        # ====================================================================
        event = SDLManager.SDL_Event()
        while SDLManager.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == SDLManager.SDL_CONTROLLERBUTTONDOWN:
                button, which = SDLManager.get_button_info(event)
                # ============================================================
                # ALERT MODE HANDLERS
                # ============================================================
                if self.alert_mode:
                    if self.alert_mode == "KILL_CONFIRM":
                        # Three-option kill menu
                        if button == SDLManager.SDL_CONTROLLER_BUTTON_A:
                            self.kill_and_restart()  # Return to launcher
                        elif button == SDLManager.SDL_CONTROLLER_BUTTON_Y:
                            self.kill_and_quit()  # Exit to desktop
                        elif button == SDLManager.SDL_CONTROLLER_BUTTON_B:
                            self.close_alert()
                            self.root.withdraw()  # Cancel, resume game
                    else:
                        # Standard two-option alerts (launch/exit confirmations)
                        if button == SDLManager.SDL_CONTROLLER_BUTTON_A:
                            if self.alert_mode == "LAUNCH":
                                self.force_launch()
                            elif self.alert_mode == "EXIT":
                                unmount_appimage()
                                self.root.destroy()
                        elif button == SDLManager.SDL_CONTROLLER_BUTTON_B:
                            self.close_alert()

                # ============================================================
                # NORMAL MODE HANDLERS
                # ============================================================
                else:
                    # Ignore input if game is running (prevent mid-game reassignment)
                    if self.ryujinx_process:
                        continue

                    if button == SDLManager.SDL_CONTROLLER_BUTTON_A:
                        self.assign_player(which)  # Assign controller
                    elif button == SDLManager.SDL_CONTROLLER_BUTTON_B:
                        self.remove_player(which)  # Remove assignment
                    elif button == SDLManager.SDL_CONTROLLER_BUTTON_START:
                        self.check_launch()        # Launch Ryujinx
                    elif button == SDLManager.SDL_CONTROLLER_BUTTON_BACK:
                        self.show_exit_confirmation()  # Exit launcher

            elif event.type == SDLManager.SDL_QUIT:
                unmount_appimage()
                self.root.destroy()

        # Schedule next update in 16ms
        self.root.after(16, self.update_loop)

    # ========================================================================
    # CONTROLLER ASSIGNMENT LOGIC
    # ========================================================================
    def assign_player(self, instance_id):
        """
        Assign a controller to the next available player slot.

        Args:
            instance_id (int): SDL2/SDL3 instance ID of the controller
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
            instance_id (int): SDL2/SDL3 instance ID of the controller to remove
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
            self.color_pool = list(COLOR_POOL)

        # 3. Assign the next available color
        new_color = self.color_pool.pop(0)
        self.hid_colors[hid_path] = new_color
        return new_color

    def refresh_grid(self):
        """Update all player slot cards to reflect current assignments."""

        for i in range(8):
            card, lbl_num, lbl_status, lbl_disc = self.slot_cards[i]

            if i < len(self.assignments):
                # ============================================================
                # ACTIVE SLOT (Controller assigned)
                # ============================================================
                hid_path, display_name = self.assignments[i]

                # --- Get the sticky pastel color ---
                active_color = self.get_assigned_color(hid_path)
                # ----------------------------------------

                # Remove trailing index suffix
                clean_name = re.sub(r'\s*\(\d+\)$', '', display_name)

                # Update Card Border (Use active_color)
                card.configure(
                    fg_color=COLOR['BG_CARD'],
                    border_color=active_color
                )

                # Update Player Number Color (Use active_color)
                lbl_num.configure(fg_color="transparent", text_color=active_color)

                # Update Name Text Color (Use active_color)
                lbl_status.place(relx=0.5, rely=0.25, anchor="center")
                lbl_status.configure(
                    text=clean_name,
                    fg_color="transparent",
                    text_color=active_color,
                    font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold")
                )

                # Show disconnect hint (Keep Red for "Danger/Action")
                lbl_disc.place(relx=0.5, rely=0.75, anchor="center")
                lbl_disc.configure(fg_color="transparent", text_color=COLOR['NEON_RED'])

            else:
                # ============================================================
                # INACTIVE SLOT (No controller assigned)
                # ============================================================
                # (This part remains exactly the same as your original code)
                card.configure(
                    fg_color=COLOR['BG_CARD'],
                    border_color=COLOR['BG_CARD']
                )
                lbl_num.configure(fg_color="transparent", text_color="#444444")
                lbl_status.place(relx=0.5, rely=0.5, anchor="center")
                lbl_status.configure(
                    text="PRESS Ⓐ CONNECT",
                    fg_color="transparent",
                    text_color=COLOR['TEXT_DIM'],
                    font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold")
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

        # Fullscreen overlay
        self.alert_frame = ctk.CTkFrame(self.root, fg_color="#000000", corner_radius=0)
        self.alert_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Dialog box
        box = ctk.CTkFrame(
            self.alert_frame,
            width=UI['ALERT_BOX_WIDTH'],
            height=UI['ALERT_BOX_HEIGHT'],
            fg_color=COLOR['ALERT_BOX_BG'],
            border_width=UI['ALERT_BOX_BORDER'],
            border_color="#444444",
            corner_radius=UI['ALERT_BOX_CORNER_RADIUS']
        )
        box.pack_propagate(False)
        box.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        if mode == "LAUNCH":
            # ================================================================
            # NO CONTROLLERS WARNING
            # ================================================================
            launch_target = "GAME" if len(sys.argv) > 1 else "RYUJINX"

            ctk.CTkLabel(
                box,
                text="⚠️ NO CONTROLLERS",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TITLE_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['ALERT_YELLOW']
            ).pack(pady=((UI['ALERT_TITLE_PADDING_TOP']), (UI['ALERT_TITLE_PADDING_BOTTOM'])))

            ctk.CTkLabel(
                box,
                text="Ryujinx will launch with default inputs.",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TEXT_SIZE']),
                fg_color="transparent",
                text_color=COLOR['ALERT_TEXT_DIM']
            ).pack(pady=(UI['ALERT_TEXT_PADDING']))

            btn_frame = ctk.CTkFrame(box, fg_color=COLOR['ALERT_BOX_BG'], corner_radius=0)
            btn_frame.pack(pady=(UI['ALERT_BTN_PADDING_TOP']))

            ctk.CTkLabel(
                btn_frame,
                text=f"Ⓐ LAUNCH {launch_target}",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_BLUE']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

            ctk.CTkLabel(
                btn_frame,
                text="Ⓑ BACK",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_RED']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

        elif mode == "EXIT":
            # ================================================================
            # EXIT CONFIRMATION
            # ================================================================
            ctk.CTkLabel(
                box,
                text="EXIT LAUNCHER?",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TITLE_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['TEXT_WHITE']
            ).pack(pady=((UI['ALERT_TITLE_PADDING_TOP']), (UI['ALERT_TITLE_PADDING_BOTTOM'])))

            ctk.CTkLabel(
                box,
                text="Are you sure you want to quit?",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TEXT_SIZE']),
                fg_color="transparent",
                text_color=COLOR['ALERT_TEXT_DIM']
            ).pack(pady=(UI['ALERT_TEXT_PADDING']))

            btn_frame = ctk.CTkFrame(box, fg_color=COLOR['ALERT_BOX_BG'], corner_radius=0)
            btn_frame.pack(pady=(UI['ALERT_BTN_PADDING_TOP']))

            ctk.CTkLabel(
                btn_frame,
                text="Ⓐ YES",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_BLUE']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

            ctk.CTkLabel(
                btn_frame,
                text="Ⓑ NO",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_RED']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

        elif mode == "KILL_CONFIRM":
            # ================================================================
            # KILL GAME MENU (THREE OPTIONS)
            # ================================================================
            ctk.CTkLabel(
                box,
                text="KILL GAME?",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TITLE_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['TEXT_WHITE']
            ).pack(pady=((UI['ALERT_TITLE_PADDING_TOP']), (UI['ALERT_TITLE_PADDING_BOTTOM'])))

            ctk.CTkLabel(
                box,
                text="How would you like to proceed?",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TEXT_SIZE']),
                fg_color="transparent",
                text_color=COLOR['ALERT_TEXT_DIM']
            ).pack(pady=(UI['ALERT_TEXT_PADDING']))

            btn_frame = ctk.CTkFrame(box, fg_color=COLOR['ALERT_BOX_BG'], corner_radius=0)
            btn_frame.pack(pady=(UI['ALERT_BTN_PADDING_TOP']))

            # Option 1: Return to launcher for controller reconfiguration
            ctk.CTkLabel(
                btn_frame,
                text="Ⓐ LAUNCHER",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_BLUE']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

            # Option 2: Exit to desktop
            ctk.CTkLabel(
                btn_frame,
                text="Ⓨ DESKTOP",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['ALERT_YELLOW']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

            # Option 3: Cancel and resume game
            ctk.CTkLabel(
                btn_frame,
                text="Ⓑ CANCEL",
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_RED']
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))

    def close_alert(self):
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

        Critical: This performs a FRESH SDL scan to get correct GUID indices
        in the OS enumeration order that Ryujinx will see.
        """
        # ====================================================================
        # STEP 1: RESET SDL SUBSYSTEM
        # ====================================================================
        # Close all existing controller handles
        for c in self.controllers.values():
            SDLManager.SDL_GameControllerClose(c)
        self.controllers.clear()

        # Reinitialize SDL2/SDL3 for fresh enumeration
        SDLManager.SDL_QuitSubSystem(SDLManager.SDL_INIT_JOYSTICK | SDLManager.SDL_INIT_GAMECONTROLLER)
        SDLManager.SDL_Init()

        # ====================================================================
        # STEP 2: BUILD HARDWARE LIST WITH CORRECT GUID INDICES
        # ====================================================================
        final_hw_list = []
        guid_counters = {}  # Track index per unique GUID

        for joystick_id in SDLManager.SDL_GetJoystickIDs():
            if not SDLManager.SDL_IsGameController(joystick_id):
                continue

            ctrl = SDLManager.SDL_GameControllerOpen(joystick_id)
            if ctrl:
                joy = SDLManager.SDL_GameControllerGetJoystick(ctrl)

                # Extract GUID
                guid_obj = SDLManager.SDL_JoystickGetGUID(joy)
                psz_guid = (ctypes.c_char * 33)()
                SDLManager.SDL_JoystickGetGUIDString(guid_obj, psz_guid, 33)
                raw_guid_str = psz_guid.value.decode()
                base_guid = self.ryujinx_guid_fix(raw_guid_str)

                # Extract HID path (for matching with assignments)
                try:
                    p = SDLManager.SDL_GameControllerPath(ctrl)
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
                    "name": SDLManager.SDL_GameControllerName(ctrl).decode()
                })

                SDLManager.SDL_GameControllerClose(ctrl)

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
                if ryujinx_version == "1.1.1403":
                    # Ryujinx (v1.1.1403)
                    entry.pop("led", None)
                    entry.pop("name", None)
                elif ryujinx_version == "1.3.1":
                    # Ryujinx (v1.3.1)
                    entry.pop("name", None)
                else:
                    # Ryujinx (v1.3.2/v1.3.3/All New version)
                    entry["name"] = matched_hw["name"]

                entry["player_index"] = f"Player{i+1}"
                entry["backend"] = backend_string
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

        if os.path.exists(TARGET_EXE):
            try:
                # Launch Ryujinx with all arguments passed to launcher
                cmd_args = [TARGET_EXE] + sys.argv[1:]
                self.ryujinx_process = subprocess.Popen(cmd_args, env=ryujinx_env)
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
    root = ctk.CTk()
    app = RyujinxLauncherApp(root)
    root.mainloop()