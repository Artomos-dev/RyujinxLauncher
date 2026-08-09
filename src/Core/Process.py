"""
Core/Process.py
Child-process lifecycle and AppImage mounting.

Emulator-agnostic. Guarantees the emulator dies with the launcher on every
platform:

    Windows : Job Object with KILL_ON_JOB_CLOSE
    Linux   : PR_SET_PDEATHSIG -> SIGKILL
    macOS   : SIGHUP restored to default in the child
"""

import ctypes
import os
import subprocess
import sys

from .Log import log, fatal

# ============================================================================
# WIN32 JOB OBJECT
# ============================================================================
_win32_job       = None
_win32_job_ready = False


def _create_win32_job():
    """Job Object with KILL_ON_JOB_CLOSE - OS kills the emulator if launcher dies."""
    if sys.platform != "win32":
        return None

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    k32 = ctypes.windll.kernel32
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None

    # Set up the extended limit info struct
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    # Set the information (Class 9 = JobObjectExtendedLimitInformation)
    result = k32.SetInformationJobObject(
        job,
        9,
        ctypes.byref(info),
        ctypes.sizeof(info)
    )

    if not result:
        err = k32.GetLastError()
        log("WARNING", "SetInformationJobObject failed", f"error={err}")
        return None

    log("INFO", "Win32 Job Object created (KILL_ON_JOB_CLOSE)")
    return job


def _job():
    """Create the Job Object on first use (so its log line reaches the log file)."""
    global _win32_job, _win32_job_ready
    if not _win32_job_ready:
        _win32_job_ready = True
        _win32_job = _create_win32_job()
    return _win32_job


# ============================================================================
# LAUNCH
# ============================================================================
def launch(cmd_args, env):
    """
    Start the emulator, tied to the launcher's lifetime.

    Args:
        cmd_args (list[str]): Full command line, executable first.
        env      (dict):      Environment for the child process.

    Returns:
        subprocess.Popen: The running emulator process.
    """
    if sys.platform == "win32":
        # CREATE_SUSPENDED so the process is attached to the Job Object before
        # it can spawn anything of its own
        process = subprocess.Popen(cmd_args, env=env, creationflags=0x00000004)
        job = _job()
        if job:
            result = ctypes.windll.kernel32.AssignProcessToJobObject(
                job, int(process._handle)
            )
            if result:
                log("INFO", "Emulator assigned to Job Object")
            else:
                err = ctypes.windll.kernel32.GetLastError()
                log("WARNING", "AssignProcessToJobObject failed", f"error={err}")
        ctypes.windll.ntdll.NtResumeProcess(int(process._handle))
    else:
        import signal as _signal
        if sys.platform == "darwin":
            _preexec = lambda: _signal.signal(_signal.SIGHUP, _signal.SIG_DFL)
        else:
            _libc = ctypes.CDLL("libc.so.6", use_errno=True)
            _preexec = lambda: _libc.prctl(1, _signal.SIGKILL, 0, 0, 0)  # PR_SET_PDEATHSIG
        process = subprocess.Popen(cmd_args, env=env, preexec_fn=_preexec)
    return process


# ============================================================================
# APPIMAGE MOUNT HELPERS (LINUX ONLY)
# ============================================================================
_mount_proc = None  # Popen handle - terminating it unmounts the squashfs


def mount_appimage(appimage_path):
    """
    Mount an AppImage using --appimage-mount and keep it mounted for the
    whole session. PR_SET_PDEATHSIG ensures the mount process is killed even
    on a hard launcher crash.

    Returns:
        str: The mount point (squashfs root). Callers usually append usr/bin.
    """
    global _mount_proc

    import signal
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1

    _mount_proc = subprocess.Popen(
        [appimage_path, "--appimage-mount"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        preexec_fn=lambda: libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)
    )

    mount_point = _mount_proc.stdout.readline().decode().strip()

    if not mount_point or not os.path.exists(mount_point):
        fatal(
            "AppImage Mount Failed",
            f"Could not mount {os.path.basename(appimage_path)}.\n\n"
            f"Please ensure the file is executable:\n"
            f"chmod +x {appimage_path}",
            "AppImage mount failed", appimage_path
        )

    log("INFO", "AppImage detected", appimage_path)
    log("INFO", "AppImage mounted at", mount_point)
    return mount_point


def unmount_appimage():
    """Terminate the mount process, releasing the squashfs mount. No-op if unmounted."""
    global _mount_proc

    if not _mount_proc:
        return

    _mount_proc.terminate()
    _mount_proc = None
    log("INFO", "AppImage unmounted")
