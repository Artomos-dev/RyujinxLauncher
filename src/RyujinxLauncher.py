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

Structure:
    Core/       emulator-agnostic engine (UI, controllers, process, logging)
    Ryujinx/    everything Ryujinx-specific (paths, version, Config.json)

Adding another emulator means adding a folder next to Ryujinx/ and an entry
script like this one. Core is never modified.

Author: Artomos
License: CC BY-NC 4.0 (Attribution-NonCommercial)
Tested with: Ryujinx 1.3.3(Windows) (Feb 2026)
"""

from Core.Bootstrap import run
from Ryujinx import Ryujinx

if __name__ == "__main__":
    run(Ryujinx())
