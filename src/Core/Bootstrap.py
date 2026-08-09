"""
Core/Bootstrap.py
The startup sequence, shared by every emulator entry script.

The order below is not cosmetic - each step depends on the previous one:

    locate()    resolves the emulator directory, so log_dir() has an answer
    init_log()  starts the logger, so everything after it is recorded
    prepare()   detects the emulator version and snapshots the child env,
                which must happen before SDL publishes its own SDL_* vars
    load_sdl()  imports the SDL wrapper (binds the shared library)
    profiles    discovered once, then owned by the emulator instance
"""

import customtkinter as ctk

from .Log import init_log, log
from .Paths import base_dir
from .Sdl import load_sdl

LAUNCHER_VERSION = "1.2.0"


def run(emulator):
    """
    Boot the launcher for a given emulator and hand control to the UI loop.

    Args:
        emulator (Emulator): A fresh instance from an emulator package.
    """
    import sys

    # 1. Where is the emulator?
    emulator.locate(base_dir())

    # 2. Logging (path-dependent, so it cannot start any earlier)
    init_log(emulator.log_dir(), LAUNCHER_VERSION, f"{emulator.name}Launcher")
    log("INFO", f"=== {emulator.name}Launcher", LAUNCHER_VERSION + " ===")
    log("INFO", "OS", sys.platform + (" (AppImage)" if emulator.is_appimage else ""))
    log("INFO", f"{emulator.name} dir", emulator.dir)
    log("INFO", "Config", emulator.config_path)
    log("INFO", "Executable", emulator.exe)

    # 3. Version, SDL backend choice, environment (before SDL is imported)
    emulator.prepare()

    # 4. Bind the SDL shared library
    sdl = load_sdl(emulator.sdl_backend(), emulator.sdl_dir())

    # 5. UI
    # Import App (and transitively Ui) BEFORE creating the CTk window.
    # Ui.py's module-level code disables automatic DPI awareness; if the
    # window is created first, it registers with the monitor's real DPI
    # scale, and the later set_window_scaling() call applies a geometry()
    # that breaks fullscreen.
    from .App import LauncherApp

    root = ctk.CTk()
    emulator.profiles = emulator.load_profiles()

    LauncherApp(root, emulator, sdl)
    root.mainloop()
