import tkinter as tk
from tkinter import ttk
import os
import sys
import glob
import traceback

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def create_startup_splash(root):
    splash = tk.Toplevel(root)
    splash.title("Starting...")
    splash.geometry("420x200")
    splash.configure(bg="#1D1D1F")
    splash.resizable(False, False)
    splash.attributes("-topmost", True)

    splash.update_idletasks()
    x = (splash.winfo_screenwidth() // 2) - (420 // 2)
    y = (splash.winfo_screenheight() // 2) - (200 // 2)
    splash.geometry(f"420x200+{x}+{y}")

    title = tk.Label(
        splash,
        text="VAD AI Studio",
        fg="#FFFFFF",
        bg="#1D1D1F",
        font=("Segoe UI", 18, "bold"),
    )
    title.pack(pady=(30, 8))

    msg = tk.Label(
        splash,
        text="Starting...",
        fg="#C7C7CC",
        bg="#1D1D1F",
        font=("Segoe UI", 10),
    )
    msg.pack()

    pct = tk.Label(
        splash,
        text="0%",
        fg="#9AA0A6",
        bg="#1D1D1F",
        font=("Segoe UI", 9),
    )
    pct.pack(pady=(6, 0))

    bar = ttk.Progressbar(splash, mode="determinate", length=320, maximum=100)
    bar.pack(pady=(14, 0))
    splash.update()
    return splash, bar, msg, pct


def update_startup_progress(splash, bar, msg_label, pct_label, percent, message):
    percent = max(0, min(100, int(percent)))
    bar["value"] = percent
    msg_label.config(text=message)
    pct_label.config(text=f"{percent}%")
    splash.update_idletasks()
    splash.update()


def main():
    try:
        root = tk.Tk()
        root.withdraw()
        splash, bar, msg_label, pct_label = create_startup_splash(root)

        update_startup_progress(splash, bar, msg_label, pct_label, 5, "Cleaning temp files...")

        import shutil
        patterns = ["*_temp.wav", "export_burn_*.ass", "temp_fast_*"]
        for p in patterns:
            for junk in glob.glob(os.path.join(BASE_DIR, p)):
                try:
                    if os.path.isdir(junk):
                        shutil.rmtree(junk)
                    else:
                        os.remove(junk)
                except Exception:
                    pass

        update_startup_progress(splash, bar, msg_label, pct_label, 20, "Loading modules...")

        try:
            from app.ui.gui_app import CustomModelApp
            update_startup_progress(splash, bar, msg_label, pct_label, 35, "Initializing application...")

            def startup_progress(percent, message):
                # Map app-internal startup range into 35-100 on splash.
                mapped = 35 + int((max(0, min(100, percent)) * 65) / 100)
                update_startup_progress(splash, bar, msg_label, pct_label, mapped, message)

            app = CustomModelApp(root, startup_progress=startup_progress)
        finally:
            try:
                if splash.winfo_exists():
                    splash.destroy()
            except Exception:
                pass
            root.deiconify()

        root.mainloop()
    except Exception:
        print("-" * 50)
        print("Fatal Error occurred:")
        traceback.print_exc()
        print("-" * 50)
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
