"""AnyHelp — a tiny, free, consent-based remote-desktop tool.

Run with no arguments for the launcher, or:
    python anyhelp.py host       # share this PC's screen
    python anyhelp.py control    # control another PC
"""
import sys
import tkinter as tk

_BG = "#1e1e24"
_FG = "#f0f0f3"
_ACCENT = "#2d7dd2"


def _launcher() -> str | None:
    choice = {"value": None}
    root = tk.Tk()
    root.title("AnyHelp")
    root.configure(bg=_BG)
    root.geometry("420x320")
    root.resizable(False, False)

    tk.Label(root, text="AnyHelp", bg=_BG, fg=_ACCENT,
             font=("Segoe UI", 26, "bold")).pack(pady=(28, 2))
    tk.Label(root, text="Free remote desktop for you and one other person",
             bg=_BG, fg="#9aa0aa", font=("Segoe UI", 10)).pack()

    def pick(value):
        choice["value"] = value
        root.destroy()

    def button(text, subtitle, value):
        frame = tk.Frame(root, bg="#2a2a32")
        frame.pack(fill="x", padx=28, pady=10)
        btn = tk.Button(frame, text=text, command=lambda: pick(value),
                        bg=_ACCENT, fg="white", relief="flat",
                        font=("Segoe UI", 13, "bold"), pady=10)
        btn.pack(fill="x")
        tk.Label(frame, text=subtitle, bg="#2a2a32", fg="#9aa0aa",
                 font=("Segoe UI", 9)).pack(pady=(4, 8))

    button("Share my screen", "Show a code and let the other person control this PC",
           "host")
    button("Control a screen", "Enter their code to view and control their PC",
           "control")

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return choice["value"]


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if arg in ("host", "share"):
        choice = "host"
    elif arg in ("control", "controller", "view"):
        choice = "control"
    else:
        choice = _launcher()

    if choice == "host":
        from host import run_host
        run_host()
    elif choice == "control":
        from controller import run_controller
        run_controller()


if __name__ == "__main__":
    main()
