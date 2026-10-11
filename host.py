"""Host: share this PC's screen and let an approved controller drive it.

UI (Tkinter) runs on the main thread; the WebRTC/asyncio work runs on a
background thread. Every session must be approved on this machine, and a live
status banner stays visible the whole time the screen is shared.
"""
import asyncio
import json
import logging
import threading
import tkinter as tk
from tkinter import messagebox

from aiortc import RTCSessionDescription

from common import gen_code, host_peer_id
from rtc import make_peer_connection
from screen import ScreenTrack
from signaling import IDTaken, Signaling

log = logging.getLogger("anyhelp.host")

_ACCENT = "#2d7dd2"
_BG = "#1e1e24"
_FG = "#f0f0f3"


class HostUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AnyHelp — Share my screen")
        self.root.configure(bg=_BG)
        self.root.geometry("460x360")
        self.root.resizable(False, False)
        self._on_close = None

        tk.Label(self.root, text="AnyHelp", bg=_BG, fg=_ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(22, 2))
        tk.Label(self.root, text="Share your screen", bg=_BG, fg=_FG,
                 font=("Segoe UI", 12)).pack()

        tk.Label(self.root, text="Give this code to the person\nyou want to let control your screen:",
                 bg=_BG, fg=_FG, font=("Segoe UI", 11), justify="center").pack(pady=(24, 6))

        self._code_var = tk.StringVar(value="— — — — — —")
        self._code_label = tk.Label(self.root, textvariable=self._code_var, bg=_BG,
                                     fg="#ffd166", font=("Consolas", 34, "bold"))
        self._code_label.pack(pady=2)

        self._status_var = tk.StringVar(value="Starting…")
        tk.Label(self.root, textvariable=self._status_var, bg=_BG, fg="#9aa0aa",
                 font=("Segoe UI", 10), wraplength=420, justify="center").pack(pady=(18, 0))

        self._stop_btn = tk.Button(self.root, text="Stop sharing", command=self._close,
                                   bg="#44444c", fg=_FG, relief="flat",
                                   font=("Segoe UI", 10), padx=14, pady=6)
        self._stop_btn.pack(side="bottom", pady=16)

        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # --- thread-safe UI updates (called from the asyncio thread) ---
    def set_code(self, code: str):
        self.root.after(0, lambda: self._code_var.set("  ".join(code)))

    def set_status(self, text: str):
        self.root.after(0, lambda: self._status_var.set(text))

    def ask_accept(self, who: str) -> bool:
        """Blocking approval prompt. Safe to call from a worker thread."""
        done = threading.Event()
        result = {}

        def show():
            result["ok"] = messagebox.askyesno(
                "Allow remote control?",
                "Someone entered your code and wants to VIEW and CONTROL "
                "your screen right now.\n\nOnly accept if you are expecting this.\n\nAllow?",
                icon="warning",
            )
            done.set()

        self.root.after(0, show)
        done.wait()
        return result.get("ok", False)

    def on_close(self, callback):
        self._on_close = callback

    def _close(self):
        if self._on_close:
            self._on_close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


async def _run_session(sig: Signaling, offer_msg: dict, ui: HostUI, stop: threading.Event):
    who = offer_msg.get("src", "unknown")
    ui.set_status("Someone is asking to connect — check the pop-up.")

    approved = await asyncio.to_thread(ui.ask_accept, who)
    if not approved:
        ui.set_status("Request declined. Waiting — share your code.")
        return

    pc = make_peer_connection()
    track = ScreenTrack()
    injector = None

    try:
        from inject import Injector
        injector = Injector(track.monitor)
    except Exception as exc:
        log.warning("input injection unavailable: %s", exc)

    finished = asyncio.Event()

    @pc.on("datachannel")
    def _on_datachannel(channel):
        @channel.on("message")
        def _on_message(message):
            if injector is None:
                return
            try:
                injector.handle(json.loads(message))
            except Exception:
                pass

    @pc.on("connectionstatechange")
    async def _on_state():
        ui.set_status(f"Connection: {pc.connectionState}")
        if pc.connectionState in ("failed", "closed", "disconnected"):
            finished.set()

    offer = offer_msg["payload"]["sdp"]
    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
    pc.addTrack(track)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await sig.send("ANSWER", who, {
        "sdp": {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp},
        "type": "media",
        "connectionId": offer_msg["payload"].get("connectionId", "conn"),
    })

    if injector is not None:
        injector.enabled = True
    ui.set_status("● LIVE — your screen is being shared and controlled.")

    # Wait until the peer disconnects or the user stops sharing.
    stop_waiter = asyncio.create_task(asyncio.to_thread(stop.wait))
    finish_waiter = asyncio.create_task(finished.wait())
    await asyncio.wait({stop_waiter, finish_waiter}, return_when=asyncio.FIRST_COMPLETED)
    for task in (stop_waiter, finish_waiter):
        task.cancel()

    if injector is not None:
        injector.shutdown()
    track.stop()
    await pc.close()


async def _host_main(ui: HostUI, stop: threading.Event):
    sig = None
    code = None
    for _ in range(12):
        code = gen_code()
        candidate = Signaling(host_peer_id(code))
        try:
            await candidate.connect()
        except IDTaken:
            continue
        except Exception as exc:
            ui.set_status(f"Could not reach the signaling server:\n{exc}")
            return
        sig = candidate
        break

    if sig is None:
        ui.set_status("Could not register a free code. Please restart.")
        return

    ui.set_code(code)
    ui.set_status("Waiting for a connection — share your code.")

    try:
        while not stop.is_set():
            msg = await sig.recv()
            kind = msg.get("type")
            if kind == "_CLOSED":
                ui.set_status("Lost connection to the signaling server. Please restart.")
                break
            if kind != "OFFER":
                continue
            await _run_session(sig, msg, ui, stop)
            if stop.is_set():
                break
            ui.set_status("Waiting for a connection — share your code.")
    finally:
        await sig.close()


def run_host():
    logging.basicConfig(level=logging.WARNING)
    ui = HostUI()
    loop = asyncio.new_event_loop()
    stop = threading.Event()

    def worker():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_host_main(ui, stop))
        except Exception as exc:
            log.exception("host crashed")
            ui.set_status(f"Error: {exc}")
        finally:
            loop.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def on_close():
        stop.set()
        try:
            loop.call_soon_threadsafe(lambda: None)
        except Exception:
            pass

    ui.on_close(on_close)
    ui.run()
    stop.set()


if __name__ == "__main__":
    run_host()
