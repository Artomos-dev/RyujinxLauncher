import ctypes
import sys
import subprocess
import os
from tkinter import messagebox
from DebugLog import log

# ========================================================================
# WIN32 JOB OBJECT
# ========================================================================
def create_win32_job():
    """Job Object with KILL_ON_JOB_CLOSE — OS kills Ryujinx if launcher dies."""
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

# Create Win32 Job Object for automatic process cleanup
win32_job = create_win32_job() if sys.platform == "win32" else None

def ryujinx_launch(cmd_args, ryujinx_env):
    # Attach Ryujinx to the job — OS kills it automatically if launcher dies
    if sys.platform == "win32":
        ryujinx_process = subprocess.Popen(cmd_args, env=ryujinx_env, creationflags=0x00000004)
        if win32_job:
            result = ctypes.windll.kernel32.AssignProcessToJobObject(
                win32_job, int(ryujinx_process._handle)
            )
            if result:
                log("INFO", "Ryujinx assigned to Job Object")
            else:
                err = ctypes.windll.kernel32.GetLastError()
                log("WARNING", "AssignProcessToJobObject failed", f"error={err}")
        ctypes.windll.ntdll.NtResumeProcess(int(ryujinx_process._handle))
    else:
        import signal as _signal
        if sys.platform == "darwin":
            _preexec = lambda: _signal.signal(_signal.SIGHUP, _signal.SIG_DFL)
        else:
            _libc = ctypes.CDLL("libc.so.6", use_errno=True)
            _preexec = lambda: _libc.prctl(1, _signal.SIGKILL, 0, 0, 0)  # PR_SET_PDEATHSIG
        ryujinx_process = subprocess.Popen(cmd_args, env=ryujinx_env, preexec_fn=_preexec)
    return ryujinx_process

# ============================================================================
# APPIMAGE MOUNT HELPERS (LINUX ONLY)
# ============================================================================
mount_proc    = None  # Popen handle — terminating it unmounts the squashfs

def mount_appimage(is_appimage, appimage_path):
    """
    Mount Ryujinx.AppImage using --appimage-mount.
    PR_SET_PDEATHSIG ensures mount process is killed even on hard launcher crash.
    Returns the mount point path.
    """
    if not is_appimage:
        return

    global mount_proc

    import signal
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1

    mount_proc = subprocess.Popen(
        [appimage_path, "--appimage-mount"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        preexec_fn=lambda: libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)
    )

    mount_point = mount_proc.stdout.readline().decode().strip()

    if not mount_point or not os.path.exists(mount_point):
        messagebox.showerror(
            "AppImage Mount Failed",
            f"Could not mount Ryujinx.AppImage.\n\n"
            f"Please ensure the file is executable:\n"
            f"chmod +x {appimage_path}"
        )
        sys.exit(1)

    log("INFO", "AppImage detected", appimage_path)
    log("INFO", "AppImage mounted at", mount_point)
    return os.path.join(mount_point, "usr", "bin")

def unmount_appimage(is_appimage):
    """Terminate the mount process, releasing the squashfs mount."""
    global mount_proc

    if not is_appimage or not mount_proc:
        return

    mount_proc.terminate()
    mount_proc = None
    log("INFO", "AppImage unmounted")