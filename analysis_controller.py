import time
import threading

class AnalysisController:
    """[시니어 컨트롤러] 엔진의 분석 루프와 렌더링 작업을 주관하는 컨트롤러 (GUI와 비동기 로직 분리)"""
    def __init__(self, engine, video_editor, transcript_manager, dispatcher):
        self.engine = engine
        self.video_editor = video_editor
        self.transcript_manager = transcript_manager
        self.dispatcher = dispatcher

    def run_analysis(self, p, stop_ev, mode, min_sil_ms, pad_ms, max_chars, options=None):
        try:
            start_time = time.time()
            
            # 콜백을 통해 UI 액션(이벤트 명)을 변환
            def dispatch_ui(task):
                action = task.pop("action")
                self.dispatcher.emit(action, task)

            if "자동 챕터 분할" in mode:
                labels = ["a person talking to camera, just chatting", "video game play screen", "web browser or document screen"]
                for chunk_res, prog in self.engine.detect_scenes_clip_stream(p, labels, stop_ev, options=options):
                    if stop_ev.is_set(): break
                    self.dispatcher.emit("progress", {"value": prog, "text": f"비전 분석 중... ({int(prog)}%)"})
                    for r in chunk_res: self.transcript_manager.add_segment(r, dispatch_ui)
                if not stop_ev.is_set():
                    total_elapsed = int(time.time() - start_time)
                    self.dispatcher.emit("complete", {"text": f"챕터 분석 완료 (소요 시간: {total_elapsed//60}분 {total_elapsed%60}초)", "is_vad": True})
                return

            audio_data, duration = self.engine.load_audio_to_memory(p)
            if stop_ev.is_set(): return
            
            if mode == "무음 제거 편집 (VAD)":
                for chunk_res, prog in self.engine.detect_speech_vad_stream(audio_data, stop_ev, min_sil_ms, pad_ms, options=options):
                    if stop_ev.is_set(): break
                    elapsed = time.time() - start_time
                    eta = int((elapsed / prog) * (100 - prog)) if prog > 5 else -1
                    self.dispatcher.emit("progress", {"value": prog, "text": f"VAD 분석 중 ({int(prog)}%){f' (남은 시간: {eta//60}분 {eta%60}초)' if eta >= 0 else ''}"})
                    for r in chunk_res: self.transcript_manager.add_segment(r, dispatch_ui)
                if not stop_ev.is_set():
                    total_elapsed = int(time.time() - start_time)
                    self.dispatcher.emit("complete", {"text": f"분석 완료 (소요 시간: {total_elapsed//60}분 {total_elapsed%60}초)", "is_vad": True})
            
            elif "깜놀" in mode:
                for chunk_res, prog in self.engine.detect_peaks_stream(audio_data, stop_ev):
                    if stop_ev.is_set(): break
                    elapsed = time.time() - start_time
                    eta = int((elapsed / prog) * (100 - prog)) if prog > 5 else -1
                    self.dispatcher.emit("progress", {"value": prog, "text": f"피크 감지 중 ({int(prog)}%){f' (남은 시간: {eta//60}분 {eta%60}초)' if eta >= 0 else ''}"})
                    for r in chunk_res: self.transcript_manager.add_segment(r, dispatch_ui)
                if not stop_ev.is_set():
                    total_elapsed = int(time.time() - start_time)
                    self.dispatcher.emit("complete", {"text": f"분석 완료 (소요 시간: {total_elapsed//60}분 {total_elapsed%60}초)", "is_vad": False})
            
            else:
                gen, total_dur = self.engine.transcribe_stream_raw(audio_data, stop_ev, options=options)
                for r in gen:
                    if stop_ev.is_set(): break
                    
                    # --- [추가] 하트비트를 수신하여 안정적인 ETA 계산 ---
                    if isinstance(r, dict) and r.get("is_heartbeat"):
                        prog = r["progress"]
                        elapsed = time.time() - start_time
                        if prog > 0.5: # 초기 튐 현상 방지
                            eta = int((elapsed / prog) * (100 - prog))
                            eta_str = f" (남은 시간: {eta//60}분 {eta%60}초)" if eta >= 0 else " (남은 시간 계산 중...)"
                            self.dispatcher.emit("progress", {"value": prog, "text": f"Whisper 분석 중 ({int(prog)}%){eta_str}"})
                        continue

                    # (기존의 자막 분할 및 추가 로직)
                    text = r['t'].strip()
                    if len(text) > max_chars:
                        chunks = self.transcript_manager.smart_split_text(text, max_chars)
                        total_char_len = sum(len(c) for c in chunks)
                        curr_ratio = 0.0
                        for c in chunks:
                            if not c: continue
                            ratio = len(c) / total_char_len
                            self.transcript_manager.add_segment({'s': r['s'] + (r['e']-r['s'])*curr_ratio, 'e': r['s'] + (r['e']-r['s'])*(curr_ratio+ratio), 't': c}, dispatch_ui)
                            curr_ratio += ratio
                    else:
                        self.transcript_manager.add_segment(r, dispatch_ui)
                
                if not stop_ev.is_set(): 
                    is_combi = "컷편집" in mode or "자연어" in mode
                    total_elapsed = int(time.time() - start_time)
                    complete_txt = f"분석 완료 ({total_elapsed//60}분 {total_elapsed%60}초)"
                    self.dispatcher.emit("complete", {"text": complete_txt, "is_vad": is_combi, "is_whisper": True})
        except Exception as ex:
            if not stop_ev.is_set(): self.dispatcher.emit("error", {"text": f"분석 오류: {str(ex)}"})
        finally:
            if 'audio_data' in locals():
                del audio_data
            import gc; gc.collect()
            if stop_ev.is_set(): 
                self.dispatcher.emit("ghost_defense", {})

    def run_editing(self, current_video_path, out_path, results_data, stop_event, settings, burn_ass=None):
        def upd_p(v, eta): self.dispatcher.emit("progress", {"value": v, "text": f"렌더링 중 ({v}%){f' - 남은 시간: {int(eta//60)}분 {int(eta%60)}초' if eta >= 0 else ''}"})
        try:
            if self.video_editor.cut_silence(current_video_path, out_path, results_data, stop_event, upd_p, v_codec=settings['v_codec'], a_codec=settings['a_codec'], v_bitrate=settings['v_bitrate'], a_bitrate=settings['a_bitrate'], fast_mode=settings['fast_mode'], burn_ass=burn_ass, overlays=settings.get('overlays'), image_overlays=settings.get('image_overlays')): 
                self.dispatcher.emit("message", {"text": f"작업 완료!\n{out_path}"})
            else: 
                self.dispatcher.emit("error", {"text": "렌더링 중 오류 발생"})
        except Exception as e: 
            self.dispatcher.emit("error", {"text": f"편집 오류: {str(e)}"})
        finally: 
            # [시니어] 사용이 끝난 임시 자막 파일(ASS) 삭제
            if burn_ass:
                try:
                    import os
                    if os.path.exists(burn_ass): os.remove(burn_ass)
                except: pass
            self.dispatcher.emit("complete", {"text": "작업 완료", "is_vad": True})

    def init_engine(self):
        try: 
            self.engine.get_model()
            self.dispatcher.emit("progress", {"value": 0, "text": "엔진 준비 완료"})
        except Exception as e: 
            self.dispatcher.emit("error", {"text": f"엔진 로드 실패: {e}"})
