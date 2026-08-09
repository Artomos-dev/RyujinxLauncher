"""
Core/Ui.py
All rendering for the launcher: theme, scaling, the 8-slot player grid,
modal alerts and toasts.

Emulator-agnostic. The UI is fed plain view-model dicts by Core/App.py and
never reads launcher state directly.

Layout is authored against a 1280x720 baseline and scaled uniformly to the
actual screen resolution, so the same numbers work from 720p to 4K.
"""

import ctypes
import os
import sys
import tkinter as tk

import customtkinter as ctk

from .Paths import resource_path

# ============================================================================
# SECTION 1: HI-DPI DISPLAY SUPPORT
# ============================================================================
# Enables proper scaling on high-resolution displays (4K, 1440p).
# Runs at import time - it must happen before any window is created.
if sys.platform == "win32":
    # 1. Stop Windows from double-scaling
    ctk.deactivate_automatic_dpi_awareness()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1+
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Windows Vista-8
        except Exception:
            pass  # Unsupported
else:
    # 2. Stop Linux from double-scaling
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
    'TOAST_POSITION_Y': 0.95,       # Toast Y position (relative)
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
# SECTION 4: DYNAMIC SCALING UTILITY
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
# SECTION 5: LAUNCHER UI
# ============================================================================
class LauncherUi:
    """
    Owns every widget, the alert state, and the resolution-change rebuild.

    Core/App.py drives it through four calls:
        refresh(slots)          - redraw the player grid
        show_toast(msg, color)  - transient message
        show_alert(mode)        - modal dialog, mode readable via .alert_mode
        close_alert()
    """

    def __init__(self, root, emulator_name, launch_label, on_rebuild):
        """
        Args:
            root          (ctk.CTk): The root window.
            emulator_name (str):     "Ryujinx" - window title and alert copy.
            launch_label  (str):     What START launches - "GAME" or "RYUJINX".
            on_rebuild    (callable): Called after a resolution change rebuilds
                                      the widgets, so App can repaint the grid.
        """
        self.root = root
        self.emulator_name = emulator_name
        self.launch_label = launch_label
        self.on_rebuild = on_rebuild

        self.alert_mode = None      # Current alert type (if any)
        self.alert_frame = None     # Alert dialog container
        self.toast_job = None       # Toast notification timer
        self.resize_job = None      # Debounce timer for resolution changes

        self.root.title(f"{emulator_name} Launcher")
        self.root.configure(fg_color=COLOR['BG_DARK'])
        self.root.attributes('-fullscreen', True)

        self._load_icon()

        # Calculate UI scaling based on screen resolution
        self.root.update_idletasks()
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.scale = calculate_scale(self.screen_width, self.screen_height)

        ctk.set_window_scaling(self.scale)  # Scales the window size
        ctk.set_widget_scaling(self.scale)  # Scales the buttons, fonts, and elements inside

        # Bind the configure event to detect resolution/scale changes
        self.root.bind("<Configure>", self._on_window_configure)

        self.build()

    def _load_icon(self):
        """Window/taskbar icon: .ico on Windows, .png elsewhere."""
        ico_path = resource_path(os.path.join("assets", "RyujinxLauncherIcon.ico"))
        png_path = resource_path(os.path.join("assets", "RyujinxLauncherPNG.png"))

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
                icon_img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, icon_img)
            except Exception:
                pass

    # ========================================================================
    # RESOLUTION CHANGE HANDLING
    # ========================================================================
    def _on_window_configure(self, event):
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
            self.resize_job = self.root.after(100, self._perform_resize)

    def _perform_resize(self):
        """Rebuild the UI with the new scale factor."""
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
        self.build()

        # Restore controller assignment visuals onto the new UI
        self.on_rebuild()

        if self.alert_mode:
            # 1. Capture current mode
            mode = self.alert_mode

            # 2. Destroy the old, wrongly scaled/positioned alert frame
            if self.alert_frame:
                self.alert_frame.destroy()
                self.alert_frame = None

            # 3. Re-draw the alert (This forces it to the top of the stack)
            self.show_alert(mode)

    # ========================================================================
    # WIDGET CONSTRUCTION
    # ========================================================================
    def build(self):
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
        self.lbl_title = ctk.CTkLabel(
            self.main_container,
            text=f"{self.launch_label} CONTROLLER SETUP",
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
                text="Ⓑ DISCONNECT   |   Ⓧ PROFILE",
                font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['NEON_RED']
            )

            # Profile selector label (center, hidden by default - shown in State B)
            lbl_profile = ctk.CTkLabel(
                card,
                text="◄   Profile: RL Default   ►",
                font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold"),
                fg_color="transparent",
                text_color=COLOR['TEXT_DIM']
            )

            self.slot_cards.append((card, lbl_num, lbl_status, lbl_disc, lbl_profile))

        # Footer: Button hints
        self.footer_frame = ctk.CTkFrame(
            self.root,
            fg_color=COLOR['FOOTER_BG'],
            height=UI['FOOTER_HEIGHT'],
            corner_radius=0
        )
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.pack_propagate(False)

        self.separator_text = ctk.CTkLabel(
            self.footer_frame,
            text="|",
            font=(UI['FONT_FAMILY'], UI['FONT_FOOTER_SIZE'], "bold"),
            fg_color="transparent",
            text_color=COLOR['TEXT_WHITE']
        )
        self.launch_text = ctk.CTkLabel(
            self.footer_frame,
            text=f"☰ LAUNCH {self.launch_label}",
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
    # PLAYER GRID
    # ========================================================================
    def refresh(self, slots):
        """
        Update all player slot cards.

        Args:
            slots (list[dict]): One entry per assigned controller, in player
                order, at most 8:
                    {"name": str, "color": "#RRGGBB",
                     "profile": str, "editing": bool}
                Remaining cards render as empty slots.
        """
        for i in range(8):
            card, lbl_num, lbl_status, lbl_disc, lbl_profile = self.slot_cards[i]

            if i < len(slots):
                # ============================================================
                # ACTIVE SLOT (Controller assigned)
                # ============================================================
                slot = slots[i]
                active_color = slot["color"]

                # Update Card Border (Use active_color)
                card.configure(
                    fg_color=COLOR['BG_CARD'],
                    border_color=active_color
                )

                # Update Player Number Color (Use active_color)
                lbl_num.configure(fg_color="transparent", text_color=active_color)

                if slot["editing"]:
                    # ========================================================
                    # STATE B: Profile Selection Mode
                    # ========================================================
                    lbl_status.place_forget()

                    lbl_profile.configure(
                        text=f"◄   Profile: {slot['profile']}   ►",
                        fg_color="transparent",
                        text_color=active_color,
                        font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold")
                    )
                    lbl_profile.place(relx=0.5, rely=0.35, anchor="center")

                    lbl_disc.place(relx=0.5, rely=0.75, anchor="center")
                    lbl_disc.configure(
                        text="Ⓑ CANCEL   |   Ⓧ CONFIRM",
                        fg_color="transparent",
                        text_color=COLOR['NEON_RED']
                    )

                else:
                    # ========================================================
                    # STATE A: Normal Mode
                    # ========================================================
                    lbl_profile.place_forget()

                    lbl_status.place(relx=0.5, rely=0.25, anchor="center")
                    lbl_status.configure(
                        text=slot["name"],
                        fg_color="transparent",
                        text_color=active_color,
                        font=(UI['FONT_FAMILY'], UI['FONT_CARD_SIZE'], "bold")
                    )

                    lbl_disc.place(relx=0.5, rely=0.75, anchor="center")
                    lbl_disc.configure(
                        text="Ⓑ DISCONNECT   |   Ⓧ PROFILE",
                        fg_color="transparent",
                        text_color=COLOR['NEON_RED']
                    )

            else:
                # ============================================================
                # INACTIVE SLOT (No controller assigned)
                # ============================================================
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
                lbl_profile.place_forget()

    # ========================================================================
    # TOAST
    # ========================================================================
    def show_toast(self, message, color=None):
        """Display a temporary notification message (hides after 2 seconds)."""
        if self.toast_job:
            self.root.after_cancel(self.toast_job)

        self.lbl_toast.configure(text_color=color or COLOR['NEON_RED'])
        self.lbl_toast.configure(text=message)
        self.lbl_toast.place(relx=0.5, rely=UI['TOAST_POSITION_Y'], anchor="center")
        self.toast_job = self.root.after(2000, lambda: self.lbl_toast.place_forget())

    # ========================================================================
    # ALERT DIALOG SYSTEM
    # ========================================================================
    def show_alert(self, mode):
        """
        Display a modal alert dialog.

        Args:
            mode (str): Alert type - "LAUNCH", "EXIT", or "KILL_CONFIRM"
        """
        self.alert_mode = mode

        # Fullscreen overlay
        self.alert_frame = ctk.CTkFrame(self.root, fg_color=COLOR['ALERT_BG'], corner_radius=0)
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
            self._alert_title(box, "⚠️ NO CONTROLLERS", COLOR['ALERT_YELLOW'])
            self._alert_text(box, f"{self.emulator_name} will launch with default inputs.")
            self._alert_buttons(box, [
                (f"Ⓐ LAUNCH {self.launch_label}", COLOR['NEON_BLUE']),
                ("Ⓑ BACK", COLOR['NEON_RED']),
            ])

        elif mode == "EXIT":
            # ================================================================
            # EXIT CONFIRMATION
            # ================================================================
            self._alert_title(box, "EXIT LAUNCHER?", COLOR['TEXT_WHITE'])
            self._alert_text(box, "Are you sure you want to quit?")
            self._alert_buttons(box, [
                ("Ⓐ YES", COLOR['NEON_BLUE']),
                ("Ⓑ NO", COLOR['NEON_RED']),
            ])

        elif mode == "KILL_CONFIRM":
            # ================================================================
            # KILL GAME MENU (THREE OPTIONS)
            # ================================================================
            self._alert_title(box, "KILL GAME?", COLOR['TEXT_WHITE'])
            self._alert_text(box, "How would you like to proceed?")
            self._alert_buttons(box, [
                ("Ⓐ LAUNCHER", COLOR['NEON_BLUE']),    # Return to launcher
                ("Ⓨ DESKTOP", COLOR['ALERT_YELLOW']),  # Exit to desktop
                ("Ⓑ CANCEL", COLOR['NEON_RED']),       # Resume game
            ])

    def close_alert(self):
        self.alert_mode = None
        if self.alert_frame:
            self.alert_frame.destroy()
            self.alert_frame = None

    # --- alert building blocks ---------------------------------------------
    def _alert_title(self, box, text, color):
        ctk.CTkLabel(
            box,
            text=text,
            font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TITLE_SIZE'], "bold"),
            fg_color="transparent",
            text_color=color
        ).pack(pady=((UI['ALERT_TITLE_PADDING_TOP']), (UI['ALERT_TITLE_PADDING_BOTTOM'])))

    def _alert_text(self, box, text):
        ctk.CTkLabel(
            box,
            text=text,
            font=(UI['FONT_FAMILY'], UI['FONT_ALERT_TEXT_SIZE']),
            fg_color="transparent",
            text_color=COLOR['ALERT_TEXT_DIM']
        ).pack(pady=(UI['ALERT_TEXT_PADDING']))

    def _alert_buttons(self, box, buttons):
        btn_frame = ctk.CTkFrame(box, fg_color=COLOR['ALERT_BOX_BG'], corner_radius=0)
        btn_frame.pack(pady=(UI['ALERT_BTN_PADDING_TOP']))

        for text, color in buttons:
            ctk.CTkLabel(
                btn_frame,
                text=text,
                font=(UI['FONT_FAMILY'], UI['FONT_ALERT_BTN_SIZE'], "bold"),
                fg_color="transparent",
                text_color=color
            ).pack(side="left", padx=(UI['ALERT_BTN_PADDING_X']))
