import os
import sys
import threading
import time
from typing import Tuple

import vlc

from .video_player_common import build_vlc_args
from .video_player_mac import MacVideoContainer
from .video_player_windows import attach_player as attach_non_macos_player


class VideoPlayerCore:
    def __init__(self, canvas_target):
        self.canvas_widget = canvas_target if hasattr(canvas_target, "winfo_id") else None
        self.canvas_id = canvas_target.winfo_id() if self.canvas_widget is not None else int(canvas_target)
        self.vlc_available = False
        self.instance = None
        self.player = None
        self.embedded_video = sys.platform != "darwin"
        self._mac_container = MacVideoContainer(self.canvas_widget)
        try:
            self.instance = vlc.Instance(*build_vlc_args())
            self.player = self.instance.media_player_new()
            self._attach_to_canvas()
            self.vlc_available = True
        except Exception as exc:
            print(f"VLC Initialization Error: {exc}")
            self._mac_container.debug_log(f"init_error: {exc}")

    def _attach_to_canvas(self):
        if sys.platform == "darwin":
            self.embedded_video = self._mac_container.attach(self.player)
            return
        attach_non_macos_player(self.player, self.canvas_id)

    def sync_video_container(self):
        if sys.platform == "darwin":
            self._mac_container.sync()

    def load_video(self, video_path, start_time: int = 0, start_playing: bool = False):
        if not self.vlc_available:
            return False
        try:
            self._mac_container.debug_log(
                f"load_video start: path={video_path} start_time={start_time} start_playing={start_playing}"
            )
            if self.player.is_playing():
                self.player.stop()

            old_media = self.player.get_media()
            if old_media:
                old_media.release()

            media = self.instance.media_new(video_path)
            media.add_option(":avcodec-hw=any")

            self._attach_to_canvas()
            self.player.set_media(media)
            self.player.video_set_scale(0.0)
            if self.embedded_video:
                self.player.video_set_mouse_input(False)
                self.player.video_set_key_input(False)

            def _async_start():
                if not start_playing:
                    self.player.audio_set_mute(True)
                self.player.play()
                timeout = time.time() + 2.0
                while time.time() < timeout:
                    if self.player.is_playing() or self.player.get_length() > 0:
                        break
                    time.sleep(0.05)

                if start_time > 0:
                    self.player.set_time(start_time)

                if not start_playing:
                    time.sleep(0.3)
                    if start_time <= 0 and self.player.get_time() <= 0:
                        self.player.set_time(1)
                        time.sleep(0.05)
                        self.player.set_time(0)
                    self.player.set_pause(1)
                    self.player.audio_set_mute(False)

            threading.Thread(target=_async_start, daemon=True).start()
            return True
        except Exception as exc:
            print(f"Error loading video: {exc}")
            self._mac_container.debug_log(f"load_video_error: {exc}")
            return False

    def set_subtitle(self, sub_path):
        if self.vlc_available and self.player and os.path.exists(sub_path):
            self.player.video_set_subtitle_file(sub_path)
            return True
        return False

    def toggle_play(self):
        if not self.vlc_available:
            return False
        if self.player.get_state() == vlc.State.Ended:
            self.player.stop()
            self.player.play()
            return True
        if self.player.is_playing():
            self.player.set_pause(1)
        else:
            self.player.play()
        return self.player.is_playing()

    def play(self):
        if self.vlc_available:
            if self.player.get_state() == vlc.State.Ended:
                self.player.stop()
            self.player.play()

    def pause(self):
        if self.vlc_available:
            self.player.set_pause(1)

    def is_playing(self):
        return self.player.is_playing() if self.vlc_available else False

    def stop(self):
        if self.vlc_available:
            self.player.stop()
        if sys.platform == "darwin":
            self._mac_container.hide()

    def set_scale(self, factor: float):
        if self.vlc_available and self.player:
            self.player.video_set_scale(factor)

    def set_time(self, ms):
        if self.vlc_available:
            if self.player.get_state() == vlc.State.Ended:
                self.player.stop()
                self.player.play()
                self.player.set_pause(1)
            self.player.set_time(int(ms))

    def get_time(self):
        return self.player.get_time() if self.vlc_available else 0

    def get_length(self):
        return self.player.get_length() if self.vlc_available else 0

    def get_position(self):
        return self.player.get_position() if self.vlc_available else 0

    def set_position(self, pos):
        if self.vlc_available:
            self.player.set_position(pos)

    def set_mute(self, mute: bool):
        if self.vlc_available and self.player:
            self.player.audio_set_mute(mute)

    def skip(self, ms):
        if self.vlc_available:
            if self.player.get_state() == vlc.State.Ended:
                self.player.stop()
                self.player.play()
                self.player.set_pause(1)
            new_time = max(0, self.player.get_time() + ms)
            self.player.set_time(new_time)

    def get_video_resolution(self) -> Tuple[int, int]:
        if not self.vlc_available or not self.player:
            return 1920, 1080
        w = self.player.video_get_width()
        h = self.player.video_get_height()
        if w <= 0 or h <= 0:
            return 1920, 1080
        return w, h
