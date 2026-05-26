#!/usr/bin/env python3
"""Standalone test script: pop up a warning dialog. Run as the target user."""

import subprocess
import sys
import time

TITLE = "Parental Controls"
MSG = "Your computer time is up or your chores are not done yet.\n\nYou will be logged off."
DELAY = 10  # seconds


def try_gdbus() -> bool:
    try:
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.freedesktop.Notifications",
                "--object-path", "/org/freedesktop/Notifications",
                "--method", "org.freedesktop.Notifications.Notify",
                "Parental Controls", "0", "dialog-warning",
                TITLE, MSG, "[]", "{}", str(DELAY * 1000),
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            time.sleep(DELAY)
            return True
        return False
    except FileNotFoundError:
        return False


def try_kdialog() -> bool:
    try:
        result = subprocess.run(
            ["kdialog", "--title", TITLE, "--sorry", MSG],
            timeout=DELAY + 5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def try_zenity() -> bool:
    try:
        subprocess.run(
            ["zenity", "--warning", f"--title={TITLE}", f"--text={MSG}", f"--timeout={DELAY}"],
            timeout=DELAY + 5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def try_tkinter() -> bool:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()

        win = tk.Toplevel(root)
        win.title(TITLE)
        win.attributes("-topmost", True)
        win.resizable(False, False)

        tk.Label(win, text=MSG, padx=20, pady=10, justify="left", wraplength=300).pack()

        bar_frame = tk.Frame(win)
        bar_frame.pack(fill="x", padx=20, pady=(0, 5))
        tk.Label(bar_frame, text="Logging off in:").pack(side="left")
        countdown_var = tk.StringVar(value=str(DELAY))
        tk.Label(bar_frame, textvariable=countdown_var, width=3).pack(side="left")

        remaining = [DELAY]

        def tick():
            remaining[0] -= 1
            countdown_var.set(str(remaining[0]))
            if remaining[0] > 0:
                win.after(1000, tick)
            else:
                root.destroy()

        win.after(1000, tick)
        root.mainloop()
        return True
    except Exception as e:
        print(f"tkinter failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    print("Trying gdbus...", flush=True)
    if try_gdbus():
        sys.exit(0)

    print("Trying kdialog...", flush=True)
    if try_kdialog():
        sys.exit(0)

    print("Trying zenity...", flush=True)
    if try_zenity():
        sys.exit(0)

    print("Trying tkinter...", flush=True)
    if try_tkinter():
        sys.exit(0)

    print("No dialog method worked — sleeping bare delay", file=sys.stderr)
    time.sleep(DELAY)
    sys.exit(1)
