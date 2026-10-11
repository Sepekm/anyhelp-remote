"""Screen-capture video track for aiortc, backed by `mss`."""
import asyncio
import time

import mss
import numpy as np
from aiortc import VideoStreamTrack
from aiortc.mediastreams import VIDEO_CLOCK_RATE, VIDEO_TIME_BASE
from av import VideoFrame


def _even(n: int) -> int:
    return n - (n % 2)


class ScreenTrack(VideoStreamTrack):
    """Grabs the primary monitor and emits paced video frames.

    `self.monitor` holds the captured region ({left, top, width, height} in
    real desktop pixels) so the host can map normalized remote-cursor
    coordinates back to actual screen positions.
    """

    kind = "video"

    def __init__(self, fps: int = 15, max_width: int = 1600):
        super().__init__()
        self.fps = fps
        self._sct = mss.mss()
        # monitors[0] is the full virtual desktop; [1] is the primary monitor.
        self.monitor = dict(self._sct.monitors[1])
        src_w, src_h = self.monitor["width"], self.monitor["height"]
        if src_w > max_width:
            scale = max_width / src_w
            self._out_w = _even(int(src_w * scale))
            self._out_h = _even(int(src_h * scale))
        else:
            self._out_w = _even(src_w)
            self._out_h = _even(src_h)
        self._frame_index = 0
        self._start = None

    async def recv(self) -> VideoFrame:
        # Pace output to the target frame rate.
        now = time.time()
        if self._start is None:
            self._start = now
        self._frame_index += 1
        target = self._start + self._frame_index / self.fps
        delay = target - now
        if delay > 0:
            await asyncio.sleep(delay)

        raw = self._sct.grab(self.monitor)
        bgra = np.asarray(raw)  # shape (h, w, 4), BGRA
        bgr = np.ascontiguousarray(bgra[:, :, :3])

        frame = VideoFrame.from_ndarray(bgr, format="bgr24")
        if (frame.width, frame.height) != (self._out_w, self._out_h):
            frame = frame.reformat(width=self._out_w, height=self._out_h)

        frame.pts = int(self._frame_index * VIDEO_CLOCK_RATE / self.fps)
        frame.time_base = VIDEO_TIME_BASE
        return frame

    def stop(self) -> None:
        super().stop()
        try:
            self._sct.close()
        except Exception:
            pass
