"""
ControllerManagerSDL3.py — SDLManager class
Part of the Ryujinx Gamepad Launcher.

Wrapper over PySDL3. Nothing outside this file ever touches sdl3 directly.
Call everything on the class — no instantiation needed.

    from ControllerManagerSDL3 import SDLManager
    SDLManager.SDL_Init()
    ids = SDLManager.SDL_GetJoystickIDs()

External dependencies:
    pysdl3  — pip install pysdl3
    SDL3 shared library must be locatable via PYSDL3_DLL_PATH env var

ID-based enumeration (SDL3 design):
    SDL_GetJoystickIDs() returns opaque uint32 IDs from SDL_GetJoysticks().
    These IDs — NOT sequential integers — must be passed to all SDL3 functions.

SDL3 key differences vs SDL2:
    - Button constants use SDL_GAMEPAD_BUTTON_* (physical position).
      SDL_GAMEPAD_BUTTON_LABEL_* are display-only — wrong for GetGamepadButton.
    - SDL_INIT_GAMECONTROLLER renamed to SDL_INIT_GAMEPAD.
    - SDL_GUIDToString replaces SDL_JoystickGetGUIDString (different signature).
    - SDL_Init returns bool (True = success) instead of int (0 = success).
"""

import ctypes
import sys
from tkinter import messagebox

# ============================================================================
# IMPORT SDL3 LIBRARY
# ============================================================================
try:
    import sdl3
except ImportError:
    messagebox.showerror("Error", "PySDL3 not installed.\nRun: pip install pysdl3")
    sys.exit(1)
except Exception as e:
    messagebox.showerror("DLL Error", f"Could not find SDL3 Library in:\nRyujinx Directory\n\nError: {e}")
    sys.exit(1)


# ============================================================================
# SDLManager CLASS
# ============================================================================

class SDLManager:
    """
    Staticmethod wrapper over SDL3.

    Three kinds of members:
        - Plain class attribute : integer constants and type aliases (no self risk)
        - sdl3.fn : direct SDL3 function aliases (blocks self injection)
        - @staticmethod def     : custom logic wrapping SDL3 calls
    """

    # =========================================================================
    # BUTTON CONSTANTS  (integers — plain class attribute)
    # =========================================================================
    SDL_CONTROLLER_BUTTON_A              = sdl3.SDL_GAMEPAD_BUTTON_SOUTH          # Cross / A
    SDL_CONTROLLER_BUTTON_B              = sdl3.SDL_GAMEPAD_BUTTON_EAST           # Circle / B
    SDL_CONTROLLER_BUTTON_X              = sdl3.SDL_GAMEPAD_BUTTON_WEST           # Square / X
    SDL_CONTROLLER_BUTTON_Y              = sdl3.SDL_GAMEPAD_BUTTON_NORTH          # Triangle / Y
    SDL_CONTROLLER_BUTTON_START          = sdl3.SDL_GAMEPAD_BUTTON_START
    SDL_CONTROLLER_BUTTON_BACK           = sdl3.SDL_GAMEPAD_BUTTON_BACK
    SDL_CONTROLLER_BUTTON_LEFT_SHOULDER  = sdl3.SDL_GAMEPAD_BUTTON_LEFT_SHOULDER
    SDL_CONTROLLER_BUTTON_RIGHT_SHOULDER = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER

    # =========================================================================
    # EVENT CONSTANTS  (integers — plain class attribute)
    # =========================================================================
    SDL_CONTROLLERBUTTONDOWN        = sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN
    SDL_QUIT                        = sdl3.SDL_EVENT_QUIT

    # =========================================================================
    # INIT CONSTANTS  (integers — plain class attribute)
    # SDL_INIT_GAMECONTROLLER renamed to SDL_INIT_GAMEPAD in SDL3
    # =========================================================================
    SDL_INIT_GAMECONTROLLER         = sdl3.SDL_INIT_GAMEPAD
    SDL_INIT_JOYSTICK               = sdl3.SDL_INIT_JOYSTICK

    # =========================================================================
    # TYPE ALIASES  (class/type — plain class attribute)
    # =========================================================================
    SDL_Event                       = sdl3.SDL_Event

    # =========================================================================
    # SDL FUNCTION ALIASES  (staticmethod — blocks self injection)
    # =========================================================================
    SDL_IsGameController            = sdl3.SDL_IsGamepad
    SDL_GameControllerOpen          = sdl3.SDL_OpenGamepad
    SDL_GameControllerClose         = sdl3.SDL_CloseGamepad
    SDL_GameControllerName          = sdl3.SDL_GetGamepadName
    SDL_GameControllerGetJoystick   = sdl3.SDL_GetGamepadJoystick
    SDL_GameControllerGetButton     = sdl3.SDL_GetGamepadButton
    SDL_GameControllerPath          = sdl3.SDL_GetGamepadPath
    SDL_JoystickInstanceID          = sdl3.SDL_GetJoystickID
    SDL_JoystickGetPlayerIndex      = sdl3.SDL_GetJoystickPlayerIndex
    SDL_JoystickGetGUID             = sdl3.SDL_GetJoystickGUID
    SDL_PollEvent                   = sdl3.SDL_PollEvent
    SDL_QuitSubSystem               = sdl3.SDL_QuitSubSystem
    SDL_GetError                    = sdl3.SDL_GetError
    SDL_Quit                        = sdl3.SDL_Quit

    # =========================================================================
    # CUSTOM WRAPPERS  (@staticmethod def — extra logic on top of SDL3)
    # =========================================================================
    @staticmethod
    def SDL_Init(flags=None):
        """
        Initialize SDL3 subsystems.
        SDL3: returns True on success, False on failure (opposite of SDL2).
        """
        if flags is None:
            flags = sdl3.SDL_INIT_GAMEPAD | sdl3.SDL_INIT_JOYSTICK
        ret = sdl3.SDL_Init(flags)
        if not ret:  # SDL3: False = failure
            err = sdl3.SDL_GetError()
            messagebox.showerror("Driver Error", f"Failed to initialize SDL3.\n{err}")

    @staticmethod
    def SDL_GetJoystickIDs():
        """
        Return list of currently connected SDL_JoystickID values.

        SDL3 is ID-based — these are opaque uint32 values, NOT sequential indices.
        Always iterate over this list; never use range(count) as SDL2 substitutes.

        Returns:
            list[int]: Joystick instance IDs (may be empty)
        """
        count = ctypes.c_int(0)
        ids_ptr = sdl3.SDL_GetJoysticks(ctypes.byref(count))
        if not ids_ptr or count.value == 0:
            return []
        return list(ids_ptr[:count.value])

    @staticmethod
    def SDL_NumJoysticks():
        """Return the count of currently connected joysticks."""
        count = ctypes.c_int(0)
        sdl3.SDL_GetJoysticks(ctypes.byref(count))
        return count.value

    @staticmethod
    def SDL_JoystickGetGUIDString(guid, buf, size):
        """
        Write GUID as 32-char hex string into buf.
        SDL3: SDL_GUIDToString(guid, buf, size) — different name, same intent as SDL2.
        """
        sdl3.SDL_GUIDToString(guid, buf, size)

    @staticmethod
    def get_button_info(event):
        """Returns (button, which) from a gamepad button event."""
        return event.gbutton.button, event.gbutton.which