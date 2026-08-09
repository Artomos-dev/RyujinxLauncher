"""
Core/App.py
The launcher state machine: controller detection, player assignment, profile
selection, kill combo, and the emulator process lifecycle.

Emulator-agnostic. Everything emulator-specific arrives through the Emulator
instance handed in by Core/Bootstrap.py.
"""

import ctypes
import os
import random
import re
import sys
import time
from tkinter import messagebox

from .Log import log
from .Process import launch
from .Ui import COLOR, COLOR_POOL, LauncherUi

MAX_PLAYERS = 8
POLL_INTERVAL_MS = 16


class LauncherApp:
    """
    Main application class for the gamepad launcher.

    Manages controller detection, assignment, and the emulator process
    lifecycle.
    """

    def __init__(self, root, emulator, sdl):
        """
        Args:
            root     (ctk.CTk):  The root window.
            emulator (Emulator): Located and prepared emulator, profiles loaded.
            sdl      (type):     SDLManager class from Core.Sdl.load_sdl().
        """
        self.root = root
        self.emu = emulator
        self.sdl = sdl

        # Frontend arguments (Playnite, LaunchBox, Moonlight...) mean we are
        # launching a specific game rather than the emulator's own UI
        launch_label = "GAME" if len(sys.argv) > 1 else emulator.name.upper()
        self.ui = LauncherUi(root, emulator.name, launch_label, self.refresh_grid)

        # Keyboard shortcuts for accessibility
        self.root.bind("<Return>", lambda e: self.handle_enter_key())
        self.root.bind("<Escape>", lambda e: self.handle_esc_key())

        # Initialize SDL2/SDL3 controller subsystem
        self.sdl.SDL_Init()

        # State management
        self.controllers = {}               # {instance_id: SDL_GameController}
        self.assignments = []               # [{"path", "name", "profile_key", "is_editing"}, ...] - Player order
        self.hardware_map = {}              # {instance_id: (hid_path, display_name)} - Currently connected
        self.color_pool = list(COLOR_POOL)  # Copy the pool to modify it locally
        random.shuffle(self.color_pool)     # Shuffle the color pool
        self.hid_colors = {}                # Dictionary to remember {hid_path: color_hex}
        self.hid_profiles = {}              # Dictionary to remember {hid_path: profile_key} across reconnects
        self.process = None                 # Emulator subprocess handle
        self.returning_to_launcher = False  # Flag for kill -> restart flow

        # Profile keys come from the emulator; the first one is the default
        self.profile_keys = list(self.emu.profiles.keys())
        self.default_profile = self.profile_keys[0] if self.profile_keys else ""

        # Start main loop
        self.update_loop()

    # ========================================================================
    # KEYBOARD INPUT HANDLERS
    # ========================================================================
    def handle_enter_key(self):
        """Handle Enter key press (confirm action in alerts)."""
        if self.ui.alert_mode == "LAUNCH":
            self.force_launch()
        elif self.ui.alert_mode == "EXIT":
            self.emu.cleanup()
            self.root.destroy()
        elif self.ui.alert_mode == "KILL_CONFIRM":
            self.kill_and_quit()

    def handle_esc_key(self):
        """Handle Escape key press (cancel/back action)."""
        if self.ui.alert_mode:
            self.ui.close_alert()
        else:
            self.ui.show_alert("EXIT")

    # ========================================================================
    # PROCESS MANAGEMENT
    # ========================================================================
    def kill_and_quit(self):
        """Kill the emulator and exit the launcher (kill menu -> Desktop)."""
        if self.process:
            self.process.kill()
            log("INFO", f"{self.emu.name} killed - exiting to desktop")
        self.emu.cleanup()
        self.root.quit()
        sys.exit()

    def kill_and_restart(self):
        """
        Kill the emulator and return to the launcher (kill menu -> Launcher).

        Sets a flag to prevent automatic exit when the process terminates.
        """
        self.returning_to_launcher = True
        time.sleep(0.005)  # 5ms delay for flag to propagate

        if self.process:
            self.process.kill()
            log("INFO", f"{self.emu.name} killed - returning to launcher")
        self.process = None

        # Reset launcher state for fresh assignment
        self.assignments = []
        self.refresh_grid()
        self.ui.close_alert()
        self.root.deiconify()
        self.root.state('normal')

    # ========================================================================
    # MAIN EVENT LOOP
    # ========================================================================
    def update_loop(self):
        """
        Main event processing loop (runs every 16ms).

        Handles:
        - Emulator process monitoring
        - Kill combo detection
        - Controller hot-plug detection
        - Gamepad button events
        """
        sdl = self.sdl

        # ====================================================================
        # EMULATOR PROCESS MONITORING
        # ====================================================================
        if self.process and not self.ui.alert_mode:
            # Check if the emulator has exited
            if self.process.poll() is not None:
                if self.returning_to_launcher:
                    # User chose "Launcher" from kill menu - reset and show UI
                    log("INFO", f"{self.emu.name} exited - returning to launcher")
                    self.assignments = []
                    self.refresh_grid()
                    self.root.deiconify()
                    self.root.state('normal')
                    self.process = None
                    self.returning_to_launcher = False
                else:
                    # Emulator closed normally or crashed - exit launcher
                    log("INFO", f"{self.emu.name} exited - closing launcher")
                    self.root.quit()
                    sys.exit()

            # ================================================================
            # GLOBAL KILL COMBO DETECTION (ANY CONTROLLER)
            # ================================================================
            # Checks all connected controllers for Back+L+R press
            # Global approach allows recovery if Player 1's controller fails
            kill_combo = False
            for ctrl in self.controllers.values():
                if (sdl.SDL_GameControllerGetButton(ctrl, sdl.SDL_CONTROLLER_BUTTON_BACK) and
                    sdl.SDL_GameControllerGetButton(ctrl, sdl.SDL_CONTROLLER_BUTTON_LEFT_SHOULDER) and
                    sdl.SDL_GameControllerGetButton(ctrl, sdl.SDL_CONTROLLER_BUTTON_RIGHT_SHOULDER)):
                    kill_combo = True
                    break

            if kill_combo:
                self.root.deiconify()  # Bring launcher to foreground
                log("INFO", "Kill combo detected - showing menu")
                self.ui.show_alert("KILL_CONFIRM")
                self.root.after(POLL_INTERVAL_MS, self.update_loop)
                return

        # ====================================================================
        # CONTROLLER HARDWARE DETECTION (HOT-PLUG SUPPORT)
        # ====================================================================
        self.hardware_map.clear()

        # Scan all connected controllers and build current hardware map
        for joystick_id in sdl.SDL_GetJoystickIDs():
            if not sdl.SDL_IsGameController(joystick_id):
                continue  # Skip non-gamepad devices (e.g., flight sticks)

            ctrl = sdl.SDL_GameControllerOpen(joystick_id)
            if ctrl:
                joy = sdl.SDL_GameControllerGetJoystick(ctrl)
                instance_id = sdl.SDL_JoystickInstanceID(joy)

                # Cache controller handle for button polling
                if instance_id not in self.controllers:
                    self.controllers[instance_id] = ctrl

                raw_name = sdl.SDL_GameControllerName(ctrl).decode()

                # Get HID path (hardware-specific, persists across reconnects)
                try:
                    path_bytes = sdl.SDL_GameControllerPath(ctrl)
                    hid_path = path_bytes.decode() if path_bytes else f"UNK_{instance_id}"
                except Exception:
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

        for assignment in self.assignments:
            if assignment["path"] in current_connected_paths:
                new_assignments.append(assignment)  # Still connected, keep assignment
            else:
                dropped_names.append((assignment["path"], assignment["name"]))  # Disconnected

        # Update state if any controllers were removed
        if len(new_assignments) != len(self.assignments):
            self.assignments = new_assignments
            self.refresh_grid()

            # Show toast notification for first disconnected controller
            if dropped_names:
                self.ui.show_toast(
                    f"⚠️ {dropped_names[0][1]} Disconnected!",
                    self.hid_colors.get(dropped_names[0][0], COLOR['NEON_RED'])
                )
                for path, name in dropped_names:
                    log("INFO", "Controller disconnected", name)
                    color = self.hid_colors.pop(path, None)
                    if color:
                        self.color_pool.append(color)
                    self.hid_profiles.pop(path, None)  # Clear profile on hardware disconnect

        # ====================================================================
        # GAMEPAD BUTTON EVENT PROCESSING
        # ====================================================================
        event = sdl.SDL_Event()
        while sdl.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl.SDL_CONTROLLERBUTTONDOWN:
                button, which = sdl.get_button_info(event)
                # ============================================================
                # ALERT MODE HANDLERS
                # ============================================================
                if self.ui.alert_mode:
                    if self.ui.alert_mode == "KILL_CONFIRM":
                        # Three-option kill menu
                        if button == sdl.SDL_CONTROLLER_BUTTON_A:
                            self.kill_and_restart()  # Return to launcher
                        elif button == sdl.SDL_CONTROLLER_BUTTON_Y:
                            self.kill_and_quit()  # Exit to desktop
                        elif button == sdl.SDL_CONTROLLER_BUTTON_B:
                            self.ui.close_alert()
                            self.root.withdraw()  # Cancel, resume game
                    else:
                        # Standard two-option alerts (launch/exit confirmations)
                        if button == sdl.SDL_CONTROLLER_BUTTON_A:
                            if self.ui.alert_mode == "LAUNCH":
                                self.force_launch()
                            elif self.ui.alert_mode == "EXIT":
                                self.emu.cleanup()
                                self.root.destroy()
                        elif button == sdl.SDL_CONTROLLER_BUTTON_B:
                            self.ui.close_alert()

                # ============================================================
                # NORMAL MODE HANDLERS
                # ============================================================
                else:
                    # Ignore input if game is running (prevent mid-game reassignment)
                    if self.process:
                        continue

                    if button == sdl.SDL_CONTROLLER_BUTTON_A:
                        # Confirm profile edit if active, otherwise assign
                        slot_idx = self.find_slot_by_instance(which)
                        if slot_idx != -1 and self.assignments[slot_idx]["is_editing"]:
                            self.toggle_profile_edit(which)
                        else:
                            self.assign_player(which)   # Assign controller
                    elif button == sdl.SDL_CONTROLLER_BUTTON_B:
                        # Cancel profile edit if active, otherwise disconnect
                        slot_idx = self.find_slot_by_instance(which)
                        if slot_idx != -1 and self.assignments[slot_idx]["is_editing"]:
                            self.assignments[slot_idx]["is_editing"] = False
                            self.refresh_grid()
                        else:
                            self.remove_player(which)   # Remove assignment
                    elif button == sdl.SDL_CONTROLLER_BUTTON_X:
                        self.toggle_profile_edit(which) # Enter/exit profile selection
                    elif button == sdl.SDL_CONTROLLER_BUTTON_DPAD_LEFT:
                        self.cycle_profile(which, -1)   # Previous profile
                    elif button == sdl.SDL_CONTROLLER_BUTTON_DPAD_RIGHT:
                        self.cycle_profile(which, 1)    # Next profile
                    elif button == sdl.SDL_CONTROLLER_BUTTON_START:
                        self.check_launch()             # Launch the emulator
                    elif button == sdl.SDL_CONTROLLER_BUTTON_BACK:
                        self.ui.show_alert("EXIT")      # Exit launcher
            elif event.type == sdl.SDL_CONTROLLERAXISMOTION:
                direction, which = sdl.get_axis_motion_info(event)
                if which is not None:
                    if direction != 0 and not sdl.axis_engaged.get(which, False):
                        sdl.axis_engaged[which] = True
                        self.cycle_profile(which, direction)
                    elif direction == 0:
                        sdl.axis_engaged[which] = False  # reset when stick returns to center
            elif event.type == sdl.SDL_QUIT:
                self.emu.cleanup()
                self.root.destroy()

        # Schedule next update
        self.root.after(POLL_INTERVAL_MS, self.update_loop)

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
        for assignment in self.assignments:
            if assignment["path"] == target_path:
                return

        # Enforce player maximum
        if len(self.assignments) >= MAX_PLAYERS:
            return

        # Restore previously selected profile for this HID, default to the first one
        profile_key = self.hid_profiles.get(target_path, self.default_profile)

        self.assignments.append({
            "path": target_path,
            "name": display_name,
            "profile_key": profile_key,
            "is_editing": False
        })
        log("INFO", f"Assigned {display_name} -> Player {len(self.assignments)} | Profile: {profile_key}")
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
        for i, assignment in enumerate(self.assignments):
            if assignment["path"] == target_path:
                found_index = i
                break

        if found_index != -1:
            self.assignments.pop(found_index)
            log("INFO", f"Removed {target_path} from Player {found_index + 1}")
            self.refresh_grid()

    # ========================================================================
    # PROFILE SELECTION LOGIC
    # ========================================================================
    def find_slot_by_instance(self, instance_id):
        """
        Find the assignments index for a given controller instance ID.

        Returns:
            int: Index into self.assignments, or -1 if not found
        """
        if instance_id not in self.hardware_map:
            return -1
        target_path, _ = self.hardware_map[instance_id]
        for i, assignment in enumerate(self.assignments):
            if assignment["path"] == target_path:
                return i
        return -1

    def toggle_profile_edit(self, instance_id):
        """
        Toggle profile selection mode (State A <-> State B) for a controller's slot.

        X in State A -> enters edit mode.
        A (or X) in State B -> confirms current selection and exits edit mode.
        """
        slot_idx = self.find_slot_by_instance(instance_id)
        if slot_idx == -1:
            return  # Controller not assigned to any slot
        self.assignments[slot_idx]["is_editing"] = not self.assignments[slot_idx]["is_editing"]
        if not self.assignments[slot_idx]["is_editing"]:
            # Selection confirmed
            log("INFO", f"Player {slot_idx + 1} profile confirmed -> {self.assignments[slot_idx]['profile_key']}")

        self.refresh_grid()

    def cycle_profile(self, instance_id, direction):
        """
        Cycle through available profiles for a controller's slot.
        Only acts when that slot is in edit mode (is_editing == True).

        Args:
            instance_id (int): SDL2/SDL3 instance ID of the controller
            direction   (int): +1 for next, -1 for previous
        """
        slot_idx = self.find_slot_by_instance(instance_id)
        if slot_idx == -1:
            return
        assignment = self.assignments[slot_idx]
        if not assignment["is_editing"]:
            return  # D-Pad ignored unless in profile selection mode
        if not self.profile_keys:
            return
        current_idx = self.profile_keys.index(assignment["profile_key"])
        new_key = self.profile_keys[(current_idx + direction) % len(self.profile_keys)]
        assignment["profile_key"] = new_key
        self.hid_profiles[assignment["path"]] = new_key
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
        """Build the view models for the player grid and hand them to the UI."""
        slots = []
        for assignment in self.assignments:
            slots.append({
                # Remove trailing index suffix, e.g. "Pro Controller (2)"
                "name": re.sub(r'\s*\(\d+\)$', '', assignment["name"]),
                "color": self.get_assigned_color(assignment["path"]),
                "profile": assignment["profile_key"],
                "editing": assignment["is_editing"],
            })
        self.ui.refresh(slots)

    # ========================================================================
    # CONFIG GENERATION & LAUNCH
    # ========================================================================
    def scan_hardware(self):
        """
        Fresh SDL enumeration performed immediately before writing the config.

        Critical: the subsystem is torn down and re-initialized so the pads are
        enumerated in the same OS order the emulator itself will see.

        Returns:
            list[dict]: [{"path", "guid", "name"}, ...] in enumeration order.
                        "guid" is the raw 32-char SDL hex string; turning it
                        into an emulator-specific id is the emulator's job.
        """
        sdl = self.sdl

        # Close all existing controller handles
        for ctrl in self.controllers.values():
            sdl.SDL_GameControllerClose(ctrl)
        self.controllers.clear()

        # Reinitialize SDL2/SDL3 for fresh enumeration
        sdl.SDL_QuitSubSystem(sdl.SDL_INIT_JOYSTICK | sdl.SDL_INIT_GAMECONTROLLER)
        sdl.SDL_Init()

        hardware = []
        for joystick_id in sdl.SDL_GetJoystickIDs():
            if not sdl.SDL_IsGameController(joystick_id):
                continue

            ctrl = sdl.SDL_GameControllerOpen(joystick_id)
            if not ctrl:
                continue

            joy = sdl.SDL_GameControllerGetJoystick(ctrl)

            # Extract GUID as a raw hex string
            guid_obj = sdl.SDL_JoystickGetGUID(joy)
            psz_guid = (ctypes.c_char * 33)()
            sdl.SDL_JoystickGetGUIDString(guid_obj, psz_guid, 33)

            # Extract HID path (for matching with assignments)
            try:
                p = sdl.SDL_GameControllerPath(ctrl)
                path = p.decode() if p else ""
            except Exception:
                path = ""

            hardware.append({
                "path": path,
                "guid": psz_guid.value.decode(),
                "name": sdl.SDL_GameControllerName(ctrl).decode()
            })

            sdl.SDL_GameControllerClose(ctrl)

        return hardware

    def check_launch(self):
        """Validate assignment state before launching."""
        if len(self.assignments) == 0:
            self.ui.show_alert("LAUNCH")  # Warn about no controllers
        else:
            self.force_launch()

    def force_launch(self):
        """
        Write the controller configuration and start the emulator.

        Any command-line arguments (e.g. a game path from Playnite) are passed
        straight through.
        """
        self.emu.write_input_config(self.assignments, self.scan_hardware())

        cmd_args = self.emu.command(sys.argv)
        log("INFO", "Launching", str(cmd_args))
        self.root.withdraw()  # Hide launcher window
        self.returning_to_launcher = False  # Clear restart flag

        if os.path.exists(self.emu.exe):
            try:
                self.process = launch(cmd_args, self.emu.env)
            except Exception as e:
                log("EXCEPTION", "Launch failed", e)
                messagebox.showerror(
                    "Launch Error",
                    f"Failed to start {self.emu.name}.\n{e}"
                )
                sys.exit()
        else:
            log("ERROR", "Executable not found", self.emu.exe)
            messagebox.showerror(
                "Missing File",
                f"Could not find {self.emu.exe}"
            )
            sys.exit()
