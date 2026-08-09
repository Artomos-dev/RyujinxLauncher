"""
Ryujinx/Config.py
Everything that understands Ryujinx's Config.json format.

Three jobs:
    1. load_template()  - reuse the user's own ProController mapping as the
                          default profile, so their button layout survives.
    2. load_profiles()  - discover profiles/controller/*.json.
    3. write_input()    - rewrite Config.json's "input_config" for a launch.

Core never looks inside any of this; profile payloads are opaque to it.
"""

import copy
import glob
import json
import os

from Core.Log import log, fatal

# ============================================================================
# DEFAULT CONTROLLER MAPPING TEMPLATE
# ============================================================================
# Fallback template if no existing config found (matches Nintendo Pro Controller layout)
FALLBACK_TEMPLATE = {
    "version": 1,
    "backend": "",
    "id": "",
    "name": "",
    "controller_type": "ProController",
    "player_index": "",
    "deadzone_left": 0.1,
    "deadzone_right": 0.1,
    "range_left": 1,
    "range_right": 1,
    "trigger_threshold": 0.5,
    "left_joycon_stick": {
        "joystick": "Left",
        "invert_stick_x": False,
        "invert_stick_y": False,
        "rotate90_cw": False,
        "stick_button": "LeftStick"
    },
    "right_joycon_stick": {
        "joystick": "Right",
        "invert_stick_x": False,
        "invert_stick_y": False,
        "rotate90_cw": False,
        "stick_button": "RightStick"
    },
    "motion": {
        "motion_backend": "GamepadDriver",
        "sensitivity": 100,
        "gyro_deadzone": 1,
        "enable_motion": True
    },
    "rumble": {
        "strong_rumble": 1,
        "weak_rumble": 1,
        "enable_rumble": True
    },
    "led": {
        "enable_led": False,
        "turn_off_led": False,
        "use_rainbow": False,
        "led_color": 0
    },
    "left_joycon": {
        "button_minus": "Back",
        "button_l": "LeftShoulder",
        "button_zl": "LeftTrigger",
        "button_sl": "SingleLeftTrigger0",
        "button_sr": "SingleRightTrigger0",
        "dpad_up": "DpadUp",
        "dpad_down": "DpadDown",
        "dpad_left": "DpadLeft",
        "dpad_right": "DpadRight"
    },
    "right_joycon": {
        "button_plus": "Start",
        "button_r": "RightShoulder",
        "button_zr": "RightTrigger",
        "button_sl": "SingleLeftTrigger1",
        "button_sr": "SingleRightTrigger1",
        "button_x": "X",
        "button_b": "B",
        "button_y": "Y",
        "button_a": "A"
    }
}

# Fields write_input() injects per launch, stripped from profiles on load
INJECTED_FIELDS = ("backend", "id", "name", "controller_type", "player_index")


# ============================================================================
# TEMPLATE
# ============================================================================
def load_template(config_file, backend_string):
    """
    Load the default controller mapping from the user's Config.json.

    Reuses the first SDL ProController entry found, so the user's own button
    layout, deadzones and motion settings become the "RL Default" profile.

    Returns:
        dict: The mapping template, or FALLBACK_TEMPLATE if none was found.
    """
    template = copy.deepcopy(FALLBACK_TEMPLATE)
    template["backend"] = backend_string

    if not os.path.exists(config_file):
        return template

    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
        if "input_config" in data and isinstance(data["input_config"], list):
            for entry in data["input_config"]:
                if (entry.get("backend") in ("GamepadSDL2", "GamepadSDL3") and
                        entry.get("controller_type") == "ProController"):
                    template = copy.deepcopy(entry)
                    break
    except Exception as e:
        log("ERROR", "Config file corrupted", config_file)
        log("EXCEPTION", "Config read exception", e)
        # Corrupted config - stop the launcher immediately
        fatal(
            "Configuration Error",
            "Could not read Ryujinx Config file.\n\n"
            "Please open Ryujinx manually once to generate valid configuration files.\n"
            "Then try launching this tool again."
        )

    return template


# ============================================================================
# PROFILES
# ============================================================================
def load_profiles(config_file, template):
    """
    Load controller profiles from Ryujinx's profiles/controller/ directory.

    The first entry is always "RL Default", built from `template`. Remaining
    entries come from *.json files on disk. Fields that write_input() injects
    at launch time are stripped so the correct values are used then. A profile
    file literally named "RL Default.json" overrides the built-in default.

    Returns:
        dict: {"display_name": data_dict, ...}
    """
    profiles = {"RL Default": copy.deepcopy(template)}

    profiles_dir = os.path.join(os.path.dirname(config_file), "profiles", "controller")

    if os.path.isdir(profiles_dir):
        for filepath in sorted(glob.glob(os.path.join(profiles_dir, "*.json"))):
            try:
                with open(filepath, 'r') as f:
                    raw = json.load(f)
                # Strip fields that write_input() will inject at launch time
                for key in INJECTED_FIELDS:
                    raw.pop(key, None)
                display_name = os.path.splitext(os.path.basename(filepath))[0]
                profiles[display_name] = raw
            except Exception as e:
                log("WARNING", "Skipping corrupted profile", filepath)
                log("EXCEPTION", "Profile load exception", e)

    log("INFO", "Profiles loaded", str(len(profiles)))
    return profiles


# ============================================================================
# GUID FORMATTING
# ============================================================================
def guid_fix(raw_hex, version):
    """
    Convert an SDL2/SDL3 GUID into Ryujinx's expected format.

    Ryujinx uses the structure 000000XX-YYZZ-AABB-CCCC-DDDDDDDDDDDD, and the
    first block differs between major Ryujinx versions.

    Args:
        raw_hex (str): Raw 32-character hex GUID from SDL2/SDL3
        version (str): Detected Ryujinx version

    Returns:
        str: Reformatted GUID for Ryujinx
    """
    if len(raw_hex) < 32:
        return raw_hex  # Invalid GUID, return as-is

    if version == "1.1.1403":
        # v1.1.1403: Standard endian swap of first 4 bytes (e.g. 8d930003)
        part1 = raw_hex[6:8] + raw_hex[4:6] + raw_hex[2:4] + raw_hex[:2]
    else:
        # v1.3.1/v1.3.2/v1.3.3: Bus ID masked (e.g. 00000003)
        bus_id = raw_hex[:2]
        part1 = f"000000{bus_id}"
    part2 = raw_hex[10:12] + raw_hex[8:10]   # Endian swap
    part3 = raw_hex[14:16] + raw_hex[12:14]  # Endian swap
    part4_a = raw_hex[16:20]
    part4_b = raw_hex[20:]

    return f"{part1}-{part2}-{part3}-{part4_a}-{part4_b}"


# ============================================================================
# WRITING THE LAUNCH CONFIG
# ============================================================================
def write_input(config_file, assignments, hardware, profiles, version, backend_string):
    """
    Rewrite the "input_config" section of Config.json for this launch.

    Only that key is replaced - the rest of the user's settings are preserved.

    Args:
        config_file    (str):        Path to Config.json
        assignments    (list[dict]): Player order: {"path", "name", "profile_key"}
        hardware       (list[dict]): Fresh SDL scan: {"path", "guid", "name"}
        profiles       (dict):       {profile_key: mapping dict}
        version        (str):        Detected Ryujinx version
        backend_string (str):        "GamepadSDL2" or "GamepadSDL3"
    """
    if not os.path.exists(config_file):
        return  # No config file to modify

    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
    except Exception:
        return  # Corrupted config

    # Ryujinx identifies duplicate pads by an index prefix on the GUID, counted
    # in OS enumeration order across every connected pad - not just assigned ones
    enumerated = []
    guid_counters = {}
    for hw in hardware:
        base_guid = guid_fix(hw["guid"], version)
        idx = guid_counters.get(base_guid, 0)
        guid_counters[base_guid] = idx + 1
        enumerated.append({
            "path": hw["path"],
            "ryu_id": f"{idx}-{base_guid}",
            "name": hw["name"]
        })

    new_input = []

    for i, assignment in enumerate(assignments):
        # Find hardware entry matching this assignment's HID path
        matched_hw = next(
            (x for x in enumerated if x["path"] == assignment["path"]),
            None
        )
        if not matched_hw:
            continue

        # Use the profile selected for this controller
        profile_data = profiles[assignment["profile_key"]]
        log("INFO", f"Saving -> Player {i+1} | {matched_hw['name']} | Profile: {assignment['profile_key']}")

        entry = copy.deepcopy(profile_data)
        entry["id"] = matched_hw["ryu_id"]      # Correct GUID with index

        if version == "1.1.1403":
            # Ryujinx (v1.1.1403) knows neither key
            entry.pop("led", None)
            entry.pop("name", None)
        elif version == "1.3.1":
            # Ryujinx (v1.3.1) has led but not name
            entry.pop("name", None)
        else:
            # Ryujinx (v1.3.2/v1.3.3/newer)
            entry["name"] = matched_hw["name"]

        entry["player_index"] = f"Player{i+1}"
        entry["backend"] = backend_string
        entry["controller_type"] = "ProController"
        new_input.append(entry)

    # Write updated config
    data["input_config"] = new_input
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log("EXCEPTION", "Config write failed, Ryujinx will use the old config", e)
