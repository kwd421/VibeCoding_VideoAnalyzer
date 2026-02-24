import os
import sys
import threading
import time
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import vlc
from engine_core import HyperTranscriptionEngine
from video_editor import VideoEditor
from video_player import VideoPlayer

class CustomModelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VAD AI Studio v25 (Vision Integrated)")
        self.root.geometry("1300x850")
        self.engine = HyperTranscriptionEngine()
        self.video_editor = VideoEditor()
        self.player = None
        self.stop_event = threading.Event()
        self.results_data = []
        self.current_video_path = None
        self.is_seeking = False
        self.ICON_PLAY = chr(9654); self.ICON_PAUSE = chr(9208)
        self.ui_queue = queue.Queue()
        self.setup_ui()
        self.player = VideoPlayer(self.video_canvas.winfo_id())
        self.bind_keys()
        self.load_engine_async()
        self.process_ui_queue()
        self.update_loop()

    def setup_ui(self):
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6); self.main_paned.pack(fill=tk.BOTH, expand=True)
        left_f = tk.Frame(self.main_paned, bg="#1a1a1a"); self.main_paned.add(left_f, minsize=750)
        self.video_canvas = tk.Frame(left_f, bg="black"); self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5); self.video_canvas.bind("<Button-1>", lambda e: self.toggle_play())
        self.seek_var = tk.DoubleVar(); self.seek_bar = tk.Scale(left_f, from_=0, to=1000, orient=tk.HORIZONTAL, variable=self.seek_var, showvalue=0, bg="#1a1a1a"); self.seek_bar.pack(fill=tk.X, padx=10, pady=2); self.seek_bar.bind("<ButtonPress-1>", self.on_seek_start); self.seek_bar.bind("<ButtonRelease-1>", self.on_seek_release)
        ctrl = tk.Frame(left_f, bg="#2d2d2d", pady=10); ctrl.pack(fill=tk.X); bg_f = tk.Frame(ctrl, bg="#2d2d2d"); bg_f.pack(expand=True)
        tk.Button(bg_f, text=chr(9194)+" 5s", command=lambda: self.skip_time(-5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)
        self.btn_play = tk.Button(bg_f, text=self.ICON_PLAY, command=self.toggle_play, width=8, bg="#27ae60", fg="white"); self.btn_play.pack(side=tk.LEFT, padx=10)
        tk.Button(bg_f, text="5s "+chr(9193), command=lambda: self.skip_time(5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)
        self.lbl_time = tk.Label(ctrl, text="00:00 / 00:00", bg="#2d2d2d", fg="white"); self.lbl_time.pack(side=tk.RIGHT, padx=20)
        right_f = tk.Frame(self.main_paned, padx=15); self.main_paned.add(right_f, minsize=450)
        af = tk.LabelFrame(right_f, text=" 분석 및 편집 설정 ", padx=10, pady=10); af.pack(fill=tk.X, pady=10)
        tk.Button(af, text="영상 파일 선택", command=self.on_select_video, bg="#34495e", fg="white", font=("bold")).pack(fill=tk.X, pady=5)
        mf = tk.Frame(af); mf.pack(fill=tk.X)
        self.mode_var = tk.StringVar(value="자연어-대사 변환")
        self.mode_combo = ttk.Combobox(mf, textvariable=self.mode_var, values=["자연어-대사 변환", "깜놀 구간 탐색 (초고속)", "무음 제거 편집 (VAD)", "자동 챕터 분할 (CLIP)"], state="readonly", width=30)
        self.mode_combo.pack(side=tk.LEFT, padx=5, pady=10); self.mode_var.trace_add("write", lambda *args: self.reset_action_button())
        self.btn_analyze = tk.Button(af, text="분석 시작", command=self.on_start_analysis, bg="#2980b9", fg="white", font=("bold"), pady=12); self.btn_analyze.pack(fill=tk.X, pady=5)
        self.btn_stop = tk.Button(af, text="작업 중지", command=self.on_stop_action, bg="#c0392b", fg="white", font=("bold"), state=tk.DISABLED); self.btn_stop.pack(fill=tk.X, pady=2)
        self.save_frame = tk.Frame(right_f); self.save_frame.pack(fill=tk.X, pady=5); self.save_frame.pack_forget()
        tk.Label(self.save_frame, text="[ 저장 옵션 선택 ]", fg="#8e44ad", font=("bold", 10)).pack(pady=5)
        self.btn_fast_save = tk.Button(self.save_frame, text="🚀 초고속 렌더링 (Stream Copy)", command=lambda: self.start_export(fast=True), bg="#8e44ad", fg="white", pady=8); self.btn_fast_save.pack(fill=tk.X, pady=2)
        self.btn_pro_save = tk.Button(self.save_frame, text="🎯 정밀 인코딩 (Match Source)", command=lambda: self.start_export(fast=False), bg="#2c3e50", fg="white", pady=8); self.btn_pro_save.pack(fill=tk.X, pady=2)
        self.btn_xml_save = tk.Button(self.save_frame, text="🎬 타임라인 내보내기 (XML)", command=self.on_export_xml, bg="#16a085", fg="white", pady=8); self.btn_xml_save.pack(fill=tk.X, pady=2)
        self.lbl_status = tk.Label(right_f, text="준비됨", fg="#27ae60", font=("bold", 10)); self.lbl_status.pack(fill=tk.X, pady=5)
        self.progress_var = tk.DoubleVar(); ttk.Progressbar(right_f, variable=self.progress_var).pack(fill=tk.X, pady=5)
        list_f = tk.Frame(right_f); list_f.pack(fill=tk.BOTH, expand=True, pady=10)
        self.tree = ttk.Treeview(list_f, columns=("no", "start", "end", "text"), show="headings"); self.tree.heading("no", text="No"); self.tree.heading("start", text="시작"); self.tree.heading("end", text="종료"); self.tree.heading("text", text="내용/길이"); self.tree.column("no", width=40, anchor=tk.CENTER); self.tree.column("start", width=80, anchor=tk.CENTER); self.tree.column("end", width=80, anchor=tk.CENTER); self.tree.column("text", width=250); sc = ttk.Scrollbar(list_f, orient=tk.VERTICAL, command=self.tree.yview); self.tree.configure(yscrollcommand=sc.set); self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sc.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 우클릭 메뉴 및 이벤트 바인딩 복구
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="시작 지점으로 이동", command=self.jump_to_start)
        self.menu.add_command(label="종료 지점으로 이동", command=self.jump_to_end)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Button-3>", self.show_context_menu)
        opt = tk.LabelFrame(right_f, text=" 상세 설정 ", padx=10, pady=10); opt.pack(fill=tk.X, pady=5); vad_f = tk.Frame(opt); vad_f.pack(fill=tk.X, pady=5); tk.Label(vad_f, text="무음 기준(초):").pack(side=tk.LEFT); self.silence_dur_var = tk.DoubleVar(value=2.0); tk.Entry(vad_f, textvariable=self.silence_dur_var, width=5).pack(side=tk.LEFT, padx=2); tk.Label(vad_f, text="음성 패딩(초):").pack(side=tk.LEFT, padx=(15, 0)); self.speech_pad_var = tk.DoubleVar(value=0.25); tk.Entry(vad_f, textvariable=self.speech_pad_var, width=5).pack(side=tk.LEFT, padx=2)
        lf = tk.Frame(opt); lf.pack(fill=tk.X); tk.Label(lf, text="대사 길이:").pack(side=tk.LEFT); self.max_len_int = tk.IntVar(value=50); self.max_len_str = tk.StringVar(value="50"); tk.Scale(lf, from_=10, to=50, orient=tk.HORIZONTAL, variable=self.max_len_int, showvalue=0, command=lambda v: self.max_len_str.set(str(v))).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5); tk.Entry(lf, textvariable=self.max_len_str, width=4).pack(side=tk.LEFT); self.export_format = tk.StringVar(value="SRT"); ex = tk.Frame(opt, pady=5); ex.pack(fill=tk.X); ttk.Combobox(ex, textvariable=self.export_format, values=["SRT", "VTT", "TXT", "CSV"], state="readonly", width=10).pack(side=tk.LEFT, padx=5); tk.Button(ex, text="자막 내보내기", command=self.export_subtitles, bg="#e67e22", fg="white").pack(side=tk.LEFT, padx=5)

    def bind_keys(self): self.root.bind("<space>", lambda e: self.toggle_play()); self.root.bind("<Left>", lambda e: self.skip_time(-5000)); self.root.bind("<Right>", lambda e: self.skip_time(5000))
    def process_ui_queue(self):
        try:
            while True:
                task = self.ui_queue.get_nowait()
                if task["action"] == "progress": self.progress_var.set(task["value"]); self.lbl_status.config(text=task["text"])
                elif task["action"] == "add_row": self.tree.insert("", "end", values=(task["i"], f"{round(task['s'], 2)}s", f"{round(task['e'], 2)}s", task['t']))
                elif task["action"] == "complete":
                    self.lbl_status.config(text=task["text"], fg="#27ae60"); self.progress_var.set(100)
                    if task.get("is_vad"): self.save_frame.pack(fill=tk.X, pady=5); self.btn_analyze.pack_forget()
                    else: self.apply_preview_subtitles(); self.btn_analyze.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                elif task["action"] == "message": messagebox.showinfo("완료", task["text"])
                elif task["action"] == "error": messagebox.showerror("Error", task["text"])
        except queue.Empty: pass
        finally: self.root.after(100, self.process_ui_queue)

    def load_engine_async(self): threading.Thread(target=self._init_engine, daemon=True).start()
    def _init_engine(self):
        try: self.engine.get_model(); self.ui_queue.put({"action": "progress", "value": 0, "text": "엔진 준비 완료"})
        except Exception as e: self.ui_queue.put({"action": "error", "text": f"엔진 로드 실패: {e}"})

    def reset_action_button(self): self.save_frame.pack_forget(); self.btn_analyze.pack(fill=tk.X, pady=5); self.btn_analyze.config(text="분석 시작", command=self.on_start_analysis, bg="#2980b9", state=tk.NORMAL); self.btn_fast_save.config(state=tk.NORMAL); self.btn_pro_save.config(state=tk.NORMAL); self.btn_xml_save.config(state=tk.NORMAL)
    def on_select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.flv")])
        if p:
            self.current_video_path = p
            if self.player.load_video(p): self.lbl_status.config(text="영상 로드됨: " + os.path.basename(p), fg="#2980b9"); self.reset_action_button()
            else: messagebox.showerror("Error", "영상을 불러올 수 없습니다.")

    def on_stop_action(self):
        if self.stop_event: self.stop_event.set(); self.lbl_status.config(text="중지 요청됨...", fg="red"); self.btn_stop.config(state=tk.DISABLED)

    def on_start_analysis(self):
        mode = self.mode_var.get()
        try: min_sil_ms, pad_ms = int(self.silence_dur_var.get() * 1000), int(self.speech_pad_var.get() * 1000)
        except: min_sil_ms, pad_ms = 2000, 250
        self.stop_event = threading.Event(); self.btn_analyze.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL); self.progress_var.set(0); self.results_data = []
        for i in self.tree.get_children(): self.tree.delete(i)
        threading.Thread(target=self.run_analysis, args=(self.current_video_path, self.stop_event, mode, min_sil_ms, pad_ms), daemon=True).start()

    def _add_result_row(self, r):
        """[시니어 헬퍼] 결과 데이터를 리스트와 UI 큐에 안전하게 추가"""
        self.results_data.append(r)
        self.ui_queue.put({"action": "add_row", "i": len(self.results_data), "s": r['s'], "e": r['e'], "t": r['t']})

    def run_analysis(self, p, stop_ev, mode, min_sil_ms, pad_ms):
        try:
            start_time = time.time()
            max_chars = self.max_len_int.get() # 사용자 설정 대사 길이
            
            if "자동 챕터 분할" in mode:
                labels = ["a person talking to camera, just chatting", "video game play screen", "web browser or document screen"]
                for chunk_res, prog in self.engine.detect_scenes_clip_stream(p, labels, stop_ev):
                    if stop_ev.is_set(): break
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"비전 분석 중... ({int(prog)}%)"})
                    for r in chunk_res: self._add_result_row(r)
                if not stop_ev.is_set(): self.ui_queue.put({"action": "complete", "text": "챕터 분석 완료", "is_vad": True})
                return

            audio_data, duration = self.engine.load_audio_to_memory(p)
            if stop_ev.is_set(): return
            
            if "무음 제거" in mode:
                for chunk_res, prog in self.engine.detect_speech_vad_stream(audio_data, stop_ev, min_sil_ms, pad_ms):
                    if stop_ev.is_set(): break
                    elapsed = time.time() - start_time
                    eta = int((elapsed / prog) * (100 - prog)) if prog > 5 else -1
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"VAD 분석 중 ({int(prog)}%){f' (남은 시간: {eta//60}분 {eta%60}초)' if eta >= 0 else ''}"})
                    for r in chunk_res: self._add_result_row(r)
                if not stop_ev.is_set(): self.ui_queue.put({"action": "complete", "text": "분석 완료 (저장 가능)", "is_vad": True})
            
            elif "깜놀" in mode:
                for chunk_res, prog in self.engine.detect_peaks_stream(audio_data, stop_ev):
                    if stop_ev.is_set(): break
                    elapsed = time.time() - start_time
                    eta = int((elapsed / prog) * (100 - prog)) if prog > 5 else -1
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"피크 감지 중 ({int(prog)}%){f' (남은 시간: {eta//60}분 {eta%60}초)' if eta >= 0 else ''}"})
                    for r in chunk_res: self._add_result_row(r)
                if not stop_ev.is_set(): self.ui_queue.put({"action": "complete", "text": "분석 완료", "is_vad": False})
            
            else:
                gen, total_dur = self.engine.transcribe_stream_raw(audio_data, stop_ev)
                last_upd, last_prog, ema_speed = time.time(), 0.0, 0.0
                for r in gen:
                    if stop_ev.is_set(): break
                    
                    text = r['t'].strip()
                    # [시니어 최적화] 대사 길이 제한 및 시각적 분할 알고리즘
                    if len(text) > max_chars:
                        words = text.split(); temp_text = ""; segment_start = r['s']; total_text_len = len(text)
                        for word in words:
                            if len(temp_text + word) + 1 > max_chars:
                                ratio = len(temp_text) / total_text_len
                                current_end = segment_start + ((r['e'] - r['s']) * ratio)
                                self._add_result_row({'s': segment_start, 'e': current_end, 't': temp_text.strip()})
                                segment_start, temp_text = current_end, word + " "
                            else: temp_text += word + " "
                        if temp_text.strip(): self._add_result_row({'s': segment_start, 'e': r['e'], 't': temp_text.strip()})
                    else:
                        self._add_result_row(r)
                    
                    prog = (r['e'] / total_dur) * 100; curr_t = time.time(); delta_t, delta_p = curr_t - last_upd, prog - last_prog
                    if delta_t > 0.5 and delta_p > 0:
                        curr_s = delta_p / delta_t
                        ema_speed = curr_s if ema_speed == 0 else (ema_speed * 0.8) + (curr_s * 0.2)
                        last_upd, last_prog = curr_t, prog
                    eta_str = f" (남은 시간: {int((100-prog)/ema_speed)//60}분 {int((100-prog)/ema_speed)%60}초)" if ema_speed > 0 else " (남은 시간 계산 중...)"
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"Whisper 분석 중 ({int(prog)}%){eta_str}"})
                if not stop_ev.is_set(): self.ui_queue.put({"action": "complete", "text": "분석 완료", "is_vad": False})
        except Exception as ex:
            if not stop_ev.is_set(): self.ui_queue.put({"action": "error", "text": f"분석 오류: {str(ex)}"})
        finally:
            if stop_ev.is_set(): self.root.after(0, lambda: [self.reset_action_button(), self.btn_stop.config(state=tk.DISABLED)])

    def start_export(self, fast=True):
        media_info = self.video_editor.get_media_info(self.current_video_path); ext = os.path.splitext(self.current_video_path)[1].lower().strip('.')
        save_path = filedialog.asksaveasfilename(defaultextension=f".{ext if ext in ['mp4','mkv','mov','avi'] else 'mp4'}", filetypes=[("Video File", f"*.{ext}")], initialfile=f"cut_{os.path.basename(self.current_video_path)}")
        if save_path:
            for b in [self.btn_fast_save, self.btn_pro_save, self.btn_xml_save]: b.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL); self.progress_var.set(0)
            settings = {'v_codec': media_info.get('v_codec', 'h264'), 'a_codec': media_info.get('a_codec', 'aac'), 'v_bitrate': f"{media_info.get('v_bitrate', 5000000) // 1000}k", 'a_bitrate': f"{media_info.get('a_bitrate', 128000) // 1000}k", 'fast_mode': fast}
            threading.Thread(target=self.run_editing, args=(save_path, settings), daemon=True).start()

    def on_export_xml(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("Final Cut Pro XML", "*.xml")], initialfile=f"Timeline_{os.path.splitext(os.path.basename(self.current_video_path))[0]}.xml")
        if save_path:
            try:
                media_info = self.video_editor.get_media_info(self.current_video_path); real_fps = media_info.get("fps", 30.0)
                if self.video_editor.export_premiere_xml(self.current_video_path, self.results_data, save_path, fps=real_fps): messagebox.showinfo("완료", f"XML 생성 완료:\n{save_path}")
                else: messagebox.showerror("오류", "XML 생성 실패")
            except Exception as e: messagebox.showerror("오류", str(e))

    def run_editing(self, out_path, settings):
        def upd_p(v, eta): self.ui_queue.put({"action": "progress", "value": v, "text": f"렌더링 중 ({v}%){f' - 남은 시간: {int(eta//60)}분 {int(eta%60)}초' if eta >= 0 else ''}"})
        try:
            if self.video_editor.cut_silence(self.current_video_path, out_path, self.results_data, self.stop_event, upd_p, v_codec=settings['v_codec'], a_codec=settings['a_codec'], v_bitrate=settings['v_bitrate'], a_bitrate=settings['a_bitrate'], fast_mode=settings['fast_mode']): self.ui_queue.put({"action": "message", "text": f"작업 완료!\n{out_path}"})
            else: self.ui_queue.put({"action": "error", "text": "렌더링 중 오류 발생"})
        except Exception as e: self.ui_queue.put({"action": "error", "text": f"편집 오류: {str(e)}"})
        finally: self.ui_queue.put({"action": "complete", "text": "작업 완료", "is_vad": True})

    def on_tree_click(self, e):
        item = self.tree.identify_row(e.y)
        if item:
            val = self.tree.item(item)['values']
            try: t_sec = float(str(val[1]).replace('s','')); self.player.set_time(int(t_sec * 1000)); self.player.toggle_play() if not self.player.is_playing() else None
            except: pass
    def jump_to_start(self):
        sel = self.tree.selection()
        if sel: self.player.set_time(int(float(str(self.tree.item(sel)['values'][1]).replace('s','')) * 1000))
    def jump_to_end(self):
        sel = self.tree.selection()
        if sel: self.player.set_time(int(float(str(self.tree.item(sel)['values'][2]).replace('s','')) * 1000))
    def show_context_menu(self, e):
        item = self.tree.identify_row(e.y)
        if item: self.tree.selection_set(item); self.menu.post(e.x_root, e.y_root)
    def apply_preview_subtitles(self):
        if not self.results_data or not self.player: return
        try:
            with open("temp_preview.srt", "w", encoding="utf-8") as f:
                for i, r in enumerate(self.results_data):
                    s = time.strftime('%H:%M:%S', time.gmtime(r['s'])) + f",{int((r['s']%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(r['e'])) + f",{int((r['e']%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
            self.player.set_subtitle(os.path.abspath("temp_preview.srt"))
        except: pass
    def toggle_play(self):
        if self.player: is_p = self.player.toggle_play(); self.btn_play.config(text=self.ICON_PAUSE if is_p else self.ICON_PLAY)
    def skip_time(self, ms): 
        if self.player: self.player.skip(ms)
    def on_seek_start(self, e):
        self.is_seeking = True
        try:
            w = self.seek_bar.winfo_width()
            if w > 0: self.player.set_position(max(0, min(1, e.x/w)))
        except: pass
    def on_seek_release(self, e): self.is_seeking = False; self.player.toggle_play() if not self.player.is_playing() else None
    def update_loop(self):
        if self.player:
            if not self.is_seeking:
                pos = self.player.get_position()
                if pos >= 0: self.seek_var.set(pos * 1000)
            curr_ms, total_ms = self.player.get_time(), self.player.get_length()
            if curr_ms >= 0 and total_ms > 0:
                c_m, c_s = divmod(int(curr_ms/1000), 60); t_m, t_s = divmod(int(total_ms/1000), 60); self.lbl_time.config(text=f"{c_m:02d}:{c_s:02d} / {t_m:02d}:{t_s:02d}")
            if hasattr(self, 'btn_play'): self.btn_play.config(text=self.ICON_PAUSE if self.player.is_playing() else self.ICON_PLAY)
        self.root.after(500, self.update_loop)
    def export_subtitles(self):
        if not self.results_data: return
        fmt = self.export_format.get(); ext = "." + fmt.lower(); initial = os.path.splitext(os.path.basename(self.current_video_path))[0]; file_path = filedialog.asksaveasfilename(defaultextension=ext, initialfile=initial, filetypes=[(fmt, "*" + ext)])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if fmt == "SRT":
                    for i, r in enumerate(self.results_data): s = time.strftime('%H:%M:%S', time.gmtime(r['s'])) + f",{int((r['s']%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(r['e'])) + f",{int((r['e']%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
                elif fmt == "TXT":
                    for r in self.results_data: f.write(f"[{round(r['s'],2)}s] {r['t']}\n")
            messagebox.showinfo("완료", "저장되었습니다.")
