import queue
import threading
import tkinter as tk
import webbrowser

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
        self._status_label = None
        self._link_url = None
        self._connecting = False

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

    # ---- Connect account ----

    def set_status(self, text, color="#666666"):
        self._post(lambda: self._do_status(text, color))

    def _do_status(self, text, color):
        self._link_url = None
        if self._status_label is not None:
            self._status_label.config(
                text=text, fg=color, cursor="", font=("Segoe UI", 9)
            )

    # ---- Clickable confirmation link ----

    def show_link(self, url):
        self._post(lambda: self._do_show_link(url))

    def _do_show_link(self, url):
        self._link_url = url
        self._do_show()  # make sure the status window is visible
        if self._status_label is not None:
            self._status_label.config(
                text="Click here to confirm this device in your browser",
                fg="#0055cc",
                cursor="hand2",
                font=("Segoe UI", 9, "underline"),
            )

    def connect_account(self):
        if self._connecting:
            return
        self._connecting = True
        threading.Thread(
            target=self._run_connect, name="connect-account", daemon=True
        ).start()

    def _run_connect(self):
        try:
            self.set_status("Connecting to account\u2026", "#444444")
            from agent import account

            def on_link(url: str):
                self.show_link(url)
                try:
                    webbrowser.open(url)
                except Exception:  # noqa: BLE001 - browser open is best-effort
                    pass

            saved = account.connect_account(on_link=on_link)
            name = (saved or {}).get("name") or ""
            self.set_status(
                f"Connected as {name}" if name else "Connected \u2713", "#1a8f3c"
            )
        except Exception as exc:  # noqa: BLE001 - surface to the UI
            self.set_status(f"Connect failed: {exc}", "#b00020")
        finally:
            self._connecting = False

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
    status_label = tk.Label(
        root, text="Not connected", fg="#666666", justify="left", wraplength=360
    )
    status_label.pack(padx=28)
    controller._status_label = status_label

    def _open_link(_event=None):
        url = getattr(controller, "_link_url", None)
        if url:
            webbrowser.open(url)

    status_label.bind("<Button-1>", _open_link)

    # Reflect an already-connected account (agent started with a stored key).
    try:
        from agent import account

        acct = account.load_account()
    except Exception:  # noqa: BLE001 - storage is best-effort
        acct = None
    if acct:
        name = (acct.get("name") or "").strip()
        status_label.config(
            text=f"Connected as {name}" if name else "Connected",
            fg="#1a8f3c",
            font=("Segoe UI", 9),
        )
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
        text="Connect account",
        command=controller.connect_account,
    ).pack(side="left", padx=6)
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

    def connect_account(icon, item):
        controller.connect_account()

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
        pystray.MenuItem("Connect account", connect_account),
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
