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
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        left_f = tk.Frame(self.main_paned, bg="#1a1a1a")
        self.main_paned.add(left_f, minsize=750)

        self.video_canvas = tk.Frame(left_f, bg="black")
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        self.video_canvas.bind("<Button-1>", lambda e: self.toggle_play())

        self.seek_var = tk.DoubleVar()
        self.seek_bar = tk.Scale(left_f, from_=0, to=1000, orient=tk.HORIZONTAL, variable=self.seek_var, showvalue=0, bg="#1a1a1a")
        self.seek_bar.pack(fill=tk.X, padx=10, pady=2)
        self.seek_bar.bind("<ButtonPress-1>", self.on_seek_start)
        self.seek_bar.bind("<ButtonRelease-1>", self.on_seek_release)
        self.seek_bar.bind("<B1-Motion>", self.on_seek_motion)

        ctrl = tk.Frame(left_f, bg="#2d2d2d", pady=10)
        ctrl.pack(fill=tk.X)
        
        bg_f = tk.Frame(ctrl, bg="#2d2d2d")
        bg_f.pack(expand=True)
        
        tk.Button(bg_f, text=chr(9194)+" 5s", command=lambda: self.skip_time(-5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)
        self.btn_play = tk.Button(bg_f, text=self.ICON_PLAY, command=self.toggle_play, width=8, bg="#27ae60", fg="white")
        self.btn_play.pack(side=tk.LEFT, padx=10)
        tk.Button(bg_f, text="5s "+chr(9193), command=lambda: self.skip_time(5000), bg="#444", fg="white", width=8).pack(side=tk.LEFT, padx=10)

        self.lbl_time = tk.Label(ctrl, text="00:00 / 00:00", bg="#2d2d2d", fg="white")
        self.lbl_time.pack(side=tk.RIGHT, padx=20)
        right_f = tk.Frame(self.main_paned, padx=15); self.main_paned.add(right_f, minsize=450)
        af = tk.LabelFrame(right_f, text=" 분석 및 편집 설정 ", padx=10, pady=10); af.pack(fill=tk.X, pady=10)
        tk.Button(af, text="영상 파일 선택", command=self.on_select_video, bg="#34495e", fg="white", font=("bold")).pack(fill=tk.X, pady=5)
        model_f = tk.Frame(af); model_f.pack(fill=tk.X, pady=5)
        tk.Label(model_f, text="AI 모델:").pack(side=tk.LEFT)
        self.ai_model_var = tk.StringVar(value="large-v3-turbo (기본)")
        self.ai_model_combo = ttk.Combobox(model_f, textvariable=self.ai_model_var, values=["large-v3-turbo (기본)", "models/whisper-medium-ko-zeroth (Medium-Zeroth)"], state="readonly", width=60)
        self.ai_model_combo.pack(side=tk.LEFT, padx=5)
        self.ai_model_var.trace_add("write", lambda *args: self.reset_action_button())
        mf = tk.Frame(af); mf.pack(fill=tk.X)
        self.mode_var = tk.StringVar(value="대사 변환 및 컷편집 (종합)")
        self.mode_combo = ttk.Combobox(mf, textvariable=self.mode_var, values=["자연어-대사 변환", "대사 변환 및 컷편집 (종합)", "깜놀 구간 탐색 (초고속)", "무음 제거 편집 (VAD)", "자동 챕터 분할 (CLIP)"], state="readonly", width=30)
        self.mode_combo.pack(side=tk.LEFT, padx=5, pady=10); self.mode_var.trace_add("write", lambda *args: self.reset_action_button())
        self.btn_analyze = tk.Button(af, text="분석 시작", command=self.on_start_analysis, bg="#2980b9", fg="white", font=("bold"), pady=12); self.btn_analyze.pack(fill=tk.X, pady=5)
        self.btn_stop = tk.Button(af, text="작업 중지", command=self.on_stop_action, bg="#c0392b", fg="white", font=("bold"), state=tk.DISABLED); self.btn_stop.pack(fill=tk.X, pady=2)
        self.save_frame = tk.Frame(right_f); self.save_frame.pack(fill=tk.X, pady=2); self.save_frame.pack_forget()
        tk.Label(self.save_frame, text="[ 영상 및 타임라인 내보내기 ]", fg="#8e44ad", font=("bold", 10)).pack(pady=2)
        btn_box = tk.Frame(self.save_frame); btn_box.pack(fill=tk.X, pady=2)
        self.btn_fast_save = tk.Button(btn_box, text="🚀 초고속 복사", command=lambda: self.start_export(fast=True), bg="#8e44ad", fg="white", pady=8); self.btn_fast_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_pro_save = tk.Button(btn_box, text="🎯 정밀 인코딩", command=lambda: self.start_export(fast=False), bg="#2c3e50", fg="white", pady=8); self.btn_pro_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_xml_save = tk.Button(btn_box, text="🎬 타임라인 XML", command=self.on_export_xml, bg="#16a085", fg="white", pady=8); self.btn_xml_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
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
        opt = tk.LabelFrame(right_f, text=" 상세 설정 ", padx=10, pady=10); opt.pack(fill=tk.X, pady=5)
        
        # [시니어 최적화] UI 공간 절약을 위해 가로 배치 및 간격 조절
        set_f = tk.Frame(opt); set_f.pack(fill=tk.X, pady=2)
        tk.Label(set_f, text="초기 프롬프트:").pack(side=tk.LEFT)
        self.initial_prompt_var = tk.StringVar(value="")
        tk.Entry(set_f, textvariable=self.initial_prompt_var, width=25).pack(side=tk.LEFT, padx=5)
        
        tk.Label(set_f, text="빔 사이즈:").pack(side=tk.LEFT, padx=(10, 0))
        self.beam_size_var = tk.IntVar(value=5)
        tk.Scale(set_f, from_=1, to=15, orient=tk.HORIZONTAL, variable=self.beam_size_var, showvalue=1, length=120).pack(side=tk.LEFT, padx=5)
        
        chk_f = tk.Frame(opt); chk_f.pack(fill=tk.X, pady=2)
        self.use_denoise_var = tk.BooleanVar(value=False); tk.Checkbutton(chk_f, text="소음 제거", variable=self.use_denoise_var).pack(side=tk.LEFT)
        self.use_dominant_var = tk.BooleanVar(value=False); tk.Checkbutton(chk_f, text="주인공만", variable=self.use_dominant_var, fg="#e67e22").pack(side=tk.LEFT, padx=10)
        
        # 언어 선택을 위로 올림
        tk.Label(chk_f, text="언어:").pack(side=tk.LEFT, padx=(10, 0))
        self.lang_var = tk.StringVar(value="한국어 (ko)")
        self.lang_combo = ttk.Combobox(chk_f, textvariable=self.lang_var, values=["한국어 (ko)", "영어 (en)", "일본어 (ja)", "중국어 (zh)", "자동 감지 (auto)"], state="readonly", width=12)
        self.lang_combo.pack(side=tk.LEFT, padx=5)

        vad_f = tk.Frame(opt); vad_f.pack(fill=tk.X, pady=2)
        
        # [시니어 추가] VAD 필터 옵션
        self.use_silero_vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vad_f, text="외부 VAD (Silero)", variable=self.use_silero_vad_var).pack(side=tk.LEFT)
        self.use_whisper_vad_var = tk.BooleanVar(value=True)
        tk.Checkbutton(vad_f, text="내부 VAD (Whisper)", variable=self.use_whisper_vad_var).pack(side=tk.LEFT, padx=5)

        tk.Label(vad_f, text="무음/패딩:").pack(side=tk.LEFT, padx=(10, 0))
        self.silence_dur_var = tk.DoubleVar(value=2.0); tk.Entry(vad_f, textvariable=self.silence_dur_var, width=4).pack(side=tk.LEFT, padx=2)
        tk.Label(vad_f, text="s /").pack(side=tk.LEFT)
        self.speech_pad_var = tk.DoubleVar(value=0.1); tk.Entry(vad_f, textvariable=self.speech_pad_var, width=4).pack(side=tk.LEFT, padx=2)
        tk.Label(vad_f, text="s").pack(side=tk.LEFT, padx=(10, 0))
        self.vad_threshold_var = tk.DoubleVar(value=0.35)
        tk.Scale(vad_f, from_=0.1, to=0.9, resolution=0.05, orient=tk.HORIZONTAL, variable=self.vad_threshold_var, showvalue=1, length=100).pack(side=tk.LEFT, padx=5)

        adv_f = tk.Frame(opt); adv_f.pack(fill=tk.X, pady=2)
        
        # [시니어 추가] 하드웨어 가속 선택기
        tk.Label(adv_f, text="가속:").pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="자동 감지 (auto)")
        ttk.Combobox(adv_f, textvariable=self.device_var, values=["자동 감지 (auto)", "NVIDIA (cuda)", "Apple Mac (mps)", "CPU (멀티코어)"], state="readonly", width=14).pack(side=tk.LEFT, padx=5)

        lf = tk.Frame(opt)
        lf.pack(fill=tk.X, pady=2)
        
        tk.Label(lf, text="대사 길이:").pack(side=tk.LEFT)
        self.max_len_int = tk.IntVar(value=50)
        self.max_len_str = tk.StringVar(value="50")
        
        tk.Scale(lf, from_=10, to=50, orient=tk.HORIZONTAL, variable=self.max_len_int, showvalue=0, command=lambda v: self.max_len_str.set(str(v)), length=150).pack(side=tk.LEFT, padx=5)
        tk.Entry(lf, textvariable=self.max_len_str, width=3).pack(side=tk.LEFT)
        
        self.export_format = tk.StringVar(value="SRT")
        tk.Button(lf, text="자막 내보내기", command=self.export_subtitles, bg="#e67e22", fg="white", padx=10).pack(side=tk.RIGHT, padx=5)
        ttk.Combobox(lf, textvariable=self.export_format, values=["SRT", "VTT", "TXT", "CSV"], state="readonly", width=6).pack(side=tk.RIGHT, padx=5)

    def bind_keys(self): self.root.bind("<space>", lambda e: self.toggle_play()); self.root.bind("<Left>", lambda e: self.skip_time(-5000)); self.root.bind("<Right>", lambda e: self.skip_time(5000))
    def process_ui_queue(self):
        try:
            while True:
                task = self.ui_queue.get_nowait()
                
                # [CRITICAL] 중지 이벤트 발동 시, 엔진 스레드의 남은 보고서(UI 이벤트)를 완전히 무시/증발 시킴
                if self.stop_event.is_set(): continue
                
                if task["action"] == "progress": self.progress_var.set(task["value"]); self.lbl_status.config(text=task["text"])
                elif task["action"] == "add_row": self.tree.insert("", "end", values=(task["i"], f"{round(task['s'], 2)}s", f"{round(task['e'], 2)}s", task['t']))
                elif task["action"] == "complete":
                    self.lbl_status.config(text=task["text"], fg="#27ae60"); self.progress_var.set(100)
                    self.btn_analyze.config(state=tk.NORMAL) # [시니어 수정] 분석 버튼은 항상 살려둠
                    if task.get("is_vad"): 
                        self.save_frame.pack(fill=tk.X, pady=5, before=self.lbl_status)
                        # [시니어 추가] 렌더링 종료 후 다른 방식(또는 XML)으로 무한 재저장 할 수 있도록 버튼 락 해제
                        for b in [self.btn_fast_save, self.btn_pro_save, self.btn_xml_save]: b.config(state=tk.NORMAL)
                    
                    if task.get("is_whisper"): self.apply_preview_subtitles()
                    self.btn_stop.config(state=tk.DISABLED)
                elif task["action"] == "message": messagebox.showinfo("완료", task["text"])
                elif task["action"] == "error": messagebox.showerror("Error", task["text"])
        except queue.Empty: pass
        finally: self.root.after(100, self.process_ui_queue)

    def load_engine_async(self): threading.Thread(target=self._init_engine, daemon=True).start()
    def _init_engine(self):
        try: self.engine.get_model(); self.ui_queue.put({"action": "progress", "value": 0, "text": "엔진 준비 완료"})
        except Exception as e: self.ui_queue.put({"action": "error", "text": f"엔진 로드 실패: {e}"})

    def reset_action_button(self): self.save_frame.pack_forget(); self.btn_analyze.config(text="분석 시작", command=self.on_start_analysis, bg="#2980b9", state=tk.NORMAL); self.btn_fast_save.config(state=tk.NORMAL); self.btn_pro_save.config(state=tk.NORMAL); self.btn_xml_save.config(state=tk.NORMAL)
    def on_select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.flv")])
        if p:
            self.current_video_path = p
            
            # 기존에 로드된 자막 파일 연결 끊기
            if hasattr(self, 'preview_srt_path'):
                self.preview_srt_path = None
                
            if self.player.load_video(p):
                self.lbl_status.config(text="영상 로드됨: " + os.path.basename(p), fg="#2980b9")
                self.reset_action_button()
                
                if hasattr(self, 'preview_srt_path') and getattr(self, 'preview_srt_path') and os.path.exists(self.preview_srt_path):
                    self.root.after(300, self.apply_preview_subtitles)
            else:
                from tkinter import messagebox
                messagebox.showerror("Error", "영상을 불러올 수 없습니다.")


    def on_stop_action(self):
        if self.stop_event and not self.stop_event.is_set(): 
            self.stop_event.set()
            # [CRITICAL] 즉시 반응 확보 및 기존 내역 완전 증발
            while not self.ui_queue.empty(): 
                try: self.ui_queue.get_nowait()
                except: pass
            self.lbl_status.config(text="■ 작업 중지 중... 완전 종료 대기", fg="red")
            self.btn_stop.config(state=tk.DISABLED)
            # 메인 스레드에서 UI를 직접 강제 정화시킴
            self.root.after(1500, lambda: self.reset_action_button() or self.lbl_status.config(text="작업 중지됨", fg="red"))

    def on_start_analysis(self):
        mode = self.mode_var.get()
        selected_model = self.ai_model_var.get().split(" ")[0]
        self.engine.set_model_id(selected_model)
        
        # [시니어 추가] 분석 옵션 수집
        try: min_sil_ms, pad_ms = int(self.silence_dur_var.get() * 1000), int(self.speech_pad_var.get() * 1000)
        except: min_sil_ms, pad_ms = 2000, 250
        
        device_val = self.device_var.get()
        if "auto" in device_val: mapped_dev = "auto"
        elif "cuda" in device_val: mapped_dev = "cuda"
        elif "mps" in device_val: mapped_dev = "mps"
        else: mapped_dev = "cpu"

        analysis_options = {
            "initial_prompt": self.initial_prompt_var.get(),
            "beam_size": self.beam_size_var.get(),
            "use_denoise": self.use_denoise_var.get(),
            "use_dominant": self.use_dominant_var.get(),
            "language": self.lang_var.get().split("(")[-1].replace(")", "").strip(),
            "vad_threshold": self.vad_threshold_var.get(),
            "min_silence_ms": min_sil_ms,
            "speech_pad_ms": pad_ms,
            "use_word_timestamps": True,
            "use_whisper_vad": self.use_whisper_vad_var.get(),
            "use_silero_vad": self.use_silero_vad_var.get(),
            "device_mode": mapped_dev
        }
        
        # 이전 큐가 조금이라도 남아있지 않도록 다시 한번 세척
        while not self.ui_queue.empty():
            try: self.ui_queue.get_nowait()
            except: pass
            
        self.stop_event = threading.Event(); self.btn_analyze.config(state=tk.DISABLED); self.btn_stop.config(state=tk.NORMAL); self.progress_var.set(0); self.results_data = []
        for i in self.tree.get_children(): self.tree.delete(i)
        threading.Thread(target=self.run_analysis, args=(self.current_video_path, self.stop_event, mode, min_sil_ms, pad_ms, analysis_options), daemon=True).start()

    def _smart_split_text(self, text, max_chars):
        """[시니어 리팩토링] 긴 텍스트를 화면 길이에 맞춰 자연스럽게 분할합니다."""
        clean_text = text.strip()
        if len(clean_text) <= max_chars:
            return [clean_text]

        chunks = []
        words = clean_text.split(' ')
        current_chunk = []
        current_len = 0

        for word in words:
            # 단어 하나가 너무 길면 강제로 자름 (예: "으아아아아아...")
            if len(word) > max_chars:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk, current_len = [], 0
                # 긴 단어 강제 분할
                for i in range(0, len(word), max_chars):
                    chunks.append(word[i:i+max_chars])
                continue

            # 현재 덩어리에 단어를 더했을 때 길이를 초과하는지 확인
            if current_len + len(word) + (1 if current_chunk else 0) > max_chars:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_len = len(word)
            else:
                current_chunk.append(word)
                current_len += len(word) + (1 if current_chunk else 0)
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        # [후처리] 마지막 줄이 너무 짧으면(예: "다.") 바로 앞줄에 붙여버림 (공간이 있다면)
        if len(chunks) > 1:
            last = chunks[-1]
            prev = chunks[-2]
            if len(last.replace(" ", "")) < max(3, int(max_chars * 0.4)) and len(prev) + len(last) + 1 <= max_chars * 1.5:
                chunks[-2] = prev + " " + last
                chunks.pop()
                
        return chunks

    def _add_result_row(self, r):
        """[시니어 헬퍼] 결과 데이터를 리스트와 UI 큐에 안전하게 추가 및 타임라인 겹침 방어"""
        if self.results_data:
            last_e = self.results_data[-1]['e']
            # 과거로 돌아가거나 완전히 중복된 유령 구간 폐기
            if r['e'] <= last_e: return 
            # 시간이 살짝 겹쳤을 때는 이전 대사가 끝난 후로 시작점을 강제 보정 (최소 10ms 갭)
            if r['s'] < last_e: r['s'] = last_e + 0.01 
            
        # VAD 등으로 표시되는 대사 길이용 시간 재계산 (구간이 잘렸을 경우 대비)
        if r['t'].endswith('s') and ' ' not in r['t'] and '[' not in r['t']:
            r['t'] = f"{(r['e'] - r['s']):.2f}s"
            
        self.results_data.append(r)
        self.ui_queue.put({"action": "add_row", "i": len(self.results_data), "s": r['s'], "e": r['e'], "t": r['t']})

    def run_analysis(self, p, stop_ev, mode, min_sil_ms, pad_ms, options=None):
        try:
            start_time = time.time()
            max_chars = self.max_len_int.get()
            
            if "자동 챕터 분할" in mode:
                labels = ["a person talking to camera, just chatting", "video game play screen", "web browser or document screen"]
                for chunk_res, prog in self.engine.detect_scenes_clip_stream(p, labels, stop_ev, options=options):
                    if stop_ev.is_set(): break
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"비전 분석 중... ({int(prog)}%)"})
                    for r in chunk_res: self._add_result_row(r)
                if not stop_ev.is_set():
                    total_elapsed = int(time.time() - start_time)
                    self.ui_queue.put({"action": "complete", "text": f"챕터 분석 완료 (소요 시간: {total_elapsed//60}분 {total_elapsed%60}초)", "is_vad": True})
                return

            audio_data, duration = self.engine.load_audio_to_memory(p)
            if stop_ev.is_set(): return
            
            if mode == "무음 제거 편집 (VAD)":
                for chunk_res, prog in self.engine.detect_speech_vad_stream(audio_data, stop_ev, min_sil_ms, pad_ms, options=options):
                    if stop_ev.is_set(): break
                    elapsed = time.time() - start_time
                    eta = int((elapsed / prog) * (100 - prog)) if prog > 5 else -1
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"VAD 분석 중 ({int(prog)}%){f' (남은 시간: {eta//60}분 {eta%60}초)' if eta >= 0 else ''}"})
                    for r in chunk_res: self._add_result_row(r)
                if not stop_ev.is_set():
                    total_elapsed = int(time.time() - start_time)
                    self.ui_queue.put({"action": "complete", "text": f"분석 완료 (소요 시간: {total_elapsed//60}분 {total_elapsed%60}초)", "is_vad": True})
            
            elif "깜놀" in mode:
                for chunk_res, prog in self.engine.detect_peaks_stream(audio_data, stop_ev):
                    if stop_ev.is_set(): break
                    elapsed = time.time() - start_time
                    eta = int((elapsed / prog) * (100 - prog)) if prog > 5 else -1
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"피크 감지 중 ({int(prog)}%){f' (남은 시간: {eta//60}분 {eta%60}초)' if eta >= 0 else ''}"})
                    for r in chunk_res: self._add_result_row(r)
                if not stop_ev.is_set():
                    total_elapsed = int(time.time() - start_time)
                    self.ui_queue.put({"action": "complete", "text": f"분석 완료 (소요 시간: {total_elapsed//60}분 {total_elapsed%60}초)", "is_vad": False})
            
            else:
                gen, total_dur = self.engine.transcribe_stream_raw(audio_data, stop_ev, options=options)
                last_upd, last_prog, ema_speed = time.time(), 0.0, 0.0
                for r in gen:
                    if stop_ev.is_set(): break
                    
                    text = r['t'].strip()
                    
                    if len(text) > max_chars:
                        chunks = self._smart_split_text(text, max_chars)
                        
                        # 문자열 길이에 비례한 정확한 타임라인 재분배
                        total_char_len = sum(len(c) for c in chunks)
                        curr_ratio = 0.0
                        for c in chunks:
                            if not c: continue
                            ratio = len(c) / total_char_len
                            self._add_result_row({'s': r['s'] + (r['e']-r['s'])*curr_ratio, 'e': r['s'] + (r['e']-r['s'])*(curr_ratio+ratio), 't': c})
                            curr_ratio += ratio
                    else:
                        self._add_result_row(r)
                    
                    prog = (r['e'] / total_dur) * 100; curr_t = time.time(); delta_t, delta_p = curr_t - last_upd, prog - last_prog
                    if delta_t > 0.5 and delta_p > 0:
                        curr_s = delta_p / delta_t
                        ema_speed = curr_s if ema_speed == 0 else (ema_speed * 0.8) + (curr_s * 0.2)
                        last_upd, last_prog = curr_t, prog
                    eta_str = f" (남은 시간: {int((100-prog)/ema_speed)//60}분 {int((100-prog)/ema_speed)%60}초)" if ema_speed > 0 else " (남은 시간 계산 중...)"
                    self.ui_queue.put({"action": "progress", "value": prog, "text": f"Whisper 분석 중 ({int(prog)}%){eta_str}"})
                
                if not stop_ev.is_set(): 
                    is_combi = "컷편집" in mode
                    total_elapsed = int(time.time() - start_time)
                    complete_txt = f"분석 완료 ({total_elapsed//60}분 {total_elapsed%60}초)"
                    self.ui_queue.put({"action": "complete", "text": complete_txt, "is_vad": is_combi, "is_whisper": True})
        except Exception as ex:
            if stop_ev is self.stop_event and not stop_ev.is_set(): self.ui_queue.put({"action": "error", "text": f"분석 오류: {str(ex)}"})
        finally:
            # [CRITICAL] 고스트 쓰레드 방어: 새 작업(새 쓰레드/이벤트)이 진행 중일 때는 이전 쓰레드가 UI의 중지 버튼 등을 훼손하지 못하게 차단
            if stop_ev is self.stop_event and stop_ev.is_set(): 
                self.root.after(0, lambda: [self.reset_action_button(), self.btn_stop.config(state=tk.DISABLED)])

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
        item = self.tree.identify_row(e.y); col = self.tree.identify_column(e.x)
        if item:
            val = self.tree.item(item)['values']
            try:
                # 시작 시간 클릭(#2) vs 종료 시간 클릭(#3) 분기 처리
                if col == '#3': t_sec = float(str(val[2]).replace('s',''))
                else: t_sec = float(str(val[1]).replace('s',''))
                self.player.set_time(int(t_sec * 1000))
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
                    s_r, e_r = r['s'], r['e']
                    # [시니어 최적화] 다음 자막과 시간이 겹치거나 맞닿으면 0.05초(50ms) 갭을 추가하여 자막 분리 깜박임 구현
                    if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']: e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                    s = time.strftime('%H:%M:%S', time.gmtime(s_r)) + f",{int((s_r%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(e_r)) + f",{int((e_r%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
            self.player.set_subtitle(os.path.abspath("temp_preview.srt"))
        except: pass
    def toggle_play(self):
        if self.player: is_p = self.player.toggle_play(); self.btn_play.config(text=self.ICON_PAUSE if is_p else self.ICON_PLAY)
    def skip_time(self, ms): 
        if self.player: self.player.skip(ms)
    def on_seek_start(self, e):
        self.is_seeking = True
        self._was_playing_before_seek = self.player.is_playing() if self.player else False
        if self.player:
            self.player.set_mute(True)
            if not self._was_playing_before_seek:
                self.player.toggle_play() # 강제 갱신을 위해 재생 시작
        self._update_seek_from_mouse(e)
    def on_seek_motion(self, e):
        if self.is_seeking: self._update_seek_from_mouse(e)
    def on_seek_release(self, e):
        if self.is_seeking: self._update_seek_from_mouse(e)
        self.is_seeking = False
        if self.player:
            if getattr(self, '_was_playing_before_seek', False):
                self.player.play() # 원래 재생 상태였다면 재생
            else:
                self.player.pause() # 원래 일시정지 상태였다면 정지
            # 즉시 뮤트 해제 시 소리가 튈 수 있어 약간의 딜레이
            self.root.after(100, lambda: self.player.set_mute(False) if self.player else None)
    def _update_seek_from_mouse(self, e):
        try:
            w = self.seek_bar.winfo_width()
            if w > 0 and self.player:
                pos = max(0.0, min(1.0, e.x / w))
                self.player.set_position(pos)
                self.seek_var.set(pos * 1000)
        except: pass
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
                    for i, r in enumerate(self.results_data):
                        s_r, e_r = r['s'], r['e']
                        if i < len(self.results_data) - 1 and e_r >= self.results_data[i+1]['s']: e_r = max(s_r + 0.1, self.results_data[i+1]['s'] - 0.05)
                        s = time.strftime('%H:%M:%S', time.gmtime(s_r)) + f",{int((s_r%1)*1000):03d}"; e = time.strftime('%H:%M:%S', time.gmtime(e_r)) + f",{int((e_r%1)*1000):03d}"; f.write(f"{i+1}\n{s} --> {e}\n{r['t']}\n\n")
                elif fmt == "TXT":
                    for r in self.results_data: f.write(f"[{round(r['s'], 2)}s] {r['t']}\n")
            messagebox.showinfo("완료", "저장되었습니다.")
