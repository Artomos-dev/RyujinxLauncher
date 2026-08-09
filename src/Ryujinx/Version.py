"""
Ryujinx/Version.py
Ryujinx version detection.

The version drives three decisions elsewhere in the Ryujinx package:
    - SDL2 vs SDL3 backend
    - which GUID layout the config expects
    - which keys must be stripped from each input entry

Detection method per platform:
    1. Windows : PE version metadata, read natively via ctypes.
    2. macOS   : Info.plist (CFBundleLongVersionString).
    3. Linux   : binary scan for the embedded "Ryujinx/x.y.z:" string.

All three fall back to the RL_RYUJINX_VERSION environment variable, then to
DEFAULT_VERSION. Official builds always embed the string, so the env-var path
exists only as a safety net for unofficial builds.
"""

import ctypes
import os
import re
import sys

from Core.Log import log, fatal

DEFAULT_VERSION = "1.1.1403"


def detect(exe_path):
    """
    Determine the Ryujinx version of the binary at exe_path.

    Returns:
        str: Version string such as "1.3.3", or DEFAULT_VERSION if detection
             fails in a recoverable way.
    """
    version = DEFAULT_VERSION

    try:
        if sys.platform == "win32":
            version = _detect_windows(exe_path, version)
        elif sys.platform == "darwin":
            version = _detect_macos(exe_path, version)
        else:
            version = _detect_linux(exe_path, version)
    except Exception as e:
        log("WARNING", "Version detection failed, falling back to", version)
        log("EXCEPTION", "Version detection exception", e)

    return version


# ============================================================================
# WINDOWS - PE VERSION METADATA
# ============================================================================
class _VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature",        ctypes.c_uint32),
        ("dwStrucVersion",     ctypes.c_uint32),
        ("dwFileVersionMS",    ctypes.c_uint32),
        ("dwFileVersionLS",    ctypes.c_uint32),
        ("dwProductVersionMS", ctypes.c_uint32),
        ("dwProductVersionLS", ctypes.c_uint32),
        ("dwFileFlagsMask",    ctypes.c_uint32),
        ("dwFileFlags",        ctypes.c_uint32),
        ("dwFileOS",           ctypes.c_uint32),
        ("dwFileType",         ctypes.c_uint32),
        ("dwFileSubtype",      ctypes.c_uint32),
        ("dwFileDateMS",       ctypes.c_uint32),
        ("dwFileDateLS",       ctypes.c_uint32),
    ]


def _detect_windows(exe_path, fallback):
    ver_info_size = ctypes.windll.version.GetFileVersionInfoSizeW(exe_path, None)
    if not ver_info_size:
        return fallback

    ver_info = ctypes.create_string_buffer(ver_info_size)
    ctypes.windll.version.GetFileVersionInfoW(exe_path, 0, ver_info_size, ver_info)

    lp_buffer = ctypes.c_void_p()
    lp_len = ctypes.c_uint()
    ctypes.windll.version.VerQueryValueW(
        ver_info, "\\", ctypes.byref(lp_buffer), ctypes.byref(lp_len)
    )

    ffi = _VS_FIXEDFILEINFO.from_address(lp_buffer.value)
    v1 = (ffi.dwFileVersionMS >> 16) & 0xFFFF
    v2 = (ffi.dwFileVersionMS >> 0) & 0xFFFF
    v3 = (ffi.dwFileVersionLS >> 16) & 0xFFFF
    version = f"{v1}.{v2}.{v3}"
    log("INFO", "Ryujinx version detected (Windows PE)", version)
    return version


# ============================================================================
# MACOS - INFO.PLIST
# ============================================================================
def _detect_macos(exe_path, fallback):
    import plistlib

    plist_path = os.path.abspath(os.path.join(exe_path, "..", "..", "Info.plist"))
    if os.path.exists(plist_path):
        with open(plist_path, 'rb') as f:
            raw = plistlib.load(f).get("CFBundleLongVersionString", fallback)
        version = raw.split("-")[0].strip('"')  # "1.3.3-e2143d4" -> "1.3.3"
        log("INFO", "Ryujinx version detected (macOS plist)", version)
        return version

    return _env_override_or_fail(
        "macOS",
        "One-Time Setup Required",
        "echo 'export RL_RYUJINX_VERSION=1.3.3' >> ~/.zshrc && source ~/.zshrc"
    )


# ============================================================================
# LINUX - BINARY SCAN
# ============================================================================
def _detect_linux(exe_path, fallback):
    # Mimics: strings Ryujinx | grep 'Ryujinx/' | grep ':' | head -1 | cut -d '"' -f2 | cut -d '/' -f2

    # Step 1: Read binary and decode to ASCII (strips all null bytes and non-printable chars)
    with open(exe_path, 'rb') as f:
        data = f.read()
    text = data.decode('ascii', errors='ignore')

    # Step 2: Scan line by line for the embedded version string
    # Looking for a line containing: "Ryujinx/1.3.3:..."
    for line in text.splitlines():
        if '"Ryujinx/' in line and ':' in line:
            # cut -d '"' -f2 -> take part inside quotes
            # cut -d '/' -f2 -> take part after the slash
            candidate = line.split('"')[1].split('/')[1].strip()

            # Validate format is X.X.X before accepting (e.g. 1.3.3)
            if re.match(r'^\d+\.\d+\.\d+$', candidate):
                log("INFO", "Ryujinx version detected (binary scan)", candidate)
                return candidate

    # Step 3: Fall back to the env var override
    return _env_override_or_fail(
        "Linux",
        "Ryujinx Version Missing",
        "echo 'export RL_RYUJINX_VERSION=1.3.3' >> ~/.bashrc && source ~/.bashrc"
    )


# ============================================================================
# SHARED FALLBACK
# ============================================================================
def _env_override_or_fail(platform_name, dialog_title, shell_hint):
    """
    Last resort: honour RL_RYUJINX_VERSION, otherwise tell the user how to set
    it and stop. Reaching here means the binary had no embedded version, which
    should not happen with official builds.
    """
    env_version = os.environ.get("RL_RYUJINX_VERSION")
    if env_version:
        version = env_version.strip()
        log("INFO", "Ryujinx version override (env var)", version)
        return version

    fatal(
        dialog_title,
        "Could not detect your Ryujinx version automatically.\n\n"
        "This is a one-time setup step required when installing or upgrading Ryujinx.\n\n"
        f"{shell_hint}\n\n"
        "(Replace 1.3.3 with your actual version). Run this in your terminal.",
        f"Ryujinx version not found ({platform_name})"
    )
