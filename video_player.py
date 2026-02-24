import vlc
import time
from typing import Tuple

class VideoPlayer:
    def __init__(self, canvas_id):
        self.canvas_id = canvas_id
        self.vlc_available = False
        self.instance = None
        self.player = None
        
        try:
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            self.vlc_available = True
        except Exception as e:
            print(f"VLC Initialization Error: {e}")

    def load_video(self, video_path):
        if not self.vlc_available: return False
        try:
            media = self.instance.media_new(video_path)
            self.player.set_media(media)
            self.player.set_hwnd(self.canvas_id)
            
            # [시니어 최적화] 하드코딩된 time.sleep(0.1) 제거 및 이벤트 기반 정지 유도
            self.player.play()
            
            # 플레이어가 실제로 재생을 시작할 때까지 아주 짧게 polling
            timeout = time.time() + 2.0
            while not self.player.is_playing() and time.time() < timeout:
                time.sleep(0.01)
                
            self.player.pause()
            return True
        except:
            return False

    def set_subtitle(self, srt_path):
        """외부 자막 파일(.srt)을 플레이어에 적용"""
        if self.vlc_available and self.player and os.path.exists(srt_path):
            self.player.video_set_subtitle_file(srt_path)
            return True
        return False

    def toggle_play(self):
        if not self.vlc_available: return False
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()
        return self.player.is_playing()

    def is_playing(self):
        return self.player.is_playing() if self.vlc_available else False

    def stop(self):
        if self.vlc_available:
            self.player.stop()

    def set_time(self, ms):
        if self.vlc_available:
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

    def skip(self, ms):
        if self.vlc_available:
            new_time = max(0, self.player.get_time() + ms)
            self.player.set_time(new_time)

    def get_video_resolution(self) -> Tuple[int, int]:
        """[시니어 최적화] VLC를 통해 로드된 영상의 원본 해상도(W, H)를 가져옴"""
        if not self.vlc_available or not self.player:
            return 1920, 1080 
        
        w = self.player.video_get_width()
        h = self.player.video_get_height()
        
        if w <= 0 or h <= 0:
            return 1920, 1080
            
        return w, h
