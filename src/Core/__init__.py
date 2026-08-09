"""
Core — emulator-agnostic launcher engine.

Nothing in this package knows which emulator is being launched. All
emulator-specific behaviour arrives through the Emulator contract in
Core/Emulator.py, supplied by the entry script.

Rule: Core must never import an emulator package (Ryujinx/, ...).
"""
