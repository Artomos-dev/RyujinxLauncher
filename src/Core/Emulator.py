"""
Core/Emulator.py
The contract every emulator package implements.

Core defines this interface; emulator packages (Ryujinx/, ...)
implement it. Core never imports an emulator package - the entry script
picks one and hands the instance to Core.Bootstrap.run().

Lifecycle, driven by Core/Bootstrap.py in this exact order:

    1. locate(base)     resolve dir / exe / config_path (mount AppImage).
                        Runs before logging, because log_dir() depends on it.
    2. <logger starts>
    3. prepare()        detect version, choose SDL backend, set process env
                        vars, snapshot the child environment.
                        Runs before the SDL wrapper is imported.
    4. <SDL loads>
    5. load_profiles()  discover selectable controller profiles.
    6. <UI runs>
    7. write_input_config(...)  called on every launch.
    8. cleanup()        called on every exit path.

Attributes an implementation must set during locate():

    dir          str   emulator directory (AppImage mount point if mounted)
    exe          str   binary the launcher will start
    config_path  str   the emulator's config file
    is_appimage  bool  purely informational, used in the startup banner

and during prepare():

    env          dict  environment handed to the emulator process
"""


class Emulator:
    """Base class - subclass this in <Name>/<Name>.py."""

    name = "Emulator"   # branding: window title, "<Name>Path.config", log filename

    def __init__(self):
        self.dir = None
        self.exe = None
        self.config_path = None
        self.is_appimage = False
        self.env = None
        self.profiles = {}

    # ------------------------------------------------------------------
    # 1. Where everything lives
    # ------------------------------------------------------------------
    def locate(self, base):
        """
        Resolve dir / exe / config_path from the launcher's base directory.
        Mount an AppImage if that is how this emulator ships.
        Must fail loudly (Core.Log.fatal) if the binary cannot be found.
        """
        raise NotImplementedError

    def log_dir(self):
        """Directory for launcher log files."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 2. Runtime setup - runs before the SDL wrapper is imported
    # ------------------------------------------------------------------
    def prepare(self):
        """
        Detect the emulator version, decide the SDL backend, set any process
        environment variables the emulator needs, and snapshot self.env for
        the child process.

        The snapshot must be taken here, before load_sdl() publishes its own
        SDL_* loader variables, so those never leak into the emulator.
        """
        raise NotImplementedError

    def sdl_backend(self):
        """Return "SDL2" or "SDL3"."""
        raise NotImplementedError

    def sdl_dir(self):
        """Directory containing the SDL shared library."""
        return self.dir

    # ------------------------------------------------------------------
    # 3. Controller profiles - payload is opaque to Core
    # ------------------------------------------------------------------
    def load_profiles(self):
        """
        Return {"display name": <payload>, ...}, insertion-ordered.

        Core only ever uses the keys: it shows them in the profile selector,
        lets the D-pad cycle them, and hands the chosen key back through
        write_input_config(). The payload is never inspected by Core, so it
        can be a dict, an INI section name, or None.

        The first entry is the default for newly assigned controllers.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 4. Writing the launch configuration
    # ------------------------------------------------------------------
    def write_input_config(self, assignments, hardware):
        """
        Persist the controller mapping in whatever format this emulator uses.

        Args:
            assignments (list[dict]): Player order, one entry per assigned pad:
                {"path": hid path, "name": display name, "profile_key": str}
            hardware    (list[dict]): Fresh SDL enumeration, in OS order:
                {"path": hid path, "guid": raw 32-char hex, "name": SDL name}

        Match the two by "path". Read the existing config and replace only the
        input section - never regenerate the whole file, or unrelated user
        settings are lost.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 5. Launching and teardown
    # ------------------------------------------------------------------
    def command(self, argv):
        """Full command line. Frontend arguments (Playnite, etc.) pass through."""
        return [self.exe] + argv[1:]

    def cleanup(self):
        """Release anything locate() acquired. Called on every exit path."""
        pass
