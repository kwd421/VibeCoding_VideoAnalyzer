import os
import sys


def build_vlc_args():
    args = ["--avcodec-hw=any", "--drop-late-frames", "--skip-frames"]
    if sys.platform.startswith("linux"):
        args.insert(0, "--no-xlib")
    return args


def attach_non_macos_player(player, canvas_id):
    if os.name == "nt":
        player.set_hwnd(canvas_id)
    else:
        player.set_xwindow(canvas_id)
