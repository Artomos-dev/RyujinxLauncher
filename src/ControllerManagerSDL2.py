"""
ControllerManagerSDL2.py — SDLManager class
Part of the Ryujinx Gamepad Launcher.

Wrapper over PySDL2. Nothing outside this file ever touches sdl2 directly.
Call everything on the class — no instantiation needed.

    from ControllerManagerSDL2 import SDLManager
    SDLManager.SDL_Init()
    ids = SDLManager.SDL_GetJoystickIDs()

External dependencies:
    pysdl2  — pip install pysdl2
    SDL2 shared library must be locatable via PYSDL2_DLL_PATH env var

Index-based enumeration (SDL2 design):
    SDL_GetJoystickIDs() returns [0, 1, 2 ...] sequential indices.
    These indices are passed directly to all other SDL2 functions.
"""

import sys
from tkinter import messagebox

# ============================================================================
# IMPORT SDL2 LIBRARY
# ============================================================================
try:
    import sdl2
    import sdl2.ext
except ImportError:
    messagebox.showerror("Error", "PySDL2 not installed.\nRun: pip install pysdl2")
    sys.exit(1)
except Exception as e:
    messagebox.showerror("DLL Error", f"Could not find SDL2 Library in:\n Ryujinx Directory\n\nError: {e}")
    sys.exit(1)


# ============================================================================
# SDLManager CLASS
# ============================================================================

class SDLManager:
    """
    Staticmethod wrapper over SDL2.

    Three kinds of members:
        - Plain class attribute : integer constants and type aliases (no self risk)
        - sdl2.fn : direct SDL2 function aliases (blocks self injection)
        - @staticmethod def     : custom logic wrapping SDL2 calls
    """

    # =========================================================================
    # BUTTON CONSTANTS  (integers — plain class attribute)
    # =========================================================================
    SDL_CONTROLLER_BUTTON_A                 = sdl2.SDL_CONTROLLER_BUTTON_A      # Cross / A
    SDL_CONTROLLER_BUTTON_B                 = sdl2.SDL_CONTROLLER_BUTTON_B      # Circle / B
    SDL_CONTROLLER_BUTTON_X                 = sdl2.SDL_CONTROLLER_BUTTON_X      # Square / X
    SDL_CONTROLLER_BUTTON_Y                 = sdl2.SDL_CONTROLLER_BUTTON_Y      # Triangle / Y
    SDL_CONTROLLER_BUTTON_START             = sdl2.SDL_CONTROLLER_BUTTON_START
    SDL_CONTROLLER_BUTTON_BACK              = sdl2.SDL_CONTROLLER_BUTTON_BACK
    SDL_CONTROLLER_BUTTON_LEFT_SHOULDER     = sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER
    SDL_CONTROLLER_BUTTON_RIGHT_SHOULDER    = sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER

    # =========================================================================
    # EVENT CONSTANTS  (integers — plain class attribute)
    # =========================================================================
    SDL_CONTROLLERBUTTONDOWN        = sdl2.SDL_CONTROLLERBUTTONDOWN
    SDL_QUIT                        = sdl2.SDL_QUIT

    # =========================================================================
    # INIT CONSTANTS  (integers — plain class attribute)
    # =========================================================================
    SDL_INIT_GAMECONTROLLER         = sdl2.SDL_INIT_GAMECONTROLLER
    SDL_INIT_JOYSTICK               = sdl2.SDL_INIT_JOYSTICK

    # =========================================================================
    # TYPE ALIASES  (class/type — plain class attribute)
    # =========================================================================
    SDL_Event                       = sdl2.SDL_Event

    # =========================================================================
    # SDL FUNCTION ALIASES  (staticmethod — blocks self injection)
    # =========================================================================
    SDL_IsGameController            = sdl2.SDL_IsGameController
    SDL_GameControllerOpen          = sdl2.SDL_GameControllerOpen
    SDL_GameControllerClose         = sdl2.SDL_GameControllerClose
    SDL_GameControllerName          = sdl2.SDL_GameControllerName
    SDL_GameControllerGetJoystick   = sdl2.SDL_GameControllerGetJoystick
    SDL_GameControllerGetButton     = sdl2.SDL_GameControllerGetButton
    SDL_GameControllerPath          = sdl2.SDL_GameControllerPath
    SDL_JoystickInstanceID          = sdl2.SDL_JoystickInstanceID
    SDL_JoystickGetPlayerIndex      = sdl2.SDL_JoystickGetPlayerIndex
    SDL_JoystickGetGUID             = sdl2.SDL_JoystickGetGUID
    SDL_JoystickGetGUIDString       = sdl2.SDL_JoystickGetGUIDString
    SDL_PollEvent                   = sdl2.SDL_PollEvent
    SDL_QuitSubSystem               = sdl2.SDL_QuitSubSystem
    SDL_GetError                    = sdl2.SDL_GetError
    SDL_Quit                        = sdl2.SDL_Quit

    # =========================================================================
    # CUSTOM WRAPPERS  (@staticmethod def — extra logic on top of SDL2)
    # =========================================================================
    @staticmethod
    def SDL_Init(flags=None):
        """
        Initialize SDL2 subsystems.
        SDL2: returns 0 on success, negative on failure.
        """
        if flags is None:
            flags = sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER
        ret = sdl2.SDL_Init(flags)
        if ret != 0:
            err = sdl2.SDL_GetError()
            messagebox.showerror("Driver Error", f"Failed to initialize SDL2.\n{err}")

    @staticmethod
    def SDL_NumJoysticks():
        """Return the count of currently connected joysticks."""
        return sdl2.SDL_NumJoysticks()

    @staticmethod
    def SDL_GetJoystickIDs():
        """
        Return sequential indices [0, 1, 2 ...] to match SDL3's ID-based interface.
        SDL2 uses integer indices directly as device handles, so index == ID here.

        Returns:
            list[int]: Sequential joystick indices (may be empty)
        """
        return list(range(sdl2.SDL_NumJoysticks()))

    @staticmethod
    def get_button_info(event):
        """Returns (button, which) from a gamepad button event."""
        return event.cbutton.button, event.cbutton.which