import ctypes

import psutil
import win32gui
import win32process


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds():
    """Return the number of seconds since the last user input (keyboard or
    mouse), or None if the idle time could not be determined."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0


class WindowsCollector:

    def get_active_application(self):
        """
        Return the current observation: the application owning the foreground
        window (fields may be None when there is no foreground window) plus
        the system idle time in seconds.
        """

        idle_seconds = get_idle_seconds()

        window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            return {
                "process_id": None,
                "process_name": None,
                "window_title": None,
                "idle_seconds": idle_seconds,
            }

        _, process_id = win32process.GetWindowThreadProcessId(
            window_handle
        )

        try:
            process = psutil.Process(process_id)

            return {
                "process_id": process_id,
                "process_name": process.name(),
                "window_title": win32gui.GetWindowText(window_handle),
                "idle_seconds": idle_seconds,
            }

        except psutil.NoSuchProcess:
            return {
                "process_id": process_id,
                "process_name": None,
                "window_title": None,
                "idle_seconds": idle_seconds,
            }