# AnyHelp

A tiny, free remote-desktop tool for two people — like AnyDesk, but no
accounts, no trials, no cost. One person shares their screen and reads out a
6-character code; the other enters the code and gets live view + mouse/keyboard
control.

It is **consent-based and visible**: the person sharing must click **Allow** on
a pop-up, and a *"● LIVE — your screen is being shared and controlled"* status
stays on their screen the whole time.

> ⚠️ **Use at your own risk.** This is a hobby project, provided with no
> warranty (see [Disclaimer](#disclaimer)). It is a real remote-access tool —
> treat the session code like a password.

## Download (no Python needed)

Grab `AnyHelp.exe` from the [**Releases**](../../releases) page and run it.
Windows SmartScreen will likely warn about an "unknown publisher" (the exe
isn't code-signed) — choose **More info → Run anyway**. Some antivirus tools may
also flag it, because a program that captures the screen and sends keystrokes
looks, to them, like the thing they're built to catch. That's expected for a
tool like this; allow it only if you trust the source (or build it yourself
from the code below).

## How it works

- A **public PeerJS server** is used only to swap the initial WebRTC handshake
  (a few kilobytes). It never sees your screen or your input.
- The actual screen video and mouse/keyboard control flow **directly between
  the two PCs** over WebRTC (peer-to-peer), encrypted by WebRTC (DTLS/SRTP).
- No account, no login, no server of your own to run.

```
Controller  --code-->  PeerJS relay  <--registers--  Host
      \__________ direct WebRTC (video + input) __________/
```

## Running it (with Python)

Needs Python 3.10+ on Windows.

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Then on the PC that will be **viewed/controlled**:

```bat
python anyhelp.py host
```

A window shows a code. Read that code to the other person.

On the PC that will **control**:

```bat
python anyhelp.py control
```

Type the code, click **Connect**. The host clicks **Allow**, and a window opens
showing the remote screen. Move the mouse and type to control it.

The `Share my screen.bat` and `Control a screen.bat` files do the same thing
with a double-click (they use the bundled `.venv`).

## Making an .exe for the other person

So your partner doesn't need to install Python:

```bat
build_exe.bat
```

This produces `dist\AnyHelp.exe`. Send them that single file. They run it,
click **Share my screen**, and read you the code. (Windows SmartScreen may warn
about an unknown publisher the first time — "More info" → "Run anyway".)

## Notes & limits

- The **code is the only secret** — anyone who has it and connects while you're
  sharing can control your PC once you click Allow. Only share it with the
  person you're expecting, and close the app when you're done.
- Shares the **primary monitor** only.
- Runs the host app **as Administrator** if you need to control programs that
  themselves run as admin (Windows blocks input into elevated windows
  otherwise).
- Most home networks connect directly via STUN. Very strict/corporate networks
  fall back to a free public TURN relay, which may be slow or occasionally
  offline; if a connection never establishes, try a different network.
- Quality is tuned for responsiveness (about 15 fps, up to ~1.5 Mbps), which is
  fine for helping with apps, settings, and browsing — not for video playback.

## Third-party free services

The connection handshake uses the **public PeerJS server** (`0.peerjs.com`), and
strict networks may fall back to a **free public TURN relay**
(`openrelay.metered.ca`). These are shared community resources that AnyHelp does
not own — they may be rate-limited, change, or go offline at any time, and they
are fine for occasional personal use but not guaranteed. For heavy or reliable
use, run your own PeerServer and/or TURN server and point `signaling.py` /
`rtc.py` at them.

## Disclaimer

AnyHelp is provided "as is", without warranty of any kind, under the
[MIT License](LICENSE). The authors are not liable for any damage, data loss,
or unauthorized access resulting from its use.

Important things to understand before using it:

- **The session code is the only secret.** Anyone who has the code and connects
  while you are sharing can control your PC *once you click Allow*. There is no
  account, no password, and no limit on connection attempts. Only share the code
  with the person you are expecting, and close the app the moment you are done.
- **You are giving real control of your machine.** Only share your screen with
  someone you trust, and only accept a connection you are actively expecting.
- The traffic between the two PCs is encrypted by WebRTC (DTLS/SRTP), but this
  project has **not** had a formal security audit. Do not rely on it for
  high-risk or sensitive situations.
- Make sure your own use complies with the rules/laws that apply to you. Never
  use it to access a computer without the clear permission of the person using
  it.

## Files

| File | What it is |
|------|-----------|
| `anyhelp.py` | Launcher / entry point |
| `host.py` | Screen-sharing side (Tkinter UI + approval) |
| `controller.py` | Controlling side (pygame viewer + input capture) |
| `screen.py` | Screen capture → WebRTC video track |
| `inject.py` | Applies received mouse/keyboard on the host |
| `keymap.py` | Keyboard translation on the controller |
| `signaling.py` | PeerJS handshake relay client |
| `rtc.py` | WebRTC / ICE configuration |
| `common.py` | Codes and peer ids |
