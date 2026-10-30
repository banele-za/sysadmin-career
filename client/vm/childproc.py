"""Make sure QEMU never outlives the game.

If the game crashes or is killed, a normal child process keeps running:
a hidden VM holding 2 GB of RAM and locking its disk file. So QEMU is
always started through start() here, which ties it to the game:

  Windows: every QEMU goes into a "job object" with KILL_ON_JOB_CLOSE. When
           the game's process ends (for any reason), Windows closes the job
           and kills everything in it.
  Linux:   the child asks the kernel (prctl PR_SET_PDEATHSIG) to be sent
           SIGKILL when its parent dies. This has to happen inside the new
           process before QEMU starts, hence preexec_fn.
"""

import logging
import subprocess

from client import host

log = logging.getLogger(__name__)
_job = None    # Windows: one job for the whole game; created on first use


def start(cmd: list[str], **kwargs) -> subprocess.Popen:
    """subprocess.Popen, but the process dies when the game does."""
    if host.LINUX:
        kwargs["preexec_fn"] = _die_with_parent
    proc = subprocess.Popen(cmd, **host.NO_WINDOW, **kwargs)
    if host.WINDOWS:
        try:
            _attach_windows(proc)
        except OSError as e:
            # Not fatal: the VM still runs, it just won't be cleaned up after a crash.
            log.warning("couldn't attach QEMU to the job object: %s", e)
    return proc


def _die_with_parent() -> None:
    """Runs in the child just before QEMU replaces it (Linux only).

    Caveat: "parent" means the *thread* that started the child. QEMU is
    started from the game's event-loop thread, which lives as long as the game.
    """
    import ctypes
    import signal
    PR_SET_PDEATHSIG = 1
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL)


def _attach_windows(proc: subprocess.Popen) -> None:
    import ctypes
    from ctypes import wintypes

    global _job
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.OpenProcess.restype = wintypes.HANDLE

    if _job is None:
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())

        # The structures Windows expects (see SetInformationJobObject docs).
        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits),
                        ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JobObjectExtendedLimitInformation = 9
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                                ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        _job = job      # deliberately never closed: closing it is what kills the VMs

    PROCESS_SET_QUOTA, PROCESS_TERMINATE = 0x0100, 0x0001
    handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc.pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel32.AssignProcessToJobObject(wintypes.HANDLE(_job), wintypes.HANDLE(handle)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))
