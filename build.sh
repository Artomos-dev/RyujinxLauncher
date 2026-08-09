#!/usr/bin/env bash
# ============================================================================
#  build.sh - build a launcher executable (Linux / macOS)
#
#  Usage:
#      ./build.sh <Name>
#
#  Examples:
#      ./build.sh Ryujinx           builds dist/RyujinxLauncher
#
#  What it does:
#      1. Finds .venv - creates it and installs requirements.txt if missing
#      2. Clears this launcher's previous build output
#      3. Builds a single-file executable into dist/
#
#  Override the environment location with:  VENV_DIR=some/other/venv ./build.sh Ryujinx
# ============================================================================

set -u

cd "$(dirname "$0")" || exit 1

NAME="${1:-}"
VENV_DIR="${VENV_DIR:-.venv}"

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
list_launchers() {
    echo
    echo " Available launchers:"
    local found=0
    for f in src/*Launcher.py; do
        [ -e "$f" ] || continue
        local base
        base="$(basename "$f" .py)"
        echo "   ./build.sh ${base%Launcher}"
        found=1
    done
    [ "$found" -eq 1 ] || echo "   (none found in src/)"
    echo
}

die() {
    echo
    echo " ERROR: $*"
    echo
    exit 1
}

# The venv layout differs on Windows shells (Git Bash / MSYS), where this
# script is occasionally used for a quick syntax or dependency check
venv_python() {
    if [ -x "$VENV_DIR/bin/python" ]; then
        echo "$VENV_DIR/bin/python"
    elif [ -x "$VENV_DIR/Scripts/python.exe" ]; then
        echo "$VENV_DIR/Scripts/python.exe"
    else
        return 1
    fi
}

# ----------------------------------------------------------------------------
# Arguments
# ----------------------------------------------------------------------------
if [ -z "$NAME" ]; then
    echo
    echo " Usage: ./build.sh <Name>"
    list_launchers
    exit 1
fi

ENTRY="src/${NAME}Launcher.py"
if [ ! -f "$ENTRY" ]; then
    echo
    echo " ERROR: $ENTRY not found."
    list_launchers
    exit 1
fi

# ----------------------------------------------------------------------------
# Platform specifics
# ----------------------------------------------------------------------------
UNAME="$(uname -s)"
case "$UNAME" in
    Darwin)
        OUTPUT="dist/${NAME}Launcher"
        DATA_SEP=":"
        ICON_CANDIDATES=("assets/${NAME}LauncherIcon.icns" "assets/RyujinxLauncherIcon.icns")
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OUTPUT="dist/${NAME}Launcher.exe"
        DATA_SEP=";"
        ICON_CANDIDATES=("assets/${NAME}LauncherIcon.ico" "assets/RyujinxLauncherIcon.ico")
        ;;
    *)
        OUTPUT="dist/${NAME}Launcher"
        DATA_SEP=":"
        ICON_CANDIDATES=("assets/${NAME}LauncherPNG.png" "assets/RyujinxLauncherPNG.png")
        ;;
esac

# ----------------------------------------------------------------------------
# 1. Virtual environment
# ----------------------------------------------------------------------------
if PY="$(venv_python)"; then
    echo "[1/3] Using environment $VENV_DIR"
    # An existing environment may predate requirements.txt - verify every build
    # and runtime dependency is present. find_spec locates them without
    # importing: importing sdl3 does network and binary resolution work.
    if ! "$PY" -c "import importlib.util,sys; sys.exit(any(importlib.util.find_spec(m) is None for m in ('PyInstaller','customtkinter','sdl2','sdl3')))" >/dev/null 2>&1; then
        echo "      Build dependencies missing - installing requirements..."
        "$PY" -m pip install -r requirements.txt || die "Installing requirements.txt failed."
    fi
else
    echo "[1/3] No environment at $VENV_DIR - creating one..."

    # Prefer whatever python3 resolves to on PATH - that is the interpreter the
    # user picked, and the one actions/setup-python installs. Candidates are
    # executed, not merely located, so a broken shim is skipped. A candidate
    # must also be Python 3.10 or newer.
    BASEPY=""
    for candidate in python3 python; do
        if "$candidate" -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >/dev/null 2>&1; then
            BASEPY="$candidate"
            break
        fi
    done
    [ -n "$BASEPY" ] || die "No Python 3.10 or newer found on PATH.
         Install Python 3.10+ and make sure it is on PATH,
         then run this script again."

    "$BASEPY" -m venv "$VENV_DIR" || die "Could not create the virtual environment at $VENV_DIR.
         On Debian/Ubuntu you may need:  sudo apt install python3-venv"

    PY="$(venv_python)" || die "Could not create the virtual environment at $VENV_DIR."

    echo "      Installing requirements..."
    "$PY" -m pip install --upgrade pip --quiet
    "$PY" -m pip install -r requirements.txt || die "Installing requirements.txt failed."
fi

# A .venv left over from an older interpreter would still build, badly
if ! "$PY" -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >/dev/null 2>&1; then
    die "$VENV_DIR uses a Python older than 3.10.
         Delete $VENV_DIR and run this script again to rebuild it."
fi

# tkinter ships with Python on Windows and macOS but is a separate package on
# many Linux distributions, and PyInstaller cannot bundle what is not installed
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    die "Python is missing tkinter, which this launcher needs.
         On Debian/Ubuntu:  sudo apt install python3-tk
         On Fedora:         sudo dnf install python3-tkinter
         On Arch:           sudo pacman -S tk"
fi

# ----------------------------------------------------------------------------
# 2. Clean this launcher's previous output
# ----------------------------------------------------------------------------
echo "[2/3] Cleaning previous build of ${NAME}Launcher..."
rm -rf "build/${NAME}Launcher"
rm -f  "$OUTPUT"
rm -f  "${NAME}Launcher.spec"

# ----------------------------------------------------------------------------
# 3. Build
# ----------------------------------------------------------------------------
# Per-launcher icon if one exists, otherwise fall back to the Ryujinx icon
ICON_ARGS=()
for icon in "${ICON_CANDIDATES[@]}"; do
    if [ -f "$icon" ]; then
        ICON_ARGS=(--icon="$icon")
        break
    fi
done

echo "[3/3] Building $(basename "$OUTPUT") from $ENTRY..."
echo

"$PY" -m PyInstaller \
    --noconfirm \
    --noconsole \
    --onefile \
    --name "${NAME}Launcher" \
    "${ICON_ARGS[@]}" \
    --add-data "assets${DATA_SEP}assets" \
    --collect-all customtkinter \
    --paths src \
    --hidden-import Core.ControllerManagerSDL2 \
    --hidden-import Core.ControllerManagerSDL3 \
    "$ENTRY" || die "PyInstaller build failed - see the output above."

[ -f "$OUTPUT" ] || die "PyInstaller reported success but $OUTPUT is missing."

chmod +x "$OUTPUT"

echo
echo "==========================================================================="
echo " Built: $OUTPUT"
echo "==========================================================================="

# The frozen binary looks for <Name>Path.config next to itself, so mirror the
# one kept at the project root into dist/ if it is there
if [ -f "${NAME}Path.config" ]; then
    cp -f "${NAME}Path.config" "dist/${NAME}Path.config"
    echo " Copied ${NAME}Path.config to dist/"
fi
