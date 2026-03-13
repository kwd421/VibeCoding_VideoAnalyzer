import vlc
import time
import os
from typing import Tuple

class VideoPlayer:
    def __init__(self, canvas_id):
        self.canvas_id = canvas_id
        self.vlc_available = False
        self.instance = None
        self.player = None
        try:
            # [시니어 최적화] 하드웨어 가속(D3D11VA) 상시 활성화
            # 화면 일시적 깨짐(log error)이 발생해도 바로 복구되므로 일관성있는 GPU 가속 유지
            # --avcodec-hw=any: 하드웨어 가속 사용 (Direct3D11 등)
            self.instance = vlc.Instance("--no-xlib", "--avcodec-hw=any", "--drop-late-frames", "--skip-frames")
            self.player = self.instance.media_player_new()
            self.player.set_hwnd(self.canvas_id)
            self.vlc_available = True
        except Exception as e:
            print(f"VLC Initialization Error: {e}")

    def load_video(self, video_path, start_time: int = 0, start_playing: bool = False):
        if not self.vlc_available: return False
        try:
            if self.player.is_playing():
                self.player.stop()
                
            old_media = self.player.get_media()
            if old_media:
                old_media.release()
                
            media = self.instance.media_new(video_path)
            
            media.add_option(":avcodec-hw=any") # 하드웨어 가속 강제
                
            self.player.set_hwnd(self.canvas_id)
            self.player.set_media(media)
            self.player.video_set_scale(0.0)
            
            # [시니어 최적화] VLC가 마우스 입력을 가로채어 Tkinter 클릭(Play/Pause)이 무시되는 현상 방어
            self.player.video_set_mouse_input(False)
            self.player.video_set_key_input(False)
            
            # [시니어 최적화] 메인 스레드 블로킹(응답 없음) 방지를 위한 비동기 재생 대기
            def _async_start():
                if not start_playing:
                    self.player.audio_set_mute(True)
                    
                self.player.play()
                timeout = time.time() + 2.0
                while not self.player.is_playing() and time.time() < timeout:
                    time.sleep(0.05)
                
                # 영상이 제대로 로드된 후 지정된 상태로 복구
                if start_time > 0:
                    self.player.set_time(start_time)
                
                if not start_playing:
                    # [검은 화면 방지] 타임라인 이동 후 GPU가 첫 프레임을 뽑아낼 시간을 잠시 줌
                    time.sleep(0.15)
                    self.player.set_pause(1)
                    self.player.audio_set_mute(False)
            
            self._async_timeout = time.time() + 2.0
            import threading
            threading.Thread(target=_async_start, daemon=True).start()
            
            return True
        except Exception as e:
            print(f"Error loading video: {e}")
            return False

    def set_subtitle(self, sub_path):
        """외부 자막 파일(.ass/.srt)을 플레이어에 적용"""
        if self.vlc_available and self.player and os.path.exists(sub_path):
            self.player.video_set_subtitle_file(sub_path)
            return True
        return False

    def toggle_play(self):
        if not self.vlc_available: return False
        
        # [시니어 최적화] 영상이 끝까지 가서 (Ended) 멈춘 상태라면 리셋(Stop) 후 처음부터 다시 재생
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

    def set_scale(self, factor: float):
        if self.vlc_available and self.player:
            self.player.video_set_scale(factor)

    def set_time(self, ms):
        if self.vlc_available:
            # [시니어 최적화] 영상이 재생 종료(Ended) 상태에 도달했을 때, 타임라인을 눌러서 시간을 돌려도
            # VLC 엔진이 시간을 먹지 않고 무시하는 현상(블로킹)을 방지하기 위해 강제 리셋 후 시간 워프
            if self.player.get_state() == vlc.State.Ended:
                self.player.stop()
                self.player.play()
                self.player.set_pause(1) # 일단 정지상태 유지
            
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
            # [시니어 최적화] 영상이 끝났을 경우 방향키로 앞뒤 탐색 시 무시되는 현상 방지
            if self.player.get_state() == vlc.State.Ended:
                self.player.stop()
                self.player.play()
                self.player.set_pause(1)
                
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
