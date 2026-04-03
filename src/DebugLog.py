"""
DebugLog.py
Lightweight debug logger for RyujinxLauncher.

Usage:
    from DebugLog import init_log, log

    init_log(log_dir, launcher_version)

    log("INFO",      "Ryujinx version", ryujinx_version)
    log("WARNING",   "Version detection failed, falling back to", "1.1.1403")
    log("ERROR",     "Config file not found", CONFIG_FILE)
    log("EXCEPTION", "AppImage mount failed", e)

Output format:
    [2026-04-03 12-00-00] [INFO]      Ryujinx version: 1.3.3
    [2026-04-03 12-00-00] [WARNING]   Version detection failed, falling back to: 1.1.1403
    [2026-04-03 12-00-00] [ERROR]     Config file not found: ~/.config/Ryujinx/Config.json
    [2026-04-03 12-00-00] [EXCEPTION] AppImage mount failed: <traceback>

Log file location:
    Windows:   <ryujinx_dir>/Logs/RyujinxLauncher_<version>_<datetime>.log
    Linux/Mac: ~/.config/Ryujinx/Logs/RyujinxLauncher_<version>_<datetime>.log
"""

import os
import sys
import traceback
from datetime import datetime

# ============================================================================
# MODULE STATE
# ============================================================================
_log_file  = None   # Open file handle
_has_console = sys.stdout is not None and hasattr(sys.stdout, 'write')

# ============================================================================
# INIT
# ============================================================================
def init_log(log_dir, launcher_version):
    """
    Initialize the logger. Must be called once before any log() calls.

    Args:
        log_dir (str):          Directory where the log file will be created.
                                Created automatically if it does not exist.
        launcher_version (str): Launcher version string (e.g. "1.2").
                                Used in the log filename.
    """
    global _log_file

    try:
        os.makedirs(log_dir, exist_ok=True)

        timestamp   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename    = f"RyujinxLauncher_{launcher_version}_{timestamp}.log"
        log_path    = os.path.join(log_dir, filename)

        _log_file = open(log_path, 'w', encoding='utf-8', buffering=1)  # line-buffered

    except Exception as e:
        # Logger must never crash the launcher - silently fall back to console only
        _log_file = None
        _print_console(f"[WARNING] Could not create log file: {e}")

# ============================================================================
# PUBLIC API
# ============================================================================
def log(level, message, *values):
    """
    Write a log entry.

    Args:
        level   (str): "INFO" | "WARNING" | "ERROR" | "EXCEPTION"
        message (str): Description of what happened.
        *values:       Optional extra values appended after a colon.
                       For EXCEPTION, pass the exception object as the first value
                       to include a full traceback.

    Examples:
        log("INFO",      "Ryujinx version", ryujinx_version)
        log("WARNING",   "Version detection failed, falling back to", "1.1.1403")
        log("ERROR",     "Config file not found", CONFIG_FILE)
        log("EXCEPTION", "AppImage mount failed", e)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    level_tag = f"[{level:<9}]"  # Padded to align columns: INFO, WARNING, ERROR, EXCEPTION

    # Build the main line
    if values:
        values_str = ", ".join(str(v) for v in values)
        line = f"[{timestamp}] {level_tag} {message}: {values_str}"
    else:
        line = f"[{timestamp}] {level_tag} {message}"

    # For exceptions, append the full traceback on following lines
    if level == "EXCEPTION" and values and isinstance(values[0], BaseException):
        tb = traceback.format_exc()
        if tb and tb.strip() != "NoneType: None":
            line = f"{line}\n{tb.rstrip()}"

    _write(line)

# ============================================================================
# INTERNAL HELPERS
# ============================================================================
def _write(line):
    """Write a line to the log file and/or console."""
    if _log_file:
        try:
            _log_file.write(line + "\n")
        except Exception:
            pass  # Never crash the launcher due to logging

    if _has_console:
        _print_console(line)

def _print_console(line):
    """Print to console, suppressing errors if console is unavailable."""
    try:
        print(line)
    except Exception:
        pass