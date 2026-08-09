"""
Core/Paths.py
Filesystem location helpers shared by every emulator.

Knows nothing about any specific emulator - callers pass the emulator name in.
"""

import glob
import os
import sys

from .Log import log


def base_dir():
    """
    The directory the launcher itself lives in.

    Frozen (.exe / PyInstaller onefile) : folder containing the executable.
    Script                              : the src/ folder.

    This is the default location the emulator is expected to sit in, and the
    folder searched for the "<Name>Path.config" override file.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # Core/Paths.py -> Core/ -> src/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    """
    Absolute path to a bundled resource (icons, images).

    Works both from a PyInstaller bundle (_MEIPASS) and from source, where
    assets/ sits next to src/ in the repository.
    """
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return os.path.join(meipass, relative_path)

    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/
    candidate = os.path.join(src, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(src), relative_path)  # repository root


def read_path_override(base, emulator_name):
    """
    Read the optional "<Name>Path.config" file sitting next to the launcher.

    The file's first line is a path to the emulator directory, letting users
    keep the launcher somewhere other than the emulator folder.

    Returns:
        str | None: The custom directory if the file exists and the path is
                    valid, otherwise None (caller falls back to `base`).
    """
    config_file = os.path.join(base, f"{emulator_name}Path.config")
    if not os.path.exists(config_file):
        return None

    try:
        with open(config_file, "r") as f:
            # clean up quotes and whitespace
            custom_path = f.readline().strip().replace('"', '')

        # verify the path actually exists before using it
        if os.path.exists(custom_path):
            log("INFO", "Path override", custom_path)
            return custom_path
    except Exception:
        # If reading fails, silently fall back to the default base directory
        pass

    return None


def find_appimage(directory, name):
    """
    Find an emulator AppImage in `directory`.

    Matches both common casings, e.g. for name="ryujinx":
        Ryujinx*.AppImage / ryujinx*.AppImage   then   RYUJINX*.AppImage

    Returns:
        str | None: Full path to the first match, or None.
    """
    head, tail = name[0], name[1:]
    matches = (
        glob.glob(os.path.join(directory, f"[{head.upper()}{head.lower()}]{tail}*.AppImage")) or
        glob.glob(os.path.join(directory, f"{name.upper()}*.AppImage"))
    )
    return matches[0] if matches else None
