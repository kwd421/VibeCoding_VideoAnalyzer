import os
import sys
import time
from typing import Tuple

import vlc

if sys.platform == "darwin":
    try:
        import objc
        from AppKit import NSApp, NSMakeRect, NSView, NSWindowAbove
    except Exception:
        objc = None
        NSApp = None
        NSMakeRect = None
        NSView = None
        NSWindowAbove = None
else:
    objc = None
    NSApp = None
    NSMakeRect = None
    NSView = None
    NSWindowAbove = None

class VideoPlayer:
    def __init__(self, canvas_widget):
        self.canvas_widget = canvas_widget
        self.canvas_id = canvas_widget.winfo_id()
        self.vlc_available = False
        self.instance = None
        self.player = None
        self.embedded_video = sys.platform != "darwin"
        self._ns_container = None
        self._ns_window = None
        self._ns_content = None
        try:
            self.instance = vlc.Instance(*self._get_vlc_args())
            self.player = self.instance.media_player_new()
            self._attach_to_canvas()
            self.vlc_available = True
        except Exception as e:
            print(f"VLC Initialization Error: {e}")
            self._debug_log(f"init_error: {e}")

    def _debug_log(self, message):
        if sys.platform != "darwin":
            return
        try:
            with open("/tmp/vibe_video_debug.log", "a", encoding="utf-8") as fp:
                fp.write(f"{time.strftime('%H:%M:%S')} {message}\n")
        except Exception:
            pass

    def _get_vlc_args(self):
        args = ["--avcodec-hw=any", "--drop-late-frames", "--skip-frames"]
        if sys.platform.startswith("linux"):
            args.insert(0, "--no-xlib")
        return args

    def _attach_to_canvas(self):
        if sys.platform == "darwin":
            self._attach_to_macos_container()
            return
        if os.name == "nt":
            self.player.set_hwnd(self.canvas_id)
        else:
            self.player.set_xwindow(self.canvas_id)

    def _attach_to_macos_container(self):
        if not all([objc, NSApp, NSMakeRect, NSView]):
            self.embedded_video = False
            return
        try:
            self.canvas_widget.update_idletasks()
            app = NSApp()
            if app is None:
                self.embedded_video = False
                self._debug_log("attach: NSApp unavailable")
                return
            window = app.keyWindow() or app.mainWindow() or (app.windows()[0] if app.windows() else None)
            if window is None:
                self.embedded_video = False
                self._debug_log("attach: no window")
                return
            content = window.contentView()
            if self._ns_container is None or self._ns_window != window:
                if self._ns_container is not None:
                    try:
                        self._ns_container.removeFromSuperview()
                    except Exception:
                        pass
                container = NSView.alloc().initWithFrame_(content.bounds())
                container.setWantsLayer_(True)
                if NSWindowAbove is not None and hasattr(content, "addSubview_positioned_relativeTo_"):
                    content.addSubview_positioned_relativeTo_(container, NSWindowAbove, None)
                else:
                    content.addSubview_(container)
                self._ns_container = container
                self._ns_window = window
                self._ns_content = content
                self._debug_log(f"attach: new_container window={window}")
            self._sync_macos_container()
            self.player.set_nsobject(objc.pyobjc_id(self._ns_container))
            self.embedded_video = True
            self._debug_log("attach: set_nsobject ok")
        except Exception as e:
            print(f"macOS video attach failed: {e}")
            self.embedded_video = False
            self._debug_log(f"attach_error: {e}")

    def _sync_macos_container(self):
        if sys.platform != "darwin" or self._ns_container is None or self._ns_content is None:
            return
        try:
            self.canvas_widget.update_idletasks()
            toplevel = self.canvas_widget.winfo_toplevel()
            content_bounds = self._ns_content.bounds()
            content_h = content_bounds.size.height
            x = self.canvas_widget.winfo_rootx() - toplevel.winfo_rootx()
            y = self.canvas_widget.winfo_rooty() - toplevel.winfo_rooty()
            w = self.canvas_widget.winfo_width()
            h = self.canvas_widget.winfo_height()
            if w <= 1 or h <= 1:
                return
            cocoa_y = max(0, content_h - y - h)
            self._ns_container.setFrame_(NSMakeRect(x, cocoa_y, w, h))
            self._ns_container.setHidden_(False)
            self._ns_container.setNeedsDisplay_(True)
            if hasattr(self._ns_container, "displayIfNeeded"):
                self._ns_container.displayIfNeeded()
        except Exception as e:
            print(f"macOS video sync failed: {e}")
            self._debug_log(f"sync_error: {e}")

    def sync_video_container(self):
        if sys.platform == "darwin":
            self._sync_macos_container()

    def load_video(self, video_path, start_time: int = 0, start_playing: bool = False):
        if not self.vlc_available: return False
        try:
            self._debug_log(f"load_video start: path={video_path} start_time={start_time} start_playing={start_playing}")
            if self.player.is_playing():
                self.player.stop()
                
            old_media = self.player.get_media()
            if old_media:
                old_media.release()
                
            media = self.instance.media_new(video_path)
            
            media.add_option(":avcodec-hw=any") # 하드웨어 가속 강제
                
            self._attach_to_canvas()
            self.player.set_media(media)
            self.player.video_set_scale(0.0)
            
            # [시니어 최적화] VLC가 마우스 입력을 가로채어 Tkinter 클릭(Play/Pause)이 무시되는 현상 방어
            if self.embedded_video:
                self.player.video_set_mouse_input(False)
                self.player.video_set_key_input(False)
            
            # [시니어 최적화] 메인 스레드 블로킹(응답 없음) 방지를 위한 비동기 재생 대기
            def _async_start():
                if not start_playing:
                    self.player.audio_set_mute(True)
                    
                self.player.play()
                self._debug_log("async_start: play issued")
                timeout = time.time() + 2.0
                while time.time() < timeout:
                    if self.player.is_playing() or self.player.get_length() > 0:
                        break
                    time.sleep(0.05)
                self._debug_log(f"async_start: playing={self.player.is_playing()} len={self.player.get_length()} time={self.player.get_time()}")
                
                # 영상이 제대로 로드된 후 지정된 상태로 복구
                if start_time > 0:
                    self.player.set_time(start_time)
                
                if not start_playing:
                    # [검은 화면 방지] 타임라인 이동 후 GPU가 첫 프레임을 뽑아낼 시간을 잠시 줌
                    time.sleep(0.3)
                    # 첫 프레임이 늦게 그려지는 경우를 위해 0ms 근처를 한 번 워프해 렌더를 깨운다.
                    if start_time <= 0 and self.player.get_time() <= 0:
                        self.player.set_time(1)
                        time.sleep(0.05)
                        self.player.set_time(0)
                    self.player.set_pause(1)
                    self.player.audio_set_mute(False)
                    self._debug_log(f"async_start: paused time={self.player.get_time()} len={self.player.get_length()}")
            
            self._async_timeout = time.time() + 2.0
            import threading
            threading.Thread(target=_async_start, daemon=True).start()
            
            return True
        except Exception as e:
            print(f"Error loading video: {e}")
            self._debug_log(f"load_video_error: {e}")
            return False

    def set_subtitle(self, sub_path):
        """외부 자막 파일(.ass/.srt)을 플레이어에 적용"""
        if self.vlc_available and self.player and os.path.exists(sub_path):
            self.player.video_set_subtitle_file(sub_path)
            return True
        return False

    def clear_subtitle(self):
        """현재 적용된 외부 자막 트랙 비활성화"""
        if not self.vlc_available or not self.player:
            return False
        try:
            self.player.video_set_spu(-1)
            return True
        except Exception:
            return False

    def set_marquee(self, text, *, size=80, color=0xFFFFFF, opacity=255, margin_v=50):
        """VLC marquee 텍스트를 영상 위에 직접 표시"""
        if not self.vlc_available or not self.player:
            return False
        try:
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 1)
            self.player.video_set_marquee_string(vlc.VideoMarqueeOption.Text, text or "")
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Size, max(8, int(size)))
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Color, int(color))
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Opacity, max(0, min(255, int(opacity))))
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Position, int(getattr(vlc.Position.bottom, "value", 6)))
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Timeout, 0)
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Refresh, 0)
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Y, max(0, int(margin_v)))
            return True
        except Exception as e:
            self._debug_log(f"marquee_error: {e}")
            return False

    def clear_marquee(self):
        if not self.vlc_available or not self.player:
            return False
        try:
            self.player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 0)
            return True
        except Exception:
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
            self.clear_marquee()
        if sys.platform == "darwin" and self._ns_container is not None:
            try:
                self._ns_container.setHidden_(True)
            except Exception:
                pass

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
