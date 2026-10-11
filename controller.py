"""Controller: enter a code, view the remote screen, and drive it.

A background thread runs WebRTC (receives video, sends input over a data
channel). The main thread runs a pygame window that renders the latest frame
and forwards mouse/keyboard events.
"""
import asyncio
import json
import logging
import os
import threading
import tkinter as tk

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402
from aiortc import RTCSessionDescription  # noqa: E402

from common import controller_peer_id, host_peer_id  # noqa: E402
from keymap import encode_key  # noqa: E402
from rtc import make_peer_connection  # noqa: E402
from signaling import Signaling  # noqa: E402

log = logging.getLogger("anyhelp.controller")

_BTN = {1: "left", 2: "middle", 3: "right"}
_ANSWER_TIMEOUT = 40  # seconds to wait for the host to accept


def _prompt_code() -> str | None:
    """Small Tkinter dialog asking for the 6-character code."""
    result = {"code": None}
    root = tk.Tk()
    root.title("AnyHelp — Connect")
    root.configure(bg="#1e1e24")
    root.geometry("380x230")
    root.resizable(False, False)

    tk.Label(root, text="AnyHelp", bg="#1e1e24", fg="#2d7dd2",
             font=("Segoe UI", 20, "bold")).pack(pady=(22, 2))
    tk.Label(root, text="Enter the code your partner is showing you:",
             bg="#1e1e24", fg="#f0f0f3", font=("Segoe UI", 11)).pack(pady=(12, 8))

    entry = tk.Entry(root, font=("Consolas", 20), justify="center", width=10)
    entry.pack(pady=4)
    entry.focus_set()

    def submit(*_):
        text = entry.get().strip().upper().replace(" ", "")
        if text:
            result["code"] = text
            root.destroy()

    entry.bind("<Return>", submit)
    tk.Button(root, text="Connect", command=submit, bg="#2d7dd2", fg="white",
              relief="flat", font=("Segoe UI", 11), padx=20, pady=6).pack(pady=14)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return result["code"]


def _geometry(vw, vh, ww, wh):
    """Letterbox the video inside the window; return draw rect + scale."""
    if vw == 0 or vh == 0:
        return None
    scale = min(ww / vw, wh / vh)
    dw, dh = int(vw * scale), int(vh * scale)
    ox, oy = (ww - dw) // 2, (wh - dh) // 2
    return {"dw": dw, "dh": dh, "ox": ox, "oy": oy}


def _to_norm(pos, geo):
    if geo is None or geo["dw"] == 0 or geo["dh"] == 0:
        return None
    nx = (pos[0] - geo["ox"]) / geo["dw"]
    ny = (pos[1] - geo["oy"]) / geo["dh"]
    if 0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0:
        return nx, ny
    return None


async def _recv_video(track, shared, lock):
    while True:
        try:
            frame = await track.recv()
        except Exception:
            break
        arr = frame.to_ndarray(format="rgb24")
        h, w, _ = arr.shape
        with lock:
            shared["frame"] = (w, h, arr.tobytes())
            shared["status"] = "LIVE"


async def _ctl_main(code, shared, lock, loop, stop, holder):
    sig = Signaling(controller_peer_id())
    try:
        await sig.connect()
    except Exception as exc:
        with lock:
            shared["error"] = f"Could not reach the signaling server:\n{exc}"
        stop.set()
        return

    pc = make_peer_connection()
    channel = pc.createDataChannel("control")
    pc.addTransceiver("video", direction="recvonly")

    out_queue: asyncio.Queue = asyncio.Queue()
    holder["queue"] = out_queue
    holder["loop"] = loop
    channel_open = asyncio.Event()

    @channel.on("open")
    def _on_open():
        channel_open.set()

    @pc.on("track")
    def _on_track(track):
        if track.kind == "video":
            asyncio.ensure_future(_recv_video(track, shared, lock))

    @pc.on("connectionstatechange")
    async def _on_state():
        with lock:
            shared["conn"] = pc.connectionState
        if pc.connectionState in ("failed", "closed", "disconnected"):
            stop.set()

    async def sender():
        await channel_open.wait()
        while True:
            ev = await out_queue.get()
            if ev is None:
                break
            try:
                channel.send(json.dumps(ev))
            except Exception:
                pass

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await sig.send("OFFER", host_peer_id(code), {
        "sdp": {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp},
        "type": "media",
        "connectionId": "conn",
        "label": "control",
        "reliable": True,
        "serialization": "json",
        "metadata": None,
        "browser": "anyhelp",
    })
    with lock:
        shared["status"] = f"Calling {code} — waiting for them to allow access…"

    sender_task = asyncio.create_task(sender())

    # Wait for the ANSWER (host accepted), with a timeout.
    got_answer = False
    try:
        async def wait_answer():
            while not stop.is_set():
                msg = await sig.recv()
                kind = msg.get("type")
                if kind == "ANSWER":
                    ans = msg["payload"]["sdp"]
                    await pc.setRemoteDescription(
                        RTCSessionDescription(sdp=ans["sdp"], type=ans["type"]))
                    return True
                if kind == "EXPIRE":
                    with lock:
                        shared["error"] = (
                            f"No one is sharing with code {code}.\n"
                            "Check the code and that they clicked 'Share my screen'.")
                    return False
                if kind == "_CLOSED":
                    with lock:
                        shared["error"] = "Lost connection to the signaling server."
                    return False
            return False

        got_answer = await asyncio.wait_for(wait_answer(), _ANSWER_TIMEOUT)
    except asyncio.TimeoutError:
        with lock:
            shared["error"] = (
                "The other side didn't answer in time.\n"
                "They may not have clicked 'Allow', or the code is wrong.")

    if got_answer:
        with lock:
            shared["status"] = "Connected — negotiating video…"
        while not stop.is_set():
            await asyncio.sleep(0.2)
    else:
        stop.set()

    out_queue.put_nowait(None)
    sender_task.cancel()
    await sig.close()
    await pc.close()


def _pygame_loop(code, shared, lock, loop, stop, holder):
    pygame.init()
    pygame.display.set_caption(f"AnyHelp — controlling {code}")
    win = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    font = pygame.font.SysFont("Segoe UI", 22)
    small = pygame.font.SysFont("Segoe UI", 15)
    clock = pygame.time.Clock()
    last_norm = None

    def send(ev):
        queue = holder.get("queue")
        if queue is not None:
            loop.call_soon_threadsafe(queue.put_nowait, ev)

    running = True
    while running and not stop.is_set():
        with lock:
            frame = shared.get("frame")
            status = shared.get("status", "")
            error = shared.get("error")

        ww, wh = win.get_size()
        geo = _geometry(frame[0], frame[1], ww, wh) if frame else None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                win = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.WINDOWFOCUSLOST:
                last_norm = None
                send({"t": "releaseall"})
            elif frame is not None:
                if event.type == pygame.MOUSEMOTION:
                    norm = _to_norm(event.pos, geo)
                    if norm and norm != last_norm:
                        last_norm = norm
                        send({"t": "m", "x": norm[0], "y": norm[1]})
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button in _BTN:
                    norm = _to_norm(event.pos, geo)
                    if norm:
                        send({"t": "m", "x": norm[0], "y": norm[1]})
                        send({"t": "md", "b": _BTN[event.button]})
                elif event.type == pygame.MOUSEBUTTONUP and event.button in _BTN:
                    send({"t": "mu", "b": _BTN[event.button]})
                elif event.type == pygame.MOUSEWHEEL:
                    send({"t": "scroll", "dy": event.y})
                elif event.type == pygame.KEYDOWN:
                    enc = encode_key(event)
                    if enc:
                        send({"t": "kd", **enc})
                elif event.type == pygame.KEYUP:
                    enc = encode_key(event)
                    if enc:
                        send({"t": "ku", **enc})

        win.fill((18, 18, 20))
        if frame is not None:
            vw, vh, buf = frame
            surface = pygame.image.frombuffer(buf, (vw, vh), "RGB")
            scaled = pygame.transform.smoothscale(surface, (geo["dw"], geo["dh"]))
            win.blit(scaled, (geo["ox"], geo["oy"]))
            label = small.render(f"AnyHelp  ·  controlling {code}  ·  {status}",
                                 True, (210, 210, 220))
            win.blit(label, (10, wh - 24))
        else:
            message = error or status or "Connecting…"
            for i, line in enumerate(message.split("\n")):
                txt = font.render(line, True, (235, 235, 240))
                win.blit(txt, (ww // 2 - txt.get_width() // 2, wh // 2 - 40 + i * 32))
            hint = small.render("This window will close if the connection fails.",
                                True, (140, 140, 150))
            win.blit(hint, (ww // 2 - hint.get_width() // 2, wh // 2 + 70))

        pygame.display.flip()
        clock.tick(60)

    send({"t": "releaseall"})
    pygame.quit()


def run_controller():
    logging.basicConfig(level=logging.WARNING)
    code = _prompt_code()
    if not code:
        return

    shared = {"frame": None, "status": "Connecting…", "error": None, "conn": ""}
    lock = threading.Lock()
    loop = asyncio.new_event_loop()
    stop = threading.Event()
    holder = {}

    def worker():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_ctl_main(code, shared, lock, loop, stop, holder))
        except Exception as exc:
            with lock:
                shared["error"] = str(exc)
            log.exception("controller crashed")
        finally:
            loop.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    try:
        _pygame_loop(code, shared, lock, loop, stop, holder)
    finally:
        stop.set()
        try:
            loop.call_soon_threadsafe(lambda: None)
        except Exception:
            pass

    # Give the user a moment to read a final error, if the window never opened video.
    with lock:
        err = shared.get("error")
    if err:
        log.warning("controller ended: %s", err)


if __name__ == "__main__":
    run_controller()
