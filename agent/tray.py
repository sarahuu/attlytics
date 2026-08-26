import queue
import threading
import tkinter as tk

import pystray
from PIL import Image, ImageDraw

from agent.main import run as run_agent


def _create_image():
    image = Image.new("RGB", (64, 64), "#069494")
    draw = ImageDraw.Draw(image)
    draw.ellipse((10, 10, 54, 54), fill="#ff69b4")
    return image


class AgentController:
    """Coordinates the status window, tray icon, and the agent thread.

    The agent loop and the tray run on background threads; the status window
    runs on the Tk main thread. Window operations from other threads are
    marshalled through a command queue that the window polls.
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._agent_thread = None
        self._commands = queue.Queue()
        self._icon = None
        self._root = None

    # ---- Agent thread ----

    def start_agent(self):
        if self.is_running():
            return
        self._stop_event.clear()
        self._agent_thread = threading.Thread(
            target=run_agent,
            args=(self._stop_event,),
            name="agent",
            daemon=True,
        )
        self._agent_thread.start()

    def stop_agent(self):
        if not self.is_running():
            return
        self._stop_event.set()
        self._agent_thread.join(timeout=5)
        self._agent_thread = None

    def is_running(self):
        return self._agent_thread is not None and self._agent_thread.is_alive()

    # ---- Window marshaling (safe to call from any thread) ----

    def _post(self, fn):
        self._commands.put(fn)

    def show_window(self):
        self._post(self._do_show)

    def hide_window(self):
        self._post(self._do_hide)

    def _do_show(self):
        if self._root is not None:
            self._root.deiconify()
            self._root.lift()

    def _do_hide(self):
        if self._root is not None:
            self._root.withdraw()

    def _do_destroy(self):
        if self._root is not None:
            self._root.destroy()

    # ---- Shutdown ----

    def shutdown(self):
        self.stop_agent()
        if self._icon is not None:
            self._icon.stop()
        self._post(self._do_destroy)


def _run_window(controller):
    """Build and run the status window. Must run on the Tk main thread."""
    root = tk.Tk()
    controller._root = root
    root.title("Attlytics Agent")
    root.resizable(False, False)

    tk.Label(
        root,
        text="Attlytics agent",
        font=("Segoe UI", 13, "bold"),
    ).pack(padx=28, pady=(18, 2))
    tk.Label(
        root,
        text="\u25cf Agent is running",
        fg="#1a8f3c",
    ).pack(padx=28)
    tk.Label(
        root,
        text="Closing this window keeps it running in the tray.\n"
             "Use the tray icon (right-click) to start/stop it.",
        fg="gray",
        justify="left",
    ).pack(padx=28, pady=(6, 0))

    buttons = tk.Frame(root)
    buttons.pack(pady=(12, 18))
    tk.Button(
        buttons,
        text="Hide to tray",
        command=controller.hide_window,
    ).pack(side="left", padx=6)
    tk.Button(
        buttons,
        text="Stop & Exit",
        command=controller.shutdown,
    ).pack(side="left", padx=6)

    root.protocol("WM_DELETE_WINDOW", controller.hide_window)

    def poll():
        try:
            while True:
                fn = controller._commands.get_nowait()
                fn()
        except queue.Empty:
            pass
        root.after(100, poll)

    root.after(100, poll)
    root.mainloop()


def _run_tray(controller):
    """Run the tray icon. Runs on a background thread."""

    def start(icon, item):
        controller.start_agent()

    def stop(icon, item):
        controller.stop_agent()

    def show(icon, item):
        controller.show_window()

    def exit_app(icon, item):
        controller.shutdown()

    menu = pystray.Menu(
        pystray.MenuItem(
            "Start agent",
            start,
            enabled=lambda item: not controller.is_running(),
        ),
        pystray.MenuItem(
            "Stop agent",
            stop,
            enabled=lambda item: controller.is_running(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show window", show, default=True),
        pystray.MenuItem("Exit", exit_app),
    )

    controller._icon = pystray.Icon(
        "attlytics-agent",
        _create_image(),
        "Attlytics agent",
        menu,
    )
    controller._icon.run()


def run_app():
    """Entry point: starts the agent, the tray, and the status window."""
    controller = AgentController()
    controller.start_agent()

    threading.Thread(
        target=_run_tray,
        args=(controller,),
        name="tray",
        daemon=True,
    ).start()

    _run_window(controller)
