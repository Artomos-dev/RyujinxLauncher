"""
Ryujinx emulator package.

Implements the Core.Emulator contract for Ryujinx:
    Ryujinx.py  - the adapter Core talks to
    Version.py  - version detection (Windows PE / macOS plist / Linux scan)
    Config.py   - Config.json template, profiles, GUID format, input writer
"""

from .Ryujinx import Ryujinx

__all__ = ["Ryujinx"]
